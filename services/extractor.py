import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from dateutil import parser as date_parser
import httpx
from github_client import GitHubClient
from models import PullRequest, ReviewComment, Review, ReviewState, ContributorType, PRStatus

logger = logging.getLogger(__name__)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = date_parser.parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _hours_between(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    diff = (end - start).total_seconds() / 3600
    return round(max(0.0, diff), 2)


def _determine_status(raw_pr: dict) -> PRStatus:
    if raw_pr.get("merged_at"):
        return PRStatus.merged
    if raw_pr.get("state") == "closed":
        return PRStatus.closed
    return PRStatus.open


def _classify_contributor(raw_pr: dict) -> ContributorType:
    assoc = (raw_pr.get("author_association") or "").upper()
    if assoc in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE", ""):
        return ContributorType.newcomer
    return ContributorType.veteran


def apply_historical_classification(prs: list[PullRequest]) -> list[PullRequest]:
    count = Counter(pr.author for pr in prs)
    for pr in prs:
        pr.pr_count_in_sample = count[pr.author]
        pr.contributor_type = ContributorType.veteran if count[pr.author] >= 3 else ContributorType.newcomer
    return prs


class PRExtractor:
    def __init__(self, client: GitHubClient, owner: str, repo: str):
        self.client = client
        self.owner = owner.strip().rstrip("/")
        self.repo = repo.strip().rstrip("/")

    def _build_pr(self, raw_pr: dict) -> PullRequest:
        user_info = raw_pr.get("user")
        author = user_info.get("login", "ghost") if isinstance(user_info, dict) else "ghost"
        pr_number = raw_pr["number"]

        contributor_type = _classify_contributor(raw_pr)

        created_at = _parse_dt(raw_pr["created_at"])
        closed_at = _parse_dt(raw_pr.get("closed_at"))
        merged_at = _parse_dt(raw_pr.get("merged_at"))
        status = _determine_status(raw_pr)

        hours_to_close = None
        hours_to_merge = None

        if closed_at and created_at and status == PRStatus.closed:
            hours_to_close = _hours_between(created_at, closed_at)
        if merged_at and created_at:
            hours_to_merge = _hours_between(created_at, merged_at)

        review_comments = max(0, raw_pr.get("review_comments", 0))
        issue_comments = max(0, raw_pr.get("comments", 0))

        return PullRequest(
            number=pr_number,
            title=raw_pr.get("title", "") or "",
            author=author,
            contributor_type=contributor_type,
            status=status,
            created_at=created_at,
            closed_at=closed_at,
            merged_at=merged_at,
            review_comments_count=review_comments,
            issue_comments_count=issue_comments,
            total_comments=review_comments + issue_comments,
            hours_to_close=hours_to_close,
            hours_to_merge=hours_to_merge,
        )

    async def _fetch_pr_detail(self, pr_number: int) -> dict:
        return await self.client.get(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
        )

    async def fetch_prs(self, limit: int = 50, state: str = "all") -> list[PullRequest]:
        per_page = min(limit, 100)
        pages_needed = max(1, (limit // per_page) + (1 if limit % per_page != 0 else 0))
        raw_prs = await self.client.get_all_pages(
            f"/repos/{self.owner}/{self.repo}/pulls",
            params={"state": state, "sort": "created", "direction": "desc", "per_page": per_page},
            max_pages=pages_needed,
        )

        raw_prs = raw_prs[:limit]
        sem = asyncio.Semaphore(10)

        async def _detail_with_sem(raw: dict) -> dict:
            async with sem:
                try:
                    return await self._fetch_pr_detail(raw["number"])
                except Exception as exc:
                    logger.warning("Falha ao obter detalhes do PR#%s: %s", raw["number"], exc)
                    return raw

        tasks = [_detail_with_sem(r) for r in raw_prs]
        detailed_prs = await asyncio.gather(*tasks)

        prs = [self._build_pr(pr) for pr in detailed_prs]
        return apply_historical_classification(prs)

    async def fetch_review_comments(self, pr: PullRequest) -> list[ReviewComment]:
        if pr.total_comments == 0 and pr.review_comments_count == 0 and pr.issue_comments_count == 0:
            return []

        comments: list[ReviewComment] = []

        try:
            if pr.review_comments_count > 0 or pr.total_comments == 0:
                raw_rc = await self.client.get_all_pages(
                    f"/repos/{self.owner}/{self.repo}/pulls/{pr.number}/comments",
                    max_pages=3,
                )
                for c in raw_rc:
                    user_info = c.get("user") or {}
                    author = user_info.get("login", "ghost")
                    is_bot = user_info.get("type") == "Bot" or author.lower().endswith("[bot]")
                    if is_bot:
                        continue

                    body = c.get("body", "") or ""
                    comments.append(
                        ReviewComment(
                            id=c["id"],
                            pr_number=pr.number,
                            author=author,
                            body=body,
                            created_at=_parse_dt(c["created_at"]),
                            tipo="review",
                            has_suggestion="```suggestion" in body,
                        )
                    )

            if pr.issue_comments_count > 0 or pr.total_comments == 0:
                raw_ic = await self.client.get_all_pages(
                    f"/repos/{self.owner}/{self.repo}/issues/{pr.number}/comments",
                    max_pages=3,
                )
                for c in raw_ic:
                    user_info = c.get("user") or {}
                    author = user_info.get("login", "ghost")
                    is_bot = user_info.get("type") == "Bot" or author.lower().endswith("[bot]")
                    if is_bot:
                        continue

                    body = c.get("body", "") or ""
                    comments.append(
                        ReviewComment(
                            id=c["id"],
                            pr_number=pr.number,
                            author=author,
                            body=body,
                            created_at=_parse_dt(c["created_at"]),
                            tipo="issue",
                            has_suggestion="```suggestion" in body,
                        )
                    )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403, 429):
                raise
            logger.warning("Erro HTTP ao extrair comentários do PR#%s: %s", pr.number, exc)
        except Exception as exc:
            logger.warning("Erro inesperado ao extrair comentários do PR#%s: %s", pr.number, exc)

        return comments

    async def fetch_all_review_comments(self, prs: list[PullRequest]) -> list[ReviewComment]:
        sem = asyncio.Semaphore(5)

        async def _fetch_with_sem(pr: PullRequest):
            async with sem:
                return await self.fetch_review_comments(pr)

        tasks = [_fetch_with_sem(pr) for pr in prs]
        results = await asyncio.gather(*tasks)

        all_comments = []
        for comments_list in results:
            all_comments.extend(comments_list)
        return all_comments

    async def fetch_reviews(self, pr: PullRequest) -> list[Review]:
        reviews: list[Review] = []
        try:
            raw_reviews = await self.client.get_all_pages(
                f"/repos/{self.owner}/{self.repo}/pulls/{pr.number}/reviews",
                max_pages=3,
            )
            for r in raw_reviews:
                state_str = (r.get("state") or "").upper()
                try:
                    state = ReviewState(state_str)
                except ValueError:
                    continue

                user_info = r.get("user") or {}
                author = user_info.get("login", "ghost")
                is_bot = user_info.get("type") == "Bot" or author.lower().endswith("[bot]")
                if is_bot:
                    continue

                reviews.append(
                    Review(
                        id=r["id"],
                        pr_number=pr.number,
                        author=author,
                        state=state,
                        submitted_at=_parse_dt(r.get("submitted_at")),
                    )
                )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403, 429):
                raise
            logger.warning("Erro HTTP ao buscar reviews do PR#%s: %s", pr.number, exc)
        except Exception as exc:
            logger.warning("Erro ao buscar reviews do PR#%s: %s", pr.number, exc)

        return reviews

    async def fetch_all_reviews(self, prs: list[PullRequest]) -> list[Review]:
        sem = asyncio.Semaphore(5)

        async def _fetch_with_sem(pr: PullRequest):
            async with sem:
                return await self.fetch_reviews(pr)

        tasks = [_fetch_with_sem(pr) for pr in prs]
        results = await asyncio.gather(*tasks)

        all_reviews = []
        for review_list in results:
            all_reviews.extend(review_list)
        return all_reviews
