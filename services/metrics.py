from collections import Counter
from datetime import datetime, timezone
from models import (
    PullRequest, ReviewComment, Review, ReviewState,
    ContributorType, PRMetrics, ComparativeReport, PRStatus, RepoDocumentation,
)


def _hours_between(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    diff = (end - start).total_seconds() / 3600
    return round(max(0.0, diff), 2)


def _compute_metrics(
    prs: list[PullRequest],
    comments: list[ReviewComment],
    reviews: list[Review],
    contributor_type: ContributorType,
) -> PRMetrics:
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
            avg_hours_to_first_review=None,
            avg_review_rounds=0.0,
            prs_with_changes_requested_pct=0.0,
            prs_with_suggestions_pct=0.0,
            comment_categories={},
        )

    merged = [pr for pr in filtered if pr.status == PRStatus.merged]
    closed_no_merge = [pr for pr in filtered if pr.status == PRStatus.closed]
    open_prs = [pr for pr in filtered if pr.status == PRStatus.open]

    resolved_count = len(merged) + len(closed_no_merge)
    acceptance_rate = (len(merged) / resolved_count) if resolved_count > 0 else 0.0

    total_comments_sum = sum(pr.total_comments for pr in filtered)
    avg_comments = total_comments_sum / total if total > 0 else 0.0

    close_times = [
        pr.hours_to_close for pr in filtered
        if pr.status == PRStatus.closed and pr.hours_to_close is not None
    ]
    merge_times = [
        pr.hours_to_merge for pr in filtered
        if pr.status == PRStatus.merged and pr.hours_to_merge is not None
    ]

    avg_close = sum(close_times) / len(close_times) if close_times else None
    avg_merge = sum(merge_times) / len(merge_times) if merge_times else None

    pr_numbers = {pr.number for pr in filtered}
    pr_map = {pr.number: pr for pr in filtered}
    relevant_reviews = [r for r in reviews if r.pr_number in pr_numbers]

    first_review_times: list[float] = []
    review_rounds_list: list[int] = []
    prs_with_changes = 0

    for pr_num in pr_numbers:
        pr = pr_map[pr_num]
        pr_reviews = [r for r in relevant_reviews if r.pr_number == pr_num]

        reviews_with_time = [r for r in pr_reviews if r.submitted_at]
        if reviews_with_time:
            first = min(reviews_with_time, key=lambda r: r.submitted_at)
            first_review_times.append(_hours_between(pr.created_at, first.submitted_at))

        changes_count = sum(1 for r in pr_reviews if r.state == ReviewState.changes_requested)
        review_rounds_list.append(changes_count)
        if changes_count > 0:
            prs_with_changes += 1

    avg_first_review = sum(first_review_times) / len(first_review_times) if first_review_times else None
    avg_rounds = sum(review_rounds_list) / len(review_rounds_list) if review_rounds_list else 0.0
    changes_pct = (prs_with_changes / total) * 100 if total > 0 else 0.0

    relevant_comments = [c for c in comments if c.pr_number in pr_numbers]
    prs_with_suggestions = len({c.pr_number for c in relevant_comments if c.has_suggestion})
    suggestions_pct = (prs_with_suggestions / total) * 100 if total > 0 else 0.0

    category_counter = Counter(c.category.value for c in relevant_comments if c.category)

    return PRMetrics(
        contributor_type=contributor_type,
        total_prs=total,
        merged_prs=len(merged),
        closed_without_merge=len(closed_no_merge),
        open_prs=len(open_prs),
        acceptance_rate=round(acceptance_rate * 100, 2),
        avg_comments_per_pr=round(avg_comments, 2),
        avg_hours_to_close=round(avg_close, 2) if avg_close is not None else None,
        avg_hours_to_merge=round(avg_merge, 2) if avg_merge is not None else None,
        avg_hours_to_first_review=round(avg_first_review, 2) if avg_first_review is not None else None,
        avg_review_rounds=round(avg_rounds, 2),
        prs_with_changes_requested_pct=round(changes_pct, 2),
        prs_with_suggestions_pct=round(suggestions_pct, 2),
        comment_categories=dict(category_counter),
    )


def build_comparative_report(
    owner: str,
    repo: str,
    prs: list[PullRequest],
    comments: list[ReviewComment],
    reviews: list[Review],
    documentation: RepoDocumentation,
) -> ComparativeReport:
    newcomer_metrics = _compute_metrics(prs, comments, reviews, ContributorType.newcomer)
    veteran_metrics = _compute_metrics(prs, comments, reviews, ContributorType.veteran)

    category_counter = Counter(c.category.value for c in comments if c.category)

    return ComparativeReport(
        repository=f"{owner}/{repo}",
        sample_size=len(prs),
        newcomers=newcomer_metrics,
        veterans=veteran_metrics,
        total_review_comments=len(comments),
        comment_category_distribution=dict(category_counter),
        documentation=documentation,
    )
