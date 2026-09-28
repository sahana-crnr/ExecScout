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
    "goldman", "sachs", "morgan", "stanley", "jpmorgan", "chase", "citi", "bank",
    "careers", "career", "job", "jobs", "hiring", "openings", "recruiting",
    "benefits", "employee", "interview", "podcast", "article", "post", "posts", "blog",
    "calendar", "event", "events", "summit", "conference", "winner", "award", "pioneers",
    "savors", "comes", "leaves", "opens", "takes", "unveils", "featured",
    "drives", "principles", "safety", "plant", "designer", "inspector",
    "candidate", "student", "intern", "broker", "realtor", "sales", "support",
    "member", "members", "airplant", "saf", "facility", "school", "episode",
    "recent", "topics", "tags", "archives", "categories", "author", "speakers",
    "speaker", "moderator", "panelist", "highlights", "stories", "story", "updates", "update",
    "lisbon", "portugal", "london", "paris", "berlin", "tokyo", "california", "texas",
    "york", "francisco", "chicago", "boston", "seattle", "washington", "angeles",
    "delhi", "mumbai", "bangalore", "singapore", "sydney", "toronto", "canada",
    "europe", "asia", "america", "global", "international", "city", "county", "district"
}

INVALID_FIRST_WORDS = {
    "the", "our", "their", "this", "that", "every", "all", "what",
    "how", "why", "when", "where", "who", "about", "meet", "join",
    "view", "read", "learn", "get", "contact", "we", "you", "program", "project",
    "partner", "expected", "announced", "named", "appointed", "promoted",
    "elected", "former", "interim", "annual", "virtual", "global", "special",
    "event", "session", "keynote", "webinar", "panel", "presentation", "conference",
    "careers", "career", "speaker", "speakers", "dr", "mr", "ms", "mrs",
    "recent", "related", "featured", "more", "posts", "post"
}

STOP_TRAILING = {
    "elected", "appointed", "named", "joins", "joined", "leaves", "left", "promoted",
    "retires", "retired", "to", "as", "at", "by", "in", "for", "from", "with", "on",
    "hosted", "speaks", "speaking", "participates", "participate", "presents",
    "addresses", "steps", "step", "down", "succeeds", "succeed", "become", "becomes",
    "announced", "expected", "welcomes", "shares", "discusses", "chairman", "ceo",
    "president", "coo", "director", "officer", "leader", "next", "visit", "call", "board",
    "savors", "comes", "takes", "drives", "unveils", "opens", "posts"
}

NON_EXECUTIVE_DISQUALIFIERS = [
    "designer", "inspector", "broker", "realtor", "technician", "student",
    "candidate", "intern", "specialist", "recruiter", "sales representative",
    "sales rep", "coordinator", "assistant", "clerk", "operator", "mechanic",
    "electrician", "nurse", "teacher", "fellow", "postdoc", "programmatic",
    "contractor", "freelancer", "machinist", "consultant", "testing engineer",
    "software engineer", "sales engineer"
]


def clean_text(text: str) -> str:
    """Clean whitespace and formatting."""
    return re.sub(r"\s+", " ", text).strip()


def clean_extracted_title(t: str, cand_name: str = "") -> str:
    """Clean extracted title string and strip leading commas, punctuation, or candidate name prefix."""
    if not t:
        return ""
    t = re.sub(r"^[\s,–\-—|:]+|[\s,–\-—|:]+$", "", t).strip()
    if cand_name and t.lower().startswith(cand_name.lower()):
        t = re.sub(r"^" + re.escape(cand_name) + r"[\s,–\-—|:]*", "", t, flags=re.IGNORECASE).strip()
    return t


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
    if any(t.lower() in NON_PERSON_WORDS for t in tokens):
        return ""
    res = " ".join(tokens)
    return res.title() if res.isupper() else res


def is_role_string(text: str, company_name: str = "") -> bool:
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
        if any(bad in t for bad in ["testing engineer", "sales rep", "inspector", "student", "candidate", "intern"]):
            return False

    # If the role explicitly specifies an external company (e.g. "at MIT Technology Review"), disqualify
    if " at " in t and company_name:
        co_slug = company_name.lower().split()[0]
        if co_slug not in t:
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
    if not title or title.lower() in ["not found", "n/a", "none", "unknown", ""]:
        return "Not Found"
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


def search_role_in_company_pages(
    person_name: str,
    pages_html: dict[str, str],
    company_name: str = "",
    domain: str = ""
) -> str:
    """
    Search company site HTML pages for the given executive's official designation/role.
    Extracts accurately from company text/DOM if found, else returns 'Not Found'.
    Never guesses from LinkedIn search headings.
    """
    if not person_name or not pages_html:
        return "Not Found"

    tokens = [re.escape(t) for t in person_name.split() if len(t) > 1]
    if not tokens:
        return "Not Found"

    first_last = r"\b" + r"\s+".join(tokens) + r"\b"
    title_pattern = (
        r"(?:co-founder and Chief [A-Za-z\s&]+ Officer|"
        r"Chief [A-Za-z\s&]+ Officer|"
        r"CEO and Co-Founder|Co-Founder and CEO|"
        r"Advisor and Co-Founder|Co-Founder and Advisor|"
        r"CEO|CTO|CFO|COO|CIO|CMO|CSO|CPO|CRO|CHRO|"
        r"President|Executive Chairman|Chairman and CEO|Chair and Chief Executive Officer|Chairwoman and CEO|"
        r"Lead Independent Director|Independent Director|Board Member|Director|"
        r"General Counsel|Corporate Secretary|Chief of Staff|"
        r"Vice President|VP[\s,]+[A-Za-z0-9\s&,/-]+|SVP[\s,]+[A-Za-z0-9\s&,/-]+|EVP[\s,]+[A-Za-z0-9\s&,/-]+|"
        r"Head of [A-Za-z0-9\s&,/-]+|"
        r"Founder|Co-Founder)"
    )

    sentence_patterns = [
        # e.g. "Speaker: Nicholas Flanders, CEO and Co-Founder" or "Nicholas Flanders, CEO and Co-Founder"
        rf"(?:Speaker|Presenter|Panelist)?[:\s]*(?:Dr\.|Mr\.|Ms\.|Mrs\.)?\s*{first_last}[,\s\-–|]+(?:the\s+)?({title_pattern})",
        # e.g. "Twelve Co-Founder and Chief Science Officer Dr. Etosha Cave"
        rf"({title_pattern})\s+(?:at\s+[\w\s]+)?(?:Dr\.|Mr\.|Ms\.|Mrs\.)?\s*{first_last}",
        # e.g. "Nicholas Flanders serves as CEO and Co-Founder"
        rf"(?:Dr\.|Mr\.|Ms\.|Mrs\.)?\s*{first_last}\s+(?:is|serves as|acts as)\s+(?:the\s+)?({title_pattern})",
    ]

    for page_url, html in pages_html.items():
        if not html:
            continue
        if person_name.lower() not in html.lower():
            continue

        soup = BeautifulSoup(html, "html.parser")

        # 1. Check direct text / sentences with strict boundary
        text = soup.get_text(separator=" ", strip=True)
        for pat in sentence_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted = clean_extracted_title(m.group(1), person_name)
                # Strip trailing event dates, months, or year stamps
                extracted = re.sub(
                    r"\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}(?:st|nd|rd|th)?|\d{4}).*$",
                    "",
                    extracted,
                    flags=re.IGNORECASE
                ).strip()
                if company_name:
                    extracted = re.sub(rf"^(?:at\s+)?{re.escape(company_name)}\s+", "", extracted, flags=re.IGNORECASE)
                    extracted = re.sub(rf"\s+(?:at|of|for)\s+{re.escape(company_name)}.*$", "", extracted, flags=re.IGNORECASE)
                if is_role_string(extracted, company_name):
                    return extracted.strip().title() if extracted.islower() else extracted.strip()

        # 2. Check immediate sibling tag if person's name is an isolated heading
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"]):
            tag_text = clean_text(tag.get_text())
            if tag_text.lower() == person_name.lower():
                next_elem = tag.find_next_sibling(["p", "span", "h4", "h5"])
                if next_elem:
                    sib_text = clean_text(next_elem.get_text())
                    if sib_text and len(sib_text) <= 55 and is_role_string(sib_text, company_name) and person_name.lower() not in sib_text.lower():
                        return sib_text.strip().title() if sib_text.islower() else sib_text.strip()

    return "Not Found"


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
                title = clean_text(p.get("jobTitle", "")) or "Not Found"
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
                        lk = generate_canonical_linkedin(clean_n)
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

        # Walk up to find the single-person card container
        card = a
        curr = a
        while curr.parent and curr.parent.name not in ["body", "html", "main", "article", "section", "[document]"]:
            parent_lk = len(curr.parent.find_all("a", href=lambda h: h and "linkedin.com/in/" in h))
            if parent_lk == 1:
                card = curr.parent
                curr = curr.parent
            else:
                break

        lines = [re.sub(r"\s+", " ", s).strip() for s in card.stripped_strings if s.strip()]
        lines = [l for l in lines if l.lower() not in STOP_WORDS and len(l) <= 80]

        cand_name = None
        cand_title = None

        # Check for dedicated role / title and name tags inside the card
        for tag in card.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "p", "div", "span"]):
            t = re.sub(r"\s+", " ", tag.get_text()).strip()
            if not t or len(t) > 75:
                continue
            if not cand_title and is_role_string(t, company_name):
                cand_title = t
            elif not cand_name and is_valid_name(t, company_name):
                cand_name = t

        # Fallback to lines inside the card
        for l in lines:
            if not cand_title and is_role_string(l, company_name):
                cand_title = l
            elif not cand_name and is_valid_name(l, company_name):
                cand_name = l

        if not cand_name:
            cand_name = parse_name_from_slug(lk_url)

        # Verify that lk_url actually corresponds to cand_name
        slug = lk_url.split("/in/")[-1].split("?")[0].strip("/").lower()
        clean_cand_tokens = [re.sub(r"[^\w]", "", t.lower()) for t in (cand_name or "").split() if len(t) > 2]
        slug_matches_cand = any(t in slug for t in clean_cand_tokens) if clean_cand_tokens else False
        if not slug_matches_cand:
            # Check if another valid person in lines matches the slug
            matched_person = None
            for l in lines:
                l_clean = clean_person_name(l, company_name)
                l_tokens = [re.sub(r"[^\w]", "", t.lower()) for t in l_clean.split() if len(t) > 2]
                if any(t in slug for t in l_tokens) and is_valid_name(l_clean, company_name):
                    matched_person = l_clean
                    break
            if matched_person:
                cand_name = matched_person
            else:
                lk_url = generate_canonical_linkedin(cand_name)

        if cand_title:
            cand_title = clean_extracted_title(cand_title, cand_name)
            if not is_role_string(cand_title, company_name):
                cand_title = "Not Found"
        else:
            cand_title = "Not Found"

        # Check if this person has external affiliation mentioned in card (e.g. "at MIT Technology Review")
        card_full_text = card.get_text(separator=" ", strip=True)
        if cand_name and f"{cand_name} at " in card_full_text:
            after_at = card_full_text.split(f"{cand_name} at ")[1][:30].lower()
            if company_name and company_name.lower() not in after_at:
                continue

        # On blog/post/event pages, require an actual verified executive role
        is_post_or_blog = any(k in page_url.lower() for k in ["/post/", "/blog/", "/news/", "/article/", "/press/", "/event", "/calendar"])
        if is_post_or_blog and cand_title == "Not Found":
            continue

        if cand_name:
            cand_name = clean_person_name(cand_name, company_name)
        norm_name = cand_name.lower() if cand_name else ""
        if norm_name and norm_name not in seen_names and is_valid_name(cand_name, company_name):
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
            if elem_text and is_role_string(elem_text, company_name) and elem_text != cand_name:
                title = elem_text
                break

        if not title:
            # Check if name_tag itself has role appended (e.g. "Jane Doe, CEO")
            full_header = clean_text(name_tag.get_text())
            if "," in full_header or " - " in full_header:
                parts = re.split(r"[,–\-]\s*", full_header, maxsplit=1)
                if len(parts) == 2 and is_role_string(parts[1], company_name):
                    title = clean_text(parts[1])
            if not title:
                continue

        title = clean_extracted_title(title, cand_name)
        if not is_role_string(title, company_name):
            continue

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
