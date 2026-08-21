import httpx

from signal_backend.services.website import check_website


def _client_with_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_live_site():
    def handler(request):
        return httpx.Response(200, text="<html>hello</html>")

    result = check_website("https://example.com", http_client=_client_with_handler(handler))
    assert result.is_live is True
    assert result.status_code == 200
    assert "hello" in result.content


def test_not_found():
    def handler(request):
        return httpx.Response(404, text="not found")

    result = check_website("https://example.com/missing", http_client=_client_with_handler(handler))
    assert result.is_live is False
    assert result.status_code == 404
    assert result.content is None


def test_connection_error():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    result = check_website("https://unreachable.example", http_client=_client_with_handler(handler))
    assert result.is_live is False
    assert result.status_code is None
    assert result.content is None


def test_timeout():
    def handler(request):
        raise httpx.TimeoutException("timed out")

    result = check_website("https://slow.example", http_client=_client_with_handler(handler))
    assert result.is_live is False
    assert result.status_code is None
