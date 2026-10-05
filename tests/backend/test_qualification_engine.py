"""Tests for tri-state qualification engine and non-critical AI summary synthesis."""

from unittest.mock import AsyncMock

import pytest

from backend.schemas.icp import CompiledICPCriteria, LocationCriteria, TargetSignals
from backend.services.qualification import QualificationEngine


def make_test_icp(
    target_categories: list[str] | None = None,
    has_website: bool | None = None,
    keywords: list[str] | None = None,
    negative_keywords: list[str] | None = None,
) -> CompiledICPCriteria:
    return CompiledICPCriteria(
        service_offering="Web Development and SEO",
        target_categories=target_categories or ["cafe", "restaurant"],
        location=LocationCriteria(city="Pune"),
        signals=TargetSignals(
            has_website=has_website,
            keywords=keywords or [],
            negative_keywords=negative_keywords or [],
        ),
    )


def test_tristate_qualification_has_website_true():
    icp = make_test_icp(has_website=True)

    # 1. Active website -> PASS (QUALIFIED)
    signals_active = {
        "website_exists": True,
        "dns_resolves": True,
        "reachable": True,
        "http_status": 200,
    }
    outcome = QualificationEngine.evaluate(icp, signals_active, "cafe", "Blue Tokai")
    assert outcome.status == "QUALIFIED"
    assert outcome.fit_score == 1.0

    # 2. No website -> FAIL (DISQUALIFIED)
    signals_none = {
        "website_exists": False,
        "reachable": None,
    }
    outcome = QualificationEngine.evaluate(icp, signals_none, "cafe", "Local Dhaba")
    assert outcome.status == "DISQUALIFIED"
    assert any("has no website" in r for r in outcome.reasons)

    # 3. Probe timeout/unknown -> UNKNOWN (REVIEW_NEEDED)
    signals_unknown = {
        "website_exists": True,
        "dns_resolves": None,
        "reachable": None,
        "error": "CONNECT_TIMEOUT",
    }
    outcome = QualificationEngine.evaluate(icp, signals_unknown, "cafe", "Pending Cafe")
    assert outcome.status == "REVIEW_NEEDED"
    assert any("unknown due to probe timeout" in r for r in outcome.reasons)


def test_tristate_qualification_has_website_false():
    icp = make_test_icp(has_website=False)

    # 1. No website -> PASS (QUALIFIED)
    signals_none = {
        "website_exists": False,
        "reachable": None,
    }
    outcome = QualificationEngine.evaluate(icp, signals_none, "cafe", "Corner Tea")
    assert outcome.status == "QUALIFIED"

    # 2. Active website -> FAIL (DISQUALIFIED)
    signals_active = {
        "website_exists": True,
        "dns_resolves": True,
        "reachable": True,
        "http_status": 200,
    }
    outcome = QualificationEngine.evaluate(icp, signals_active, "cafe", "Starbucks")
    assert outcome.status == "DISQUALIFIED"
    assert any("business has an active website" in r for r in outcome.reasons)

    # 3. Probe timeout/unknown -> UNKNOWN (REVIEW_NEEDED)
    signals_unknown = {
        "website_exists": True,
        "dns_resolves": None,
        "reachable": None,
        "error": "DNS_RESOLUTION_FAILED",
    }
    outcome = QualificationEngine.evaluate(icp, signals_unknown, "cafe", "Unknown Site")
    assert outcome.status == "REVIEW_NEEDED"


def test_positive_and_negative_keyword_rules():
    icp = make_test_icp(
        keywords=["organic", "artisanal"],
        negative_keywords=["fast food", "franchise"],
    )

    # 1. Matches positive keyword and no negative -> QUALIFIED
    signals_good = {
        "page_title": "Blue Tokai Coffee",
        "meta_description": "We roast organic and artisanal coffee daily.",
    }
    outcome = QualificationEngine.evaluate(icp, signals_good, "cafe", "Blue Tokai")
    assert outcome.status == "QUALIFIED"

    # 2. Contains negative keyword -> DISQUALIFIED
    signals_neg = {
        "page_title": "Fast Food Express",
        "meta_description": "Organic coffee and fast food franchise.",
    }
    outcome = QualificationEngine.evaluate(icp, signals_neg, "cafe", "Express Cafe")
    assert outcome.status == "DISQUALIFIED"
    assert any("negative keyword" in r for r in outcome.reasons)

    # 3. Available text contains none of positive keywords -> DISQUALIFIED
    signals_no_match = {
        "page_title": "General Tea Stall",
        "meta_description": "Serving standard tea and snacks.",
    }
    outcome = QualificationEngine.evaluate(icp, signals_no_match, "cafe", "Tea Stall")
    assert outcome.status == "DISQUALIFIED"
    assert any("None of the target keywords" in r for r in outcome.reasons)

    # 4. Text content missing on existing site -> UNKNOWN (REVIEW_NEEDED)
    signals_empty_text = {
        "website_exists": True,
        "page_title": None,
        "meta_description": None,
    }
    outcome = QualificationEngine.evaluate(icp, signals_empty_text, "cafe", "Blank Site")
    assert outcome.status == "REVIEW_NEEDED"
    assert any("Keywords could not be verified" in r for r in outcome.reasons)


def test_category_matching():
    icp = make_test_icp(target_categories=["restaurant", "cafe"])

    outcome_pass = QualificationEngine.evaluate(icp, {}, "restaurant", "Diner")
    assert any(
        e.rule_name == "category_match" and e.result == "PASS"
        for e in outcome_pass.rule_evaluations
    )

    outcome_fail = QualificationEngine.evaluate(icp, {}, "dentist", "Dental Clinic")
    assert outcome_fail.status == "DISQUALIFIED"
    assert any("is not in target categories" in r for r in outcome_fail.reasons)


@pytest.mark.anyio
async def test_ai_summary_synthesis_graceful_failure():
    """Verify that failure of AI summary does not crash or fail qualification."""
    icp = make_test_icp()
    outcome = QualificationEngine.evaluate(icp, {"reachable": True}, "cafe", "Blue Tokai")
    assert outcome.status == "QUALIFIED"

    # Mock an AI provider that raises an exception (e.g. rate limit, network timeout)
    failing_ai = AsyncMock()
    failing_ai.complete_structured.side_effect = RuntimeError("OpenRouter 429 Too Many Requests")

    summary = await QualificationEngine.synthesize_rationale(
        icp=icp,
        signals={"reachable": True},
        outcome=outcome,
        ai_provider=failing_ai,
    )

    # Qualification result is preserved; deterministic fallback is returned
    assert "Qualified" in summary
    assert outcome.status == "QUALIFIED"
