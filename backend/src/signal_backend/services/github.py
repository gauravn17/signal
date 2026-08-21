import httpx

from signal_backend.config import settings


class GitHubRateLimitError(Exception):
    def __init__(self, reset_at: int | None = None):
        self.reset_at = reset_at
        super().__init__(f"GitHub API rate limit exceeded, resets at {reset_at}")


def _auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


class GitHubClient:
    def __init__(self, http_client: httpx.Client | None = None):
        self._client = http_client or httpx.Client(
            base_url="https://api.github.com", headers=_auth_headers(), timeout=10.0
        )

    def get_user(self, username: str) -> dict | None:
        response = self._request("GET", f"/users/{username}")
        return None if response.status_code == 404 else response.json()

    def get_user_repos(self, username: str) -> list[dict]:
        response = self._request(
            "GET", f"/users/{username}/repos", params={"per_page": 100, "sort": "pushed"}
        )
        return [] if response.status_code == 404 else response.json()

    def get_repo_commits(self, owner: str, repo: str, author: str | None = None) -> list[dict]:
        params = {"per_page": 50}
        if author:
            params["author"] = author
        response = self._request("GET", f"/repos/{owner}/{repo}/commits", params=params)
        return [] if response.status_code == 404 else response.json()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            reset = response.headers.get("X-RateLimit-Reset")
            raise GitHubRateLimitError(reset_at=int(reset) if reset else None)
        if response.status_code != 404:
            response.raise_for_status()
        return response


def get_github_client() -> GitHubClient:
    return GitHubClient()
