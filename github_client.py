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
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30, headers=self.headers)
        return self._client

    async def get(self, path: str, params: dict = None) -> Any:
        client = self._get_client()
        response = await client.get(
            f"{self.base_url}{path}",
            params=params or {},
        )
        response.raise_for_status()
        return response.json()

    async def get_all_pages(self, path: str, params: dict = None, max_pages: int = 5) -> list:
        results = []
        page = 1
        base_params = params or {}
        per_page = base_params.get("per_page", 100)
        client = self._get_client()

        while page <= max_pages:
            page_params = {**base_params, "page": page, "per_page": per_page}
            response = await client.get(
                f"{self.base_url}{path}",
                params=page_params,
            )
            response.raise_for_status()
            data = response.json()

            if not data or not isinstance(data, list):
                break

            results.extend(data)

            if len(data) < per_page:
                break

            page += 1

        return results

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


github_client = GitHubClient()
