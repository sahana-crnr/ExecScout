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
