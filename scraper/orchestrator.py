"""
orchestrator.py - Coordinates crawling, extraction, SerpApi enrichment, and contact discovery.
Optimized for ultra-fast parallel crawling and universal company URL support.
"""

import logging
from typing import Callable, Optional
from urllib.parse import urlparse

from .crawler import (
    discover_leadership_pages,
    extract_brand_name,
    fetch_pages_concurrently,
    get_base_domain,
    normalize_url,
)
from .extractor import extract_executives_from_html
from .serp_enricher import SerpEnricher
from .contact_finder import discover_company_contacts, enrich_executives_with_contacts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_executive_pipeline(
    company_url: str,
    serpapi_key: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> tuple[list[dict], dict]:
    """
    Universal pipeline to discover company executives, LinkedIn profiles, and contact details.

    Args:
        company_url: e.g. "https://stripe.com" or "https://www.icanbwell.com/"
        serpapi_key: Optional SerpApi key (conserves 250 quota)
        progress_callback: Optional callback func(status_message, progress_fraction)

    Returns:
        tuple: (list of executive dicts, stats dict)
    """
    def report(msg: str, frac: float):
        if progress_callback:
            progress_callback(msg, frac)
        logger.info(f"[{int(frac * 100)}%] {msg}")

    normalized_url = normalize_url(company_url)
    domain = get_base_domain(normalized_url)

    enricher = SerpEnricher(api_key=serpapi_key)

    report(f"Scanning {domain} for leadership & team pages...", 0.15)
    candidate_urls, homepage_html = discover_leadership_pages(normalized_url)

    # Extract real commercial brand name (e.g. "b.well Connected Health" instead of "Icanbwell")
    company_name = extract_brand_name(homepage_html, domain)
    logger.info(f"Identified Brand Name: '{company_name}' for domain: '{domain}'")

    # Parallel fetch of candidate pages (under 3-4s total)
    report(f"Fetching {len(candidate_urls)} candidate pages in parallel...", 0.35)
    pages_html = fetch_pages_concurrently(candidate_urls)
    if homepage_html and normalized_url not in pages_html:
        pages_html[normalized_url] = homepage_html

    all_executives = []
    seen_names = set()

    report("Extracting executives, roles & LinkedIn profiles...", 0.50)
    for page_url, html in pages_html.items():
        execs = extract_executives_from_html(html, page_url, company_name=company_name)
        for e in execs:
            norm_name = e["name"].lower()
            if norm_name not in seen_names:
                seen_names.add(norm_name)
                e["company"] = company_name
                e["domain"] = domain
                all_executives.append(e)

    # If dedicated leadership/team pages yielded executives, filter out loose unlinked cards from the generic homepage
    has_dedicated_source = any(e.get("source_page") != normalized_url for e in all_executives)
    if has_dedicated_source:
        all_executives = [e for e in all_executives if e.get("source_page") != normalized_url or e.get("direct_source")]

    # If no executives found on static pages (e.g. Twelve / ClearJet JS sites), use 1 SerpApi batch query fallback
    if not all_executives and serpapi_key:
        report("No static leadership page found. Querying key executives via SerpApi...", 0.65)
        batch_execs = enricher.search_company_executives(company_name, domain)
        for e in batch_execs:
            norm_name = e["name"].lower()
            if norm_name not in seen_names:
                seen_names.add(norm_name)
                e["company"] = company_name
                e["domain"] = domain
                all_executives.append(e)

    # Ensure LinkedIn profile is strictly a verified direct profile link or empty (never a search query link)
    for e in all_executives:
        curr_link = e.get("linkedin_url", "")
        if "search/results" in curr_link or "/search?" in curr_link:
            e["linkedin_url"] = ""
            e["direct_source"] = False

    direct_linkedin_count = sum(1 for e in all_executives if e.get("linkedin_url") and e.get("direct_source"))
    report(f"Discovered {len(all_executives)} executives ({direct_linkedin_count} verified LinkedIn profiles)...", 0.75)

    # Contact discovery
    report("Extracting corporate contact info & email patterns...", 0.90)
    company_contacts = {}
    if homepage_html:
        company_contacts = discover_company_contacts(homepage_html, domain)

    all_executives = enrich_executives_with_contacts(all_executives, domain, company_contacts)

    stats = enricher.get_stats()
    stats["total_executives"] = len(all_executives)
    stats["direct_linkedin_count"] = sum(1 for e in all_executives if e.get("linkedin_url") and e.get("direct_source"))
    stats["serpapi_enriched_count"] = sum(1 for e in all_executives if e.get("linkedin_url") and not e.get("direct_source"))
    stats["candidate_pages_scanned"] = len(candidate_urls)
    stats["domain"] = domain
    stats["company_name"] = company_name

    report("Complete! Executive intelligence extracted.", 1.0)
    return all_executives, stats
