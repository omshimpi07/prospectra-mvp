"""Tests for deterministic opportunity scoring engine and dynamic profiles."""

import pytest

from backend.schemas.icp import CompiledICPCriteria, LocationCriteria, TargetSignals
from backend.services.scoring import (
    ScoringEngine,
    resolve_scoring_profile,
)


def make_test_icp(
    service_offering: str = "Web Design and Frontend Development",
    target_categories: list[str] | None = None,
    keywords: list[str] | None = None,
) -> CompiledICPCriteria:
    return CompiledICPCriteria(
        service_offering=service_offering,
        target_categories=target_categories or ["cafe", "restaurant"],
        location=LocationCriteria(city="Pune"),
        signals=TargetSignals(
            has_website=True,
            keywords=keywords or [],
        ),
    )


def test_resolve_scoring_profile_deterministic():
    assert (
        resolve_scoring_profile("Custom WordPress website redesign and mobile optimization")
        == "WEB_REDESIGN_MODERNIZATION"
    )
    assert (
        resolve_scoring_profile("SEO growth, Google Ads, and PPC campaigns") == "MARKETING_AND_SEO"
    )
    assert (
        resolve_scoring_profile("Commercial equipment supplier and B2B distributor")
        == "GENERAL_B2B_SALES"
    )


@pytest.mark.parametrize(
    "service_offering",
    [
        "Website redesign and mobile development",
        "SEO and Google Ads marketing",
        "Commercial coffee machine distributor",
    ],
)
def test_all_profiles_factor_weights_sum_to_one(service_offering: str):
    """Every deterministic scoring profile must satisfy sum(max_factor_impact) == 1.00."""
    icp = make_test_icp(service_offering=service_offering)
    signals = {
        "website_exists": True,
        "reachable": True,
        "http_status": 200,
        "mobile_viewport": True,
        "ssl_valid": True,
        "https_enforced": True,
        "public_emails": ["contact@example.com"],
        "public_phones": ["+919876543210"],
    }
    computed = ScoringEngine.calculate_score(
        icp=icp,
        signals=signals,
        canonical_category="cafe",
        business_name="Cafe Artisan",
        qualification_status="QUALIFIED",
    )

    max_sum = round(sum(f.max_impact for f in computed.factors), 2)
    assert max_sum == 1.00, (
        f"Profile {computed.scoring_profile} weights sum to {max_sum}, expected 1.00"
    )


def test_score_mathematics_and_multipliers():
    """Verify raw_score, priority_score, and multipliers."""
    icp = make_test_icp(service_offering="Website redesign")
    signals = {
        "website_exists": True,
        "reachable": True,
        "http_status": 200,
        "mobile_viewport": False,  # Gap: +0.25
        "ssl_valid": False,  # Gap: +0.15
        "https_enforced": False,
        "public_emails": ["contact@example.com"],
        "public_phones": ["+919876543210"],
    }

    # 1. QUALIFIED -> status_multiplier = 1.0
    res_qual = ScoringEngine.calculate_score(
        icp=icp,
        signals=signals,
        canonical_category="cafe",
        business_name="Cafe Artisan",
        qualification_status="QUALIFIED",
    )
    assert res_qual.status_multiplier == 1.0
    assert res_qual.priority_score == res_qual.raw_score
    assert 0.0 <= res_qual.priority_score <= 1.0

    # 2. REVIEW_NEEDED -> status_multiplier = 0.60
    res_review = ScoringEngine.calculate_score(
        icp=icp,
        signals=signals,
        canonical_category="cafe",
        business_name="Cafe Artisan",
        qualification_status="REVIEW_NEEDED",
    )
    assert res_review.status_multiplier == 0.60
    assert res_review.priority_score == round(res_review.raw_score * 0.60, 4)
    # Explicit check: sum(factor impacts) == raw_score, but does NOT equal priority_score under 0.60 multiplier
    assert round(sum(f.impact for f in res_review.factors), 4) == res_review.raw_score
    assert res_review.priority_score < res_review.raw_score

    # 3. DISQUALIFIED -> priority_score == 0.0
    res_disqual = ScoringEngine.calculate_score(
        icp=icp,
        signals=signals,
        canonical_category="cafe",
        business_name="Cafe Artisan",
        qualification_status="DISQUALIFIED",
    )
    assert res_disqual.status_multiplier == 0.0
    assert res_disqual.priority_score == 0.0
    assert res_disqual.raw_score > 0.0  # Raw factors exist, but multiplier zeroes it out


def test_score_boundary_conditions():
    """Verify priority_score strictly within [0.0, 1.0] at extremes."""
    icp = make_test_icp()

    # Extreme minimum: all empty / disqualified -> 0.0
    res_min = ScoringEngine.calculate_score(
        icp=icp,
        signals={},
        canonical_category="unrelated_category",
        business_name="Empty",
        qualification_status="DISQUALIFIED",
    )
    assert res_min.priority_score == 0.0

    # Extreme maximum: perfect signals matching all factors
    res_max = ScoringEngine.calculate_score(
        icp=icp,
        signals={
            "website_exists": True,
            "reachable": True,
            "http_status": 200,
            "mobile_viewport": False,
            "ssl_valid": False,
            "https_enforced": False,
            "public_emails": ["hello@cafe.com"],
            "public_phones": ["+919876543210"],
        },
        canonical_category="cafe",
        business_name="Perfect Opportunity Cafe",
        qualification_status="QUALIFIED",
    )
    assert 0.8 <= res_max.priority_score <= 1.0


def test_differential_scoring_same_business_different_icps():
    """Verify that the SAME business receives different scores for different ICP offerings."""
    business_signals = {
        "website_exists": True,
        "reachable": True,
        "http_status": 200,
        "response_time_ms": 150.0,
        "mobile_viewport": False,  # Pain point for web redesign; obstacle for SEO
        "ssl_valid": False,  # Pain point for web redesign; obstacle for SEO
        "https_enforced": False,
        "public_emails": ["owner@cafe.com"],
        "public_phones": ["+919876543210"],
    }

    # Seller A: Website Redesign
    icp_redesign = make_test_icp(service_offering="Mobile Responsive Website Redesign")
    score_redesign = ScoringEngine.calculate_score(
        icp=icp_redesign,
        signals=business_signals,
        canonical_category="cafe",
        business_name="Heritage Cafe",
        qualification_status="QUALIFIED",
    )

    # Seller B: SEO & Google Ads Management
    icp_seo = make_test_icp(service_offering="SEO Growth and Google Ads Campaigns")
    score_seo = ScoringEngine.calculate_score(
        icp=icp_seo,
        signals=business_signals,
        canonical_category="cafe",
        business_name="Heritage Cafe",
        qualification_status="QUALIFIED",
    )

    # For web redesign, lacking mobile and SSL is a high-value opportunity (+0.40)
    assert score_redesign.priority_score > score_seo.priority_score
    assert score_redesign.priority_score >= 0.80
    assert score_seo.priority_score <= 0.70
    assert round(score_redesign.priority_score - score_seo.priority_score, 2) >= 0.25


def test_unknown_signals_never_rewarded():
    """Unknown or unobserved probe signals must receive 0.0 impact and be labeled 'unknown'."""
    icp = make_test_icp(service_offering="Website Redesign")
    unprobed_signals = {
        "website_exists": True,
        "reachable": None,
        "mobile_viewport": None,  # Probe timed out / inconclusive
        "ssl_valid": None,  # Probe timed out / inconclusive
    }

    computed = ScoringEngine.calculate_score(
        icp=icp,
        signals=unprobed_signals,
        canonical_category="cafe",
        business_name="Mystery Cafe",
        qualification_status="REVIEW_NEEDED",
    )

    mv_factor = next(f for f in computed.factors if f.key == "mobile_gap")
    assert mv_factor.status == "unknown"
    assert mv_factor.impact == 0.0

    ssl_factor = next(f for f in computed.factors if f.key == "ssl_gap")
    assert ssl_factor.status == "unknown"
    assert ssl_factor.impact == 0.0


def test_web_development_scores_no_website_prospect_highly():
    """Verify prospects with no website are awarded acute opportunity in web development profile."""
    icp = make_test_icp(service_offering="Website Design and Development")
    signals = {
        "website_exists": False,
        "reachable": None,
        "public_emails": [],
        "public_phones": ["+919876543210"],
    }
    computed = ScoringEngine.calculate_score(
        icp=icp,
        signals=signals,
        canonical_category="cafe",
        business_name="Artisan Cafe",
        qualification_status="QUALIFIED",
    )
    # Total weights must sum to 1.00
    assert round(sum(f.max_impact for f in computed.factors), 2) == 1.00
    # No website factor should be matched and award 0.40
    no_web_factor = next(f for f in computed.factors if f.key == "no_website_opportunity")
    assert no_web_factor.status == "matched"
    assert no_web_factor.impact == 0.40
    # Overall score should be high (>= 0.65)
    assert computed.priority_score >= 0.65
