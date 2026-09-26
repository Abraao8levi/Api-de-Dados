from fastapi import APIRouter, Path, Query
from routers.prs import _clean_repo_params, _extrair_prs_interno, _cache_comments_key
from services.classifier import apply_auto_categorization
from services.extractor import PRExtractor
from services.metrics import build_comparative_report
from github_client import github_client
from models import ComparativeReport, ReviewComment
import cache

router = APIRouter(prefix="/metrics", tags=["Métricas"])


@router.get(
    "/{owner}/{repo:path}",
    response_model=ComparativeReport,
    summary="4. Relatório comparativo: Newcomers vs. Veteranos",
    description="Calcula e retorna métricas comparativas entre novatos e veteranos.",
)
async def relatorio_comparativo(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    limit: int = Query(default=50, ge=5, le=100, description="Quantidade de PRs a analisar"),
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
    forcar_atualizacao: bool = Query(default=False, description="Ignorar cache local"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key_comments = _cache_comments_key(clean_owner, clean_repo)

    prs = await _extrair_prs_interno(
        clean_owner, clean_repo, limit=limit, state=state, forcar=forcar_atualizacao
    )

    comments_raw = cache.carregar(key_comments)
    if not comments_raw or forcar_atualizacao:
        extractor = PRExtractor(github_client, clean_owner, clean_repo)
        comments = await extractor.fetch_all_review_comments(prs)
        comments = apply_auto_categorization(comments)
        cache.salvar(key_comments, [c.model_dump(mode="json") for c in comments])
    else:
        comments = [ReviewComment(**c) if isinstance(c, dict) else c for c in comments_raw]

    return build_comparative_report(clean_owner, clean_repo, prs, comments)
