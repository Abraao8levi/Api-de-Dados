from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


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


class ReviewComment(BaseModel):
    id: int
    pr_number: int
    author: str
    body: str
    created_at: datetime
    category: Optional[CommentCategory] = None


class PullRequest(BaseModel):
    number: int
    title: str
    author: str
    contributor_type: ContributorType
    status: PRStatus
    created_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    review_comments_count: int
    issue_comments_count: int
    total_comments: int
    hours_to_close: Optional[float] = None
    hours_to_merge: Optional[float] = None


class PRMetrics(BaseModel):
    contributor_type: ContributorType
    total_prs: int
    merged_prs: int
    closed_without_merge: int
    open_prs: int
    acceptance_rate: float
    avg_comments_per_pr: float
    avg_hours_to_close: Optional[float]
    avg_hours_to_merge: Optional[float]
    comment_categories: dict


class ComparativeReport(BaseModel):
    repository: str
    sample_size: int
    newcomers: PRMetrics
    veterans: PRMetrics
    total_review_comments: int
    comment_category_distribution: dict


class CategorizationRequest(BaseModel):
    comment_id: int
    category: CommentCategory
