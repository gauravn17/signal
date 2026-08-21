import httpx
import pytest

from signal_backend.services.github import GitHubClient, GitHubRateLimitError


def _client_with_handler(handler) -> GitHubClient:
    return GitHubClient(
        http_client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    )


def test_get_user_found():
    def handler(request):
        assert request.url.path == "/users/octocat"
        return httpx.Response(200, json={"login": "octocat", "public_repos": 8})

    user = _client_with_handler(handler).get_user("octocat")
    assert user["login"] == "octocat"


def test_get_user_not_found():
    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    assert _client_with_handler(handler).get_user("ghost") is None


def test_rate_limit_raises():
    def handler(request):
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"},
            json={"message": "rate limited"},
        )

    with pytest.raises(GitHubRateLimitError):
        _client_with_handler(handler).get_user("octocat")


def test_get_user_repos():
    def handler(request):
        assert request.url.path == "/users/octocat/repos"
        return httpx.Response(200, json=[{"name": "hello-world", "pushed_at": "2024-01-01T00:00:00Z"}])

    repos = _client_with_handler(handler).get_user_repos("octocat")
    assert repos[0]["name"] == "hello-world"


def test_get_repo_commits():
    def handler(request):
        assert request.url.path == "/repos/octocat/hello-world/commits"
        return httpx.Response(200, json=[{"sha": "abc123", "commit": {"author": {"date": "2024-01-01T00:00:00Z"}}}])

    commits = _client_with_handler(handler).get_repo_commits("octocat", "hello-world")
    assert commits[0]["sha"] == "abc123"
