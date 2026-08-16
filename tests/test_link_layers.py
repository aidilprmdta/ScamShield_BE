"""Unit tests layer heuristik & URLhaus."""
import pytest
import respx
from httpx import Response

from app.services.link_check.custom_rules import check_heuristics, expand_short_link
from app.services.link_check.urlhaus_client import URLHAUS_ENDPOINT, check_urlhaus


def test_check_heuristics_detects_ip():
    result = check_heuristics("http://192.168.1.1/login")
    assert result["is_ip"] is True
    assert any("IP" in f for f in result["flags"])


def test_check_heuristics_detects_excessive_hyphens():
    result = check_heuristics("https://bca-login-secure-verify.xyz/auth")
    assert result["excessive_hyphens"] is True


def test_check_heuristics_clean_domain():
    result = check_heuristics("https://www.example.com/path")
    assert result["flags"] == []


@pytest.mark.asyncio
@respx.mock
async def test_expand_short_link_follows_redirect():
    respx.head("https://bit.ly/abc").mock(
        return_value=Response(302, headers={"Location": "https://example.com/final"})
    )
    respx.head("https://example.com/final").mock(return_value=Response(200))

    result = await expand_short_link("https://bit.ly/abc")
    assert result == "https://example.com/final"


@pytest.mark.asyncio
@respx.mock
async def test_check_urlhaus_true_when_ok():
    respx.post(URLHAUS_ENDPOINT).mock(
        return_value=Response(200, json={"query_status": "ok"})
    )
    assert await check_urlhaus("http://evil.test/") is True


@pytest.mark.asyncio
@respx.mock
async def test_check_urlhaus_false_when_no_results():
    respx.post(URLHAUS_ENDPOINT).mock(
        return_value=Response(200, json={"query_status": "no_results"})
    )
    assert await check_urlhaus("https://example.com/") is False


@pytest.mark.asyncio
@respx.mock
async def test_check_urlhaus_false_on_http_error():
    respx.post(URLHAUS_ENDPOINT).mock(return_value=Response(500))
    assert await check_urlhaus("https://example.com/") is False
