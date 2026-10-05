"""Deterministic, ICP-specific opportunity scoring engine."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from backend.models.base import utc_now
from backend.schemas.icp import CompiledICPCriteria
from backend.schemas.prospect import ScoreFactor

SCORING_VERSION = "v1.0"

# Token sets for deterministic scoring profile selection
WEB_REDESIGN_TOKENS = {
    "web",
    "website",
    "websites",
    "redesign",
    "mobile",
    "responsive",
    "frontend",
    "developer",
    "development",
    "design",
    "ui",
    "ux",
    "wordpress",
    "shopify",
}

MARKETING_SEO_TOKENS = {
    "seo",
    "marketing",
    "ads",
    "advertising",
    "traffic",
    "leads",
    "ppc",
    "content",
    "social",
    "instagram",
    "growth",
}


def resolve_scoring_profile(service_offering: str) -> str:
    """Deterministically map a seller's service offering into a scoring strategy profile."""
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", service_offering.lower()))
    if tokens & WEB_REDESIGN_TOKENS:
        return "WEB_REDESIGN_MODERNIZATION"
    if tokens & MARKETING_SEO_TOKENS:
        return "MARKETING_AND_SEO"
    return "GENERAL_B2B_SALES"


@dataclass
class ComputedScore:
    """Result of scoring evaluation."""

    priority_score: float
    raw_score: float
    status_multiplier: float
    scoring_profile: str
    scoring_version: str
    scored_at: datetime
    factors: list[ScoreFactor]

    def to_breakdown_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary for score_breakdown persistence."""
        return {
            "priority_score": self.priority_score,
            "raw_score": self.raw_score,
            "status_multiplier": self.status_multiplier,
            "scoring_profile": self.scoring_profile,
            "scoring_version": self.scoring_version,
            "scored_at": self.scored_at.isoformat(),
            "factors": [f.model_dump() for f in self.factors],
        }


class ScoringEngine:
    """Evaluates prospect research evidence against ICP to produce explainable scores."""

    @staticmethod
    def calculate_score(
        icp: CompiledICPCriteria,
        signals: dict[str, Any],
        canonical_category: str,
        business_name: str,
        qualification_status: str,
    ) -> ComputedScore:
        """Compute deterministic, explainable priority score and factor breakdown."""
        now = utc_now()
        profile = resolve_scoring_profile(icp.service_offering)
        factors: list[ScoreFactor] = []

        # -------------------------------------------------------------
        # Status Multiplier
        # -------------------------------------------------------------
        if qualification_status == "QUALIFIED":
            status_multiplier = 1.0
        elif qualification_status == "REVIEW_NEEDED":
            status_multiplier = 0.60
        else:  # DISQUALIFIED or UNQUALIFIED
            status_multiplier = 0.0

        # Build text corpus for keyword checks
        page_title = signals.get("page_title") or ""
        meta_desc = signals.get("meta_description") or ""
        text_corpus = (
            f"{business_name} {canonical_category} {page_title} {meta_desc}".lower().strip()
        )

        # -------------------------------------------------------------
        # Profile 1: WEB_REDESIGN_MODERNIZATION (Total Max Impact: 1.00)
        # -------------------------------------------------------------
        if profile == "WEB_REDESIGN_MODERNIZATION":
            # 1. Mobile Viewport Gap (Max: 0.25)
            # Opportunity: Site is active but lacks mobile viewport optimization
            mv = signals.get("mobile_viewport")
            if mv is False:
                factors.append(
                    ScoreFactor(
                        key="mobile_gap",
                        label="Lacks Mobile Viewport",
                        impact=0.25,
                        max_impact=0.25,
                        status="matched",
                        evidence_snippet="HTML lacks <meta name='viewport'> tag; acute redesign opportunity.",
                    )
                )
            elif mv is True:
                factors.append(
                    ScoreFactor(
                        key="mobile_gap",
                        label="Lacks Mobile Viewport",
                        impact=0.0,
                        max_impact=0.25,
                        status="unmatched",
                        evidence_snippet="Site already includes mobile viewport tag.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="mobile_gap",
                        label="Lacks Mobile Viewport",
                        impact=0.0,
                        max_impact=0.25,
                        status="unknown",
                        evidence_snippet="Mobile viewport could not be determined due to unread/unreachable page.",
                    )
                )

            # 2. SSL Security Gap (Max: 0.15)
            ssl_val = signals.get("ssl_valid")
            https_enf = signals.get("https_enforced")
            if ssl_val is False or https_enf is False:
                factors.append(
                    ScoreFactor(
                        key="ssl_gap",
                        label="Insecure / Missing SSL",
                        impact=0.15,
                        max_impact=0.15,
                        status="matched",
                        evidence_snippet="Site lacks valid SSL certificate or does not enforce HTTPS.",
                    )
                )
            elif ssl_val is True and https_enf is True:
                factors.append(
                    ScoreFactor(
                        key="ssl_gap",
                        label="Insecure / Missing SSL",
                        impact=0.0,
                        max_impact=0.15,
                        status="unmatched",
                        evidence_snippet="Site has valid SSL certificate with HTTPS enforced.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="ssl_gap",
                        label="Insecure / Missing SSL",
                        impact=0.0,
                        max_impact=0.15,
                        status="unknown",
                        evidence_snippet="SSL security state could not be verified.",
                    )
                )

            # 3. Category Relevance (Max: 0.20)
            if canonical_category in icp.target_categories:
                factors.append(
                    ScoreFactor(
                        key="category_fit",
                        label="Target Category Alignment",
                        impact=0.20,
                        max_impact=0.20,
                        status="matched",
                        evidence_snippet=f"Category '{canonical_category}' matches target categories.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="category_fit",
                        label="Target Category Alignment",
                        impact=0.0,
                        max_impact=0.20,
                        status="unmatched",
                        evidence_snippet=f"Category '{canonical_category}' does not match target categories.",
                    )
                )

            # 4. Keyword Boost (Max: 0.15)
            if icp.signals.keywords:
                matched_kws = [kw for kw in icp.signals.keywords if kw.lower() in text_corpus]
                if matched_kws:
                    kw_ratio = min(1.0, len(matched_kws) / len(icp.signals.keywords))
                    kw_impact = round(0.15 * kw_ratio, 2)
                    factors.append(
                        ScoreFactor(
                            key="keyword_fit",
                            label="Target Keyword Matches",
                            impact=kw_impact,
                            max_impact=0.15,
                            status="matched",
                            evidence_snippet=f"Matched keywords: {', '.join(matched_kws)}.",
                        )
                    )
                else:
                    factors.append(
                        ScoreFactor(
                            key="keyword_fit",
                            label="Target Keyword Matches",
                            impact=0.0,
                            max_impact=0.15,
                            status="unmatched",
                            evidence_snippet="None of the target keywords were found in page text.",
                        )
                    )
            else:
                # If no keywords specified, give default relevance points
                factors.append(
                    ScoreFactor(
                        key="keyword_fit",
                        label="Target Keyword Matches",
                        impact=0.15,
                        max_impact=0.15,
                        status="matched",
                        evidence_snippet="No keyword restrictions specified; full topical fit granted.",
                    )
                )

            # 5. Outreach Contact Readiness (Max: 0.15)
            has_email = bool(signals.get("public_emails"))
            has_phone = bool(signals.get("public_phones"))
            contact_impact = (0.10 if has_email else 0.0) + (0.05 if has_phone else 0.0)
            factors.append(
                ScoreFactor(
                    key="contact_readiness",
                    label="Outreach Channel Availability",
                    impact=round(contact_impact, 2),
                    max_impact=0.15,
                    status="matched" if (has_email or has_phone) else "unmatched",
                    evidence_snippet=f"Emails: {len(signals.get('public_emails', []))}, Phones: {len(signals.get('public_phones', []))}.",
                )
            )

            # 6. Baseline Operational Vitality (Max: 0.10)
            reachable = signals.get("reachable")
            if reachable is True:
                factors.append(
                    ScoreFactor(
                        key="baseline_vitality",
                        label="Active Domain Presence",
                        impact=0.10,
                        max_impact=0.10,
                        status="matched",
                        evidence_snippet=f"Domain is active (status {signals.get('http_status') or 200}).",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="baseline_vitality",
                        label="Active Domain Presence",
                        impact=0.0,
                        max_impact=0.10,
                        status="unmatched" if reachable is False else "unknown",
                        evidence_snippet="Domain is unreachable or dead.",
                    )
                )

        # -------------------------------------------------------------
        # Profile 2: MARKETING_AND_SEO (Total Max Impact: 1.00)
        # -------------------------------------------------------------
        elif profile == "MARKETING_AND_SEO":
            # 1. Technical Conversion Foundation (Max: 0.25)
            # Marketing/SEO requires an already responsive and secure site to convert traffic
            mv = signals.get("mobile_viewport")
            ssl_val = signals.get("ssl_valid")
            if mv is True and ssl_val is True:
                factors.append(
                    ScoreFactor(
                        key="tech_foundation",
                        label="Mobile & Security Foundation",
                        impact=0.25,
                        max_impact=0.25,
                        status="matched",
                        evidence_snippet="Site is mobile-friendly with valid SSL; ready for marketing traffic.",
                    )
                )
            elif mv is True or ssl_val is True:
                factors.append(
                    ScoreFactor(
                        key="tech_foundation",
                        label="Mobile & Security Foundation",
                        impact=0.12,
                        max_impact=0.25,
                        status="matched",
                        evidence_snippet="Partial technical foundation; some conversion leakage expected.",
                    )
                )
            elif mv is None and ssl_val is None:
                factors.append(
                    ScoreFactor(
                        key="tech_foundation",
                        label="Mobile & Security Foundation",
                        impact=0.0,
                        max_impact=0.25,
                        status="unknown",
                        evidence_snippet="Technical foundation could not be verified.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="tech_foundation",
                        label="Mobile & Security Foundation",
                        impact=0.0,
                        max_impact=0.25,
                        status="unmatched",
                        evidence_snippet="Site lacks mobile viewport and SSL; poor fit for SEO/paid traffic.",
                    )
                )

            # 2. Target Category Relevance (Max: 0.20)
            if canonical_category in icp.target_categories:
                factors.append(
                    ScoreFactor(
                        key="category_fit",
                        label="Target Category Alignment",
                        impact=0.20,
                        max_impact=0.20,
                        status="matched",
                        evidence_snippet=f"Category '{canonical_category}' in target categories.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="category_fit",
                        label="Target Category Alignment",
                        impact=0.0,
                        max_impact=0.20,
                        status="unmatched",
                        evidence_snippet=f"Category '{canonical_category}' not in target categories.",
                    )
                )

            # 3. Keyword Fit & Search Intent (Max: 0.20)
            if icp.signals.keywords:
                matched_kws = [kw for kw in icp.signals.keywords if kw.lower() in text_corpus]
                if matched_kws:
                    kw_ratio = min(1.0, len(matched_kws) / len(icp.signals.keywords))
                    factors.append(
                        ScoreFactor(
                            key="keyword_fit",
                            label="Target Keyword Matches",
                            impact=round(0.20 * kw_ratio, 2),
                            max_impact=0.20,
                            status="matched",
                            evidence_snippet=f"Matched SEO keywords: {', '.join(matched_kws)}.",
                        )
                    )
                else:
                    factors.append(
                        ScoreFactor(
                            key="keyword_fit",
                            label="Target Keyword Matches",
                            impact=0.0,
                            max_impact=0.20,
                            status="unmatched",
                            evidence_snippet="None of target keywords matched page content.",
                        )
                    )
            else:
                factors.append(
                    ScoreFactor(
                        key="keyword_fit",
                        label="Target Keyword Matches",
                        impact=0.20,
                        max_impact=0.20,
                        status="matched",
                        evidence_snippet="No keyword restrictions specified; full topical fit granted.",
                    )
                )

            # 4. Outreach & Social Footprint (Max: 0.20)
            has_email = bool(signals.get("public_emails"))
            has_phone = bool(signals.get("public_phones"))
            has_socials = bool(signals.get("social_links"))
            c_impact = (
                (0.10 if has_email else 0.0)
                + (0.05 if has_phone else 0.0)
                + (0.05 if has_socials else 0.0)
            )
            factors.append(
                ScoreFactor(
                    key="contact_readiness",
                    label="Outreach & Social Footprint",
                    impact=round(c_impact, 2),
                    max_impact=0.20,
                    status="matched" if c_impact > 0 else "unmatched",
                    evidence_snippet=f"Email: {has_email}, Phone: {has_phone}, Socials: {len(signals.get('social_links', {}))}.",
                )
            )

            # 5. Baseline Operational Speed (Max: 0.15)
            reachable = signals.get("reachable")
            resp_ms = signals.get("response_time_ms")
            if reachable is True and resp_ms is not None and resp_ms < 1000.0:
                factors.append(
                    ScoreFactor(
                        key="baseline_vitality",
                        label="Fast & Responsive Domain",
                        impact=0.15,
                        max_impact=0.15,
                        status="matched",
                        evidence_snippet=f"Fast server response ({resp_ms}ms).",
                    )
                )
            elif reachable is True:
                factors.append(
                    ScoreFactor(
                        key="baseline_vitality",
                        label="Fast & Responsive Domain",
                        impact=0.08,
                        max_impact=0.15,
                        status="matched",
                        evidence_snippet=f"Reachable but slow server response ({resp_ms}ms).",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="baseline_vitality",
                        label="Fast & Responsive Domain",
                        impact=0.0,
                        max_impact=0.15,
                        status="unmatched" if reachable is False else "unknown",
                        evidence_snippet="Site is not reachable.",
                    )
                )

        # -------------------------------------------------------------
        # Profile 3: GENERAL_B2B_SALES (Total Max Impact: 1.00)
        # -------------------------------------------------------------
        else:
            # 1. Target Category Relevance (Max: 0.30)
            if canonical_category in icp.target_categories:
                factors.append(
                    ScoreFactor(
                        key="category_fit",
                        label="Target Category Alignment",
                        impact=0.30,
                        max_impact=0.30,
                        status="matched",
                        evidence_snippet=f"Category '{canonical_category}' matches target categories.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="category_fit",
                        label="Target Category Alignment",
                        impact=0.0,
                        max_impact=0.30,
                        status="unmatched",
                        evidence_snippet=f"Category '{canonical_category}' not in target categories.",
                    )
                )

            # 2. Outreach Channel Availability (Max: 0.30)
            has_email = bool(signals.get("public_emails"))
            has_phone = bool(signals.get("public_phones"))
            has_socials = bool(signals.get("social_links"))
            c_impact = (
                (0.15 if has_email else 0.0)
                + (0.10 if has_phone else 0.0)
                + (0.05 if has_socials else 0.0)
            )
            factors.append(
                ScoreFactor(
                    key="contact_readiness",
                    label="Outreach Channel Availability",
                    impact=round(c_impact, 2),
                    max_impact=0.30,
                    status="matched" if c_impact > 0 else "unmatched",
                    evidence_snippet=f"Email: {has_email}, Phone: {has_phone}, Socials: {has_socials}.",
                )
            )

            # 3. Keyword Alignment (Max: 0.20)
            if icp.signals.keywords:
                matched_kws = [kw for kw in icp.signals.keywords if kw.lower() in text_corpus]
                if matched_kws:
                    kw_ratio = min(1.0, len(matched_kws) / len(icp.signals.keywords))
                    factors.append(
                        ScoreFactor(
                            key="keyword_fit",
                            label="Target Keyword Matches",
                            impact=round(0.20 * kw_ratio, 2),
                            max_impact=0.20,
                            status="matched",
                            evidence_snippet=f"Matched keywords: {', '.join(matched_kws)}.",
                        )
                    )
                else:
                    factors.append(
                        ScoreFactor(
                            key="keyword_fit",
                            label="Target Keyword Matches",
                            impact=0.0,
                            max_impact=0.20,
                            status="unmatched",
                            evidence_snippet="No positive keywords found in business digital presence.",
                        )
                    )
            else:
                factors.append(
                    ScoreFactor(
                        key="keyword_fit",
                        label="Target Keyword Matches",
                        impact=0.20,
                        max_impact=0.20,
                        status="matched",
                        evidence_snippet="No keyword restrictions specified; full topical fit granted.",
                    )
                )

            # 4. Verified Digital Presence (Max: 0.20)
            reachable = signals.get("reachable")
            if reachable is True:
                factors.append(
                    ScoreFactor(
                        key="digital_presence",
                        label="Verified Active Web Presence",
                        impact=0.20,
                        max_impact=0.20,
                        status="matched",
                        evidence_snippet="Business operates an active, responding web domain.",
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        key="digital_presence",
                        label="Verified Active Web Presence",
                        impact=0.0,
                        max_impact=0.20,
                        status="unmatched" if reachable is False else "unknown",
                        evidence_snippet="No active web presence verified.",
                    )
                )

        # -------------------------------------------------------------
        # Score Mathematics: raw_score and priority_score
        # -------------------------------------------------------------
        raw_score = round(sum(f.impact for f in factors), 4)
        raw_score = max(0.0, min(1.0, raw_score))

        priority_score = round(raw_score * status_multiplier, 4)
        priority_score = max(0.0, min(1.0, priority_score))

        return ComputedScore(
            priority_score=priority_score,
            raw_score=raw_score,
            status_multiplier=status_multiplier,
            scoring_profile=profile,
            scoring_version=SCORING_VERSION,
            scored_at=now,
            factors=factors,
        )
