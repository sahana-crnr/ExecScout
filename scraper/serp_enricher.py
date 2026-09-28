"""
serp_enricher.py - Targeted SerpApi search with persistent local cache to protect the 250 query/month quota.
"""

import json
import logging
import os
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "serp_cache.json")


class SerpEnricher:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        self.cache = self._load_cache()
        self.searches_made = 0
        self.searches_saved = 0

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

    def find_linkedin_for_executive(self, name: str, company: str) -> Optional[str]:
        """
        Look up an executive's LinkedIn profile using SerpApi.
        Strictly checks cache first to conserve monthly quota.
        """
        cache_key = f"linkedin::{name.strip().lower()}::{company.strip().lower()}"

        # 1. Check local cache first (Free!)
        if cache_key in self.cache:
            self.searches_saved += 1
            logger.info(f"[CACHE HIT] LinkedIn for {name} ({company}): {self.cache[cache_key]}")
            return self.cache[cache_key]

        # 2. Check if API key is present
        if not self.api_key:
            logger.warning("No SerpApi key provided. Skipping Google search fallback.")
            return None

        # 3. Perform single targeted Google Search
        try:
            import requests

            query = f'site:linkedin.com/in "{name}" "{company}"'
            params = {
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "num": 1,
            }

            logger.info(f"[SERPAPI CALL] Querying: {query}")
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            self.searches_made += 1

            if resp.status_code == 200:
                data = resp.json()
                organic = data.get("organic_results", [])
                if organic and "link" in organic[0]:
                    link = organic[0]["link"].split("?")[0].rstrip("/")
                    if "linkedin.com/in/" in link:
                        self.cache[cache_key] = link
                        self._save_cache()
                        return link
        except Exception as e:
            logger.error(f"SerpApi request failed for {name}: {e}")

        # Cache negative result as empty string to prevent burning searches on reruns
        self.cache[cache_key] = ""
        self._save_cache()
        return None

    def search_company_executives(self, company_name: str, domain: str) -> list[dict]:
        """
        Fallback search for companies with no static leadership page.
        Uses a SINGLE SerpApi search query to retrieve multiple executives.
        Query: site:linkedin.com/in "CompanyName" (CEO OR CTO OR President OR Founder)
        """
        cache_key = f"company_execs::{company_name.strip().lower()}"
        if cache_key in self.cache:
            self.searches_saved += 1
            logger.info(f"[CACHE HIT] Company executives for {company_name}")
            return self.cache[cache_key]

        if not self.api_key:
            return []

        try:
            import requests

            query = f'site:linkedin.com/in "{company_name}" (CEO OR CTO OR President OR "Vice President" OR Founder OR "Board of Directors")'
            params = {
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "num": 10,
            }

            logger.info(f"[SERPAPI BATCH] Searching key executives for {company_name}")
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            self.searches_made += 1

            found_execs = []
            if resp.status_code == 200:
                data = resp.json()
                organic = data.get("organic_results", [])
                for res in organic:
                    link = res.get("link", "").split("?")[0].rstrip("/")
                    title_text = res.get("title", "")
                    snippet = res.get("snippet", "")

                    if "linkedin.com/in/" in link and " - " in title_text:
                        # LinkedIn titles typically format as: "Name - Title - Company | LinkedIn"
                        parts = title_text.split(" - ")
                        name = parts[0].strip()
                        raw_title = parts[1].split("|")[0].strip() if len(parts) > 1 else "Executive"

                        from .extractor import is_valid_name, categorize_role
                        if is_valid_name(name):
                            found_execs.append({
                                "name": name,
                                "title": raw_title,
                                "category": categorize_role(raw_title),
                                "linkedin_url": link,
                                "source_page": f"SerpApi Google ({domain})",
                                "direct_source": False,
                            })

                self.cache[cache_key] = found_execs
                self._save_cache()
                return found_execs

        except Exception as e:
            logger.error(f"SerpApi batch search failed: {e}")

        return []

    def get_stats(self) -> dict:
        """Return usage stats for this session."""
        return {
            "searches_made": self.searches_made,
            "searches_saved_by_cache": self.searches_saved,
            "total_cached_queries": len(self.cache),
        }
