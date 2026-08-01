from app.models.analyze_schema import RecommendedAction, RiskLevel, ScanType
from app.services.risk_engine.risk_scorer import build_analysis_result


def test_build_analysis_result_low_risk():
    llm_result = {
        "risk_score": 10,
        "risk_level": "low",
        "explanation": "Tidak ada indikasi penipuan.",
        "red_flags": [],
        "recommendation": "ignore",
        "recommendation_text": "Aman, lanjutkan seperti biasa.",
        "category": None,
    }
    result = build_analysis_result(
        scan_type=ScanType.CHAT, input_summary="Halo, apa kabar?", llm_result=llm_result
    )
    assert result.risk_level == RiskLevel.LOW
    assert result.risk_score == 10
    assert result.recommendation == RecommendedAction.IGNORE


def test_build_analysis_result_clamps_invalid_score():
    llm_result = {
        "risk_score": 999,
        "risk_level": "unknown_value",
        "explanation": "x",
        "recommendation": "not_a_valid_action",
    }
    result = build_analysis_result(
        scan_type=ScanType.CHAT, input_summary="test", llm_result=llm_result
    )
    assert result.risk_score == 100
    assert result.risk_level == RiskLevel.HIGH
    assert result.recommendation == RecommendedAction.BLOCK


def test_build_analysis_result_force_high_risk_from_safe_browsing():
    llm_result = {
        "risk_score": 20,
        "risk_level": "low",
        "explanation": "Tampak biasa saja.",
        "recommendation": "ignore",
    }
    result = build_analysis_result(
        scan_type=ScanType.LINK,
        input_summary="http://phishing-example.com",
        llm_result=llm_result,
        force_high_risk=True,
    )
    assert result.risk_level == RiskLevel.HIGH
    assert result.risk_score >= 85
    assert result.recommendation == RecommendedAction.BLOCK


def test_red_flags_parsing_ignores_malformed_items():
    llm_result = {
        "risk_score": 50,
        "risk_level": "medium",
        "explanation": "x",
        "recommendation": "proceed_carefully",
        "red_flags": [
            {"label": "Urgensi berlebihan", "detail": "Meminta transfer segera"},
            "bukan dict, harus diabaikan",
            {"detail": "tidak ada label, harus diabaikan"},
        ],
    }
    result = build_analysis_result(
        scan_type=ScanType.CHAT, input_summary="test", llm_result=llm_result
    )
    assert len(result.red_flags) == 1
    assert result.red_flags[0].label == "Urgensi berlebihan"
