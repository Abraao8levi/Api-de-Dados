import re
import httpx
from fastapi import APIRouter, HTTPException, Query, Path
from github_client import GitHubClient
from services.extractor import PRExtractor
from services.classifier import apply_auto_categorization
from models import PullRequest, ReviewComment, CategorizationRequest
import cache

router = APIRouter(prefix="/prs", tags=["Pull Requests"])

_mem: dict[str, dict] = {}


def _clean_repo_params(owner: str, repo: str = "") -> tuple[str, str]:
    full_text = f"{owner} {repo}".strip()
    matches = re.findall(r"(?:https?://github\.com/)?([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", full_text)
    if matches:
        return matches[-1][0], matches[-1][1].replace(".git", "")

    clean_owner = re.sub(r"^https?://(www\.)?github\.com/", "", owner.strip()).replace(".git", "").strip("/")
    clean_repo = re.sub(r"^https?://(www\.)?github\.com/", "", repo.strip()).replace(".git", "").strip("/")

    if "/" in clean_owner:
        parts = clean_owner.split("/")
        return parts[0], parts[1]
    if "/" in clean_repo:
        parts = clean_repo.split("/")
        return parts[0], parts[1]

    return clean_owner, clean_repo


def _key(owner: str, repo: str) -> str:
    o, r = _clean_repo_params(owner, repo)
    return f"{o}/{r}"


def _get_from_cache(key: str, campo: str):
    if key in _mem and campo in _mem[key]:
        return _mem[key][campo]

    dados = cache.carregar(key)
    if dados and campo in dados:
        _mem.setdefault(key, {})
        _mem[key][campo] = dados[campo]
        return dados[campo]

    return None


def _save_to_cache(key: str, campo: str, valor) -> None:
    _mem.setdefault(key, {})
    _mem[key][campo] = valor

    dados = cache.carregar(key) or {}
    dados[campo] = valor
    cache.salvar(key, dados)


async def _extrair_prs_interno(owner: str, repo: str, limit: int = 50, state: str = "all", forcar: bool = False) -> list[PullRequest]:
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = f"{clean_owner}/{clean_repo}"

    if not forcar:
        cached = _get_from_cache(key, "prs")
        if cached:
            return [PullRequest(**pr) if isinstance(pr, dict) else pr for pr in cached]

    client = GitHubClient()
    extractor = PRExtractor(client, clean_owner, clean_repo)

    try:
        prs = await extractor.fetch_prs(limit=limit, state=state)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Repositório '{clean_owner}/{clean_repo}' não foi encontrado ou é privado. Se for privado, gere um token com escopo 'repo' (acesso total).",
            )
        elif e.response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Token do GitHub inválido ou expirado. Verifique a variável GITHUB_TOKEN no arquivo .env.",
            )
        elif e.response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="Limite de requisições do GitHub atingido ou acesso negado. Aguarde alguns minutos ou verifique suas permissões.",
            )
        else:
            raise HTTPException(status_code=502, detail=f"Erro na API do GitHub: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar PRs: {str(e)}")

    prs_dict = [pr.model_dump(mode="json") for pr in prs]
    _save_to_cache(key, "prs", prs_dict)
    return prs


@router.get(
    "/{owner}/{repo}",
    response_model=list[PullRequest],
    summary="1. Extrair PRs de um repositório",
    description="Extrai Pull Requests e classifica automaticamente entre novatos (newcomers) e veteranos.",
)
async def listar_prs(
    owner: str = Path(..., description="Dono/Organização (ex: EbookFoundation ou fastapi)"),
    repo: str = Path(..., description="Nome do repositório (ex: free-programming-books ou fastapi)"),
    limit: int = Query(default=50, ge=5, le=100, description="Quantidade de PRs a extrair"),
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
    forcar_atualizacao: bool = Query(default=False, description="Ignorar cache e buscar dados novos do GitHub"),
):
    return await _extrair_prs_interno(owner, repo, limit=limit, state=state, forcar=forcar_atualizacao)


@router.get(
    "/{owner}/{repo}/comments",
    response_model=list[ReviewComment],
    summary="2. Extrair e categorizar comentários de review",
    description="Coleta os comentários dos PRs. Se os PRs ainda não tiverem sido extraídos, a extração ocorre automaticamente.",
)
async def listar_comentarios(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    auto_categorize: bool = Query(default=True, description="Categorizar automaticamente por regras de palavras-chave"),
    forcar_atualizacao: bool = Query(default=False, description="Ignorar cache local"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = f"{clean_owner}/{clean_repo}"

    prs = await _extrair_prs_interno(clean_owner, clean_repo, limit=50, forcar=forcar_atualizacao)

    if not forcar_atualizacao:
        cached = _get_from_cache(key, "comments")
        if cached:
            return [ReviewComment(**c) if isinstance(c, dict) else c for c in cached]

    client = GitHubClient()
    extractor = PRExtractor(client, clean_owner, clean_repo)

    try:
        comments = await extractor.fetch_all_review_comments(prs)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar comentários no GitHub: {str(e)}")

    if auto_categorize:
        comments = apply_auto_categorization(comments)

    comments_dict = [c.model_dump(mode="json") for c in comments]
    _save_to_cache(key, "comments", comments_dict)

    return comments


@router.patch(
    "/{owner}/{repo}/comments/categorize",
    summary="3. Categorizar comentário manualmente",
)
async def categorizar_comentario(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
    body: CategorizationRequest = ...,
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = f"{clean_owner}/{clean_repo}"
    comments_raw = _get_from_cache(key, "comments")

    if not comments_raw:
        raise HTTPException(
            status_code=404,
            detail="Nenhum comentário encontrado em cache. Execute a extração de comentários primeiro.",
        )

    atualizado = False
    for c in comments_raw:
        if c["id"] == body.comment_id:
            c["category"] = body.category.value
            atualizado = True
            break

    if not atualizado:
        raise HTTPException(status_code=404, detail=f"Comentário com ID {body.comment_id} não encontrado.")

    _save_to_cache(key, "comments", comments_raw)
    return {"detail": "Comentário categorizado com sucesso.", "comment_id": body.comment_id, "category": body.category}


@router.get("/{owner}/{repo}/cache/info", summary="Consultar validade do cache local")
async def info_cache(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = f"{clean_owner}/{clean_repo}"
    detalhes = cache.info(key)
    if not detalhes:
        return {"status": f"Sem dados em cache para {clean_owner}/{clean_repo}"}
    return detalhes


@router.delete("/{owner}/{repo}/cache", summary="Limpar cache do repositório")
async def limpar_cache(
    owner: str = Path(..., description="Dono do repositório"),
    repo: str = Path(..., description="Nome do repositório"),
):
    clean_owner, clean_repo = _clean_repo_params(owner, repo)
    key = f"{clean_owner}/{clean_repo}"
    cache.invalidar(key)
    _mem.pop(key, None)
    return {"detail": f"Cache de {clean_owner}/{clean_repo} removido com sucesso."}
