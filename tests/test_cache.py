from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache import cache_clear
from app.services.ai_engine.gemini_client import analyze_with_gemini


@pytest.fixture(autouse=True)
def _clear_cache():
    cache_clear()
    yield
    cache_clear()


@pytest.mark.asyncio
@patch("app.services.ai_engine.gemini_client._call_gemini", new_callable=AsyncMock)
async def test_identical_prompt_hits_cache_and_calls_api_once(mock_call):
    mock_call.return_value = {"risk_score": 40, "risk_level": "medium"}

    result1 = await analyze_with_gemini("Analisis pesan: menang undian!")
    result2 = await analyze_with_gemini("Analisis pesan: menang undian!")

    assert result1 == result2 == {"risk_score": 40, "risk_level": "medium"}
    mock_call.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.services.ai_engine.gemini_client._call_gemini", new_callable=AsyncMock)
async def test_different_prompt_bypasses_cache(mock_call):
    mock_call.side_effect = [
        {"risk_score": 10, "risk_level": "low"},
        {"risk_score": 90, "risk_level": "high"},
    ]

    result1 = await analyze_with_gemini("pesan A")
    result2 = await analyze_with_gemini("pesan B")

    assert result1["risk_score"] == 10
    assert result2["risk_score"] == 90
    assert mock_call.await_count == 2
