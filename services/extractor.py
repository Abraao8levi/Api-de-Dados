import asyncio
from datetime import datetime, timezone
from dateutil import parser as date_parser
from github_client import GitHubClient
from models import PullRequest, ReviewComment, ContributorType, PRStatus


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return date_parser.parse(value)


def _hours_between(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return round((end - start).total_seconds() / 3600, 2)


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


class PRExtractor:
    def __init__(self, client: GitHubClient, owner: str, repo: str):
        self.client = client
        self.owner = owner.strip().rstrip("/")
        self.repo = repo.strip().rstrip("/")

    def _build_pr(self, raw_pr: dict) -> PullRequest:
        user_info = raw_pr.get("user")
        author = user_info["login"] if user_info else "ghost"
        pr_number = raw_pr["number"]

        contributor_type = _classify_contributor(raw_pr)

        created_at = _parse_dt(raw_pr["created_at"])
        closed_at = _parse_dt(raw_pr.get("closed_at"))
        merged_at = _parse_dt(raw_pr.get("merged_at"))
        status = _determine_status(raw_pr)

        hours_to_close = None
        hours_to_merge = None

        if closed_at and created_at:
            hours_to_close = _hours_between(created_at, closed_at)
        if merged_at and created_at:
            hours_to_merge = _hours_between(created_at, merged_at)

        review_comments = raw_pr.get("review_comments", 0)
        issue_comments = raw_pr.get("comments", 0)

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

    async def fetch_prs(self, limit: int = 50, state: str = "all") -> list[PullRequest]:
        pages_needed = max(1, (limit // 100) + (1 if limit % 100 != 0 else 0))
        raw_prs = await self.client.get_all_pages(
            f"/repos/{self.owner}/{self.repo}/pulls",
            params={"state": state, "sort": "created", "direction": "desc"},
            max_pages=pages_needed,
        )

        raw_prs = raw_prs[:limit]
        return [self._build_pr(pr) for pr in raw_prs]

    async def fetch_review_comments(self, pr: PullRequest) -> list[ReviewComment]:
        if pr.review_comments_count == 0 and pr.issue_comments_count == 0:
            return []

        comments = []

        try:
            if pr.review_comments_count > 0:
                raw_rc = await self.client.get_all_pages(
                    f"/repos/{self.owner}/{self.repo}/pulls/{pr.number}/comments",
                    max_pages=2,
                )
                for c in raw_rc:
                    user_info = c.get("user")
                    author = user_info["login"] if user_info else "ghost"
                    comments.append(
                        ReviewComment(
                            id=c["id"],
                            pr_number=pr.number,
                            author=author,
                            body=c.get("body", "") or "",
                            created_at=_parse_dt(c["created_at"]),
                        )
                    )

            if pr.issue_comments_count > 0:
                raw_ic = await self.client.get_all_pages(
                    f"/repos/{self.owner}/{self.repo}/issues/{pr.number}/comments",
                    max_pages=2,
                )
                for c in raw_ic:
                    user_info = c.get("user")
                    author = user_info["login"] if user_info else "ghost"
                    comments.append(
                        ReviewComment(
                            id=c["id"],
                            pr_number=pr.number,
                            author=author,
                            body=c.get("body", "") or "",
                            created_at=_parse_dt(c["created_at"]),
                        )
                    )
        except Exception:
            pass

        return comments

    async def fetch_all_review_comments(self, prs: list[PullRequest]) -> list[ReviewComment]:
        sem = asyncio.Semaphore(10)

        async def _fetch_with_sem(pr: PullRequest):
            async with sem:
                return await self.fetch_review_comments(pr)

        tasks = [_fetch_with_sem(pr) for pr in prs]
        results = await asyncio.gather(*tasks)

        all_comments = []
        for comments_list in results:
            all_comments.extend(comments_list)
        return all_comments
