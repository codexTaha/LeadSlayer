from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx


MAX_HTML_BYTES = 150_000
MAX_EXTRACTED_CHARS = 2_500

_TECH_FINGERPRINTS: tuple[tuple[str, str], ...] = (
    ("shopify-checkout", "Shopify Plus"),
    ("cdn.shopify.com", "Shopify"),
    ("woocommerce", "WooCommerce"),
    ("wp-content", "WordPress"),
    ("klaviyo", "Klaviyo"),
    ("rechargepayments", "Recharge"),
    ("gorgias", "Gorgias"),
    ("stripe.com", "Stripe"),
    ("hubspot", "HubSpot"),
    ("hs-scripts", "HubSpot"),
    ("intercom", "Intercom"),
    ("webflow", "Webflow"),
    ("__next", "Next.js"),
    ("kubernetes", "Kubernetes"),
    ("datadog", "Datadog"),
    ("segment.com", "Segment"),
    ("magento", "Magento"),
    ("bigcommerce", "BigCommerce"),
)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IGNORED_EMAIL_FRAGMENTS = (
    "example.com",
    "sentry.io",
    "wixpress.com",
    "shopify.com",
    "squarespace.com",
    "wordpress.org",
    "w3.org",
    "noreply@",
    "no-reply@",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".css",
    ".js",
)


@dataclass
class CompanySiteIntel:
    reachable: bool
    summary: str = ""
    emails: list[str] = field(default_factory=list)
    tech_signals: list[str] = field(default_factory=list)


class _ReadableHTMLParser(HTMLParser):
    """Lightweight stdlib HTML-to-text extractor stripping scripts/styles."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.title: str = ""
        self.meta_description: str = ""
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        if tag_l in ("script", "style", "noscript", "svg"):
            self._skip_depth += 1
        elif tag_l == "title":
            self._in_title = True
        elif tag_l == "meta":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            name = attr_map.get("name", "").lower() or attr_map.get("property", "").lower()
            if name in ("description", "og:description") and not self.meta_description:
                self.meta_description = attr_map.get("content", "").strip()

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l in ("script", "style", "noscript", "svg") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag_l == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title and not self.title:
            self.title = cleaned
        else:
            self._chunks.append(cleaned)

    def render(self) -> str:
        parts: list[str] = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.meta_description:
            parts.append(f"Summary: {self.meta_description}")
        body = re.sub(r"\s+", " ", " ".join(self._chunks)).strip()
        if body:
            parts.append(f"Page Content: {body}")
        return "\n".join(parts)[:MAX_EXTRACTED_CHARS]


def is_safe_public_url(raw_url: str) -> str | None:
    """Validate HTTP(S) URL and block loopback/private SSRF targets."""
    candidate = raw_url.strip()
    if not candidate:
        return None
    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None

    host = parsed.hostname.lower()
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        return None

    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return None
    except ValueError:
        pass  # Domain name, not a raw IP literal

    return candidate


def extract_readable_text(html: str) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html[:MAX_HTML_BYTES])
    parser.close()
    return parser.render()


async def fetch_site_context(url: str | None, timeout_s: float = 3.0) -> str | None:
    """Safely fetch and extract concise landing page copy for MarketAuditor / Hunter."""
    if not url:
        return None
    safe_url = is_safe_public_url(url)
    if not safe_url:
        return None

    try:
        async with httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "LeadSlayerBot/1.0 (+https://leadslayer.ai)"},
        ) as client:
            resp = await client.get(safe_url)
            if resp.status_code >= 400:
                return None
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "text/plain" not in content_type:
                return None
            extracted = extract_readable_text(resp.text)
            return extracted if len(extracted) >= 30 else None
    except (httpx.HTTPError, ValueError):
        return None


def extract_emails_from_html(html: str, expected_domain: str | None = None) -> list[str]:
    """Extract clean, non-asset public contact emails from HTML markup."""
    seen: list[str] = []
    for raw in _EMAIL_RE.findall(html[:MAX_HTML_BYTES]):
        lower = raw.lower()
        if any(frag in lower for frag in _IGNORED_EMAIL_FRAGMENTS):
            continue
        if raw not in seen:
            seen.append(raw)
    if expected_domain:
        root = expected_domain.lower().removeprefix("www.")
        domain_first = [e for e in seen if root in e.lower()]
        return domain_first[:5]
    return seen[:5]


def detect_tech_signals(html: str) -> list[str]:
    """Fingerprint common storefront & SaaS technologies from page HTML."""
    lower = html[:MAX_HTML_BYTES].lower()
    detected: list[str] = []
    for needle, label in _TECH_FINGERPRINTS:
        if needle in lower and label not in detected:
            detected.append(label)
    return detected


async def fetch_company_intel(domain: str, timeout_s: float = 3.5) -> CompanySiteIntel:
    """
    Safely verify a discovered company domain via live HTTP GET and extract
    landing copy, tech fingerprints, and any publicly listed contact emails.
    """
    safe_base = is_safe_public_url(domain)
    if not safe_base:
        return CompanySiteIntel(reachable=False)

    parsed = urlparse(safe_base)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    target_urls = [safe_base, f"{base_origin}/contact", f"{base_origin}/pages/contact"]

    combined_text_parts: list[str] = []
    found_emails: list[str] = []
    found_tech: list[str] = []
    reachable = False

    try:
        async with httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "LeadSlayerBot/1.0 (+https://leadslayer.ai)"},
        ) as client:
            for url in target_urls:
                try:
                    resp = await client.get(url)
                except (httpx.HTTPError, ValueError):
                    continue
                if resp.status_code >= 400:
                    continue
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "text/plain" not in content_type:
                    continue
                reachable = True
                html = resp.text
                text = extract_readable_text(html)
                if text and len(combined_text_parts) < 2:
                    combined_text_parts.append(text[:1000])
                for email in extract_emails_from_html(html, expected_domain=parsed.hostname):
                    if email not in found_emails:
                        found_emails.append(email)
                for tech in detect_tech_signals(html):
                    if tech not in found_tech:
                        found_tech.append(tech)
                # Stop after /contact only if homepage lacked emails
                if url == safe_base and found_emails:
                    break
    except (httpx.HTTPError, ValueError):
        return CompanySiteIntel(reachable=False)

    return CompanySiteIntel(
        reachable=reachable,
        summary=" | ".join(combined_text_parts)[:1400],
        emails=found_emails[:3],
        tech_signals=found_tech[:6],
    )
