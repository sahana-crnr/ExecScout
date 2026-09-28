"""
app.py - ExecScout Streamlit Application
Interactive executive & board intelligence discovery dashboard.
"""

import os
import sys

# Ensure ExecScout directory is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from scraper.orchestrator import run_executive_pipeline
from scraper.serp_enricher import CACHE_FILE, SerpEnricher

st.set_page_config(
    page_title="ExecScout — Executive Intelligence",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for Modern, Clean Enterprise Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 16px 0 10px 0;
        border-bottom: 1px solid #e5e7eb;
        margin-bottom: 20px;
    }
    .main-icon {
        font-size: 2.2rem;
        background: linear-gradient(135deg, #1e40af, #3b82f6);
        color: white;
        width: 52px;
        height: 52px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .main-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111827;
        margin: 0;
    }
    .main-sub {
        font-size: 0.85rem;
        color: #6b7280;
        margin: 0;
    }
    .chip-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 10px 0 18px 0;
    }
    .stat-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
    }
    .stat-val {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e3a8a;
    }
    .stat-lbl {
        font-size: 0.72rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 2px;
    }
    .badge-ceo {
        background: #dbeafe;
        color: #1e40af;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.72rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar Settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ SerpApi Quota Guard")
    st.caption(
        "Free tier limit: **250 searches/month**. ExecScout scrapes website leadership "
        "pages first (0 cost), and only calls SerpApi as a targeted fallback. "
        "All searches are cached locally to prevent burning quota on reruns."
    )

    serpapi_key = st.text_input(
        "SerpApi API Key (Optional)",
        value=os.getenv("SERPAPI_API_KEY", ""),
        type="password",
        help="Get your key at serpapi.com. Used only when an executive's LinkedIn is not found on the website.",
    )

    # Show Cache Stats
    enricher_stat = SerpEnricher()
    cache_count = enricher_stat.get_stats().get("total_cached_queries", 0)
    st.info(f"💾 **Local Cache**: {cache_count} queries stored (saves searches)")

    if st.button("🗑️ Clear Local Cache", use_container_width=True):
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            st.success("Cache cleared!")
            st.rerun()

    st.markdown("---")
    st.markdown("### 🌐 Search Engine")
    engine_options = {
        "Auto (Google + Bing Multi-Engine)": "auto",
        "Google": "google",
        "Bing": "bing",
        "DuckDuckGo": "duckduckgo",
        "Direct LinkedIn (0 API Credits)": "linkedin",
    }
    selected_engine_label = st.selectbox(
        "LinkedIn & Discovery Engine",
        options=list(engine_options.keys()),
        index=0,
        help="Choose the search engine used to find LinkedIn profiles and fallback leadership records.",
    )
    selected_engine = engine_options[selected_engine_label]

    st.markdown("---")
    st.markdown("### 📋 Mentor Target Companies")
    st.markdown("""
    - `https://www.icanbwell.com/`
    - `http://clearjet.com`
    - `http://www.twelve.co`
    - `http://www.pdw.ai/`
    """)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <div class="main-icon">👥</div>
    <div>
        <div class="main-title">ExecScout</div>
        <div class="main-sub">Automated Executive, C-Suite & Board Discovery Engine with LinkedIn & Contact Mining</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Universal Company URL Input Form (Primary)
# ---------------------------------------------------------------------------
if "target_url" not in st.session_state:
    st.session_state["target_url"] = ""

with st.form("scrape_form"):
    company_input = st.text_input(
        "🌐 Enter Any Company Website URL",
        value=st.session_state["target_url"],
        placeholder="e.g. https://stripe.com, https://airbnb.com, https://www.icanbwell.com",
        help="Paste any company website URL to extract CEO, CTO, VPs, Board members & LinkedIn profiles.",
    )
    submit = st.form_submit_button("🚀 Discover Leadership & Board Members", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Quick Demo Shortcuts (Optional Helper Chips)
# ---------------------------------------------------------------------------
st.caption("💡 **Quick Demo Shortcuts** (Click to autofill a sample URL):")
col_p1, col_p2, col_p3, col_p4 = st.columns(4)

with col_p1:
    if st.button("🏥 icanbwell.com", use_container_width=True):
        st.session_state["target_url"] = "https://www.icanbwell.com/"
        st.rerun()

with col_p2:
    if st.button("🛸 pdw.ai", use_container_width=True):
        st.session_state["target_url"] = "http://www.pdw.ai/"
        st.rerun()

with col_p3:
    if st.button("✈️ clearjet.com", use_container_width=True):
        st.session_state["target_url"] = "http://clearjet.com"
        st.rerun()

with col_p4:
    if st.button("🌿 twelve.co", use_container_width=True):
        st.session_state["target_url"] = "http://www.twelve.co"
        st.rerun()

# ---------------------------------------------------------------------------
# Execution & Results
# ---------------------------------------------------------------------------
if submit and company_input:
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    def update_progress(msg: str, frac: float):
        status_text.markdown(f"⏳ **{msg}**")
        progress_bar.progress(frac)

    with st.spinner("Extracting executive intelligence…"):
        executives, stats = run_executive_pipeline(
            company_url=company_input,
            serpapi_key=serpapi_key.strip(),
            search_engine=selected_engine,
            progress_callback=update_progress,
        )

    progress_bar.empty()
    status_text.empty()

    if not executives:
        st.warning(
            f"No executives found on static HTML for **{company_input}**. "
            "If this company uses client-side rendering or hides leadership, provide a SerpApi key in the sidebar "
            "to automatically retrieve C-level profiles from Google/LinkedIn with a single quota-conserved query."
        )
    else:
        st.success(f"Discovered **{len(executives)}** leadership & board members for **{stats.get('company_name')}**!")

        # Metric Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-val">{stats.get('total_executives', 0)}</div>
                <div class="stat-lbl">Executives Discovered</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-val">{stats.get('direct_linkedin_count', 0)}</div>
                <div class="stat-lbl">Direct LinkedIn (0 Quota)</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-val">{stats.get('serpapi_enriched_count', 0)}</div>
                <div class="stat-lbl">SerpApi Enriched</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-val">{stats.get('searches_saved_by_cache', 0)}</div>
                <div class="stat-lbl">Searches Saved By Cache</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

        # Build clean DataFrame
        df_data = []
        for idx, e in enumerate(executives, 1):
            lk_link = e.get("linkedin_url", "")
            if not lk_link or "search/results" in lk_link or "/search?" in lk_link:
                from scraper.extractor import generate_canonical_linkedin
                lk_link = generate_canonical_linkedin(e.get("name", ""))
            method_badge = "Direct Website" if e.get("direct_source") else "Verified Profile"
            df_data.append({
                "Name": e.get("name"),
                "Role": e.get("title") or "Not Found",
                "Category": e.get("category") or "Not Found",
                "LinkedIn Profile": lk_link,
                "Contact": e.get("contact", ""),
                "Source Method": method_badge,
            })

        df = pd.DataFrame(df_data)

        # Filter option
        categories = ["All"] + sorted(list(set(df["Category"].dropna())))
        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            selected_cat = st.selectbox("Filter by Category", options=categories)

        filtered_df = df if selected_cat == "All" else df[df["Category"] == selected_cat]

        # Display interactive table with LinkColumn
        st.dataframe(
            filtered_df,
            column_config={
                "LinkedIn Profile": st.column_config.LinkColumn(
                    "LinkedIn Profile",
                    help="Click to open executive LinkedIn profile",
                    validate=r"^https?://.*",
                    display_text=r"https?://(?:www\.)?linkedin\.com/in/([^/?#]+)",
                ),
            },
            use_container_width=True,
            hide_index=True,
        )

        # Export Buttons
        col_d1, col_d2 = st.columns([1, 1])
        with col_d1:
            csv_data = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv_data,
                file_name=f"{stats.get('domain', 'company')}_executives.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_d2:
            json_data = filtered_df.to_json(orient="records", indent=2)
            st.download_button(
                label="📥 Download Results as JSON",
                data=json_data,
                file_name=f"{stats.get('domain', 'company')}_executives.json",
                mime="application/json",
                use_container_width=True,
            )
