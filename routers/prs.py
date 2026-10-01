import re
from typing import Literal
import httpx
from fastapi import APIRouter, HTTPException, Query, Path
from github_client import github_client
from services.extractor import PRExtractor
from services.classifier import apply_auto_categorization
from models import PullRequest, ReviewComment, CategorizationRequest, CommentCategory
import cache

router = APIRouter(prefix="/prs", tags=["Pull Requests"])


def _clean_repo_params(owner: str, repo: str = "") -> tuple[str, str]:
    full_text = f"{owner.strip()} {repo.strip()}".strip()
    match = re.search(r"(?:https?://github\.com/)?([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", full_text)
    if match:
        return match.group(1), match.group(2).replace(".git", "")

    clean_owner = re.sub(r"^https?://(www\.)?github\.com/", "", owner.strip()).replace(".git", "").strip("/")
    clean_repo = re.sub(r"^https?://(www\.)?github\.com/", "", repo.strip()).replace(".git", "").strip("/")

    if "/" in clean_owner:
        parts = clean_owner.split("/")
        return parts[0], parts[1]
    if "/" in clean_repo:
        parts = clean_repo.split("/")
        return parts[0], parts[1]

    return clean_owner, clean_repo


def _cache_prs_key(owner: str, repo: str, state: str, limit: int) -> str:
    return f"{owner}__{repo}__prs__{state}__{limit}"


def _cache_comments_key(owner: str, repo: str) -> str:
    return f"{owner}__{repo}__comments"


def _cache_reviews_key(owner: str, repo: str) -> str:
    return f"{owner}__{repo}__reviews"


async def _extrair_prs_interno(
    owner: str,
    repo: str,
    limit: int = 50,
    state: str = "all",
    forcar: bool = False,
) -> list[PullRequest]:
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = _cache_prs_key(clean_owner, clean_repo, state, limit)

    if not forcar:
        cached = cache.carregar(key)
        if cached:
            return [PullRequest(**pr) if isinstance(pr, dict) else pr for pr in cached]

    extractor = PRExtractor(github_client, clean_owner, clean_repo)

    try:
        prs = await extractor.fetch_prs(limit=limit, state=state)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Repositório '{clean_owner}/{clean_repo}' não encontrado ou privado no GitHub. "
                       "Se o repositório for privado ou pertencer a uma organização, certifique-se de que o "
                       "GITHUB_TOKEN no arquivo .env possui acesso concedido a essa organização e repositório.",
            )
        elif e.response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Token do GitHub inválido ou expirado. Verifique GITHUB_TOKEN no arquivo .env.",
            )
        elif e.response.status_code in (403, 429):
            raise HTTPException(
                status_code=403,
                detail="Limite de requisições do GitHub atingido ou acesso negado.",
            )
        raise HTTPException(status_code=502, detail=f"Erro na API do GitHub: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar PRs: {str(e)}")

    prs_dict = [pr.model_dump(mode="json") for pr in prs]
    cache.salvar(key, prs_dict)
    return prs


@router.patch(
    "/{owner}/{repo:path}/comments/categorize",
    summary="3. Categorizar comentário manualmente",
)
async def categorizar_comentario(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    body: CategorizationRequest = ...,
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = _cache_comments_key(clean_owner, clean_repo)
    comments_raw = cache.carregar(key)

    if not comments_raw:
        raise HTTPException(
            status_code=404,
            detail="Nenhum comentário encontrado em cache. Execute a extração de comentários primeiro.",
        )

    atualizado = False
    for c in comments_raw:
        id_match = c.get("id") == body.comment_id
        tipo_match = True if body.tipo is None else c.get("tipo") == body.tipo
        if id_match and tipo_match:
            c["category"] = body.category.value
            atualizado = True
            break

    if not atualizado:
        raise HTTPException(status_code=404, detail=f"Comentário com ID {body.comment_id} não encontrado.")

    cache.salvar(key, comments_raw)
    return {"detail": "Comentário categorizado com sucesso.", "comment_id": body.comment_id, "category": body.category}


@router.get(
    "/{owner}/{repo:path}/comments",
    response_model=list[ReviewComment],
    summary="2. Extrair e categorizar comentários de review",
    description="Coleta os comentários dos PRs com categorização semântica.",
)
async def listar_comentarios(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    categoria: CommentCategory | None = Query(default=None, description="Filtrar por categoria específica (deixe vazio para retornar todas)"),
    tipo: Literal["review", "issue"] | None = Query(default=None, description="Filtrar por tipo (review de código ou issue geral)"),
    auto_categorize: bool = Query(default=True, description="Categorizar automaticamente por regras de palavras-chave"),
    forcar_atualizacao: bool = Query(default=False, description="Ignorar cache local"),
    limit: int = Query(default=50, ge=5, le=100, description="Quantidade de PRs a considerar"),
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = _cache_comments_key(clean_owner, clean_repo)

    if not forcar_atualizacao:
        cached = cache.carregar(key)
        if cached:
            comments = [ReviewComment(**c) if isinstance(c, dict) else c for c in cached]
            if categoria:
                comments = [c for c in comments if c.category == categoria]
            if tipo:
                comments = [c for c in comments if c.tipo == tipo]
            return comments

    prs = await _extrair_prs_interno(
        clean_owner, clean_repo, limit=limit, state=state, forcar=forcar_atualizacao
    )

    extractor = PRExtractor(github_client, clean_owner, clean_repo)

    try:
        comments = await extractor.fetch_all_review_comments(prs)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 429):
            raise HTTPException(status_code=403, detail="Limite de requisições do GitHub atingido ao buscar comentários.")
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Token do GitHub inválido ao buscar comentários.")
        raise HTTPException(status_code=502, detail=f"Erro na API do GitHub: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar comentários no GitHub: {str(e)}")

    if auto_categorize:
        comments = apply_auto_categorization(comments)

    comments_dict = [c.model_dump(mode="json") for c in comments]
    cache.salvar(key, comments_dict)

    if categoria:
        comments = [c for c in comments if c.category == categoria]
    if tipo:
        comments = [c for c in comments if c.tipo == tipo]

    return comments


@router.get("/{owner}/{repo:path}/cache/info", summary="Consultar validade do cache local")
async def info_cache(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    limit: int = Query(default=50, ge=5, le=100),
    state: str = Query(default="all"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = _cache_prs_key(clean_owner, clean_repo, state, limit)
    detalhes = cache.info(key)
    if not detalhes:
        return {"status": f"Sem dados em cache para {clean_owner}/{clean_repo}"}
    return detalhes


@router.delete("/{owner}/{repo:path}/cache", summary="Limpar cache do repositório")
async def limpar_cache(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    for state in ("all", "open", "closed"):
        for limit in (10, 20, 30, 50, 100):
            cache.invalidar(_cache_prs_key(clean_owner, clean_repo, state, limit))
    cache.invalidar(_cache_comments_key(clean_owner, clean_repo))
    cache.invalidar(_cache_reviews_key(clean_owner, clean_repo))
    return {"detail": f"Cache de {clean_owner}/{clean_repo} removido com sucesso."}


@router.get(
    "/{owner}/{repo:path}",
    response_model=list[PullRequest],
    summary="1. Extrair PRs de um repositório",
    description="Extrai Pull Requests e classifica automaticamente entre novatos e veteranos.",
)
async def listar_prs(
    owner: str = Path(..., description="Dono ou organização do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    limit: int = Query(default=50, ge=5, le=100, description="Quantidade de PRs a extrair"),
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
    forcar_atualizacao: bool = Query(default=False, description="Ignorar cache local"),
):
    return await _extrair_prs_interno(owner, repo, limit=limit, state=state, forcar=forcar_atualizacao)
