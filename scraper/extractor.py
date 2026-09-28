"""
extractor.py - Parses executives, designations, and LinkedIn profile links from HTML & JSON-LD.
Universal extractor designed to work across any company website architecture.
"""

import json
import re
import urllib.parse
from typing import Optional
from bs4 import BeautifulSoup, Tag

# Target roles to identify and extract
TARGET_ROLES_REGEX = re.compile(
    r"\b("
    r"CEO|Chief Executive Officer|"
    r"CTO|Chief Technology Officer|"
    r"President|Co-President|"
    r"Vice President|VP|SVP|EVP|Senior Vice President|Executive Vice President|"
    r"Chief Operating Officer|COO|"
    r"Chief Financial Officer|CFO|"
    r"Chief Information Officer|CIO|"
    r"Chief Revenue Officer|CRO|"
    r"Chief Medical Officer|CMO|"
    r"Chief Strategy Officer|CSO|"
    r"Chief Innovation Officer|"
    r"Chief Product Officer|CPO|"
    r"Chief Outcomes Officer|"
    r"Chief Marketing Officer|"
    r"Chief People Officer|"
    r"Chief Human Resources Officer|CHRO|"
    r"Chief Legal Officer|General Counsel|"
    r"Chief Privacy|Chief of Staff|Corporate Secretary|"
    r"Executive Chairman|Chairman|Chairwoman|Chair|"
    r"Lead Independent Director|Independent Director|"
    r"Board Member|Board of Directors|Director|Trustee|"
    r"Managing Director|General Partner|Partner|"
    r"Founder|Co-Founder|Head of"
    r")\b",
    re.IGNORECASE,
)

ROLE_TERMS = {
    "ceo", "cto", "cfo", "coo", "cio", "cro", "cmo", "cso", "cpo", "chro",
    "officer", "president", "vice president", "vp", "svp", "evp",
    "founder", "co-founder", "director", "chairman", "chairwoman", "chair",
    "board", "trustee", "partner", "general counsel", "corporate secretary",
    "managing director", "head of", "chief", "staff"
}

STOP_WORDS = {
    "our team", "leadership team", "board of directors", "executive team",
    "meet the team", "about us", "who we are", "read more", "view profile",
    "contact us", "get in touch", "learn more", "careers", "advisors",
    "investors", "mission", "privacy policy", "terms of use", "our leadership",
    "company", "team", "news", "press", "events", "all rights reserved",
    "linkedin", "view bio", "read bio", "profile", "more", "menu", "close"
}

NON_PERSON_WORDS = {
    "series", "round", "news", "latest", "airpower", "competencies", "overview",
    "press", "events", "solutions", "products", "services", "platform", "insights",
    "resources", "privacy", "terms", "cookie", "copyright", "rights", "reserved",
    "ventures", "capital", "technologies", "holdings", "group", "corporation",
    "partners", "inc", "llc", "corp", "ltd", "core", "mission", "vision",
    "about", "team", "leadership", "board", "directors", "executives", "software",
    "committee", "charter", "investor", "relations", "statement", "disclosure",
    "filings", "governance", "headquarters", "presentation", "report", "scale",
    "strength", "impact", "power", "growth", "vision", "future", "wells", "fargo",
    "goldman", "sachs", "morgan", "stanley", "jpmorgan", "chase", "citi", "bank"
}

INVALID_FIRST_WORDS = {
    "the", "our", "their", "this", "that", "every", "all", "what",
    "how", "why", "when", "where", "who", "about", "meet", "join",
    "view", "read", "learn", "get", "contact", "we", "you", "program", "project",
    "partner", "expected", "announced", "named", "appointed", "promoted",
    "elected", "former", "interim", "annual", "virtual", "global", "special",
    "event", "session", "keynote", "webinar", "panel", "presentation", "conference"
}

STOP_TRAILING = {
    "elected", "appointed", "named", "joins", "joined", "leaves", "left", "promoted",
    "retires", "retired", "to", "as", "at", "by", "in", "for", "from", "with", "on",
    "hosted", "speaks", "speaking", "participates", "participate", "presents",
    "addresses", "steps", "step", "down", "succeeds", "succeed", "become", "becomes",
    "announced", "expected", "welcomes", "shares", "discusses", "chairman", "ceo",
    "president", "coo", "director", "officer", "leader", "next", "visit", "call", "board"
}

NON_EXECUTIVE_DISQUALIFIERS = [
    "designer", "inspector", "broker", "realtor", "technician", "student",
    "candidate", "intern", "specialist", "recruiter", "sales representative",
    "sales rep", "coordinator", "assistant", "clerk", "operator", "mechanic",
    "electrician", "nurse", "teacher", "fellow", "postdoc", "programmatic",
    "contractor", "freelancer", "machinist", "consultant"
]


def clean_text(text: str) -> str:
    """Clean whitespace and formatting."""
    return re.sub(r"\s+", " ", text).strip()


def clean_person_name(name: str, company_name: str = "") -> str:
    """Sanitize and strip noise, trailing transition verbs, and company tokens from person names."""
    cleaned = re.sub(r"[^\w\s\.,-]", " ", name).strip().rstrip(":,;.-–|")
    tokens = [w for w in re.split(r"[\s\.,:;]+", cleaned) if w]
    if company_name:
        co_tokens = [c.lower() for c in re.split(r"[\s\.,]+", company_name) if len(c) > 2]
        while tokens and tokens[0].lower() in co_tokens:
            tokens.pop(0)
        while tokens and tokens[-1].lower() in co_tokens:
            tokens.pop()
    while tokens and (tokens[-1].lower() in STOP_TRAILING or len(tokens[-1]) <= 1):
        tokens.pop()
    if len(tokens) < 2 or len(tokens) > 4:
        return ""
    if tokens[0].lower() in INVALID_FIRST_WORDS:
        return ""
    res = " ".join(tokens)
    return res.title() if res.isupper() else res


def is_role_string(text: str) -> bool:
    """Check if a string represents a bona fide executive leadership role."""
    t = text.lower().strip()
    cta_patterns = [
        "partner with", "partners with", "our partner", "become a partner",
        "trusted partner", "with us", "contact us", "work with", "join our"
    ]
    if any(p in t for p in cta_patterns):
        return False

    # Disqualify non-executive / junior roles
    if any(bad in t for bad in NON_EXECUTIVE_DISQUALIFIERS):
        if not any(k in t for k in ["chief", "vice president", "vp", "head of", "director of", "managing director"]):
            return False
        if any(bad in t for bad in ["programmatic", "inspector", "broker", "student", "candidate", "intern", "realtor", "sales rep"]):
            return False

    return any(r in t for r in ROLE_TERMS) or bool(TARGET_ROLES_REGEX.search(text))


def is_valid_name(name: str, company_name: str = "") -> bool:
    """Validate whether a candidate string looks like a legitimate executive person name."""
    name = clean_person_name(name, company_name)
    if not name or len(name) < 3 or len(name) > 35:
        return False
    if name.lower() in STOP_WORDS:
        return False
    if is_role_string(name):
        return False
    if company_name and company_name.lower() in name.lower():
        return False

    tokens = [re.sub(r"[^\w]", "", w.lower()) for w in re.split(r"[\s\.,:;]+", name) if w]
    tokens = [t for t in tokens if t]
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    if tokens[0] in INVALID_FIRST_WORDS or tokens[-1] in STOP_TRAILING:
        return False
    if len(tokens[-1]) < 2:
        return False
    if any(char.isdigit() for char in name):
        return False
    for t in tokens:
        if t in NON_PERSON_WORDS:
            return False
    words = [w for w in re.split(r"[\s\.,]+", name) if w]
    if not all(w[0].isupper() for w in words if w.isalpha()):
        return False
    return True



def parse_name_from_slug(lk_url: str) -> str:
    """Extract person name from LinkedIn URL slug (e.g. /in/kristen-valdes -> Kristen Valdes)."""
    slug = lk_url.split("/in/")[-1].split("?")[0].strip("/")
    parts = slug.split("-")
    ignore_tokens = {"mba", "phd", "cpa", "phr", "jd", "md", "bba", "ms", "bs"}
    clean_parts = [p.capitalize() for p in parts if p.isalpha() and p.lower() not in ignore_tokens]
    return " ".join(clean_parts[:3])


def generate_canonical_linkedin(name: str) -> str:
    """
    Generate a canonical direct LinkedIn profile URL from an executive's name.
    Format: https://www.linkedin.com/in/first-last
    Never outputs search queries or placeholder strings.
    """
    if not name:
        return ""
    clean_name = re.sub(
        r",?\s*\b(DBE|PhD|Ph\.D\.|MBA|CPA|MD|M\.D\.|Esq|JD|J\.D\.|III|II|IV|Jr\.?|Sr\.?|MS|BSc|BA)\b",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    raw_tokens = [re.sub(r"[^\w]", "", w.lower()) for w in re.split(r"[\s\.,\-]+", clean_name) if w]
    tokens = [t for t in raw_tokens if len(t) >= 1 and not t.isdigit()]
    if len(tokens) >= 2:
        slug = "-".join(tokens)
        return f"https://www.linkedin.com/in/{slug}"
    elif len(tokens) == 1:
        return f"https://www.linkedin.com/in/{tokens[0]}"
    return ""


def categorize_role(title: str) -> str:
    """Map a detailed title into an executive category."""
    title_lower = title.lower()
    if "ceo" in title_lower or "chief executive" in title_lower:
        return "CEO"
    elif "cto" in title_lower or "chief technology" in title_lower:
        return "CTO"
    elif "president" in title_lower and "vice" not in title_lower and "vp" not in title_lower:
        return "President"
    elif any(k in title_lower for k in ["vice president", "vp", "svp", "evp"]):
        return "Vice President"
    elif any(k in title_lower for k in ["board", "director", "chairman", "chairwoman", "chair", "trustee"]):
        return "Board Member"
    elif "founder" in title_lower:
        return "Founder"
    elif any(k in title_lower for k in ["cfo", "coo", "cio", "cmo", "cso", "cpo", "chro", "chief", "general counsel", "corporate secretary"]):
        return "C-Suite"
    return "Executive"


def extract_from_json_ld(soup: BeautifulSoup, page_url: str, company_name: str) -> list[dict]:
    """Extract executive members embedded in Schema.org JSON-LD data."""
    executives = []
    seen = set()

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string or script.get_text() or ""
            data = json.loads(content)
            items = data if isinstance(data, list) else [data]

            raw_people = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Direct Person schema
                if item.get("@type") == "Person":
                    raw_people.append(item)
                # Organization / Corporation schema
                elif item.get("@type") in ["Organization", "Corporation"]:
                    for field in ["member", "employee", "founder", "alumni", "founders"]:
                        val = item.get(field)
                        if isinstance(val, list):
                            raw_people.extend([v for v in val if isinstance(v, dict) and v.get("@type") == "Person"])
                        elif isinstance(val, dict) and val.get("@type") == "Person":
                            raw_people.append(val)

            for p in raw_people:
                name = clean_text(p.get("name", ""))
                title = clean_text(p.get("jobTitle", "")) or "Executive"
                if not is_valid_name(name, company_name):
                    continue

                # Find LinkedIn in sameAs
                same_as = p.get("sameAs", [])
                if isinstance(same_as, str):
                    same_as = [same_as]
                lk_url = next((url for url in same_as if "linkedin.com/in/" in url), "")

                norm_name = name.lower()
                if norm_name not in seen:
                    seen.add(norm_name)
                    executives.append({
                        "name": name,
                        "title": title,
                        "category": categorize_role(title),
                        "linkedin_url": lk_url,
                        "source_page": page_url,
                        "direct_source": bool(lk_url),
                    })
        except Exception:
            continue

    return executives


def extract_from_hydration_scripts(soup: BeautifulSoup, page_url: str, company_name: str) -> list[dict]:
    """Extract executive members embedded in client-side Next.js / Nuxt hydration scripts."""
    executives = []
    seen = set()

    def search_dict(d: dict):
        if not isinstance(d, dict):
            return
        name_cand = d.get("name") or d.get("fullName") or d.get("personName") or d.get("author")
        title_cand = d.get("title") or d.get("role") or d.get("position") or d.get("designation") or d.get("jobTitle")
        
        if isinstance(name_cand, str) and isinstance(title_cand, str):
            clean_n = clean_text(name_cand)
            clean_t = clean_text(title_cand)
            if is_valid_name(clean_n, company_name) and is_role_string(clean_t):
                norm = clean_n.lower()
                if norm not in seen:
                    seen.add(norm)
                    lk = d.get("linkedin") or d.get("linkedinUrl") or d.get("linkedin_url") or ""
                    if not isinstance(lk, str) or "linkedin.com/in/" not in lk:
                        encoded_q = urllib.parse.quote(f"{clean_n} {company_name}")
                        lk = f"https://www.linkedin.com/search/results/all/?keywords={encoded_q}"
                        direct = False
                    else:
                        direct = True
                    executives.append({
                        "name": clean_n,
                        "title": clean_t,
                        "category": categorize_role(clean_t),
                        "linkedin_url": lk,
                        "source_page": page_url,
                        "direct_source": direct,
                    })

        for v in d.values():
            if isinstance(v, dict):
                search_dict(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        search_dict(item)

    for script in soup.find_all("script", id=lambda i: i in ["__NEXT_DATA__", "__NUXT_DATA__"]):
        try:
            raw = script.string or script.get_text() or ""
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    search_dict(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            search_dict(item)
        except Exception:
            continue

    return executives


def extract_executives_from_html(
    html_content: str,
    page_url: str = "",
    company_name: str = ""
) -> list[dict]:
    """
    Extract executive names, designations, and LinkedIn profile links from HTML and JSON-LD.
    Returns list of dicts: {name, title, category, linkedin_url, source_page, direct_source}.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    executives = []
    seen_links = set()
    seen_names = set()

    # Strategy 0: Schema.org / JSON-LD extraction
    json_ld_execs = extract_from_json_ld(soup, page_url, company_name)
    for e in json_ld_execs:
        norm = e["name"].lower()
        if norm not in seen_names:
            seen_names.add(norm)
            executives.append(e)

    # Strategy 0.5: Next.js / Nuxt hydration extraction
    hydration_execs = extract_from_hydration_scripts(soup, page_url, company_name)
    for e in hydration_execs:
        norm = e["name"].lower()
        if norm not in seen_names:
            seen_names.add(norm)
            executives.append(e)

    # Clean out scripts, styles, forms, footers, headers for DOM parsing
    for tag in soup(["script", "style", "nav", "footer", "form", "noscript", "svg"]):
        tag.decompose()

    # Strategy 1: Direct LinkedIn Link-Driven Extraction (Highest precision, 0 API cost)
    linkedin_tags = soup.find_all("a", href=lambda h: h and "linkedin.com/in/" in h)
    for a in linkedin_tags:
        lk_url = a["href"].split("?")[0].rstrip("/")
        if lk_url in seen_links:
            continue
        seen_links.add(lk_url)

        # Walk up to find the highest ancestor containing strictly 1 linkedin link
        card = a
        curr = a.parent
        while curr and curr.name not in ["body", "html", "[document]"]:
            lk_count = len(curr.find_all("a", href=lambda h: h and "linkedin.com/in/" in h))
            if lk_count == 1:
                card = curr
                curr = curr.parent
            else:
                break

        lines = [re.sub(r"\s+", " ", s).strip() for s in card.stripped_strings if s.strip()]
        lines = [l for l in lines if l.lower() not in STOP_WORDS and len(l) <= 70]

        cand_name = None
        cand_title = None

        for l in lines:
            if is_role_string(l):
                if not cand_title:
                    cand_title = l
            else:
                words = l.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
                    if not cand_name and is_valid_name(l, company_name):
                        cand_name = l

        if not cand_name:
            cand_name = parse_name_from_slug(lk_url)

        if not cand_title:
            cand_title = "Executive"

        norm_name = cand_name.lower()
        if norm_name not in seen_names and is_valid_name(cand_name, company_name):
            seen_names.add(norm_name)
            executives.append({
                "name": cand_name,
                "title": cand_title,
                "category": categorize_role(cand_title),
                "linkedin_url": lk_url,
                "source_page": page_url,
                "direct_source": True,
            })

    # Strategy 2: Card / Container Search (for team pages without direct LinkedIn links)
    containers = soup.find_all(["div", "article", "section", "li"])
    for container in containers:
        # Skip wrapper elements that contain multiple heading tags
        headings = container.find_all(["h2", "h3", "h4", "h5"])
        if len(headings) > 2:
            continue

        text = container.get_text(separator=" ", strip=True)
        role_match = TARGET_ROLES_REGEX.search(text)
        if not role_match:
            continue

        name_tag = container.find(["h2", "h3", "h4", "h5", "strong", "b"])
        if not name_tag:
            continue

        cand_name = clean_text(name_tag.get_text())
        if not is_valid_name(cand_name, company_name):
            continue

        norm_name = cand_name.lower()
        if norm_name in seen_names:
            continue

        title = ""
        for elem in container.find_all(["p", "span", "div", "h4", "h5", "h6"]):
            # Skip the name tag itself or any element enclosing it
            if elem == name_tag or name_tag in elem.descendants:
                continue
            elem_text = clean_text(elem.get_text())
            if elem_text and is_role_string(elem_text) and elem_text != cand_name:
                # If title was accidentally prefixed with candidate name, strip it
                if elem_text.lower().startswith(cand_name.lower()):
                    elem_text = clean_text(elem_text[len(cand_name):].lstrip(" ,-–|:"))
                if is_role_string(elem_text):
                    title = elem_text
                    break

        if not title:
            # Check if name_tag itself has role appended (e.g. "Jane Doe, CEO")
            full_header = clean_text(name_tag.get_text())
            if "," in full_header or " - " in full_header:
                parts = re.split(r"[,–\-]\s*", full_header, maxsplit=1)
                if len(parts) == 2 and is_role_string(parts[1]):
                    title = clean_text(parts[1])
            if not title:
                continue

        title = title[:100].strip()
        seen_names.add(norm_name)
        # Assign direct canonical LinkedIn profile if not explicitly linked in DOM
        executives.append({
            "name": cand_name,
            "title": title,
            "category": categorize_role(title),
            "linkedin_url": generate_canonical_linkedin(cand_name),
            "source_page": page_url,
            "direct_source": False,
        })

    return executives
