"""
run_scraper.py - CLI runner for ExecScout.
Extracts leadership & board members from company URLs without UI.
"""

import argparse
import json
import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure proper import path regardless of where script is invoked
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from scraper.orchestrator import run_executive_pipeline

PRESET_URLS = [
    "https://www.icanbwell.com/",
    "http://clearjet.com",
    "http://www.twelve.co",
    "http://www.pdw.ai/",
]


def print_table(executives: list[dict], domain: str):
    """Print an ASCII table in the terminal with full, clickable LinkedIn links."""
    if not executives:
        print(f"\n[!] No executives found for {domain}.\n")
        return

    print("\n" + "=" * 130)
    print(f"  EXECUTIVE INTELLIGENCE: {domain.upper()} ({len(executives)} found)")
    print("=" * 130)
    header = f"{'Name':<22} | {'Role':<32} | {'Contact':<30} | {'LinkedIn Profile (Clickable)'}"
    print(header)
    print("-" * 130)

    for e in executives:
        name = e.get("name", "")[:21]
        role = e.get("title", "")[:31]
        contact = e.get("inferred_email") or e.get("contact", "")
        contact_short = contact[:29]
        lk = e.get("linkedin_url", "")
        # Keep full valid clickable URL without truncating
        lk_clean = lk if lk else "N/A"
        print(f"{name:<22} | {role:<32} | {contact_short:<30} | {lk_clean}")
    print("=" * 130 + "\n")


def main():
    parser = argparse.ArgumentParser(description="ExecScout: Company Leadership & Board Member Discovery Engine")
    parser.add_argument("--url", type=str, help="Single company URL to scrape")
    parser.add_argument("--all-presets", action="store_true", help="Run against all 4 mentor sample companies")
    parser.add_argument("--serpapi-key", type=str, default="", help="SerpApi API key (or set SERPAPI_API_KEY env var)")
    parser.add_argument("--output", type=str, default="executives.csv", help="Output CSV file path")

    args = parser.parse_args()

    api_key = args.serpapi_key or os.getenv("SERPAPI_API_KEY", "")

    urls_to_process = []
    if args.all_presets:
        urls_to_process = PRESET_URLS
    elif args.url:
        urls_to_process = [args.url]
    else:
        print("No URL specified. Running against default preset: https://www.icanbwell.com/")
        print("Tip: Use --url <company_url> or --all-presets")
        urls_to_process = ["https://www.icanbwell.com/"]

    all_results = []
    for u in urls_to_process:
        print(f"\n[*] Processing: {u}...")
        execs, stats = run_executive_pipeline(u, serpapi_key=api_key)
        print_table(execs, stats.get("domain", u))
        all_results.extend(execs)

    if all_results:
        df = pd.DataFrame(all_results)
        df.to_csv(args.output, index=False)
        print(f"[OK] Exported {len(all_results)} executive records to {args.output}")

        json_out = os.path.splitext(args.output)[0] + ".json"
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"[OK] Exported JSON to {json_out}\n")


if __name__ == "__main__":
    main()
