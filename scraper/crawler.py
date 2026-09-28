"""
crawler.py - Discovers and fetches leadership & team pages for any company URL.
Supports concurrent fetching, brand name extraction, and intelligent path scoring.
"""

import concurrent.futures
import logging
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Expanded corporate paths tested across root and subpath prefixes
COMMON_FALLBACK_PATHS = [
    "/about/leadership",
    "/about-us/leadership",
    "/company/leadership",
    "/leadership",
    "/leadership-team",
    "/executive-leadership",
    "/executive-team",
    "/executives",
    "/our-leadership",
    "/our-team",
    "/team",
    "/people",
    "/management",
    "/about/our-team",
    "/about-us/our-team",
    "/about/team",
    "/about-us/team",
    "/company/team",
    "/company/our-team",
    "/company/executives",
    "/about/executives",
    "/about-us/executives",
    "/about/management",
    "/about-us/management",
    "/board-of-directors",
    "/board",
    "/about/board-of-directors",
    "/about-us/board-of-directors",
    "/corporate-governance",
    "/corporate-governance/board-of-directors",
    "/investor-relations/corporate-governance",
    "/governance/board-of-directors",
    "/about-us",
    "/about",
    "/who-we-are",
    "/company",
]

# Keywords used to identify leadership links
LEADERSHIP_KEYWORDS = [
    "leadership", "executive", "board", "director", "governance",
    "team", "people", "management", "our-team", "about", "company", "who-we-are"
]



def normalize_url(url: str) -> str:
    """Ensure URL has scheme and is stripped."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def get_base_domain(url: str) -> str:
    """Extract root domain e.g. icanbwell.com or stripe.com."""
    parsed = urlparse(normalize_url(url))
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_brand_name(html: str, domain: str) -> str:
    """Extract the real commercial company name from HTML metadata."""
    if not html:
        return domain.split(".")[0].capitalize()

    soup = BeautifulSoup(html, "html.parser")

    # 1. OpenGraph site name
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        cand = og_site["content"].strip()
        if cand and len(cand) < 40:
            return cand

    # 2. Application name meta tag
    app_meta = soup.find("meta", attrs={"name": "application-name"})
    if app_meta and app_meta.get("content"):
        cand = app_meta["content"].strip()
        if cand and len(cand) < 40:
            return cand

    # 3. Clean Title tag
    title_tag = soup.find("title")
    if title_tag and title_tag.text:
        text = title_tag.text.strip()
        parts = re.split(r"[:\|\-–•]", text)
        if parts:
            first_part = parts[0].strip()
            if 2 <= len(first_part) <= 30 and not any(w in first_part.lower() for w in ["welcome", "home", "the modern", "page"]):
                return first_part

    # Fallback to domain root
    base = domain.split(".")[0]
    return base.capitalize()


def fetch_html(url: str, timeout: int = 8) -> str:
    """Fetch HTML content with headers and error handling."""
    normalized = normalize_url(url)
    try:
        resp = requests.get(normalized, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        logger.debug(f"Fetch failed for {normalized} with status {resp.status_code}")
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(normalized, headers=HEADERS, timeout=timeout, verify=False)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
    except Exception:
        pass
    return ""


def score_link(path: str, text: str) -> int:
    """Score a link based on leadership relevance."""
    combined = f"{path.lower()} {text.lower()}"
    score = 0
    if any(k in combined for k in ["leadership", "executive", "board", "director", "governance"]):
        score += 20
    elif any(k in combined for k in ["team", "people", "management", "our-team", "officers"]):
        score += 15
    elif any(k in combined for k in ["about", "company", "who-we-are"]):
        score += 5

    # Penalize non-team pages
    negative_words = [
        "blog", "article", "press-release", "news", "careers", "jobs",
        "privacy", "terms", "legal", "security", "cookie", "login", "signin",
        "signup", "register", "support", "help", "pricing", "whitepaper",
        "guide", "guides", "doc", "docs", "documentation", "resource", "resources",
        "case-study", "case-studies", "product", "products", "solution", "solutions",
        "api", "developer", "developers", "compliance", "risk-management",
        "asset-management", "wealth-management", "content-management", "device-management"
    ]
    if any(n in combined for n in negative_words):
        score -= 30
    return score


def extract_candidate_links_from_html(
    html: str,
    base_page_url: str,
    base_domain: str
) -> dict[str, int]:
    """Extract and score internal links from an HTML document."""
    discovered = {}
    if not html:
        return discovered

    soup = BeautifulSoup(html, "html.parser")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = urljoin(base_page_url, href)
        parsed_link = urlparse(full_url)

        # Must be same domain or subdomain
        if base_domain not in parsed_link.netloc.lower():
            continue

        path = parsed_link.path.rstrip("/")
        if not path:
            continue

        link_text = a_tag.get_text().strip()
        score = score_link(path, link_text)
        if score > 0:
            clean_url = f"{parsed_link.scheme}://{parsed_link.netloc}{path}"
            # Preserve valuable query filters like ?group=board-of-directors
            if parsed_link.query and any(k in parsed_link.query.lower() for k in ["board", "leadership", "team", "executive", "director"]):
                clean_url = f"{clean_url}?{parsed_link.query}"
            discovered[clean_url] = max(discovered.get(clean_url, 0), score)

    return discovered


def discover_leadership_pages(company_url: str) -> tuple[list[str], str]:
    """
    Given any company URL, crawl the homepage and discover prioritized candidate leadership pages.
    Performs 2-hop navigation on hub pages (About/Company) and preserves subpath prefixes.
    Returns:
        tuple: (list of prioritized URLs, homepage_html)
    """
    normalized_home = normalize_url(company_url)
    parsed_home = urlparse(normalized_home)
    base_domain = get_base_domain(company_url)

    discovered_links = {}

    # 1. Fetch homepage
    home_html = fetch_html(normalized_home, timeout=10)
    if home_html:
        home_links = extract_candidate_links_from_html(home_html, normalized_home, base_domain)
        discovered_links.update(home_links)

    # 2. 2-Hop Discovery on Hub Pages:
    # If direct high-priority leadership pages (score >= 15) are limited,
    # inspect candidate hub pages (e.g. /about, /about-us, /company) for nested leadership links
    high_priority_count = sum(1 for s in discovered_links.values() if s >= 15)
    hub_candidates = [
        url for url, s in discovered_links.items()
        if 5 <= s < 15 and url != normalized_home
    ][:3]

    if hub_candidates and high_priority_count < 3:
        hub_pages_html = fetch_pages_concurrently(hub_candidates, max_workers=3)
        for hub_url, h_html in hub_pages_html.items():
            nested_links = extract_candidate_links_from_html(h_html, hub_url, base_domain)
            for n_url, n_score in nested_links.items():
                if n_score >= 10:  # Only add team/leadership pages from 2nd hop
                    discovered_links[n_url] = max(discovered_links.get(n_url, 0), n_score)

    # Sort real discovered links by score descending (these exist on the site, so highest priority!)
    sorted_discovered = [
        url for url, s in sorted(discovered_links.items(), key=lambda item: item[1], reverse=True)
        if s > 0
    ]

    # 3. Add hypothetical fallback paths to test if needed
    base_path = parsed_home.path.rstrip("/")
    fallback_links = []
    prefixes = [""]
    if base_path and base_path != "/":
        prefixes.insert(0, base_path)

    for prefix in prefixes:
        for path in COMMON_FALLBACK_PATHS:
            combined_path = f"{prefix}{path}"
            fallback_url = f"{parsed_home.scheme}://{parsed_home.netloc}{combined_path}"
            if fallback_url not in discovered_links and fallback_url not in fallback_links:
                fallback_links.append(fallback_url)

    # Prioritize: real discovered links first, then top fallback guesses, then homepage
    final_candidates = []
    for u in sorted_discovered:
        if u not in final_candidates:
            final_candidates.append(u)

    for u in fallback_links:
        if len(final_candidates) >= 15:
            break
        if u not in final_candidates:
            final_candidates.append(u)

    if normalized_home not in final_candidates:
        final_candidates.append(normalized_home)

    logger.info(f"Discovered {len(final_candidates)} candidate pages for {company_url}")
    return final_candidates, home_html


def fetch_pages_concurrently(urls: list[str], max_workers: int = 8) -> dict[str, str]:
    """Fetch multiple candidate pages in parallel to keep scraper ultra-fast."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch_html, url, 7): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                html = future.result()
                if html:
                    results[url] = html
            except Exception:
                pass
    return results

