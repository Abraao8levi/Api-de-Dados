from fastapi import APIRouter, HTTPException, Query
from github_client import GitHubClient
from services.extractor import PRExtractor
from services.classifier import apply_auto_categorization
from models import PullRequest, ReviewComment, CategorizationRequest

router = APIRouter(prefix="/prs", tags=["Pull Requests"])

_store: dict[str, dict] = {}


def _store_key(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


@router.get("/{owner}/{repo}", response_model=list[PullRequest])
async def listar_prs(
    owner: str,
    repo: str,
    limit: int = Query(default=50, ge=5, le=100),
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
):
    client = GitHubClient()
    extractor = PRExtractor(client, owner, repo)

    try:
        prs = await extractor.fetch_prs(limit=limit, state=state)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar GitHub API: {str(e)}")

    key = _store_key(owner, repo)
    if key not in _store:
        _store[key] = {}
    _store[key]["prs"] = prs

    return prs


@router.get("/{owner}/{repo}/comments", response_model=list[ReviewComment])
async def listar_comentarios(
    owner: str,
    repo: str,
    auto_categorize: bool = Query(default=True),
):
    key = _store_key(owner, repo)
    prs = _store.get(key, {}).get("prs")

    if not prs:
        raise HTTPException(
            status_code=404,
            detail="PRs não encontrados em cache. Faça GET /{owner}/{repo} primeiro.",
        )

    client = GitHubClient()
    extractor = PRExtractor(client, owner, repo)

    try:
        comments = await extractor.fetch_all_review_comments(prs)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar GitHub API: {str(e)}")

    if auto_categorize:
        comments = apply_auto_categorization(comments)

    _store[key]["comments"] = comments
    return comments


@router.patch("/{owner}/{repo}/comments/categorize")
async def categorizar_comentario(owner: str, repo: str, body: CategorizationRequest):
    key = _store_key(owner, repo)
    comments: list[ReviewComment] = _store.get(key, {}).get("comments", [])

    for comment in comments:
        if comment.id == body.comment_id:
            comment.category = body.category
            return {"detail": "Comentário categorizado com sucesso.", "comment_id": body.comment_id, "category": body.category}

    raise HTTPException(status_code=404, detail=f"Comentário {body.comment_id} não encontrado no cache.")
