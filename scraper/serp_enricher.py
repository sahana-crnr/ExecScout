"""
serp_enricher.py - Targeted SerpApi search with persistent local cache to protect the 250 query/month quota.
Includes strict executive title verification, company association validation, and robust network retries.
"""

import json
import logging
import os
import re
import time
import urllib.parse
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "serp_cache.json")


def is_profile_for_company(title: str, snippet: str, target_company: str, target_domain: str) -> bool:
    """Strictly verify that a search snippet or LinkedIn title refers to the target company."""
    clean_co = re.sub(r"[™®©]", "", target_company).split("|")[0].split("-")[0].strip().lower()
    co_slug = target_domain.split(".")[0].lower()
    full_text = f"{title} {snippet}".lower()

    # Must mention target company or target domain
    has_co_mention = (clean_co in full_text) or (target_domain.lower() in full_text) or (co_slug in full_text)
    if not has_co_mention:
        return False

    # Check LinkedIn title: "Name - Role - Company | LinkedIn" or "Name - Role at Company | LinkedIn"
    title_clean = title.split("|")[0].strip()
    parts = [p.strip() for p in title_clean.split(" - ")]
    if len(parts) >= 3:
        profile_co = parts[-1].lower()
        if clean_co not in profile_co and co_slug not in profile_co:
            return False

    at_match = re.search(r"\bat\s+([A-Za-z0-9\s\.\,&]+)", title_clean, re.IGNORECASE)
    if at_match:
        profile_co = at_match.group(1).lower().strip()
        if clean_co not in profile_co and co_slug not in profile_co:
            return False

    # Guard against common generic words (e.g. 'twelve years', 'box', 'scale')
    if clean_co in ["twelve", "one", "two", "three", "next", "square", "block", "box", "scale"]:
        co_pat = (
            r"\b(at|of|with|for|joins|ceo|cto|founder|co-founder)\s+"
            + re.escape(clean_co)
            + r"\b|\b"
            + re.escape(clean_co)
            + r"\s+(inc|llc|co2|benefit|technologies|team|leadership|ceo|cto|airplant|solutions)\b"
        )
        if not re.search(co_pat, full_text, re.IGNORECASE) and target_domain.lower() not in full_text:
            return False

    return True


class SerpEnricher:
    def __init__(self, api_key: Optional[str] = None, default_engine: str = "auto"):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        self.default_engine = default_engine.lower() if default_engine else "auto"
        self.cache = self._load_cache()
        self.searches_made = 0
        self.searches_saved = 0
        self.consecutive_failures = 0
        self.disabled = False

    def _load_cache(self) -> dict:
        """Load persistent JSON cache of previous SerpApi searches."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not read cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def _serpapi_request(self, params: dict, retries: int = 1) -> Optional[dict]:
        """Execute a SerpApi search with 8-second timeout and circuit breaker to prevent delays."""
        if self.disabled:
            return None

        import requests

        for attempt in range(retries + 1):
            try:
                resp = requests.get("https://serpapi.com/search", params=params, timeout=8)
                self.searches_made += 1
                if resp.status_code == 200:
                    self.consecutive_failures = 0
                    return resp.json()
                elif resp.status_code in [401, 403, 429]:
                    logger.info(f"[SerpApi] Service status {resp.status_code}. Disabling API queries for this session.")
                    self.disabled = True
                    return None
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt < retries:
                    time.sleep(1)
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 2:
                        logger.info("[SerpApi] Repeated timeouts detected. Falling back to direct extraction for this session.")
                        self.disabled = True
            except Exception:
                self.consecutive_failures += 1
                break
        return None

    def find_linkedin_for_executive(self, name: str, company: str, engine: Optional[str] = None) -> Optional[str]:
        """
        Look up an executive's LinkedIn profile using any specified search engine
        (Google, Bing, DuckDuckGo, Yahoo, or Direct LinkedIn).
        Strictly verifies that the found LinkedIn profile matches the executive's name.
        """
        from .extractor import generate_canonical_linkedin

        search_engine = (engine or self.default_engine or "auto").lower()

        # If LinkedIn direct is chosen, return canonical profile immediately (0 API credits)
        if search_engine in ["linkedin", "direct"]:
            return generate_canonical_linkedin(name)

        clean_co = re.sub(r"[™®©]", "", company).split("|")[0].split("-")[0].strip()
        cache_key = f"linkedin::{search_engine}::{name.strip().lower()}::{clean_co.lower()}"

        # 1. Check local cache first (Free!)
        if cache_key in self.cache:
            self.searches_saved += 1
            cached_val = self.cache[cache_key]
            logger.info(f"[CACHE HIT] LinkedIn ({search_engine}) for {name} ({clean_co}): {cached_val}")
            return cached_val or None

        # Also check general cache without engine
        general_cache_key = f"linkedin::{name.strip().lower()}::{clean_co.lower()}"
        if general_cache_key in self.cache:
            self.searches_saved += 1
            cached_val = self.cache[general_cache_key]
            if cached_val:
                logger.info(f"[CACHE HIT] LinkedIn for {name} ({clean_co}): {cached_val}")
                return cached_val

        # 2. Check if API key is present or circuit breaker is tripped
        if self.disabled or not self.api_key:
            return generate_canonical_linkedin(name)

        # 3. Determine search engines to attempt
        engines_to_try = [search_engine]
        if search_engine == "auto":
            engines_to_try = ["google"]

        name_tokens = [re.sub(r"[^\w]", "", w.lower()) for w in re.split(r"[\s\.,]+", name) if w]
        last_name = name_tokens[-1] if name_tokens else ""
        first_name = name_tokens[0] if name_tokens else ""

        for eng in engines_to_try:
            params = {
                "engine": eng,
                "q": f'"{name}" "{clean_co}" site:linkedin.com/in',
                "api_key": self.api_key,
                "num": 5,
            }
            if eng in ["google", "bing"]:
                params["gl"] = "us"
                params["hl"] = "en"

            logger.info(f"[SERPAPI CALL] Querying LinkedIn via {eng.upper()} for: {name} ({clean_co})")
            data = self._serpapi_request(params)
            if data:
                organic = data.get("organic_results", [])
                for res in organic:
                    link = res.get("link", "").split("?")[0].rstrip("/")
                    title = res.get("title", "").lower()

                    if "linkedin.com/in/" in link:
                        slug = link.split("/in/")[-1].lower()
                        last_match = bool(last_name and (last_name in slug or last_name in title))
                        first_match = bool(first_name and (first_name in slug or first_name in title))

                        if last_match or (first_match and len(name_tokens) <= 2):
                            self.cache[cache_key] = link
                            self._save_cache()
                            return link

        # Fallback to direct canonical profile URL if search engines found no link
        canonical = generate_canonical_linkedin(name)
        self.cache[cache_key] = canonical
        self._save_cache()
        return canonical

    def search_company_executives(self, company_name: str, domain: str, engine: Optional[str] = None) -> list[dict]:
        """
        Fallback search for companies with no static leadership page or WAF-protected sites.
        Extracts validated C-suite and executive leaders with strict role & company validation across any engine.
        """
        search_engine = (engine or self.default_engine or "auto").lower()
        active_engine = "google" if search_engine in ["auto", "linkedin"] else search_engine

        clean_company = re.sub(r"[™®©]", "", company_name).split("|")[0].split("-")[0].strip()
        cache_key = f"company_execs::{active_engine}::{clean_company.lower()}"

        if cache_key in self.cache:
            self.searches_saved += 1
            logger.info(f"[CACHE HIT] Company executives ({active_engine}) for {clean_company}")
            return self.cache[cache_key]

        # Also check general cache
        general_key = f"company_execs::{clean_company.lower()}"
        if general_key in self.cache:
            self.searches_saved += 1
            logger.info(f"[CACHE HIT] Company executives for {clean_company}")
            return self.cache[general_key]

        if not self.api_key:
            return []

        from .extractor import (
            is_valid_name,
            is_role_string,
            clean_person_name,
            categorize_role,
            generate_canonical_linkedin,
        )

        found_execs = []
        seen_names = set()

        # Query 1: Leadership news and company announcements
        query1 = f'"{clean_company}" "{domain}" (CEO OR CTO OR Founder OR President OR "Chief")'
        params1 = {
            "engine": active_engine,
            "q": query1,
            "api_key": self.api_key,
            "num": 10,
        }
        if active_engine in ["google", "bing"]:
            params1["gl"] = "us"
            params1["hl"] = "en"

        logger.info(f"[SERPAPI BATCH] Searching key executives via {active_engine.upper()} for {clean_company} ({domain})")
        data1 = self._serpapi_request(params1)
        organic1 = data1.get("organic_results", []) if data1 else []

        patterns = [
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}),\s+(Chief [A-Za-z\s&]+ Officer|CEO|CTO|CFO|COO|President|Vice President|Co-Founder|Founder)",
            r"(?:co-founder and\s+)?(CEO|CTO|CFO|COO|President|Chief [A-Za-z\s&]+ Officer|Co-Founder)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            r"Who is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*-\s*([A-Za-z\s&]+ at " + re.escape(clean_company) + r")",
            re.escape(clean_company) + r"\s+(?:Co-Founder|Chairman and CEO|CEO|President),\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+is the\s+(CEO|CTO|President|Founder)",
            r"(?:Leader\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+as\s+(Chief [A-Za-z\s&]+ Officer|CEO|CTO|Executive Chairman)",
            r"Chief Operating Officer\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+Elected as Next\s+(CEO)",
            r"Chairman and CEO\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+as\s+(Chairman and CEO|CEO|Executive Chairman|Presiding Director)"
        ]

        # Process organic results from Query 1
        for res in organic1:
            link = res.get("link", "").split("?")[0].rstrip("/")
            title_text = res.get("title", "")
            snippet = res.get("snippet", "")

            # Direct LinkedIn hits (discover person name & profile, but role must be verified from company site)
            if "linkedin.com/in/" in link and " - " in title_text:
                parts = title_text.split(" - ")
                raw_name = parts[0].strip()
                c_name = clean_person_name(raw_name, clean_company)

                if c_name and is_valid_name(c_name, clean_company) and is_profile_for_company(title_text, snippet, clean_company, domain):
                    norm = c_name.lower()
                    if norm not in seen_names:
                        seen_names.add(norm)
                        # Role is set to Not Found until verified against the company site
                        found_execs.append({
                            "name": c_name,
                            "title": "Not Found",
                            "category": "Not Found",
                            "linkedin_url": link,
                            "source_page": f"SerpApi {active_engine.capitalize()} ({domain})",
                            "direct_source": False,
                        })

            # Text snippet patterns
            combined_text = f"{title_text} {snippet}"
            for pat in patterns:
                for m in re.finditer(pat, combined_text, re.IGNORECASE):
                    groups = m.groups()
                    if len(groups) == 2:
                        if is_role_string(groups[0]):
                            t_str, n_str = groups[0], groups[1]
                        else:
                            n_str, t_str = groups[0], groups[1]
                    elif len(groups) == 1:
                        n_str = groups[0]
                        t_str = "Chairman and CEO" if "Chairman and CEO" in pat else "Co-Founder"
                    else:
                        continue

                    c_name = clean_person_name(n_str, clean_company)
                    c_title = t_str.strip()
                    norm = c_name.lower()

                    if c_name and is_valid_name(c_name, clean_company) and is_role_string(c_title) and norm not in seen_names:
                        seen_names.add(norm)
                        canonical_lk = generate_canonical_linkedin(c_name)
                        found_execs.append({
                            "name": c_name,
                            "title": c_title,
                            "category": categorize_role(c_title),
                            "linkedin_url": canonical_lk,
                            "source_page": f"SerpApi {active_engine.capitalize()} ({domain})",
                            "direct_source": False,
                        })

        # Query 2: If fewer than 2 executives discovered, query LinkedIn directory specifically
        if len(found_execs) < 2:
            query2 = f'site:linkedin.com/in "{clean_company}" (CEO OR CTO OR "Chief Executive Officer" OR President OR Founder)'
            params2 = {
                "engine": active_engine,
                "q": query2,
                "api_key": self.api_key,
                "num": 10,
            }
            if active_engine in ["google", "bing"]:
                params2["gl"] = "us"
                params2["hl"] = "en"

            logger.info(f"[SERPAPI BATCH] Directory query via {active_engine.upper()} for {clean_company} ({domain})")
            data2 = self._serpapi_request(params2)
            organic2 = data2.get("organic_results", []) if data2 else []

            for res in organic2:
                link = res.get("link", "").split("?")[0].rstrip("/")
                title_text = res.get("title", "")
                snippet = res.get("snippet", "")

                if "linkedin.com/in/" in link and " - " in title_text:
                    parts = title_text.split(" - ")
                    raw_name = parts[0].strip()
                    c_name = clean_person_name(raw_name, clean_company)

                    if c_name and is_valid_name(c_name, clean_company) and is_profile_for_company(title_text, snippet, clean_company, domain):
                        norm = c_name.lower()
                        if norm not in seen_names:
                            seen_names.add(norm)
                            # Role is set to Not Found until verified against the company site
                            found_execs.append({
                                "name": c_name,
                                "title": "Not Found",
                                "category": "Not Found",
                                "linkedin_url": link,
                                "source_page": f"SerpApi {active_engine.capitalize()} ({domain})",
                                "direct_source": False,
                            })

        self.cache[cache_key] = found_execs
        self._save_cache()
        return found_execs

    def get_stats(self) -> dict:
        """Return usage stats for this session."""
        return {
            "searches_made": self.searches_made,
            "searches_saved_by_cache": self.searches_saved,
            "total_cached_queries": len(self.cache),
            "search_engine": self.default_engine,
        }

