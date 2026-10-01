from enum import Enum
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class ContributorType(str, Enum):
    newcomer = "newcomer"
    veteran = "veteran"


class CommentCategory(str, Enum):
    correcao_tecnica = "correcao_tecnica"
    explicacao_didatica = "explicacao_didatica"
    rejeicao = "rejeicao"
    elogio = "elogio"
    neutro = "neutro"


class PRStatus(str, Enum):
    open = "open"
    closed = "closed"
    merged = "merged"


class ReviewState(str, Enum):
    approved = "APPROVED"
    changes_requested = "CHANGES_REQUESTED"
    commented = "COMMENTED"
    dismissed = "DISMISSED"


class ReviewComment(BaseModel):
    id: int
    pr_number: int
    author: str
    body: str
    created_at: datetime
    tipo: Literal["review", "issue"] = "issue"
    category: Optional[CommentCategory] = None
    has_suggestion: bool = False


class Review(BaseModel):
    id: int
    pr_number: int
    author: str
    state: ReviewState
    submitted_at: Optional[datetime] = None


class PullRequest(BaseModel):
    number: int
    title: str
    author: str
    contributor_type: ContributorType
    status: PRStatus
    created_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    review_comments_count: int = 0
    issue_comments_count: int = 0
    total_comments: int = 0
    hours_to_close: Optional[float] = None
    hours_to_merge: Optional[float] = None
    pr_count_in_sample: int = 1


class RepoDocumentation(BaseModel):
    has_contributing: bool = False
    has_pr_template: bool = False
    contributing_url: Optional[str] = None
    pr_template_url: Optional[str] = None


class PRMetrics(BaseModel):
    contributor_type: ContributorType
    total_prs: int
    merged_prs: int
    closed_without_merge: int
    open_prs: int
    acceptance_rate: float
    avg_comments_per_pr: float
    avg_hours_to_close: Optional[float] = None
    avg_hours_to_merge: Optional[float] = None
    avg_hours_to_first_review: Optional[float] = None
    avg_review_rounds: float = 0.0
    prs_with_changes_requested_pct: float = 0.0
    prs_with_suggestions_pct: float = 0.0
    comment_categories: dict[str, int] = Field(default_factory=dict)


class ComparativeReport(BaseModel):
    repository: str
    sample_size: int
    newcomers: PRMetrics
    veterans: PRMetrics
    total_review_comments: int
    comment_category_distribution: dict[str, int] = Field(default_factory=dict)
    documentation: RepoDocumentation = Field(default_factory=RepoDocumentation)


class CategorizationRequest(BaseModel):
    comment_id: int
    category: CommentCategory
    tipo: Optional[Literal["review", "issue"]] = None
