"""Deterministic signal extraction from fetched HTML and HTTP metadata."""

import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from backend.providers.web.fetcher import FetchedPage

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_CLEAN_REGEX = re.compile(r"[^\d+]")

CMS_PATTERNS = {
    "wordpress": [
        re.compile(r"wp-content", re.IGNORECASE),
        re.compile(r"wp-includes", re.IGNORECASE),
        re.compile(
            r'<meta[^>]+name=["\']generator["\'][^>]+content=["\'][^"\']*wordpress', re.IGNORECASE
        ),
    ],
    "shopify": [
        re.compile(r"cdn\.shopify\.com", re.IGNORECASE),
        re.compile(r"Shopify\.theme", re.IGNORECASE),
    ],
    "wix": [
        re.compile(r"wix\.com", re.IGNORECASE),
        re.compile(r"_wix_", re.IGNORECASE),
        re.compile(r"wixsite\.com", re.IGNORECASE),
    ],
    "squarespace": [
        re.compile(r"static1\.squarespace\.com", re.IGNORECASE),
        re.compile(r"squarespace\.com", re.IGNORECASE),
    ],
    "webflow": [
        re.compile(r"data-wf-page", re.IGNORECASE),
        re.compile(r"uploads-ssl\.webflow\.com", re.IGNORECASE),
        re.compile(r"assets\.website-files\.com", re.IGNORECASE),
    ],
}


def detect_cms(html_text: str) -> str | None:
    """Detect CMS platform deterministically from HTML text patterns."""
    for cms_name, patterns in CMS_PATTERNS.items():
        if any(p.search(html_text) for p in patterns):
            return cms_name
    return None


def extract_signals_from_page(page: FetchedPage) -> dict[str, Any]:
    """Extract deterministic technical, content, and public contact signals from a fetched page."""
    signals: dict[str, Any] = {
        "website_exists": True,
        "dns_resolves": page.dns_resolves,
        "reachable": page.reachable,
        "http_status": page.status_code,
        "response_time_ms": page.response_time_ms,
        "https_enforced": page.https_enforced,
        "ssl_valid": page.ssl_valid,
        "ssl_days_remaining": page.ssl_days_remaining,
        "mobile_viewport": None,
        "page_title": None,
        "meta_description": None,
        "cms_platform": None,
        "public_emails": [],
        "public_phones": [],
        "social_links": {},
    }

    if not page.reachable or not page.text:
        return signals

    html = page.text
    signals["cms_platform"] = detect_cms(html)

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return signals

    # 1. Mobile viewport
    viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.IGNORECASE)})
    signals["mobile_viewport"] = bool(viewport_tag)

    # 2. Title & Description
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        signals["page_title"] = title_tag.string.strip()[:200]

    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.IGNORECASE)})
    if desc_tag and desc_tag.get("content"):
        content_val = str(desc_tag.get("content"))
        signals["meta_description"] = content_val.strip()[:300]

    # 3. Public Contact Anchors (Strictly business-level public links)
    emails: set[str] = set()
    phones: set[str] = set()
    socials: dict[str, str] = {}

    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()

        # mailto:
        if href.lower().startswith("mailto:"):
            email_candidate = href.split(":", 1)[1].split("?")[0].strip().lower()
            if EMAIL_REGEX.match(email_candidate):
                emails.add(email_candidate)

        # tel:
        elif href.lower().startswith("tel:"):
            phone_candidate = href.split(":", 1)[1].split("?")[0].strip()
            if len(phone_candidate) >= 7:
                phones.add(phone_candidate)

        # WhatsApp click-to-chat
        elif "wa.me/" in href or "api.whatsapp.com/send" in href:
            socials["whatsapp"] = href

        # Social channels
        elif "instagram.com" in href and "instagram" not in socials:
            parsed = urlparse(href)
            if parsed.path.strip("/") and not any(x in parsed.path for x in ("/p/", "/explore/")):
                socials["instagram"] = href
        elif "facebook.com" in href and "facebook" not in socials:
            parsed = urlparse(href)
            if parsed.path.strip("/"):
                socials["facebook"] = href
        elif "linkedin.com/company" in href and "linkedin" not in socials:
            socials["linkedin"] = href

    signals["public_emails"] = sorted(emails)[:5]
    signals["public_phones"] = sorted(phones)[:5]
    signals["social_links"] = socials

    return signals
