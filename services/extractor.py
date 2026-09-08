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
    return (end - start).total_seconds() / 3600


def _determine_status(raw_pr: dict) -> PRStatus:
    if raw_pr.get("merged_at"):
        return PRStatus.merged
    if raw_pr.get("state") == "closed":
        return PRStatus.closed
    return PRStatus.open


class PRExtractor:
    def __init__(self, client: GitHubClient, owner: str, repo: str):
        self.client = client
        self.owner = owner
        self.repo = repo
        self._contributor_pr_cache: dict[str, int] = {}

    async def _count_previous_prs(self, username: str, current_pr_number: int) -> int:
        if username in self._contributor_pr_cache:
            return self._contributor_pr_cache[username]

        count = await self.client.get_contributor_pr_count(self.owner, self.repo, username)
        self._contributor_pr_cache[username] = count
        return count

    def _classify_contributor(self, pr_count_before: int) -> ContributorType:
        return ContributorType.newcomer if pr_count_before <= 1 else ContributorType.veteran

    async def _build_pr(self, raw_pr: dict) -> PullRequest:
        author = raw_pr["user"]["login"]
        pr_number = raw_pr["number"]

        total_prs = await self._count_previous_prs(author, pr_number)
        contributor_type = self._classify_contributor(total_prs)

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
            title=raw_pr["title"],
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
        pages_needed = max(1, (limit // 100) + 1)
        raw_prs = await self.client.get_all_pages(
            f"/repos/{self.owner}/{self.repo}/pulls",
            params={"state": state, "sort": "created", "direction": "desc"},
            max_pages=pages_needed,
        )

        raw_prs = raw_prs[:limit]

        tasks = [self._build_pr(pr) for pr in raw_prs]
        prs = await asyncio.gather(*tasks)
        return list(prs)

    async def fetch_review_comments(self, pr_number: int) -> list[ReviewComment]:
        raw_comments = await self.client.get_all_pages(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/comments",
            max_pages=2,
        )

        comments = []
        for c in raw_comments:
            comments.append(
                ReviewComment(
                    id=c["id"],
                    pr_number=pr_number,
                    author=c["user"]["login"],
                    body=c["body"],
                    created_at=_parse_dt(c["created_at"]),
                )
            )
        return comments

    async def fetch_all_review_comments(self, prs: list[PullRequest]) -> list[ReviewComment]:
        all_comments = []
        for pr in prs:
            comments = await self.fetch_review_comments(pr.number)
            all_comments.extend(comments)
        return all_comments
