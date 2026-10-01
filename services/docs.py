import logging
from github_client import GitHubClient
from models import RepoDocumentation

logger = logging.getLogger(__name__)

_CONTRIBUTING_PATHS = [
    "CONTRIBUTING.md",
    "contributing.md",
    "docs/CONTRIBUTING.md",
]

_PR_TEMPLATE_PATHS = [
    ".github/pull_request_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "pull_request_template.md",
    "PULL_REQUEST_TEMPLATE.md",
]


async def _try_fetch(client: GitHubClient, owner: str, repo: str, paths: list[str]) -> tuple[bool, str | None]:
    for path in paths:
        try:
            data = await client.get(f"/repos/{owner}/{repo}/contents/{path}")
            return True, data.get("html_url")
        except Exception:
            continue
    return False, None


async def fetch_repo_docs(client: GitHubClient, owner: str, repo: str) -> RepoDocumentation:
    has_contributing, contributing_url = await _try_fetch(client, owner, repo, _CONTRIBUTING_PATHS)
    has_pr_template, pr_template_url = await _try_fetch(client, owner, repo, _PR_TEMPLATE_PATHS)

    if has_contributing:
        logger.info("CONTRIBUTING.md encontrado em %s/%s", owner, repo)
    if has_pr_template:
        logger.info("PR template encontrado em %s/%s", owner, repo)

    return RepoDocumentation(
        has_contributing=has_contributing,
        has_pr_template=has_pr_template,
        contributing_url=contributing_url,
        pr_template_url=pr_template_url,
    )
