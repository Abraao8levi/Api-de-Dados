from collections import Counter
from models import PullRequest, ReviewComment, ContributorType, PRMetrics, ComparativeReport, PRStatus


def _compute_metrics(prs: list[PullRequest], comments: list[ReviewComment], contributor_type: ContributorType) -> PRMetrics:
    filtered = [pr for pr in prs if pr.contributor_type == contributor_type]

    total = len(filtered)
    if total == 0:
        return PRMetrics(
            contributor_type=contributor_type,
            total_prs=0,
            merged_prs=0,
            closed_without_merge=0,
            open_prs=0,
            acceptance_rate=0.0,
            avg_comments_per_pr=0.0,
            avg_hours_to_close=None,
            avg_hours_to_merge=None,
            comment_categories={},
        )

    merged = [pr for pr in filtered if pr.status == PRStatus.merged]
    closed_no_merge = [pr for pr in filtered if pr.status == PRStatus.closed]
    open_prs = [pr for pr in filtered if pr.status == PRStatus.open]

    acceptance_rate = len(merged) / total if total else 0.0

    total_comments = sum(pr.total_comments for pr in filtered)
    avg_comments = total_comments / total if total else 0.0

    close_times = [pr.hours_to_close for pr in filtered if pr.hours_to_close is not None]
    merge_times = [pr.hours_to_merge for pr in filtered if pr.hours_to_merge is not None]

    avg_close = sum(close_times) / len(close_times) if close_times else None
    avg_merge = sum(merge_times) / len(merge_times) if merge_times else None

    pr_numbers = {pr.number for pr in filtered}
    relevant_comments = [c for c in comments if c.pr_number in pr_numbers]
    category_counter = Counter(c.category.value for c in relevant_comments if c.category)

    return PRMetrics(
        contributor_type=contributor_type,
        total_prs=total,
        merged_prs=len(merged),
        closed_without_merge=len(closed_no_merge),
        open_prs=len(open_prs),
        acceptance_rate=round(acceptance_rate * 100, 2),
        avg_comments_per_pr=round(avg_comments, 2),
        avg_hours_to_close=round(avg_close, 2) if avg_close else None,
        avg_hours_to_merge=round(avg_merge, 2) if avg_merge else None,
        comment_categories=dict(category_counter),
    )


def build_comparative_report(
    owner: str,
    repo: str,
    prs: list[PullRequest],
    comments: list[ReviewComment],
) -> ComparativeReport:
    newcomer_metrics = _compute_metrics(prs, comments, ContributorType.newcomer)
    veteran_metrics = _compute_metrics(prs, comments, ContributorType.veteran)

    category_counter = Counter(c.category.value for c in comments if c.category)

    return ComparativeReport(
        repository=f"{owner}/{repo}",
        sample_size=len(prs),
        newcomers=newcomer_metrics,
        veterans=veteran_metrics,
        total_review_comments=len(comments),
        comment_category_distribution=dict(category_counter),
    )
