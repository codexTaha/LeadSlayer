"""Tier A + Tier B Part 1 bridge wrapping Harvey's $0 collectors, people extractor, ATS feeds, and MX pattern resolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.harvey_bridge import ensure_harvey_on_path
from app.services.url_fetcher import detect_tech_signals, extract_readable_text, is_safe_public_url

import re

ensure_harvey_on_path()

# Detect parked domains or domain-for-sale landing pages (e.g. Spaceship, Sedo, GoDaddy)
_PARKED_DOMAIN_PATTERNS = [
    re.compile(r"domain\s+(?:is\s+)?(?:for\s+sale|parked|available)", re.I),
    re.compile(r"buy\s+this\s+domain", re.I),
    re.compile(r"inquire\s+about\s+this\s+domain", re.I),
    re.compile(r"parked\s+(?:free\s+)?(?:courtesy\s+of|by|page)", re.I),
    re.compile(r"spaceship\.com", re.I),
    re.compile(r"sedoparking\.com|sedo\s+domain\s+parking", re.I),
    re.compile(r"hugedomains\.com", re.I),
    re.compile(r"dan\.com/buy-domain", re.I),
    re.compile(r"godaddy(?:\.com)?\s+parked", re.I),
    re.compile(r"namecheap(?:\.com)?\s+parked", re.I),
    re.compile(r"this\s+(?:web\s*)?page\s+is\s+parked", re.I),
    re.compile(r"under\s+construction\s+-\s+domain\s+has\s+been\s+registered", re.I),
]


def is_parked_page(html: str) -> bool:
    """Return True if page HTML exhibits clear domain parking/for-sale indicators."""
    sample = html[:50_000]
    return any(p.search(sample) for p in _PARKED_DOMAIN_PATTERNS)

from harvey.collectors.ats import detect_board, read_board  # noqa: E402
from harvey.collectors.discover import JUNK_DOMAIN_PATTERNS  # noqa: E402
from harvey.collectors.people import (  # noqa: E402
    emails_on_page,
    find_people,
    menu_links,
    split_person_name,
)
from harvey.collectors.profile import TECH_FINGERPRINTS  # noqa: E402
from harvey.integrations.email_finder import (  # noqa: E402
    build_email,
    classify_mx,
    get_mx_host,
    site_email_evidence,
)


@dataclass
class HarveyCompanyDossier:
    reachable: bool
    summary: str = ""
    emails: list[str] = field(default_factory=list)
    resolved_email: str = ""
    email_status: str = "unknown"  # verified | guess | invalid | unknown
    mx_provider: str = ""
    email_pattern: str = ""
    tech_signals: list[str] = field(default_factory=list)
    decision_makers: list[dict] = field(default_factory=list)
    ats_open_roles: list[str] = field(default_factory=list)
    ats_board_label: str = ""


def is_junk_or_self_domain(domain: str, own_domain: str = "") -> bool:
    """Checks domain against own_domain and Harvey's comprehensive JUNK_DOMAIN_PATTERNS."""
    clean = (domain or "").strip().lower().strip(".")
    if not clean or "." not in clean:
        return True
    if own_domain and (clean == own_domain or clean.endswith(f".{own_domain}")):
        return True
    return any(pat.search(clean) for pat in JUNK_DOMAIN_PATTERNS)


def _detect_combined_tech_signals(html: str) -> list[str]:
    """Combines LeadSlayer's storefront fingerprints with Harvey's TECH_FINGERPRINTS."""
    import re

    detected = detect_tech_signals(html)
    head = html[:180_000]
    for label, patterns in TECH_FINGERPRINTS.items():
        if label in detected:
            continue
        if any(re.search(pat, head, re.I) for pat in patterns):
            detected.append(label)
    return detected


def _filter_on_domain_emails(addresses: list[str], domain: str) -> list[str]:
    root = (domain or "").lower().removeprefix("www.")
    if not root:
        return []
    return [a for a in addresses if a.lower().endswith(f"@{root}") or f".{root}" in a.lower().partition("@")[2]]


async def research_company_with_harvey(
    domain: str,
    candidate_name: str = "",
    candidate_role: str = "",
    timeout_s: float = 3.5,
) -> HarveyCompanyDossier:
    """
    Executes Harvey's $0 multi-page research pipeline for a single company domain:
    1) Homepage + menu_links (/about, /team, /contact) crawl
    2) Cloudflare/mailto/schema email extraction (on-domain only)
    3) Real executive/owner name extraction via extract_people
    4) Public ATS job-board detection & JSON posting fetch (Greenhouse/Lever/Ashby/Workable)
    5) DNS MX classification + site email pattern derivation + email candidate resolution
    """
    safe_home = is_safe_public_url(domain)
    if not safe_home:
        return HarveyCompanyDossier(reachable=False)

    parsed = urlparse(safe_home)
    clean_domain = (parsed.hostname or "").lower().removeprefix("www.")
    pages: list[tuple[str, str]] = []
    summaries: list[str] = []
    all_emails: list[str] = []
    all_tech: list[str] = []
    ats_roles: list[str] = []
    ats_label = ""
    reachable = False

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers=headers,
        ) as client:
            home_resp = await client.get(safe_home)
            if home_resp.status_code < 400 and "html" in home_resp.headers.get("content-type", "").lower():
                home_html = home_resp.text
                if is_parked_page(home_html):
                    # Reject parked/for-sale domain immediately
                    return HarveyCompanyDossier(reachable=False)
                reachable = True
                home_url = str(home_resp.url)
                pages.append((home_url, home_html))
                text = extract_readable_text(home_html)
                if text:
                    summaries.append(text[:900])

                # Discover internal team/about/contact pages via Harvey menu_links + common fallback paths
                follow_urls = menu_links(home_html, home_url, limit=3)
                base_origin = f"{parsed.scheme}://{parsed.netloc}"
                for extra in (f"{base_origin}/contact", f"{base_origin}/pages/contact"):
                    if extra not in follow_urls and len(follow_urls) < 4:
                        follow_urls.append(extra)

                for sub_url in follow_urls[:4]:
                    try:
                        r = await client.get(sub_url)
                        if r.status_code < 400 and "html" in r.headers.get("content-type", "").lower():
                            pages.append((str(r.url), r.text))
                    except (httpx.HTTPError, ValueError):
                        continue

                # Check ATS board linked on homepage or followed pages
                for _, page_html in pages:
                    board = detect_board(page_html, domain=clean_domain)
                    if board is not None:
                        ats_label = board.label
                        postings = await read_board(client, board)
                        ats_roles = [p.summary() for p in postings[:5]]
                        break
    except (httpx.HTTPError, ValueError):
        return HarveyCompanyDossier(reachable=False)

    # Extract emails, tech signals, and owners across all crawled pages
    for _, page_html in pages:
        on_domain = _filter_on_domain_emails(emails_on_page(page_html), clean_domain)
        for em in on_domain:
            if em not in all_emails:
                all_emails.append(em)
        for tech in _detect_combined_tech_signals(page_html):
            if tech not in all_tech:
                all_tech.append(tech)

    site_title = clean_domain.split(".")[0].title()
    decision_makers = (
        find_people(pages, domain=clean_domain, site_name=site_title)
        if pages
        else []
    )

    # Choose top person name (prefer existing LinkedIn/Search name if real, else Harvey extracted owner)
    chosen_first, chosen_last = "", ""
    if candidate_name:
        split = split_person_name(candidate_name)
        if split:
            chosen_first, chosen_last = split
    if not chosen_first and decision_makers:
        chosen_first = decision_makers[0].get("first_name", "")
        chosen_last = decision_makers[0].get("last_name", "")

    people_tuples = [
        (p["first_name"], p["last_name"])
        for p in decision_makers
        if p.get("first_name") and p.get("last_name")
    ]
    if chosen_first and chosen_last and (chosen_first, chosen_last) not in people_tuples:
        people_tuples.insert(0, (chosen_first, chosen_last))

    # Tier B Part 1: DNS MX lookup + site email pattern derivation ($0, zero accounts)
    mx_host = await get_mx_host(clean_domain)
    mx_provider = classify_mx(mx_host or "")

    known_personal, detected_pattern, _ = site_email_evidence(
        all_emails, people_tuples, clean_domain
    )

    resolved_email = ""
    email_status = "unknown"

    if mx_provider == "none":
        email_status = "invalid"

    # 1. Exact personal email verified from website HTML
    if chosen_first and chosen_last and known_personal:
        for fn, ln, addr in known_personal:
            if fn.lower() == chosen_first.lower() and ln.lower() == chosen_last.lower():
                resolved_email = addr
                if mx_provider != "none":
                    email_status = "verified"
                break

    # 2. Construct personal email from inferred site pattern + MX check
    if not resolved_email and chosen_first and chosen_last and detected_pattern and mx_provider != "none":
        built = build_email(detected_pattern, chosen_first, chosen_last, clean_domain)
        if built:
            resolved_email = built
            email_status = "guess"

    # 3. Direct public email found on site (e.g., founder@ / hello@ / info@)
    if not resolved_email and all_emails:
        resolved_email = all_emails[0]
        if mx_provider != "none":
            email_status = "verified"

    # 4. Pattern guess with default format when named person exists on MX-valid domain
    if not resolved_email and chosen_first and chosen_last and mx_provider != "none":
        resolved_email = build_email("{f}.{l}", chosen_first, chosen_last, clean_domain)
        if resolved_email:
            email_status = "guess"

    return HarveyCompanyDossier(
        reachable=reachable,
        summary=" | ".join(summaries)[:1400],
        emails=all_emails[:5],
        resolved_email=resolved_email,
        email_status=email_status,
        mx_provider=mx_provider,
        email_pattern=detected_pattern,
        tech_signals=all_tech[:8],
        decision_makers=decision_makers[:5],
        ats_open_roles=ats_roles,
        ats_board_label=ats_label,
    )


async def search_linkedin_via_harvey_browser(
    keywords: str,
    title: str = "",
    max_results: int = 10,
) -> list[dict]:
    """
    Runs Harvey's Playwright LinkedInAutomation if LINKEDIN_EMAIL/LINKEDIN_PASSWORD
    and playwright are configured. Returns [] gracefully when unavailable.
    """
    if not settings.linkedin_email or not settings.linkedin_password:
        return []
    try:
        from harvey.integrations.linkedin import LinkedInAutomation
    except ImportError:
        return []

    bot = LinkedInAutomation(settings.linkedin_email, settings.linkedin_password)
    try:
        return await bot.search_people(
            keywords=keywords,
            title=title,
            max_results=max_results,
        )
    except Exception:
        return []
    finally:
        try:
            await bot.close()
        except Exception:
            pass
