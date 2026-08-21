import httpx


class WebsiteCheckResult:
    def __init__(self, url: str, is_live: bool, status_code: int | None, content: str | None):
        self.url = url
        self.is_live = is_live
        self.status_code = status_code
        self.content = content


def check_website(url: str, http_client: httpx.Client | None = None) -> WebsiteCheckResult:
    client = http_client or httpx.Client(follow_redirects=True, timeout=10.0)
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return WebsiteCheckResult(url=url, is_live=False, status_code=None, content=None)

    return WebsiteCheckResult(
        url=url,
        is_live=response.is_success,
        status_code=response.status_code,
        content=response.text if response.is_success else None,
    )
