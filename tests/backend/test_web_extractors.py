"""Tests for deterministic signal extraction from HTML and HTTP metadata."""

from backend.providers.web.extractors import detect_cms, extract_signals_from_page
from backend.providers.web.fetcher import FetchedPage

RESPONSIVE_WP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Artisanal cafe serving organic coffee and fresh pastries in Pune.">
    <meta name="generator" content="WordPress 6.4.2">
    <title>Blue Tokai Coffee Roasters</title>
</head>
<body>
    <h1>Welcome to Blue Tokai</h1>
    <p>Contact us for reservations or inquiries.</p>
    <a href="mailto:hello@bluetokai.com">Email Us</a>
    <a href="tel:+919876543210">Call Us</a>
    <a href="https://wa.me/919876543210">WhatsApp</a>
    <a href="https://www.instagram.com/bluetokaicoffee">Instagram</a>
    <a href="https://www.linkedin.com/company/blue-tokai-coffee-roasters/">LinkedIn</a>
</body>
</html>
"""

LEGACY_NON_RESPONSIVE_HTML = """
<html>
<head>
    <title>Old Style Diner</title>
</head>
<body>
    <table width="800">
        <tr><td>Welcome to Old Style Diner!</td></tr>
    </table>
</body>
</html>
"""

SHOPIFY_HTML = """
<html>
<head>
    <script src="https://cdn.shopify.com/s/files/1/theme.js"></script>
    <title>Organic Store</title>
</head>
<body></body>
</html>
"""


def test_detect_cms():
    assert detect_cms(RESPONSIVE_WP_HTML) == "wordpress"
    assert detect_cms(SHOPIFY_HTML) == "shopify"
    assert detect_cms(LEGACY_NON_RESPONSIVE_HTML) is None


def test_extract_signals_responsive_wordpress_site():
    page = FetchedPage(
        original_url="https://bluetokai.com",
        final_url="https://bluetokai.com",
        status_code=200,
        reachable=True,
        text=RESPONSIVE_WP_HTML,
        response_time_ms=120.5,
        https_enforced=True,
        ssl_valid=True,
        ssl_days_remaining=85,
        dns_resolves=True,
    )

    signals = extract_signals_from_page(page)

    assert signals["website_exists"] is True
    assert signals["dns_resolves"] is True
    assert signals["reachable"] is True
    assert signals["http_status"] == 200
    assert signals["https_enforced"] is True
    assert signals["ssl_valid"] is True
    assert signals["ssl_days_remaining"] == 85
    assert signals["mobile_viewport"] is True
    assert signals["page_title"] == "Blue Tokai Coffee Roasters"
    assert "Artisanal cafe" in signals["meta_description"]
    assert signals["cms_platform"] == "wordpress"
    assert "hello@bluetokai.com" in signals["public_emails"]
    assert "+919876543210" in signals["public_phones"]
    assert "whatsapp" in signals["social_links"]
    assert "instagram" in signals["social_links"]
    assert "linkedin" in signals["social_links"]


def test_extract_signals_legacy_non_responsive_site():
    page = FetchedPage(
        original_url="http://olddiner.com",
        final_url="http://olddiner.com",
        status_code=200,
        reachable=True,
        text=LEGACY_NON_RESPONSIVE_HTML,
        https_enforced=False,
        ssl_valid=False,
        dns_resolves=True,
    )

    signals = extract_signals_from_page(page)

    assert signals["reachable"] is True
    assert signals["mobile_viewport"] is False
    assert signals["page_title"] == "Old Style Diner"
    assert signals["meta_description"] is None
    assert signals["cms_platform"] is None
    assert signals["public_emails"] == []


def test_extract_signals_unreachable_page():
    page = FetchedPage(
        original_url="https://deadsite.example",
        final_url="https://deadsite.example",
        reachable=False,
        error="DNS_RESOLUTION_FAILED",
        dns_resolves=False,
    )

    signals = extract_signals_from_page(page)

    assert signals["website_exists"] is True
    assert signals["reachable"] is False
    assert signals["dns_resolves"] is False
    assert signals["mobile_viewport"] is None
    assert signals["page_title"] is None
