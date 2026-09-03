"""BI 看板视觉样式与配色常量。

把 streamlit_app.py 内联的 <style> 块集中到此模块，便于统一维护企业浅色主题，
避免巨型单文件。"""

# Streamlit 注入用的看板样式（含 <style> 标签，直接 st.markdown 即可）。
BI_DASHBOARD_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

    :root {
        --brand: #1565C0;
        --teal: #14B8A6;
        --orange: #F97316;
        --purple: #8B5CF6;
        --green: #22C55E;
        --bg: #F6F8FC;
        --surface: #FFFFFF;
        --surface-2: #F8FAFC;
        --sidebar: #EEF2F7;
        --line: #E2E8F0;
        --line-strong: #CBD5E1;
        --ink: #0F172A;
        --ink-2: #475569;
        --muted: #64748B;
        --sans: "Manrope", "Noto Sans SC", "Microsoft YaHei", sans-serif;
        --mono: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    }

    html, body, [class*="css"] {
        font-family: var(--sans);
    }
    .stApp {
        background: var(--bg);
        color: var(--ink);
    }
    .block-container {
        max-width: 1440px;
        padding-top: 2.1rem;
        padding-bottom: 3.5rem;
        padding-left: 2.25rem;
        padding-right: 2.25rem;
    }
    [data-testid="stHeader"] {
        background: var(--bg);
        border-bottom: 1px solid var(--line);
    }
    [data-testid="stSidebar"] {
        background: var(--sidebar);
        border-right: 1px solid var(--line);
        color: var(--ink);
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 2rem;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-size: 15px;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    [data-testid="stSidebar"] label p {
        color: var(--ink-2);
        font-size: 13px;
        font-weight: 600;
    }

    h1, h2, h3 {
        color: var(--ink);
        font-family: var(--sans);
        letter-spacing: -0.03em;
    }
    h1 {
        font-size: 30px !important;
        font-weight: 800 !important;
        line-height: 1.25 !important;
        padding-bottom: 0.35rem;
    }
    h2 {
        font-size: 22px !important;
        font-weight: 800 !important;
        line-height: 1.35 !important;
        margin-top: 0.25rem;
    }
    h3, h4, h5 {
        font-weight: 700 !important;
        line-height: 1.4 !important;
    }
    p, li {
        color: var(--ink-2);
    }
    hr {
        margin: 1.35rem 0;
        border-color: var(--line);
    }
    code, pre {
        font-family: var(--mono);
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stCaptionContainer"] {
        color: var(--muted);
    }

    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 16px 18px;
        box-shadow: none;
        min-height: 118px;
    }
    [data-testid="stMetricLabel"] p {
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    [data-testid="stMetricValue"] {
        color: var(--ink);
        font-family: var(--mono);
        font-size: 30px !important;
        font-weight: 700;
        letter-spacing: -0.04em;
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stMetricDelta"] {
        font-family: var(--mono);
        font-size: 12px;
        font-variant-numeric: tabular-nums;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 1px solid var(--line);
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 0 14px;
        border-radius: 8px 8px 0 0;
        color: var(--muted);
        font-weight: 700;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--surface-2);
        color: var(--ink);
    }
    .stTabs [aria-selected="true"] {
        color: var(--brand);
        background: var(--surface);
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
    }
    [data-testid="stDataFrame"] *,
    [data-testid="stTable"] * {
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stExpander"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        font-weight: 700;
        color: var(--ink);
    }
    div[data-testid="stAlert"] {
        border-radius: 10px;
        border: 1px solid var(--line);
        box-shadow: none;
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 8px;
        border: 1px solid var(--line-strong);
        background: var(--surface);
        color: var(--ink);
        font-weight: 700;
        box-shadow: none;
    }
    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: var(--brand);
        color: var(--brand);
        background: var(--surface);
    }
    .stButton > button:focus,
    .stDownloadButton > button:focus {
        box-shadow: 0 0 0 2px rgba(21, 101, 192, 0.16);
    }

    [data-baseweb="select"] > div,
    .stDateInput input,
    .stTextInput input {
        border-radius: 8px !important;
        border-color: var(--line) !important;
        background: var(--surface) !important;
    }
    .stSlider [data-baseweb="slider"] {
        padding-bottom: 8px;
    }

    @media (max-width: 760px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 1.4rem;
        }
        h1 { font-size: 26px !important; }
        [data-testid="stMetric"] { min-height: 0; }
    }
</style>
"""
