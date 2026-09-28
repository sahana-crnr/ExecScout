# 👥 ExecScout — Executive & Board Intelligence Engine

**ExecScout** is an automated intelligence tool designed to scrape and extract company leadership (CEO, CTO, President, VPs, Board Members) along with their **mandatory LinkedIn profiles** and corporate contact details.

It is built with an **intelligent 3-tier quota conservation strategy** to respect SerpApi's free tier limit (**250 searches/month**).

---

## 🚀 Key Features

1. **Direct Website Scraping (Zero API Cost)**:
   - Automatically crawls company homepages and uncovers leadership pages (`/about`, `/team`, `/leadership`, `/board`, `/company`).
   - Extracts names, executive designations, and **direct LinkedIn `/in/` links** embedded on the website without burning any search API quota.

2. **SerpApi Quota Guard (250 Searches/Month Conservation)**:
   - **Cache First**: Checks local `serp_cache.json` before querying Google. Rerunning against a company consumes 0 queries.
   - **Targeted Fallback**: Only issues a search query when an executive's LinkedIn profile is absent from the company website.
   - Single-query batch fallback for JS-rendered / dynamic sites (`site:linkedin.com/in "Company" (CEO OR CTO OR President)`).

3. **Contact Details & Email Pattern Mining**:
   - Extracts public contact emails and phone numbers from corporate pages.
   - Deduces corporate email formats (e.g. `{first}.{last}@{domain}`).

4. **Streamlit Interactive UI + Headless CLI**:
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

Or set it as an environment variable or enter it directly into the Streamlit sidebar:

```bash
# Windows PowerShell
$env:SERPAPI_API_KEY="your_api_key_here"

# Linux / macOS
export SERPAPI_API_KEY="your_api_key_here"
```

_(Note: ExecScout still extracts all direct website executives and LinkedIn profiles even without an API key!)_

---

## 🖥️ Running the Application

### Option A: Streamlit Web Dashboard (Recommended)

```bash
streamlit run app.py
```

_Open your browser at `http://localhost:8501` to test with 1-click presets._

### Option B: Headless CLI

```bash
# Single company URL
python run_scraper.py --url https://www.icanbwell.com/

# Run against all 4 sample companies
python run_scraper.py --all-presets --output results.csv
```

---

## 🏢 Tested Target Companies

| Company                     | URL                          | Discovery Method                    |
| --------------------------- | ---------------------------- | ----------------------------------- |
| **b.well Connected Health** | `https://www.icanbwell.com/` | Direct HTML (`/about-bwell/`)       |
| **Performance Drone Works** | `http://www.pdw.ai/`         | Direct HTML (`/company-leadership`) |
| **Twelve CleanTech**        | `http://www.twelve.co`       | Targeted SerpApi Fallback           |
| **ClearJet Logistics**      | `http://clearjet.com`        | Targeted SerpApi Fallback           |

---

## 🛡️ License & Data Ethics

ExecScout strictly accesses publicly available corporate website information and respects standard scraping etiquette and rate limits.
