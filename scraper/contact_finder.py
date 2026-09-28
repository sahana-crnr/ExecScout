"""
contact_finder.py - Discovers company contact emails, phone numbers, and infers executive email addresses.
"""

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}")


def discover_company_contacts(html_content: str, domain: str) -> dict:
    """
    Extract public emails and phone numbers from company page HTML.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text()

    # Extract all emails
    found_emails = set(EMAIL_REGEX.findall(text))
    # Filter out image/asset artifacts and irrelevant extensions
    valid_emails = [
        e.lower() for e in found_emails
        if not any(e.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"])
        and len(e) < 50
    ]

    # Prioritize domain emails
    domain_emails = [e for e in valid_emails if domain.lower() in e.split("@")[-1]]

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
        "domain_emails": domain_emails[:5],
        "general_emails": valid_emails[:5],
        "phones": cleaned_phones[:3],
    }


def generate_executive_email(name: str, domain: str) -> str:
    """
    Generate the standard corporate email pattern: first.last@domain.com
    Strips internal/subdomain prefixes (e.g. corporate.flipkart.net -> flipkart.net)
    """
    clean_domain = domain.lower()
    for prefix in ["corporate.", "portal.", "about.", "careers.", "team.", "investors.", "blog.", "news."]:
        if clean_domain.startswith(prefix):
            clean_domain = clean_domain[len(prefix):]
            break

    parts = re.split(r"[\s\.-]+", name.strip().lower())
    if len(parts) >= 2:
        first = re.sub(r"[^a-z]", "", parts[0])
        last = re.sub(r"[^a-z]", "", parts[-1])
        if first and last:
            return f"{first}.{last}@{clean_domain}"
    elif len(parts) == 1:
        first = re.sub(r"[^a-z]", "", parts[0])
        if first:
            return f"{first}@{clean_domain}"
    return f"contact@{clean_domain}"


def enrich_executives_with_contacts(executives: list[dict], domain: str, company_contacts: dict) -> list[dict]:
    """
    Add contact information (direct or corporate pattern) to each executive record.
    """
    primary_email = ""
    if company_contacts.get("domain_emails"):
        primary_email = company_contacts["domain_emails"][0]
    elif company_contacts.get("general_emails"):
        primary_email = company_contacts["general_emails"][0]

    phone = company_contacts.get("phones", [""])[0] if company_contacts.get("phones") else ""

    for exc in executives:
        inferred_email = generate_executive_email(exc["name"], domain)
        # Assign contact string
        contact_str = f"📧 {inferred_email}"
        if phone:
            contact_str += f" | 📞 {phone}"
        exc["contact"] = contact_str
        exc["inferred_email"] = inferred_email
        exc["company_email"] = primary_email

    return executives
