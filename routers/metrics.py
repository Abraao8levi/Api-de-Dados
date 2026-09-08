from fastapi import APIRouter, Path, Query
from routers.prs import _get_from_cache, _clean_repo_params, _extrair_prs_interno, _save_to_cache
from services.classifier import apply_auto_categorization
from services.extractor import PRExtractor
from services.metrics import build_comparative_report
from github_client import GitHubClient
from models import ComparativeReport, PullRequest, ReviewComment

router = APIRouter(prefix="/metrics", tags=["Métricas"])


@router.get(
    "/{owner}/{repo}",
    response_model=ComparativeReport,
    summary="4. Relatório comparativo: Newcomers vs. Veteranos",
    description="Calcula e retorna todas as métricas comparativas. Se os dados ainda não tiverem sido minerados, a mineração é feita automaticamente.",
)
async def relatorio_comparativo(
    owner: str = Path(..., description="Dono do repositório (ex: EbookFoundation ou fastapi)"),
    repo: str = Path(..., description="Nome do repositório (ex: free-programming-books ou fastapi)"),
    forcar_atualizacao: bool = Query(default=False, description="Ignorar cache e reextrair do zero"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = f"{clean_owner}/{clean_repo}"

    prs = await _extrair_prs_interno(clean_owner, clean_repo, limit=50, forcar=forcar_atualizacao)

    comments_raw = _get_from_cache(key, "comments")
    if not comments_raw or forcar_atualizacao:
        client = GitHubClient()
        extractor = PRExtractor(client, clean_owner, clean_repo)
        comments = await extractor.fetch_all_review_comments(prs)
        comments = apply_auto_categorization(comments)
        _save_to_cache(key, "comments", [c.model_dump(mode="json") for c in comments])
    else:
        comments = [ReviewComment(**c) if isinstance(c, dict) else c for c in comments_raw]

    return build_comparative_report(clean_owner, clean_repo, prs, comments)
