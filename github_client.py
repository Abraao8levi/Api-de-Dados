import httpx
from typing import Any
from config import settings


class GitHubClient:
    def __init__(self):
        self.base_url = settings.github_api_url
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self.headers = headers

    async def get(self, path: str, params: dict = None) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params or {},
            )
            response.raise_for_status()
            return response.json()

    async def get_all_pages(self, path: str, params: dict = None, max_pages: int = 5) -> list:
        results = []
        page = 1
        base_params = params or {}

        async with httpx.AsyncClient(timeout=30) as client:
            while page <= max_pages:
                page_params = {**base_params, "page": page, "per_page": 100}
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    params=page_params,
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    break

                results.extend(data)
                page += 1

        return results

    async def get_contributor_pr_count(self, owner: str, repo: str, username: str) -> int:
        try:
            data = await self.get(
                f"/search/issues",
                params={
                    "q": f"repo:{owner}/{repo} type:pr author:{username}",
                    "per_page": 1,
                },
            )
            return data.get("total_count", 0)
        except Exception:
            return 0


github_client = GitHubClient()
