from fastapi import APIRouter, HTTPException
from routers.prs import _store
from services.metrics import build_comparative_report
from models import ComparativeReport

router = APIRouter(prefix="/metrics", tags=["Métricas"])


def _store_key(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


@router.get("/{owner}/{repo}", response_model=ComparativeReport)
async def relatorio_comparativo(owner: str, repo: str):
    key = _store_key(owner, repo)
    cached = _store.get(key, {})

    prs = cached.get("prs")
    comments = cached.get("comments", [])

    if not prs:
        raise HTTPException(
            status_code=404,
            detail="PRs não encontrados em cache. Faça GET /prs/{owner}/{repo} primeiro.",
        )

    report = build_comparative_report(owner, repo, prs, comments)
    return report
