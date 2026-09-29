"""
contact_finder.py - Discovers company contact emails, phone numbers, and extracts verified executive email addresses.
Strictly extracts real, published emails from website DOM, schema, APIs, and pages.
Never synthesizes or guesses fake email addresses.
"""

import re
import urllib.parse
from typing import Optional
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}")
PHONE_PREFIX_PATTERNS = [
    re.compile(r"(?:phone|direct|mobile|cell|tel|call|contact|whatsapp|reach me at|ph)[:\s]+(\+?[\d\s\-\.\(\)]{9,22})", re.IGNORECASE),
]


def clean_phone(phone_str: str) -> Optional[str]:
    """Clean and validate a raw phone number string."""
    if not phone_str:
        return None
    raw = phone_str.strip().rstrip(".,;!?:")
    digits = re.sub(r"\D", "", raw)
    if 10 <= len(digits) <= 15:
        # Reject generic toll-free prefixes (800, 888, 877, 866, 855)
        if any(digits.startswith(pfx) for pfx in ["800", "888", "877", "866", "855", "1800", "1888", "1877", "1866"]):
            return None
        # Reject dummy repeated numbers (e.g. 0000000000, 1111111111)
        if len(set(digits)) <= 2:
            return None
        return raw
    return None

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".ico", ".css", ".js", ".map", ".woff", ".woff2", ".ttf"
}

DUMMY_DOMAINS = {
    "example.com", "domain.com", "yourdomain.com", "company.com", "test.com", "email.com", "site.com"
}

DUMMY_USERS = {
    "username", "user", "name", "yourname", "email", "placeholder", "xxx", "test", "demo"
}


def clean_email(email_str: str) -> Optional[str]:
    """
    Clean and validate a raw email string (e.g. from mailto: links or text).
    Strips URL encoding, query parameters (?subject=...), and invalid asset extensions.
    """
    if not email_str:
        return None

    # Strip mailto: prefix if present
    email_clean = re.sub(r"^mailto:", "", email_str.strip(), flags=re.IGNORECASE)
    # Strip URL query parameters
    email_clean = email_clean.split("?")[0].strip()
    email_clean = urllib.parse.unquote(email_clean).strip().lower()

    # Search for valid email pattern
    match = EMAIL_REGEX.search(email_clean)
    if not match:
        return None

    candidate = match.group(0).lower()

    # Check for asset file extensions
    if any(candidate.endswith(ext) for ext in ASSET_EXTENSIONS):
        return None

    # Check length
    if len(candidate) > 60 or len(candidate) < 5:
        return None

    # Check for placeholder/dummy emails
    parts = candidate.split("@")
    if len(parts) != 2:
        return None

    user_part, domain_part = parts
    if domain_part in DUMMY_DOMAINS or user_part in DUMMY_USERS:
        return None

    return candidate


def discover_company_contacts(html_content: str, domain: str) -> dict:
    """
    Extract public emails and phone numbers from company page HTML.
    Extracts both <a href="mailto:..."> and text-based emails.
    """
    if not html_content:
        return {"domain_emails": [], "general_emails": [], "phones": [], "all_emails": []}

    soup = BeautifulSoup(html_content, "html.parser")

    discovered_emails = set()

    # 1. Extract from mailto: anchors
    for a in soup.find_all("a", href=lambda h: h and "mailto:" in h.lower()):
        href = a["href"]
        cleaned = clean_email(href)
        if cleaned:
            discovered_emails.add(cleaned)

    # 2. Extract from full text
    text = soup.get_text(separator=" ")
    for raw_email in EMAIL_REGEX.findall(text):
        cleaned = clean_email(raw_email)
        if cleaned:
            discovered_emails.add(cleaned)

    # Prioritize domain emails
    clean_domain = domain.lower()
    for prefix in ["corporate.", "portal.", "about.", "careers.", "team.", "investors.", "blog.", "news."]:
        if clean_domain.startswith(prefix):
            clean_domain = clean_domain[len(prefix):]
            break

    domain_emails = [e for e in discovered_emails if clean_domain in e.split("@")[-1]]
    general_emails = [e for e in discovered_emails if e not in domain_emails]

    # Extract phone numbers
    phones = set(PHONE_REGEX.findall(text))
    cleaned_phones = []
    for p in phones:
        if isinstance(p, tuple):
            p_str = "".join(p).strip()
        else:
            p_str = str(p).strip()
        if len(re.sub(r"\D", "", p_str)) >= 10:
            cleaned_phones.append(p_str)

    return {
        "domain_emails": domain_emails[:10],
        "general_emails": general_emails[:10],
        "all_emails": list(discovered_emails),
        "phones": cleaned_phones[:3],
    }


def match_email_to_person(name: str, domain: str, discovered_emails: list[str]) -> Optional[str]:
    """
    Check if any real email discovered on the company website matches an executive's name.
    Supported real corporate patterns:
      - first.last@
      - first_last@
      - firstlast@
      - first-last@
      - flast@ (first initial + last name)
      - first@
      - last.first@
    """
    if not name or not discovered_emails:
        return None

    # Clean name tokens
    tokens = [re.sub(r"[^a-z]", "", t.lower()) for t in re.split(r"[\s\.-]+", name.strip()) if t]
    tokens = [t for t in tokens if len(t) > 1]
    if not tokens:
        return None

    first = tokens[0]
    last = tokens[-1] if len(tokens) > 1 else ""
    first_initial = first[0] if first else ""

    candidate_patterns = set()
    if first and last:
        candidate_patterns.add(f"{first}.{last}")
        candidate_patterns.add(f"{first}_{last}")
        candidate_patterns.add(f"{first}{last}")
        candidate_patterns.add(f"{first}-{last}")
        candidate_patterns.add(f"{first_initial}{last}")
        candidate_patterns.add(f"{first_initial}.{last}")
        candidate_patterns.add(f"{first_initial}_{last}")
        candidate_patterns.add(f"{last}.{first}")
        candidate_patterns.add(f"{last}_{first}")
        candidate_patterns.add(f"{first}")
    elif first:
        candidate_patterns.add(first)

    clean_domain = domain.lower()
    for prefix in ["corporate.", "portal.", "about.", "careers.", "team.", "investors.", "blog.", "news."]:
        if clean_domain.startswith(prefix):
            clean_domain = clean_domain[len(prefix):]
            break

    # Prioritize domain-matching emails first
    for email in discovered_emails:
        user_part, email_domain = email.split("@")
        user_clean = user_part.lower()
        if user_clean in candidate_patterns:
            if clean_domain in email_domain:
                return email

    # Secondary check for any discovered email
    for email in discovered_emails:
        user_part, _ = email.split("@")
        user_clean = user_part.lower()
        if user_clean in candidate_patterns:
            return email

    return None


def generate_executive_email(name: str, domain: str) -> str:
    """
    DEPRECATED: Preserved for backwards compatibility only.
    Always returns 'Not Found' to prevent fabricating fake email addresses.
    """
    return "Not Found"


def enrich_executives_with_contacts(executives: list[dict], domain: str, company_contacts: dict) -> list[dict]:
    """
    Enrich executive records with verified, real contact information extracted from the website.
    If no verified email is published on the site for that person, assigns 'Not Found'.
    Never fabricates or guesses personal email addresses.
    """
    discovered_emails = company_contacts.get("all_emails", [])
    primary_email = ""
    if company_contacts.get("domain_emails"):
        primary_email = company_contacts["domain_emails"][0]
    elif company_contacts.get("general_emails"):
        primary_email = company_contacts["general_emails"][0]

    for exc in executives:
        # 1. Check if executive already has a direct email from their DOM card, JSON-LD, or SPA API
        direct = clean_email(exc.get("direct_email", ""))

        if direct:
            exc["email"] = direct
            exc["contact"] = direct
        else:
            # 2. Check if any real email discovered on the company website matches this person
            matched = match_email_to_person(exc.get("name", ""), domain, discovered_emails)
            if matched:
                exc["email"] = matched
                exc["contact"] = matched
            else:
                # 3. Not published on site -> Strictly 'Not Found'
                exc["email"] = "Not Found"
                exc["contact"] = "Not Found"

        # Deprecate inferred_email field
        exc["inferred_email"] = exc["email"]
        exc["company_email"] = primary_email

    return executives


def extract_contact_from_linkedin_html(html_content: str) -> dict:
    """
    Parse a public LinkedIn profile page or overlay for verified email and phone numbers.
    Checks meta tags, JSON-LD, anchor tags (mailto/tel), and section text.
    """
    if not html_content:
        return {"email": None, "phone": None}

    soup = BeautifulSoup(html_content, "html.parser")
    found_email = None
    found_phone = None

    # 1. Check mailto: and tel: links
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:") and not found_email:
            cleaned = clean_email(href)
            if cleaned and "linkedin.com" not in cleaned:
                found_email = cleaned
        elif href.lower().startswith("tel:") and not found_phone:
            raw = href.replace("tel:", "").strip()
            cleaned = clean_phone(raw)
            if cleaned:
                found_phone = cleaned

    # 2. Check meta tags (description, og:description, twitter:description)
    if not found_email or not found_phone:
        for m in soup.find_all("meta"):
            content = m.get("content", "")
            if not content:
                continue
            if not found_email:
                for em in EMAIL_REGEX.findall(content):
                    cleaned = clean_email(em)
                    if cleaned and "linkedin.com" not in cleaned:
                        found_email = cleaned
                        break
            if not found_phone:
                for pat in PHONE_PREFIX_PATTERNS:
                    match = pat.search(content)
                    if match:
                        cand = clean_phone(match.group(1 if match.lastindex else 0))
                        if cand:
                            found_phone = cand
                            break

    # 3. Check JSON-LD schema
    if not found_email or not found_phone:
        import json
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                raw_json = s.string or s.get_text() or ""
                data = json.loads(raw_json)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if not found_email and item.get("email"):
                        cleaned = clean_email(str(item.get("email")))
                        if cleaned and "linkedin.com" not in cleaned:
                            found_email = cleaned
                    if not found_phone and item.get("telephone"):
                        cleaned = clean_phone(str(item.get("telephone")))
                        if cleaned:
                            found_phone = cleaned
            except Exception:
                pass

    # 4. Check page text
    if not found_email or not found_phone:
        text = soup.get_text(separator=" ")
        if not found_email:
            for em in EMAIL_REGEX.findall(text):
                cleaned = clean_email(em)
                if cleaned and "linkedin.com" not in cleaned:
                    found_email = cleaned
                    break
        if not found_phone:
            for pat in PHONE_PREFIX_PATTERNS:
                match = pat.search(text)
                if match:
                    cand = clean_phone(match.group(1 if match.lastindex else 0))
                    if cand:
                        found_phone = cand
                        break

    return {"email": found_email, "phone": found_phone}


def fetch_linkedin_contact_info(linkedin_url: str, enricher=None) -> dict:
    """
    Query an executive's LinkedIn profile for public contact info (email and phone).
    Attempts direct fetch with realistic browser headers. If rate-limited or unavailable,
    uses cached search engine query if enricher is provided.
    """
    if not linkedin_url or "linkedin.com/in/" not in linkedin_url:
        return {"email": None, "phone": None}

    clean_url = linkedin_url.split("?")[0].rstrip("/")
    slug = clean_url.split("/in/")[-1].strip("/")

    # Check cache in enricher if available
    cache_key = f"linkedin_contact::{slug}"
    if enricher and hasattr(enricher, "cache") and cache_key in enricher.cache:
        return enricher.cache[cache_key]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    import requests

    contact_res = {"email": None, "phone": None}

    # 1. Direct fetch of profile
    try:
        resp = requests.get(clean_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            contact_res = extract_contact_from_linkedin_html(resp.text)
    except Exception:
        pass

    # 2. If email/phone still not found, try overlay contact-info
    if not contact_res.get("email") and not contact_res.get("phone"):
        try:
            overlay_url = f"{clean_url}/overlay/contact-info/"
            resp_overlay = requests.get(overlay_url, headers=headers, timeout=5)
            if resp_overlay.status_code == 200:
                contact_res = extract_contact_from_linkedin_html(resp_overlay.text)
        except Exception:
            pass

    # 3. If still not found and enricher has valid api_key, check search snippets
    if not contact_res.get("email") and not contact_res.get("phone") and enricher and getattr(enricher, "api_key", None):
        try:
            params = {
                "engine": "google",
                "q": f'site:linkedin.com/in/{slug} ("email" OR "phone" OR "contact" OR "@")',
                "api_key": enricher.api_key,
                "num": 3,
            }
            data = enricher._serpapi_request(params)
            if data and "organic_results" in data:
                matching_snippets = []
                for r in data["organic_results"]:
                    r_link = r.get("link", "").lower()
                    if f"/in/{slug}" in r_link:
                        matching_snippets.append(r.get("snippet", "") + " " + r.get("title", ""))
                if matching_snippets:
                    contact_res = extract_contact_from_linkedin_html(f"<html><body>{' '.join(matching_snippets)}</body></html>")
        except Exception:
            pass

    # Save to enricher cache if enricher is present
    if enricher and hasattr(enricher, "cache"):
        enricher.cache[cache_key] = contact_res
        enricher._save_cache()

    return contact_res


def enrich_executives_from_linkedin(executives: list[dict], enricher=None) -> list[dict]:
    """
    For any executive whose contact is 'Not Found', inspect their LinkedIn profile to extract
    any publicly available email or contact phone number.
    """
    for exc in executives:
        curr_contact = exc.get("contact", "")
        # Only check if contact is not found on website
        if curr_contact and curr_contact != "Not Found":
            continue

        lk_url = exc.get("linkedin_url") or exc.get("linkedin_profile") or ""
        if not lk_url or "linkedin.com/in/" not in lk_url:
            continue

        contact_info = fetch_linkedin_contact_info(lk_url, enricher=enricher)
        found_email = contact_info.get("email")
        found_phone = contact_info.get("phone")

        if found_email and found_phone:
            exc["email"] = found_email
            exc["phone"] = found_phone
            exc["contact"] = f"📧 {found_email} | 📞 {found_phone}"
            exc["contact_source"] = "LinkedIn Profile"
        elif found_email:
            exc["email"] = found_email
            exc["contact"] = found_email
            exc["contact_source"] = "LinkedIn Profile"
        elif found_phone:
            exc["phone"] = found_phone
            exc["contact"] = f"📞 {found_phone}"
            exc["contact_source"] = "LinkedIn Profile"

    return executives

