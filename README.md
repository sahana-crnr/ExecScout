# 👥 ExecScout — Executive & Board Intelligence Engine

**ExecScout** is an automated intelligence tool designed to scrape and extract company leadership (CEO, CTO, President, VPs, Board Members) along with their **mandatory LinkedIn profiles** and corporate contact details.

It is built with an **intelligent 3-tier quota conservation strategy** to respect SerpApi's free tier limit (**250 searches/month**).

---

## 🚀 Key Features

1. **Direct Website & SPA Scraping (Zero API Cost)**:
   - Automatically crawls company homepages and uncovers leadership pages (`/about`, `/team`, `/leadership`, `/board`, `/company`).
   - **SPA Discovery Engine**: Inspects Angular, React, and Vue client-side JavaScript bundles to automatically uncover internal REST APIs (e.g. Flipkart's `/ws/getContents/ABOUT/LEADERS`) and extract official leadership data from client-side SPAs.
   - Extracts names, executive designations, and **direct LinkedIn `/in/` links** embedded on the website without burning any search API quota.

2. **Multi-Engine Search & LinkedIn Resolution**:
   - Supports **Google**, **Bing**, **DuckDuckGo**, **Yahoo**, and **Direct LinkedIn** resolution.
   - **Auto Multi-Engine**: Queries Google with automatic fallback to Bing, and seamlessly resolves direct canonical LinkedIn profiles (`https://www.linkedin.com/in/{slug}`) if external engines yield no link.
   - User-selectable search engine in both the Streamlit UI sidebar and the CLI runner (`--engine`).

3. **SerpApi Quota Guard (250 Searches/Month Conservation)**:
   - **Cache First**: Checks local `serp_cache.json` before querying external search engines. Rerunning against a company consumes 0 queries.
   - **Targeted Fallback**: Only issues a search query when an executive's LinkedIn profile is absent from the company website.
   - Single-query batch fallback for JS-rendered / dynamic sites (`site:linkedin.com/in "Company" (CEO OR CTO OR President)`).

4. **Contact Details & Email Pattern Mining**:
   - Extracts public contact emails and phone numbers from corporate pages.
   - Deduces corporate email formats (e.g. `{first}.{last}@{domain}`).

5. **Streamlit Interactive UI + Headless CLI**:
   - Interactive web dashboard with 1-click test chips for target companies.
   - Clickable LinkedIn links and category filters (CEO, CTO, President, VP, Board).
   - Export to **CSV** and **JSON**.
   - Standalone CLI runner (`run_scraper.py`).

---

## 📦 Setup & Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Set SerpApi Key

If you have a SerpApi key, copy `.env.example` to `.env` and set your key:

```bash
cp .env.example .env
# Edit .env and set:
# SERPAPI_API_KEY=your_key_here
```

Or enter it directly into the Streamlit sidebar or pass `--serpapi-key` via CLI.

_(Note: ExecScout extracts all direct website executives, SPA leaders, and LinkedIn profiles even without an API key!)_

---

## 🖥️ Running the Application

### Option A: Streamlit Web Dashboard (Recommended)

```bash
streamlit run app.py
```

_Open your browser at `http://localhost:8501` to test with 1-click presets and multi-engine selection._

### Option B: Headless CLI

```bash
# Single company URL with auto multi-engine
python run_scraper.py --url https://corporate.flipkart.net/about-us

# Specify a search engine (auto, google, bing, duckduckgo, linkedin)
python run_scraper.py --url https://www.icanbwell.com/ --engine auto
python run_scraper.py --url http://www.twelve.co --engine bing

# Run against sample companies
python run_scraper.py --all-presets --output results.csv
```

---

## 🏢 Tested Benchmark Companies

| Company | URL | Discovery Method | Results |
|---|---|---|---|
| **Flipkart Group** | `https://corporate.flipkart.net/about-us` | Angular SPA REST API Engine | 11 Leaders (CEO, CHRO, CFO, SVPs) |
| **b.well Connected Health** | `https://www.icanbwell.com/` | Direct HTML Card Walking | 11 Executives (CEO, CFO, CTO, VPs) |
| **Performance Drone Works** | `http://www.pdw.ai/` | Direct HTML Container Extraction | 10 Executives (CEO, CTO, Founders) |
| **Twelve CleanTech** | `http://www.twelve.co` | On-Page Leadership Filter | 4 True Executives (CEO, Founders, VPs) |
| **ClearJet Logistics** | `http://clearjet.com` | Targeted Fallback Query | Validated Leadership |

---

## 🛡️ License & Data Ethics

ExecScout strictly accesses publicly available corporate website information and respects standard scraping etiquette and rate limits.
