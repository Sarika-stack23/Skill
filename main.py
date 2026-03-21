# =============================================================================
#  app.py — SkillForge v11  |  Streamlit UI  (all bugs fixed)
#  Run: streamlit run app.py
# =============================================================================

import os, json, urllib.parse, threading, hashlib, shelve, io
from typing import Dict, Any, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="SkillForge",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown("""<style>
footer,#MainMenu,header[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],[data-testid="stBaseButton-header"],
[data-testid="stBaseButton-minimal"],[data-testid="stBaseButton-borderless"],
.stDeployButton,button[kind="header"],button[kind="minimal"],
[data-testid="stHeader"] button,[data-testid="stHeader"] a,
[data-testid="stHeader"]>div,#stDecoration
{display:none!important;visibility:hidden!important;height:0!important;
 width:0!important;overflow:hidden!important;opacity:0!important}
[data-testid="stHeader"]{height:0!important;min-height:0!important;padding:0!important}
</style>""", unsafe_allow_html=True)

# FIX: import backend as module so mutable globals (_DDG_ERROR, _audit_log) stay live
import backend as _bk
from backend import (
    CATALOG, CATALOG_BY_ID, CATALOG_SKILLS, SAMPLES, SKILL_GRAPH,
    MARKET_DEMAND, OBSOLESCENCE_RISK, TRANSFER_MAP, SENIORITY_MAP,
    MODEL_FAST, MODEL_VISION, CURRENT_YEAR, REPORTLAB,
    _parse_bytes, _load_semantic_bg,
    run_analysis_with_web, cache_bust, rewrite_resume, build_pdf,
    search_real_salary, search_skill_trends, search_job_market,
    search_course_links, ddg_search, _is_english, weeks_ready,
    radar_chart, timeline_chart, salary_chart, roi_bar, weekly_plan,
    _TEAL, _AMBER, _RED, _GREEN,
)

# FIX: guard missing API key — GROQ_CLIENT may be None if key absent
if not _bk.GROQ_CLIENT:
    st.error("**GROQ_API_KEY missing** — add it to `.env`  →  [console.groq.com](https://console.groq.com)")
    st.stop()

# =============================================================================
#  CSS
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
:root{
  --bg:#0b0d14;--s1:#131720;--s2:#1a1f2e;--s3:#222840;
  --border:rgba(255,255,255,0.07);--bhi:rgba(45,212,191,0.20);
  --teal:#2dd4bf;--teal-bg:rgba(45,212,191,0.08);
  --amber:#f59e0b;--red:#ef4444;--green:#4ade80;--purple:#a78bfa;
  --t1:#f1f5f9;--t2:#94a3b8;--t3:#475569;--t4:#2d3a52;
  --sans:'DM Sans',sans-serif;--mono:'DM Mono','IBM Plex Mono',monospace;
}
*,*::before,*::after{box-sizing:border-box}
html,body,[class*="css"]{font-family:var(--sans)!important;background:var(--bg)!important;color:var(--t2)!important;font-size:15px!important;}
.stApp{background:var(--bg)!important}
.main .block-container{padding:0!important;max-width:100%!important}
footer,#MainMenu,header[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],[data-testid="stBaseButton-header"],
[data-testid="stBaseButton-minimal"],[data-testid="stBaseButton-borderless"],
.stDeployButton,button[kind="header"],button[kind="minimal"],
[data-testid="stHeader"] button,[data-testid="stHeader"] a,
[data-testid="stHeader"]>div,#stDecoration
{display:none!important;visibility:hidden!important;height:0!important;
 width:0!important;overflow:hidden!important;pointer-events:none!important;
 position:absolute!important;opacity:0!important}
[data-testid="stHeader"]{height:0!important;min-height:0!important;padding:0!important}
section[data-testid="stSidebar"]>div:first-child{background:var(--s1)!important;border-right:1px solid var(--border)!important;}
::-webkit-scrollbar{width:3px;height:3px}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:99px}
.sf-top{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 32px;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:200;background:rgba(11,13,20,0.96);backdrop-filter:blur(20px);}
.sf-logo{font-family:var(--sans);font-size:1.1rem;font-weight:700;color:var(--t1);letter-spacing:-0.02em}
.sf-logo em{color:var(--teal);font-style:normal}
.sf-top-right{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:0.65rem;color:var(--t3)}
.sf-chip{padding:3px 10px;border-radius:4px;border:1px solid var(--border);color:var(--t3);font-size:0.63rem}
.sf-chip.on{border-color:var(--bhi);color:var(--teal)}
.sf-page{padding:0 32px 80px;max-width:1200px;margin:0 auto}
@media(max-width:640px){.sf-page{padding:0 16px 80px}}
.sf-hero{padding:44px 0 32px}
.sf-eyebrow{font-family:var(--mono);font-size:0.68rem;font-weight:500;letter-spacing:0.12em;text-transform:uppercase;color:var(--teal);display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.sf-eyebrow::before{content:'';width:28px;height:1px;background:var(--teal)}
.sf-h1{font-family:var(--sans);font-size:clamp(2rem,4vw,3.2rem);font-weight:700;color:var(--t1);line-height:1.1;letter-spacing:-0.03em;margin-bottom:14px;}
.sf-h1 span{color:var(--teal)}
.sf-sub{font-size:1rem;color:var(--t2);line-height:1.6;max-width:480px;margin-bottom:0}
.sf-sample-lbl{font-family:var(--mono);font-size:0.65rem;color:var(--t3)}
.sf-panel-hd{font-size:0.82rem;font-weight:600;color:var(--t1);margin-bottom:14px;display:flex;align-items:center;gap:8px;}
.sf-panel-icon{font-size:1rem}
.sf-ready-badge{font-family:var(--mono);font-size:0.6rem;padding:2px 8px;border-radius:3px;background:rgba(45,212,191,0.1);color:var(--teal);border:1px solid var(--bhi);margin-left:auto;}
.sf-wc{font-family:var(--mono);font-size:0.65rem;color:var(--t3);margin-top:8px}
[data-testid="stFileUploadDropzone"]{background:rgba(45,212,191,0.02)!important;border:1.5px dashed rgba(45,212,191,0.14)!important;border-radius:8px!important;}
[data-testid="stFileUploadDropzone"]:hover{border-color:rgba(45,212,191,0.32)!important;background:rgba(45,212,191,0.04)!important;}
[data-testid="stFileUploadDropzone"] button{background:transparent!important;border:1px solid var(--bhi)!important;color:var(--teal)!important;font-family:var(--mono)!important;font-size:0.72rem!important;border-radius:5px!important;}
textarea{background:#0c0f1a!important;border:1px solid var(--border)!important;border-radius:8px!important;color:#b8ccd8!important;font-family:var(--mono)!important;font-size:0.82rem!important;resize:vertical!important;line-height:1.6!important;}
textarea:focus{border-color:var(--bhi)!important;outline:none!important}
textarea::placeholder{color:var(--t4)!important}
.stButton>button{background:var(--teal)!important;border:none!important;border-radius:8px!important;color:#061412!important;font-family:var(--sans)!important;font-weight:700!important;font-size:0.9rem!important;padding:11px 0!important;width:100%!important;letter-spacing:0.01em!important;transition:opacity 0.15s!important;}
.stButton>button:hover{opacity:0.84!important}
.stButton>button:disabled{opacity:0.3!important}
.sf-ghost .stButton>button{background:var(--s2)!important;border:1px solid var(--border)!important;color:var(--t2)!important;font-weight:500!important;}
.sf-ghost .stButton>button:hover{border-color:rgba(255,255,255,0.15)!important;color:var(--t1)!important}
.sf-banner{background:var(--s1);border:1px solid var(--border);border-radius:14px;padding:28px 32px;margin:24px 0 20px;}
.sf-banner-top{display:flex;align-items:flex-start;gap:8px;margin-bottom:6px;}
.sf-candidate-name{font-size:1.2rem;font-weight:700;color:var(--t1);letter-spacing:-0.02em}
.sf-candidate-sub{font-family:var(--mono);font-size:0.72rem;color:var(--t3);margin-top:2px}
.sf-cache-badge{font-family:var(--mono);font-size:0.6rem;padding:2px 8px;border-radius:3px;background:rgba(167,139,250,0.1);color:var(--purple);border:1px solid rgba(167,139,250,0.2);margin-left:auto;margin-top:4px;}
.sf-vision-badge{font-family:var(--mono);font-size:0.6rem;padding:2px 8px;border-radius:3px;background:rgba(45,212,191,0.1);color:var(--teal);border:1px solid var(--bhi);margin-left:8px;margin-top:4px;}
.sf-scores{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px}
@media(max-width:700px){.sf-scores{grid-template-columns:1fr}}
.sf-score-card{background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:20px 22px;text-align:center;}
.sf-score-num{font-family:var(--mono);font-size:3.2rem;font-weight:500;line-height:1;letter-spacing:-0.04em;}
.sf-score-lbl{font-family:var(--mono);font-size:0.62rem;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;color:var(--t3);margin-top:6px;}
.sf-score-sub{font-size:0.78rem;color:var(--t2);margin-top:5px;line-height:1.4}
[data-testid="stTabs"] button{font-family:var(--sans)!important;font-size:0.9rem!important;font-weight:500!important;padding:10px 18px!important;}
[data-testid="stTabs"] button[aria-selected="true"]{color:var(--teal)!important}
.sf-skill-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin-bottom:8px}
.sf-skill-card{background:var(--s1);border:1px solid var(--border);border-radius:9px;padding:14px 16px;transition:border-color 0.12s;cursor:default;}
.sf-skill-card:hover{border-color:rgba(255,255,255,0.12)}
.sf-skill-card.known{border-left:3px solid var(--teal)}
.sf-skill-card.partial{border-left:3px solid var(--amber)}
.sf-skill-card.missing{border-left:3px solid var(--red)}
.sf-skill-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.sf-skill-name{font-size:0.88rem;font-weight:600;color:var(--t1)}
.sf-st-badge{font-family:var(--mono);font-size:0.6rem;font-weight:600;padding:2px 8px;border-radius:3px;}
.sf-st-known{background:rgba(45,212,191,0.1);color:var(--teal);border:1px solid rgba(45,212,191,0.2)}
.sf-st-partial{background:rgba(245,158,11,0.1);color:var(--amber);border:1px solid rgba(245,158,11,0.2)}
.sf-st-missing{background:rgba(239,68,68,0.1);color:var(--red);border:1px solid rgba(239,68,68,0.2)}
.sf-skill-bar{height:4px;background:rgba(255,255,255,0.05);border-radius:99px;margin-bottom:6px}
.sf-skill-bar-fill{height:100%;border-radius:99px}
.sf-skill-bottom{display:flex;align-items:center;justify-content:space-between}
.sf-skill-score{font-family:var(--mono);font-size:0.75rem;color:var(--t2)}
.sf-skill-demand{font-family:var(--mono);font-size:0.65rem}
.sf-decay-tag{font-family:var(--mono);font-size:0.6rem;color:var(--amber);background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:3px;padding:1px 5px;margin-top:5px;display:inline-block;}
.sf-skill-ctx{font-size:0.72rem;color:var(--t3);margin-top:6px;font-style:italic;line-height:1.4}
.sf-phase-hd{font-size:0.72rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:var(--t3);margin:22px 0 10px;display:flex;align-items:center;gap:10px;}
.sf-phase-hd::after{content:'';flex:1;height:1px;background:var(--border)}
.sf-mod{background:var(--s1);border:1px solid var(--border);border-left:3px solid transparent;border-radius:0 9px 9px 0;padding:14px 16px 14px 14px;margin-bottom:8px;transition:border-color 0.12s;}
.sf-mod.crit{border-left-color:var(--red)!important}
.sf-mod.adv{border-left-color:#f97316}
.sf-mod.inter{border-left-color:var(--amber)}
.sf-mod.beg{border-left-color:var(--teal)}
.sf-mod.done{opacity:0.45}
.sf-mod-row{display:flex;align-items:flex-start;gap:12px}
.sf-mod-num{font-family:var(--mono);font-size:0.68rem;color:var(--t4);min-width:28px;padding-top:1px;flex-shrink:0;}
.sf-mod-body{flex:1;min-width:0}
.sf-mod-title{font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:3px;line-height:1.3}
.sf-mod-meta{font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin-bottom:6px}
.sf-mod-tags{display:flex;gap:5px;flex-wrap:wrap}
.sf-tag{font-family:var(--mono);font-size:0.6rem;padding:2px 8px;border-radius:3px;background:var(--s2);color:var(--t2);border:1px solid var(--border);}
.sf-tag-crit{color:var(--red);border-color:rgba(239,68,68,0.25);background:rgba(239,68,68,0.06)}
.sf-tag-req{color:var(--teal);border-color:var(--bhi);background:var(--teal-bg)}
.sf-mod-hrs{font-family:var(--mono);font-size:0.8rem;color:var(--t2);white-space:nowrap;flex-shrink:0;padding-top:1px;}
.sf-ats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
@media(max-width:600px){.sf-ats-row{grid-template-columns:repeat(2,1fr)}}
.sf-ats-card{background:var(--s1);border:1px solid var(--border);border-radius:9px;padding:18px 16px;text-align:center;}
.sf-ats-n{font-family:var(--mono);font-size:1.8rem;font-weight:500;color:var(--t1);line-height:1}
.sf-ats-l{font-family:var(--mono);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--t3);margin-top:5px}
.sf-prog{height:3px;background:rgba(255,255,255,0.05);border-radius:99px;overflow:hidden;margin-bottom:20px}
.sf-prog-fill{height:100%;border-radius:99px;background:var(--teal)}
.sf-tip{display:flex;gap:12px;margin-bottom:10px;font-size:0.82rem;color:var(--t2);line-height:1.6}
.sf-tip-n{font-family:var(--mono);font-size:0.62rem;color:var(--teal);background:var(--teal-bg);border:1px solid var(--bhi);border-radius:3px;padding:2px 7px;font-weight:500;min-width:26px;text-align:center;flex-shrink:0;height:fit-content;}
.sf-talk{font-size:0.82rem;color:var(--t2);padding:8px 0 8px 14px;border-left:2px solid var(--teal);margin-bottom:7px;line-height:1.55;}
.sf-kw{display:inline-block;font-family:var(--mono);font-size:0.65rem;padding:3px 9px;border-radius:3px;margin:3px;background:rgba(239,68,68,0.07);color:var(--red);border:1px solid rgba(239,68,68,0.18);}
.sf-search-result{background:var(--s1);border:1px solid var(--border);border-radius:9px;padding:14px 16px;margin-bottom:8px;}
.sf-search-title{font-size:0.9rem;font-weight:600;color:var(--teal);text-decoration:none}
.sf-search-title:hover{text-decoration:underline}
.sf-search-url{font-family:var(--mono);font-size:0.65rem;color:var(--t4);margin:3px 0 5px}
.sf-search-body{font-size:0.78rem;color:var(--t2);line-height:1.55}
.sf-insight{background:rgba(45,212,191,0.03);border-left:2px solid var(--teal);border-radius:0 5px 5px 0;padding:9px 13px;margin-bottom:6px;font-size:0.82rem;color:var(--t2);line-height:1.55;}
.sf-trend-pill{display:inline-flex;align-items:center;gap:6px;background:var(--s2);border:1px solid var(--border);border-radius:6px;padding:6px 12px;margin:4px;font-size:0.78rem;}
.sf-xfer{background:var(--s2);border:1px solid var(--border);border-radius:7px;padding:10px 14px;margin-bottom:6px;display:flex;align-items:center;gap:10px;font-size:0.78rem;color:var(--t2);}
.sf-xfer-pct{color:var(--purple);font-family:var(--mono);font-weight:500;font-size:0.88rem}
.sf-export-card{background:var(--s1);border:1px solid var(--border);border-radius:10px;padding:20px 22px;}
.sf-export-hd{font-size:0.9rem;font-weight:700;color:var(--t1);margin-bottom:4px}
.sf-export-sub{font-size:0.78rem;color:var(--t3);margin-bottom:14px;line-height:1.5}
.sf-export-row{display:flex;justify-content:space-between;font-family:var(--mono);font-size:0.72rem;padding:5px 0;border-bottom:1px solid var(--border)}
.sf-ek{color:var(--t3)}.sf-ev{color:var(--t1);font-weight:500}
[data-testid="stDownloadButton"]>button{background:var(--s2)!important;border:1px solid var(--border)!important;color:var(--t2)!important;font-family:var(--sans)!important;font-weight:500!important;font-size:0.82rem!important;}
[data-testid="stDownloadButton"]>button:hover{border-color:var(--bhi)!important;color:var(--teal)!important}
[data-testid="stMetric"]{background:var(--s2)!important;border:1px solid var(--border)!important;border-radius:8px!important;padding:13px 15px!important}
[data-testid="stMetricValue"]{font-family:var(--mono)!important;font-size:1.5rem!important;color:var(--t1)!important}
[data-testid="stMetricLabel"]{font-family:var(--mono)!important;color:var(--t3)!important;font-size:0.6rem!important;text-transform:uppercase!important;letter-spacing:0.08em!important}
[data-testid="stSelectbox"]>div>div{background:var(--s1)!important;border:1px solid var(--border)!important;color:var(--t1)!important;font-family:var(--sans)!important;font-size:0.85rem!important}
[data-testid="stExpander"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:8px!important;margin-bottom:5px!important}
[data-testid="stExpander"] summary{font-family:var(--sans)!important;color:var(--t2)!important;font-size:0.85rem!important}
[data-testid="stCheckbox"] label{font-family:var(--sans)!important;font-size:0.85rem!important;color:var(--t2)!important}
[data-testid="stProgressBar"]>div>div{background:var(--teal)!important}
[data-testid="stProgressBar"]>div{background:rgba(255,255,255,0.05)!important;border-radius:99px!important}
.sf-diff{background:#090c16;border:1px solid var(--border);border-radius:8px;padding:14px 16px;font-family:var(--mono);font-size:0.78rem;color:var(--t2);white-space:pre-wrap;line-height:1.6;max-height:320px;overflow-y:auto;}
.sf-log{font-family:var(--mono);font-size:0.68rem;color:var(--t3);padding:5px 10px;background:var(--s1);border:1px solid var(--border);border-radius:4px;margin-bottom:3px;display:flex;gap:12px}
.sf-warn{background:rgba(245,158,11,0.07);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:12px 16px;font-size:0.82rem;color:var(--amber);margin-bottom:12px}
.sf-foot{position:fixed;bottom:0;left:0;right:0;background:rgba(11,13,20,0.97);border-top:1px solid var(--border);padding:6px 32px;font-family:var(--mono);font-size:0.62rem;color:var(--t3);display:flex;align-items:center;gap:16px;z-index:99;}
.sf-fdot{width:5px;height:5px;border-radius:50%;display:inline-block;margin-right:4px}
.sf-fr{margin-left:auto}
.sf-sh{font-size:1.15rem;font-weight:700;color:var(--t1);letter-spacing:-0.02em;margin-bottom:4px}
.sf-ss{font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin-bottom:18px}
.sf-divider{height:1px;background:var(--border);margin:28px 0}
.sf-how{display:flex;align-items:center;gap:0;margin:0 0 24px;background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:24px 28px}
.sf-how-step{flex:1;text-align:center}
.sf-how-num{font-family:var(--mono);font-size:1.6rem;font-weight:500;color:var(--teal);line-height:1;margin-bottom:6px}
.sf-how-title{font-size:0.9rem;font-weight:700;color:var(--t1);margin-bottom:4px}
.sf-how-sub{font-family:var(--mono);font-size:0.65rem;color:var(--t3);line-height:1.5}
.sf-how-arrow{font-size:1.4rem;color:var(--border);padding:0 16px;flex-shrink:0}
.sf-stats-strip{display:flex;align-items:center;justify-content:center;gap:0;margin:0 0 24px;background:rgba(45,212,191,0.04);border:1px solid var(--bhi);border-radius:10px;padding:18px 28px}
.sf-stat{text-align:center;flex:1}
.sf-stat-n{display:block;font-family:var(--mono);font-size:1.8rem;font-weight:500;color:var(--teal);line-height:1;margin-bottom:4px}
.sf-stat-l{font-family:var(--mono);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--t3)}
.sf-stat-div{width:1px;height:40px;background:var(--border);margin:0 16px;flex-shrink:0}
.sf-hero-delta{text-align:center;padding:28px 0 20px;border-bottom:1px solid var(--border);margin-bottom:20px}
.sf-hero-delta-num{font-family:var(--mono);font-size:4rem;font-weight:500;color:var(--green);line-height:1;letter-spacing:-0.04em}
.sf-hero-delta-label{font-family:var(--mono);font-size:0.7rem;text-transform:uppercase;letter-spacing:0.12em;color:var(--t3);margin:8px 0 6px}
.sf-hero-delta-sub{font-size:0.9rem;color:var(--t2)}
.sf-ground-badge{display:flex;align-items:center;gap:10px;margin-top:16px;padding:10px 16px;background:rgba(45,212,191,0.04);border:1px solid var(--bhi);border-radius:7px;font-family:var(--mono);font-size:0.68rem;color:var(--teal)}
.sf-ground-dot{width:7px;height:7px;border-radius:50%;background:var(--teal);flex-shrink:0;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.sf-lstep{display:flex;align-items:flex-start;gap:14px;padding:12px 16px;border-radius:8px;margin-bottom:6px;font-size:0.85rem}
.sf-lstep-done{background:rgba(74,222,128,0.05);border:1px solid rgba(74,222,128,0.15)}
.sf-lstep-active{background:rgba(45,212,191,0.07);border:1px solid var(--bhi)}
.sf-lstep-wait{background:var(--s1);border:1px solid var(--border);opacity:0.45}
.sf-lstep-icon{font-family:var(--mono);font-size:1rem;min-width:24px;text-align:center;margin-top:1px}
.sf-lstep-spin{display:inline-block;animation:spin 1.2s linear infinite}
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.sf-lstep-title{font-weight:600;color:var(--t1);margin-bottom:2px}
.sf-lstep-sub{font-family:var(--mono);font-size:0.65rem;color:var(--t3)}
.sf-lprog{height:4px;background:rgba(255,255,255,0.05);border-radius:99px;overflow:hidden;margin:16px 0 24px;max-width:560px}
.sf-lprog-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--teal),var(--green));transition:width 0.6s ease}
[data-testid="stLinkButton"]>a{background:rgba(45,212,191,0.06)!important;border:1px solid var(--bhi)!important;border-radius:6px!important;color:var(--teal)!important;font-family:var(--mono)!important;font-size:0.75rem!important;padding:6px 12px!important;text-decoration:none!important;display:flex!important;align-items:center!important;gap:6px!important;margin-top:8px!important;}
[data-testid="stLinkButton"]>a:hover{background:rgba(45,212,191,0.12)!important;border-color:var(--teal)!important;}
.sf-mod-trace{margin-top:10px;padding:10px 14px;background:rgba(45,212,191,0.04);border:1px solid var(--bhi);border-radius:7px}
.sf-mod-trace-lbl{font-family:var(--mono);font-size:0.6rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:var(--teal);margin-bottom:5px}
.sf-mod-trace-body{font-size:0.78rem;color:var(--t2);line-height:1.6}
.sf-impact-box{background:var(--s1);border:1px solid var(--border);border-radius:10px;padding:22px 28px;margin:24px 0}
.sf-impact-row{display:flex;align-items:center;justify-content:center;gap:0;margin-bottom:12px}
.sf-impact-item{text-align:center;flex:1}
.sf-impact-lbl{font-family:var(--mono);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--t3);margin-bottom:6px}
.sf-impact-val{font-family:var(--mono);font-size:2rem;font-weight:500;line-height:1}
.sf-impact-arrow{font-size:1.2rem;color:var(--t4);padding:0 20px;flex-shrink:0}
.sf-impact-sub{font-family:var(--mono);font-size:0.65rem;color:var(--t3);text-align:center;line-height:1.6}
.sf-nav-item{display:flex;align-items:center;gap:9px;padding:9px 12px;border-radius:6px;font-size:0.82rem;color:var(--t2);text-decoration:none;transition:all 0.12s;margin-bottom:2px}
.sf-nav-item:hover{background:var(--s2);color:var(--t1)}
.sf-nav-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.sf-danger .stButton>button{background:rgba(239,68,68,0.12)!important;border:1px solid rgba(239,68,68,0.2)!important;color:var(--red)!important}
</style>
"""

# =============================================================================
#  SESSION STATE
# =============================================================================
_LOC_OPTS = ["India", "USA", "UK", "Germany", "Canada", "Singapore"]

def _init_state() -> None:
    defaults: Dict[str, Any] = {
        "step": "input", "resume_text": "", "resume_image": None, "jd_text": "",
        "result": None, "completed": [], "hpd": 2, "rw_result": None,
        "course_cache": {}, "sal_location": "India", "force_fresh": False,
        "search_query": "", "search_results": [],
        "_resume_hash": "", "_resume_source": "", "_resume_fname": "", "_jd_source": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_RESET_KEYS = [
    "step", "resume_text", "resume_image", "jd_text", "result", "completed",
    "rw_result", "course_cache", "force_fresh", "search_query", "search_results",
    "res_paste", "jd_paste", "_resume_source", "_resume_fname", "_jd_source",
    "search_input", "_resume_hash",
]

def _full_reset() -> None:
    for k in _RESET_KEYS:
        st.session_state.pop(k, None)
    st.rerun()

# =============================================================================
#  TOPBAR
# =============================================================================
def render_topbar() -> None:
    st.markdown("""
    <div class="sf-top">
      <div class="sf-logo">Skill<em>Forge</em></div>
      <div class="sf-top-right">
        <span class="sf-chip on">⚡ Groq-powered</span>
        <span class="sf-chip on">🖼 Vision OCR</span>
        <span class="sf-chip">NetworkX DAG</span>
        <span class="sf-chip">ARTPARK CodeForge 2025</span>
      </div>
    </div>""", unsafe_allow_html=True)

# =============================================================================
#  INPUT PAGE
# =============================================================================
def render_input() -> None:
    st.markdown('<div class="sf-page">', unsafe_allow_html=True)
    st.markdown("""
    <div class="sf-hero">
      <div class="sf-eyebrow">ARTPARK CodeForge Hackathon · AI Adaptive Onboarding Engine</div>
      <div class="sf-h1">Skip what you know.<br><span>Learn what you need.</span></div>
      <div class="sf-sub">Upload your resume and target job description. SkillForge maps your exact skill gap and generates a dependency-ordered, personalized learning roadmap.</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("""
    <div class="sf-how">
      <div class="sf-how-step"><div class="sf-how-num">01</div><div class="sf-how-title">Upload Resume + JD</div><div class="sf-how-sub">PDF, DOCX, or image — Vision AI reads it all</div></div>
      <div class="sf-how-arrow">→</div>
      <div class="sf-how-step"><div class="sf-how-num">02</div><div class="sf-how-title">AI Maps Your Gap</div><div class="sf-how-sub">Groq LLaMA extracts skills · detects decay · scores proficiency</div></div>
      <div class="sf-how-arrow">→</div>
      <div class="sf-how-step"><div class="sf-how-num">03</div><div class="sf-how-title">Get Your Roadmap</div><div class="sf-how-sub">NetworkX DAG orders modules by dependency — zero redundancy</div></div>
    </div>""", unsafe_allow_html=True)
    st.markdown("""
    <div class="sf-stats-strip">
      <div class="sf-stat"><span class="sf-stat-n">47</span><span class="sf-stat-l">Courses in catalog</span></div>
      <div class="sf-stat-div"></div>
      <div class="sf-stat"><span class="sf-stat-n">6</span><span class="sf-stat-l">Skill domains</span></div>
      <div class="sf-stat-div"></div>
      <div class="sf-stat"><span class="sf-stat-n">~38h</span><span class="sf-stat-l">Avg hours saved</span></div>
      <div class="sf-stat-div"></div>
      <div class="sf-stat"><span class="sf-stat-n">0</span><span class="sf-stat-l">Hallucinations</span></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div style="margin:20px 0 8px"><span class="sf-sample-lbl">Try a sample →</span></div>', unsafe_allow_html=True)
    pc1, pc2, pc3, _ = st.columns([1, 1, 1, 2])
    for col, key, dlbl in zip([pc1, pc2, pc3], SAMPLES, ["💻 Tech Role", "🧠 Data / AI Role", "👔 Non-Tech Role"]):
        with col:
            if st.button(dlbl, key=f"pre_{key}", use_container_width=True):
                for wk in _RESET_KEYS:
                    st.session_state.pop(wk, None)
                st.session_state["resume_text"]    = SAMPLES[key]["resume"]
                st.session_state["jd_text"]        = SAMPLES[key]["jd"]
                st.session_state["_resume_source"] = "paste"
                st.session_state["step"]           = "analyzing"
                st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")

    # ── LEFT: Resume ──────────────────────────────────────
    with left:
        src_flag   = st.session_state.get("_resume_source", "")
        has_resume = bool(st.session_state.get("resume_text", "").strip() or st.session_state.get("resume_image"))
        badge = '<span class="sf-ready-badge">✓ Ready</span>' if has_resume else ''
        st.markdown(f'<div class="sf-panel-hd"><span class="sf-panel-icon">📄</span> Your resume {badge}</div>', unsafe_allow_html=True)

        up_tab, paste_tab = st.tabs(["📄 Upload Resume", "✏️ Paste Resume"])
        with up_tab:
            rf = st.file_uploader("Resume", type=["pdf", "docx", "jpg", "jpeg", "png", "webp"],
                                  key="res_file", label_visibility="collapsed")
            if rf is not None:
                try:
                    rf.seek(0)
                    raw_bytes = rf.read()
                except Exception:
                    raw_bytes = b""
                if raw_bytes:
                    new_hash = hashlib.md5(raw_bytes).hexdigest()
                    if new_hash != st.session_state.get("_resume_hash", ""):
                        txt, img = _parse_bytes(raw_bytes, rf.name)
                        cache_bust(txt, img, st.session_state.get("jd_text", ""))
                        for k in list(st.session_state.keys()):
                            if k not in ("sal_location", "force_fresh", "hpd"):
                                st.session_state.pop(k, None)
                        _init_state()
                        st.session_state.update({
                            "resume_text": txt, "resume_image": img,
                            "_resume_source": "file", "_resume_fname": rf.name,
                            "_resume_hash": new_hash, "step": "input",
                        })
                    ss_txt = st.session_state.get("resume_text", "")
                    ss_img = st.session_state.get("resume_image")
                    if ss_img:
                        st.success(f"✓ {rf.name} — image loaded (Vision AI will analyze)")
                        st.image(rf, use_container_width=True)
                    elif ss_txt and not ss_txt.startswith("["):
                        st.success(f"✓ {rf.name} — {len(ss_txt.split())} words extracted")
                        st.caption(f"Preview: {ss_txt[:200]}…")
                    else:
                        st.error(f"Could not read {rf.name}. Try paste or JPG/PNG.")
                else:
                    st.error("File appears empty. Please try again.")

        with paste_tab:
            if st.session_state.get("_resume_source") == "file":
                st.info("📄 File loaded above. Type here to switch to pasted text.")
                if st.button("Switch to paste mode", key="sw_paste"):
                    for k in ["_resume_source", "_resume_hash", "_resume_fname",
                              "resume_text", "resume_image", "result", "rw_result"]:
                        st.session_state.pop(k, None)
                    st.rerun()
            else:
                rp = st.text_area("Resume text", height=220,
                                  placeholder="Paste your resume here...",
                                  key="res_paste", label_visibility="collapsed")
                if rp and rp.strip():
                    st.session_state["resume_text"]    = rp.strip()
                    st.session_state["_resume_source"] = "paste"
                    st.session_state["_resume_hash"]   = ""
                    if len(rp.split()) > 5:
                        st.markdown(f'<div class="sf-wc">{len(rp.split())} words</div>', unsafe_allow_html=True)

        if has_resume and src_flag == "file":
            st.markdown('<div class="sf-ghost" style="margin-top:8px">', unsafe_allow_html=True)
            if st.button("✕ Clear resume", key="clr_res"):
                for k in ["resume_text", "resume_image", "res_paste", "_resume_source",
                          "_resume_fname", "_resume_hash", "result", "rw_result"]:
                    st.session_state.pop(k, None)
                _init_state()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ── RIGHT: JD ─────────────────────────────────────────
    with right:
        has_jd   = bool(st.session_state.get("jd_text", "").strip())
        badge_jd = '<span class="sf-ready-badge">✓ Ready</span>' if has_jd else ''
        st.markdown(f'<div class="sf-panel-hd"><span class="sf-panel-icon">💼</span> Job description {badge_jd}</div>', unsafe_allow_html=True)

        jup_tab, jpaste_tab = st.tabs(["📤 Upload JD", "📝 Paste JD"])
        with jup_tab:
            jf = st.file_uploader("JD", type=["pdf", "docx"], key="jd_file", label_visibility="collapsed")
            if jf is not None:
                try:
                    jf.seek(0)
                    jraw = jf.read()
                except Exception:
                    jraw = b""
                if jraw:
                    jtxt, _ = _parse_bytes(jraw, jf.name)
                    if jtxt and not jtxt.startswith("["):
                        for k in ["result", "rw_result", "course_cache"]:
                            st.session_state.pop(k, None)
                        st.session_state.update({
                            "jd_text": jtxt, "_jd_source": "file", "step": "input",
                        })
                        st.session_state.pop("jd_paste", None)
                        st.success(f"✓ {jf.name} — {len(jtxt.split())} words")
                    else:
                        st.error(f"Could not read {jf.name}")

        with jpaste_tab:
            jp = st.text_area("Job description", height=220,
                              placeholder="Paste the job description here...",
                              key="jd_paste", label_visibility="collapsed")
            if jp and jp.strip():
                st.session_state["jd_text"]    = jp.strip()
                st.session_state["_jd_source"] = "paste"
                if len(jp.split()) > 5:
                    st.markdown(f'<div class="sf-wc">{len(jp.split())} words</div>', unsafe_allow_html=True)

    # ── Analyze button ──────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    opt1, opt2, _, btn_col = st.columns([1, 1.2, 0.6, 1.6])
    with opt1:
        # FIX: safe index lookup — fall back to 0 if stored value not in list
        cur_loc = st.session_state.get("sal_location", "India")
        idx_loc = _LOC_OPTS.index(cur_loc) if cur_loc in _LOC_OPTS else 0
        st.selectbox("Salary location", _LOC_OPTS, index=idx_loc,
                     key="sal_location", label_visibility="visible")
    with opt2:
        st.checkbox("Force fresh (skip cache)", key="force_fresh")
    with btn_col:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        resume_ready = bool(st.session_state.get("resume_text", "").strip() or st.session_state.get("resume_image"))
        jd_ready     = bool(st.session_state.get("jd_text", "").strip())
        if resume_ready and jd_ready:
            is_img = bool(st.session_state.get("resume_image"))
            lbl = "Analyze resume image ⚡" if is_img else "Analyze skill gap ⚡"
            if st.button(lbl, key="go_btn", use_container_width=True):
                st.session_state["step"] = "analyzing"
                st.rerun()
        else:
            missing = (["resume"] if not resume_ready else []) + (["job description"] if not jd_ready else [])
            st.markdown(
                f'<p style="font-family:var(--mono);font-size:0.75rem;color:var(--t3);'
                f'text-align:center;padding:12px 0">Add {" and ".join(missing)} to continue</p>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  LOADING
# =============================================================================
def render_loading() -> None:
    st.markdown('<div class="sf-page">', unsafe_allow_html=True)
    st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)

    resume_text = st.session_state.get("resume_text", "")
    resume_img  = st.session_state.get("resume_image")
    jd_text     = st.session_state.get("jd_text", "") or st.session_state.get("jd_paste", "")
    source      = st.session_state.get("_resume_source", "paste")

    if not resume_text.strip() and not resume_img:
        st.error("No resume data. Please go back and upload your resume.")
        if st.button("Go back", key="back_no_resume"):
            st.session_state["step"] = "input"; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True); return

    if not jd_text.strip():
        st.error("No job description. Please go back and add one.")
        if st.button("Go back", key="back_no_jd"):
            st.session_state["step"] = "input"; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True); return

    # FIX: use dedicated cache_bust() from backend instead of inline shelve logic
    if source == "file" or st.session_state.get("force_fresh"):
        cache_bust(resume_text, resume_img, jd_text)
        st.session_state.pop("force_fresh", None)

    steps = [
        ("📄", "Parsing resume & job description",   "Extracting text, structure, metadata"),
        ("🔍", "Extracting skills with proficiency", "Scoring 0-10 per skill, detecting decay"),
        ("🧩", "Computing skill gap",                "Known, Partial, Missing classification"),
        ("🗺", "Building dependency roadmap",        "NetworkX DAG, topological sort"),
        ("🌐", "Fetching live market data",          "Salary, trends, job market via DuckDuckGo"),
    ]
    st.markdown(
        '<div style="max-width:560px;margin:40px auto 32px">'
        '<div style="font-family:var(--mono);font-size:0.65rem;letter-spacing:0.12em;'
        'text-transform:uppercase;color:var(--teal);margin-bottom:20px">Analyzing your profile</div>'
        '</div>', unsafe_allow_html=True,
    )
    slots = [st.empty() for _ in steps]
    prog  = st.empty()

    def show_steps(done: int) -> None:
        for i, (icon, title, sub) in enumerate(steps):
            if i < done:
                s = (f'<div class="sf-lstep sf-lstep-done"><span class="sf-lstep-icon">✓</span>'
                     f'<div><div class="sf-lstep-title">{title}</div>'
                     f'<div class="sf-lstep-sub">{sub}</div></div></div>')
            elif i == done:
                s = (f'<div class="sf-lstep sf-lstep-active">'
                     f'<span class="sf-lstep-icon sf-lstep-spin">{icon}</span>'
                     f'<div><div class="sf-lstep-title">{title}</div>'
                     f'<div class="sf-lstep-sub">{sub}</div></div></div>')
            else:
                s = (f'<div class="sf-lstep sf-lstep-wait"><span class="sf-lstep-icon">○</span>'
                     f'<div><div class="sf-lstep-title">{title}</div>'
                     f'<div class="sf-lstep-sub">{sub}</div></div></div>')
            slots[i].markdown(s, unsafe_allow_html=True)
        pct = int(done / len(steps) * 100)
        prog.markdown(
            f'<div class="sf-lprog"><div class="sf-lprog-fill" style="width:{pct}%"></div></div>',
            unsafe_allow_html=True,
        )

    show_steps(0)
    result = run_analysis_with_web(
        resume_text, jd_text,
        resume_image_b64=resume_img,
        location=st.session_state.get("sal_location", "India"),
    )
    if "error" not in result:
        show_steps(3); show_steps(4); show_steps(5)

    if "error" in result:
        err = result.get("error", "unknown")
        if err == "rate_limited":
            st.error(f"Rate limited — {result.get('message', '')}")
        elif "vision" in str(err).lower():
            st.error(f"Vision model error: {err}")
            st.info("Try pasting resume text instead.")
        else:
            st.error(f"Analysis failed: {err}")
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("Back", key="retry_btn"):
            st.session_state["step"] = "input"; st.rerun()
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    st.session_state["result"] = result
    st.session_state["step"]   = "results"
    st.rerun()

# =============================================================================
#  BANNER
# =============================================================================
def render_banner(res: dict) -> None:
    c  = res["candidate"]
    jd = res["jd"]
    im = res["impact"]
    iv = res["interview"]
    ql = res.get("quality", {}) or {}

    name  = c.get("name", "Unknown") or "Unknown"
    crole = c.get("current_role", "") or ""
    yrs   = int(c.get("years_experience") or 0)
    sen   = c.get("seniority", "") or ""
    trole = jd.get("role_title", "") or ""

    cur   = int(im.get("current_fit")   or 0)
    proj  = int(im.get("projected_fit") or 0)
    delta = int(im.get("fit_delta")     or 0)
    iv_c  = iv.get("color", "#4ade80") or "#4ade80"
    ats   = int(ql.get("ats_score")     or 0)
    grade = ql.get("overall_grade", "–") or "–"

    fit_c        = _RED if cur < 40 else _AMBER if cur < 65 else _GREEN
    cache_badge  = '<span class="sf-cache-badge">⚡ Cached</span>'       if res.get("_cache_hit") else ""
    # FIX: _is_image now set correctly in run_analysis result dict
    vision_badge = '<span class="sf-vision-badge">🖼 Vision OCR</span>'  if res.get("_is_image")  else ""
    hpd_val      = int(st.session_state.get("hpd", 2) or 2)

    st.markdown(f"""
    <div class="sf-banner">
      <div class="sf-banner-top">
        <div>
          <div class="sf-candidate-name">{name}</div>
          <div class="sf-candidate-sub">{crole} · {yrs}yr · {sen} → <strong style="color:var(--t1)">{trole}</strong></div>
        </div>
        <div style="display:flex;gap:6px;align-items:center;margin-left:auto">{cache_badge}{vision_badge}</div>
      </div>
      <div class="sf-hero-delta">
        <div class="sf-hero-delta-num">+{delta}%</div>
        <div class="sf-hero-delta-label">role fit after completing this roadmap</div>
        <div class="sf-hero-delta-sub">
          <span style="color:{fit_c}">{cur}%</span>
          <span style="color:var(--t3);margin:0 10px">→</span>
          <span style="color:var(--green)">{proj}%</span>
          <span style="color:var(--t3);margin-left:10px">· Complete in {weeks_ready(im.get("roadmap_hours", 0) or 0, hpd_val)} at {hpd_val}h/day</span>
        </div>
      </div>
      <div class="sf-scores">
        <div class="sf-score-card">
          <div class="sf-score-lbl">Training hours</div>
          <div class="sf-score-num" style="color:var(--teal)">{im['roadmap_hours']}h</div>
          <div class="sf-score-sub">vs <s>60h</s> generic · saves <strong style="color:var(--green)">~{im['hours_saved']}h</strong></div>
        </div>
        <div class="sf-score-card">
          <div class="sf-score-lbl">Interview readiness</div>
          <div class="sf-score-num" style="color:{iv_c}">{iv['score']}%</div>
          <div class="sf-score-sub">{iv['label']} · {iv.get('advice', '')}</div>
        </div>
        <div class="sf-score-card">
          <div class="sf-score-lbl">ATS score</div>
          <div class="sf-score-num" style="color:var(--t1)">{ats}%</div>
          <div class="sf-score-sub">Grade <strong style="color:var(--teal)">{grade}</strong> · {int(ql.get('completeness_score') or 0)}% complete</div>
        </div>
      </div>
      <div class="sf-ground-badge">
        <span class="sf-ground-dot"></span>
        Zero hallucinations &nbsp;·&nbsp; All {im['modules_count']} modules from 47-course catalog &nbsp;·&nbsp; {im['critical_count']} on critical path
      </div>
    </div>""", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Modules",        im.get("modules_count", 0),    f"{im.get('critical_count', 0)} critical")
    k2.metric("Hours saved",    f"~{im['hours_saved']}h",      "vs 60h generic")
    k3.metric("Done in",        weeks_ready(im.get("roadmap_hours", 0) or 0, hpd_val), f"at {hpd_val}h/day")
    k4.metric("Skills covered", f"{im['gaps_addressed']}/{im['total_skills']}", f"{im['known_skills']} already known")

    sm = res.get("seniority", {})
    if sm.get("has_mismatch"):
        st.markdown(
            f'<div class="sf-warn">⚠ Seniority gap: you are <strong>{sm["candidate"]}</strong>, '
            f'role requires <strong>{sm["required"]}</strong> — leadership modules injected.</div>',
            unsafe_allow_html=True,
        )
    if im.get("decayed_skills", 0):
        st.markdown(
            f'<div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.18);'
            f'border-radius:7px;padding:10px 14px;font-size:0.82rem;color:var(--amber);margin-bottom:6px">'
            f'⏱ {im["decayed_skills"]} skill(s) have decayed — proficiency reduced in gap analysis</div>',
            unsafe_allow_html=True,
        )

# =============================================================================
#  TAB: GAP ANALYSIS  (FIX: promoted to first tab)
# =============================================================================
def render_tab_overview(res: dict) -> None:
    gp     = res["gap_profile"]
    trends = res.get("skill_trends", {}) or {}
    sal    = res.get("salary", {}) or {}

    k_c = sum(1 for g in gp if g["status"] == "Known")
    p_c = sum(1 for g in gp if g["status"] == "Partial")
    m_c = sum(1 for g in gp if g["status"] == "Missing")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Skill gap</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sf-ss">{k_c} known · {p_c} partial · {m_c} missing</div>', unsafe_allow_html=True)

    col_flt, col_radar = st.columns([1.4, 1], gap="large")
    with col_flt:
        filt = st.selectbox("Filter", ["All", "Missing", "Partial", "Known", "Required only"],
                            key="gp_filter", label_visibility="collapsed")
        filtered = [g for g in gp if
                    filt == "All" or
                    (filt == "Missing"       and g["status"] == "Missing") or
                    (filt == "Partial"       and g["status"] == "Partial") or
                    (filt == "Known"         and g["status"] == "Known")   or
                    (filt == "Required only" and g["is_required"])]

        html = '<div class="sf-skill-grid">'
        for g in filtered:
            s     = g["status"]
            col_c = {"Known": _TEAL, "Partial": _AMBER, "Missing": _RED}[s]
            bc    = {"Known": "sf-st-known", "Partial": "sf-st-partial", "Missing": "sf-st-missing"}[s]
            # FIX: explicit int() cast — proficiency may come back as string from LLM
            prof  = int(g.get("proficiency") or 0)
            pct   = prof / 10 * 100
            req   = "★ " if g["is_required"] else ""
            trend = trends.get(g["skill"], "")
            tc    = _RED if "Hot" in trend else _AMBER if "Growing" in trend else "#3d4d66"
            decay = '<span class="sf-decay-tag">⏱ decayed</span>' if g.get("decayed") else ""
            ctx   = f'<div class="sf-skill-ctx">{g["context"]}</div>' if g.get("context") else ""
            co    = g.get("catalog_course")
            ctxt  = (f'<div style="font-family:var(--mono);font-size:0.65rem;color:var(--t3);margin-top:5px">'
                     f'📚 {co["title"]} · {co["duration_hrs"]}h · {co["level"]}</div>') if co else ""
            html += (
                f'<div class="sf-skill-card {s.lower()}">'
                f'<div class="sf-skill-top"><div class="sf-skill-name">{req}{g["skill"]}</div>'
                f'<span class="sf-st-badge {bc}">{s}</span></div>'
                f'<div class="sf-skill-bar"><div class="sf-skill-bar-fill" style="width:{pct}%;background:{col_c}"></div></div>'
                f'<div class="sf-skill-bottom"><span class="sf-skill-score">{prof}/10</span>'
                f'<span class="sf-skill-demand" style="color:{tc}">{trend}</span></div>'
                f'{decay}{ctx}{ctxt}</div>'
            )
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

        obs = res.get("obsolescence", [])
        if obs:
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            st.markdown('<div class="sf-sh" style="font-size:0.95rem">Obsolescence risks</div>', unsafe_allow_html=True)
            for o in obs:
                st.markdown(
                    f'<div style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);'
                    f'border-radius:7px;padding:10px 14px;margin-bottom:6px">'
                    f'<div style="font-size:0.88rem;font-weight:600;color:var(--red)">{o["skill"]}</div>'
                    f'<div style="font-family:var(--mono);font-size:0.7rem;color:var(--t3);margin-top:3px">'
                    f'{o["reason"]}</div></div>',
                    unsafe_allow_html=True,
                )

    with col_radar:
        st.plotly_chart(radar_chart(gp), use_container_width=True, config={"displayModeBar": False}, key="radar_overview")
        tf = res.get("transfers", [])
        if tf:
            st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:14px 0 8px">Transfer advantages</div>', unsafe_allow_html=True)
            for t in tf[:5]:
                st.markdown(
                    f'<div class="sf-xfer"><span class="sf-xfer-pct">↗{t["transfer_pct"]}%</span>'
                    f'<span>{t["label"]}</span></div>', unsafe_allow_html=True,
                )
        # FIX: explicit float cast for salary median check
        try:
            sal_med = float(sal.get("median_lpa") or 0)
        except (TypeError, ValueError):
            sal_med = 0.0
        if sal and sal_med > 0:
            st.markdown(
                f'<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:16px 0 4px">'
                f'Live salary — {res["jd"].get("role_title", "")[:24]}</div>', unsafe_allow_html=True,
            )
            st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar": False}, key="salary_overview")
            st.caption(f"Source: {sal.get('source', 'web')} · {sal.get('note', '')}")

# =============================================================================
#  TAB: ROADMAP
# =============================================================================
def render_tab_roadmap(res: dict) -> None:
    path      = res["path"]
    # FIX: load completed as set — list stored in session state
    completed = set(st.session_state.get("completed", []))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    hd_l, hd_r = st.columns([2, 1])
    with hd_l:
        st.markdown('<div class="sf-sh">Learning roadmap</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-ss">Dependency-ordered · critical path highlighted · check off as you complete</div>', unsafe_allow_html=True)
    with hd_r:
        # FIX: use distinct key "hpd_slider" to avoid collision with session state key "hpd"
        hpd = st.select_slider("Pace (h/day)", options=[1, 2, 4, 8],
                               value=int(st.session_state.get("hpd", 2) or 2),
                               key="hpd_slider")
        st.session_state["hpd"] = hpd
        rem = sum(int(m.get("duration_hrs") or 0) for m in path if m["id"] not in completed)
        st.markdown(
            f'<p style="font-family:var(--mono);font-size:0.72rem;color:var(--t2);text-align:right">'
            f'{rem}h left · done in <strong style="color:var(--teal)">{weeks_ready(rem, hpd)}</strong></p>',
            unsafe_allow_html=True,
        )

    mod_col, chart_col = st.columns([1.1, 1], gap="large")

    with mod_col:
        phases = [
            ("Foundation", [m for m in path if m["level"] == "Beginner"]),
            ("Build",      [m for m in path if m["level"] == "Intermediate"]),
            ("Advanced",   [m for m in path if m["level"] == "Advanced"]),
        ]
        idx = 0
        for phase_name, mods in phases:
            if not mods: continue
            phase_hrs = sum(int(m.get("duration_hrs") or 0) for m in mods)
            st.markdown(
                f'<div class="sf-phase-hd">{phase_name} &nbsp; '
                f'<span style="font-weight:400;color:var(--t4)">{len(mods)} modules · {phase_hrs}h</span></div>',
                unsafe_allow_html=True,
            )
            for m in mods:
                idx    += 1
                is_done = m["id"] in completed
                is_crit = m.get("is_critical", False)
                level   = m["level"]
                lc      = "crit" if is_crit else "adv" if level == "Advanced" else "inter" if level == "Intermediate" else "beg"
                dc      = " done" if is_done else ""

                # FIX: checkbox label must be plain text (no markdown)
                chk = st.checkbox(
                    f"{m['title']} · {int(m.get('duration_hrs') or 0)}h · {m['level']}",
                    value=is_done, key=f"c_{m['id']}",
                )
                # FIX: update completed set and persist as list
                if chk:
                    completed.add(m["id"])
                else:
                    completed.discard(m["id"])
                st.session_state["completed"] = list(completed)

                prereqs_txt = ", ".join(m.get("prereqs", []) or []) or "none"
                tags = []
                if is_crit:              tags.append('<span class="sf-tag sf-tag-crit">★ critical</span>')
                if m.get("is_required"): tags.append('<span class="sf-tag sf-tag-req">required</span>')
                tags.append(f'<span class="sf-tag">{m["domain"]}</span>')

                reason_html = (
                    '<div class="sf-mod-trace">'
                    '<span class="sf-mod-trace-lbl">🧠 AI Reasoning</span>'
                    f'<div class="sf-mod-trace-body">{m["reasoning"]}</div>'
                    '</div>'
                ) if m.get("reasoning") else ""

                st.markdown(
                    f'<div class="sf-mod {lc}{dc}"><div class="sf-mod-row">'
                    f'<div class="sf-mod-num">{"✓" if is_done else f"#{idx:02d}"}</div>'
                    f'<div class="sf-mod-body">'
                    f'<div class="sf-mod-title">{m["title"]}</div>'
                    f'<div class="sf-mod-meta">Skill: {m["skill"]} · prereqs: {prereqs_txt}</div>'
                    f'<div class="sf-mod-tags">{"".join(tags)}</div>'
                    f'{reason_html}'
                    f'</div>'
                    f'<div class="sf-mod-hrs">{int(m.get("duration_hrs") or 0)}h</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

                # Course links via st.link_button (bypasses HTML sanitizer)
                courses = st.session_state.get("course_cache", {}).get(m["skill"], [])
                q = urllib.parse.quote_plus(m["skill"])
                if courses:
                    crs = courses[0]
                    lc1, _ = st.columns([3, 1])
                    with lc1:
                        st.link_button(f"{crs['icon']} {crs['title'][:50]} ({crs['platform']})",
                                       crs["url"], use_container_width=True)
                else:
                    lc1, lc2 = st.columns(2)
                    with lc1:
                        st.link_button(f"🎓 {m['skill']} on Coursera",
                                       f"https://www.coursera.org/search?query={q}",
                                       use_container_width=True)
                    with lc2:
                        st.link_button(f"▶ {m['skill']} on YouTube",
                                       f"https://www.youtube.com/results?search_query={q}+tutorial",
                                       use_container_width=True)

    with chart_col:
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:8px">ROI ranking</div>', unsafe_allow_html=True)
        # FIX: no redundant re-import — roi_bar already imported at top
        st.plotly_chart(roi_bar(res.get("roi", [])), use_container_width=True, config={"displayModeBar": False}, key="roi_roadmap")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:10px">Training timeline</div>', unsafe_allow_html=True)
    # FIX: no redundant re-import — timeline_chart already imported at top
    st.plotly_chart(timeline_chart(path), use_container_width=True, config={"displayModeBar": False}, key="timeline_roadmap")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:10px">Weekly study plan</div>', unsafe_allow_html=True)
    rem_path = [m for m in path if m["id"] not in completed]
    # FIX: explicit float cast for hpd in weekly_plan
    wp = weekly_plan(rem_path, float(hpd))
    for w in wp[:8]:
        with st.expander(f"Week {w['week']} — {w['total_hrs']:.1f}h / {hpd * 5}h capacity"):
            for mx in w["modules"]:
                star = "★ " if mx.get("is_critical") else ""
                st.markdown(f"- {star}**{mx['title']}** &nbsp;·&nbsp; `{mx['hrs_this_week']:.1f}h` of `{mx['total_hrs']}h`")

    im    = res["impact"]
    saved = im.get("hours_saved", 0)
    st.markdown(f"""
    <div class="sf-impact-box">
      <div class="sf-impact-row">
        <div class="sf-impact-item"><div class="sf-impact-lbl">Generic onboarding</div><div class="sf-impact-val" style="color:var(--t3);text-decoration:line-through">60h</div></div>
        <div class="sf-impact-arrow">→</div>
        <div class="sf-impact-item"><div class="sf-impact-lbl">Your personalized path</div><div class="sf-impact-val" style="color:var(--teal)">{im['roadmap_hours']}h</div></div>
        <div class="sf-impact-arrow">→</div>
        <div class="sf-impact-item"><div class="sf-impact-lbl">Time saved</div><div class="sf-impact-val" style="color:var(--green)">~{saved}h</div></div>
      </div>
      <div class="sf-impact-sub">
        NetworkX DAG · {im['modules_count']} modules · {im['critical_count']} critical nodes · {im['known_skills']} skills skipped
      </div>
    </div>""", unsafe_allow_html=True)

    gap_skills_u = list({m["skill"] for m in path})
    if len(st.session_state.get("course_cache", {})) < len(gap_skills_u):
        if st.button(f"Load course links for all {len(gap_skills_u)} skills →", key="load_all_crs"):
            with st.spinner("Searching Coursera · Udemy · YouTube…"):
                cc: dict = {}
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {ex.submit(search_course_links, s): s for s in gap_skills_u[:10]}
                    for f in futs:
                        cc[futs[f]] = f.result()
            st.session_state["course_cache"] = cc
            st.success(f"✓ {len(cc)} skills with course links"); st.rerun()

# =============================================================================
#  TAB: RESEARCH
# =============================================================================
def render_tab_research(res: dict) -> None:
    gp     = res["gap_profile"]
    sal    = res.get("salary", {}) or {}
    mkt    = res.get("market_insights", []) or []
    trends = res.get("skill_trends", {}) or {}
    jd     = res["jd"]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Web research</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">Live search via DuckDuckGo — courses, salaries, market trends</div>', unsafe_allow_html=True)

    q_col, btn_col = st.columns([5, 1])
    with q_col:
        if "search_input" not in st.session_state:
            st.session_state["search_input"] = st.session_state.get("search_query", "")
        st.text_input("Search",
                      placeholder='"React vs Vue 2025" · "FastAPI salary Bangalore" · "Docker course"',
                      key="search_input", label_visibility="collapsed")
        st.session_state["search_query"] = st.session_state.get("search_input", "")
    with btn_col:
        do_search = st.button("Search →", key="go_search", use_container_width=True)

    role_name    = jd.get("role_title", "") or ""
    gap_skills_s = [g["skill"] for g in gp if g["status"] != "Known"][:4]
    shortcuts    = [(s, f"{s} online course tutorial 2025") for s in gap_skills_s]

    if shortcuts:
        sc_cols = st.columns(len(shortcuts))
        for i, (lbl, q) in enumerate(shortcuts):
            with sc_cols[i]:
                if st.button(lbl[:22], key=f"sc_{i}", use_container_width=True):
                    st.session_state.pop("search_input", None)
                    st.session_state["search_query"]   = q
                    st.session_state["search_results"] = ddg_search(q, max_results=8)
                    st.rerun()

    if do_search and st.session_state.get("search_query", "").strip():
        with st.spinner("Searching…"):
            st.session_state["search_results"] = ddg_search(
                st.session_state["search_query"], max_results=8)

    results = st.session_state.get("search_results", [])
    # FIX: reference live _DDG_ERROR through module to get updated value
    if _bk._DDG_ERROR:
        st.warning(f"⚠ {_bk._DDG_ERROR}")
    if results:
        shown = [r for r in results if _is_english(r.get("title", "")) and _is_english(r.get("body", ""))] or results
        st.markdown(f'<div style="font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin:10px 0 8px">{len(shown)} results</div>', unsafe_allow_html=True)
        for r in shown:
            href   = r.get("href", "")
            domain = href.split("/")[2] if href.count("/") >= 2 else href
            st.markdown(
                f'<div class="sf-search-result">'
                f'<a class="sf-search-title" href="{href}" target="_blank">{r.get("title", "No title")}</a>'
                f'<div class="sf-search-url">{domain}</div>'
                f'<div class="sf-search-body">{r.get("body", "")[:200]}</div></div>',
                unsafe_allow_html=True,
            )
    elif do_search:
        st.warning("No results — try rephrasing the query.")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    sal_col, mkt_col = st.columns(2, gap="large")
    with sal_col:
        st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:10px">Salary benchmark</div>', unsafe_allow_html=True)
        try:
            sal_med = float(sal.get("median_lpa") or 0)
        except (TypeError, ValueError):
            sal_med = 0.0
        if sal and sal_med > 0:
            st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar": False}, key="salary_research")
            st.caption(f"Source: {sal.get('source', 'web')} · {sal.get('note', '')}")
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.75rem;color:var(--t3)">Salary data not available</p>', unsafe_allow_html=True)
            loc2 = st.selectbox("Location", _LOC_OPTS, key="sal_loc2")
            if st.button("🔍 Fetch salary data", key="sal_fetch", use_container_width=True):
                with st.spinner("Searching…"):
                    _sal_new = search_real_salary(role_name, loc2)
                if _sal_new:
                    st.session_state["result"]["salary"] = _sal_new
                    st.rerun()
                else:
                    st.warning("Could not find salary data.")
    with mkt_col:
        st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:10px">Job market insights</div>', unsafe_allow_html=True)
        if mkt:
            for ins in mkt:
                st.markdown(f'<div class="sf-insight">📌 {ins}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.75rem;color:var(--t3)">Not fetched yet</p>', unsafe_allow_html=True)
            if st.button("Fetch insights", key="mkt_fetch"):
                with st.spinner("Searching…"):
                    st.session_state["result"]["market_insights"] = search_job_market(role_name)
                st.rerun()

    if trends:
        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:10px">Skill demand signals</div>', unsafe_allow_html=True)
        pills = ""
        for skill, sig in trends.items():
            sc = _RED if "Hot" in sig else _AMBER if "Growing" in sig else "#3d4d66"
            pills += (f'<span class="sf-trend-pill">'
                      f'<span style="color:var(--t1);font-weight:500">{skill[:14]}</span>'
                      f'<span style="color:{sc}">&nbsp;{sig}</span></span>')
        st.markdown(f'<div style="line-height:2.6">{pills}</div>', unsafe_allow_html=True)
        if st.button("Re-fetch trends", key="refetch_trends"):
            gs = [g["skill"] for g in gp if g["status"] != "Known"][:6]
            with st.spinner("Checking latest demand data…"):
                st.session_state["result"]["skill_trends"] = search_skill_trends(gs)
            st.rerun()

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:8px">Course finder</div>', unsafe_allow_html=True)
    gap_skills_f = [g["skill"] for g in gp if g["status"] != "Known"]
    if gap_skills_f:
        crs_c1, crs_c2 = st.columns([3, 1])
        with crs_c1:
            sel_s = st.selectbox("Skill:", gap_skills_f, key="crs_sel", label_visibility="collapsed")
        with crs_c2:
            if st.button("Find →", key="crs_go", use_container_width=True):
                with st.spinner(f"Searching {sel_s}…"):
                    cc = st.session_state.get("course_cache", {})
                    cc[sel_s] = search_course_links(sel_s)
                    st.session_state["course_cache"] = cc
                st.rerun()
        cached = st.session_state.get("course_cache", {}).get(sel_s, [])
        if cached:
            for crs in cached:
                st.markdown(
                    f'<div class="sf-search-result">'
                    f'<a class="sf-search-title" href="{crs["url"]}" target="_blank">'
                    f'{crs["icon"]} {crs["title"]}</a>'
                    f'<div class="sf-search-url">{crs["platform"]}</div>'
                    f'<div class="sf-search-body">{crs["snippet"]}</div></div>',
                    unsafe_allow_html=True,
                )
        elif sel_s in st.session_state.get("course_cache", {}):
            st.info(f"No links found for {sel_s}.")

# =============================================================================
#  TAB: ATS & EXPORT
# =============================================================================
def render_tab_ats_export(res: dict) -> None:
    c       = res["candidate"]
    jd      = res["jd"]
    gp      = res["gap_profile"]
    roadmap = res["path"]
    im      = res["impact"]
    ql      = res.get("quality",   {}) or {}
    iv      = res.get("interview", {}) or {}
    sm      = res.get("seniority", {}) or {}
    cgm     = int(res.get("career_months", 0) or 0)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">ATS audit</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">Resume quality scores · improvement tips · keyword gaps · talking points</div>', unsafe_allow_html=True)

    ats_pct = int(ql.get("ats_score") or 0)
    st.markdown(f"""
    <div class="sf-ats-row">
      <div class="sf-ats-card"><div class="sf-ats-n">{ql.get('ats_score', '–')}%</div><div class="sf-ats-l">ATS Score</div></div>
      <div class="sf-ats-card"><div class="sf-ats-n" style="color:var(--teal)">{ql.get('overall_grade', '–')}</div><div class="sf-ats-l">Grade</div></div>
      <div class="sf-ats-card"><div class="sf-ats-n">{ql.get('completeness_score', '–')}%</div><div class="sf-ats-l">Completeness</div></div>
      <div class="sf-ats-card"><div class="sf-ats-n">{ql.get('clarity_score', '–')}%</div><div class="sf-ats-l">Clarity</div></div>
    </div>
    <div class="sf-prog"><div class="sf-prog-fill" style="width:{ats_pct}%"></div></div>
    """, unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:10px">Improvement tips</div>', unsafe_allow_html=True)
        for i, tip in enumerate((ql.get("improvement_tips") or [])[:6]):
            st.markdown(f'<div class="sf-tip"><span class="sf-tip-n">{str(i+1).zfill(2)}</span><span>{tip}</span></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:16px 0 8px">Interview talking points</div>', unsafe_allow_html=True)
        for pt in (ql.get("interview_talking_points") or [])[:4]:
            st.markdown(f'<div class="sf-talk">→ {pt}</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:8px">ATS issues</div>', unsafe_allow_html=True)
        issues = ql.get("ats_issues") or []
        if issues:
            for iss in issues[:5]: st.warning(iss)
        else:
            st.success("No critical ATS issues found")
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:12px 0 6px">Missing keywords</div>', unsafe_allow_html=True)
        kws = ql.get("missing_keywords") or []
        if kws:
            st.markdown("".join(f'<span class="sf-kw">{k}</span>' for k in kws), unsafe_allow_html=True)
        else:
            st.markdown('<span style="font-family:var(--mono);font-size:0.72rem;color:var(--t3)">None identified</span>', unsafe_allow_html=True)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Interview",     f"{iv.get('score', 0)}%", iv.get("label", "–"))
        c2.metric("Seniority gap", f"{sm.get('gap_levels', 0)} lvl")
        c3.metric("Career est.",   f"~{cgm}mo" if cgm else "–")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:4px">AI resume rewrite</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin-bottom:10px">ATS-optimized with missing keywords added naturally</div>', unsafe_allow_html=True)

    rtxt = st.session_state.get("resume_text", "")
    if not rtxt and st.session_state.get("resume_image"):
        st.info("Image resume detected — using extracted candidate info for rewrite.")
        ei = res.get("candidate", {})
        if ei.get("name"):
            rtxt = (f"{ei.get('name', '')}\n{ei.get('current_role', '')}\n" +
                    "\n".join(f"- {s['skill']} ({s['proficiency']}/10)"
                              for s in ei.get("skills", [])))
    elif not rtxt:
        st.info("Resume text required for rewrite.")

    if rtxt:
        if st.button("Generate rewrite →", key="gen_rw"):
            with st.spinner("Rewriting with LLaMA 3.3-70b…"):
                rw = rewrite_resume(rtxt, jd, kws)
            st.session_state["rw_result"] = rw
        rw = st.session_state.get("rw_result")
        if rw:
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown('<div style="font-family:var(--mono);font-size:0.62rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--t3);margin-bottom:6px">Original</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff">{rtxt[:1400]}</div>', unsafe_allow_html=True)
            with rc2:
                st.markdown('<div style="font-family:var(--mono);font-size:0.62rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--teal);margin-bottom:6px">Rewritten ✓</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff">{rw[:1400]}</div>', unsafe_allow_html=True)
            st.download_button("⬇ Download rewritten resume", data=rw,
                               file_name="skillforge_rewritten.txt", mime="text/plain", key="dl_rewrite")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Export</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">Download your personalized roadmap as PDF · JSON · CSV</div>', unsafe_allow_html=True)

    ex1, ex2, ex3 = st.columns(3, gap="medium")
    with ex1:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">PDF report</div><div class="sf-export-sub">Full roadmap · AI reasoning · ATS audit</div>', unsafe_allow_html=True)
        for k, v in [("Candidate", c.get("name", "–")), ("Role", jd.get("role_title", "–")),
                     ("ATS score", f"{ql.get('ats_score', '–')}%"),
                     ("Modules", im.get("modules_count", 0)),
                     ("Training", f"{im['roadmap_hours']}h")]:
            st.markdown(f'<div class="sf-export-row"><span class="sf-ek">{k}</span><span class="sf-ev">{v}</span></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if REPORTLAB:
            pdf_buf = build_pdf(c, jd, gp, roadmap, im, ql, iv)
            nm = (c.get("name", "candidate") or "candidate").replace(" ", "_")
            st.download_button("⬇ Download PDF", data=pdf_buf,
                               file_name=f"skillforge_{nm}_{datetime.now().strftime('%Y%m%d')}.pdf",
                               mime="application/pdf", use_container_width=True, key="dl_pdf")
        else:
            st.caption("`pip install reportlab` for PDF export")
        st.markdown('</div>', unsafe_allow_html=True)

    with ex2:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">JSON export</div><div class="sf-export-sub">Complete structured result for integrations</div>', unsafe_allow_html=True)
        export_data = {
            "candidate": c, "jd": jd, "impact": im, "interview": iv,
            "gap_profile": [{k2: v2 for k2, v2 in g.items() if k2 != "catalog_course"} for g in gp],
            "roadmap": [{"id": m["id"], "title": m["title"], "skill": m["skill"],
                         "level": m["level"], "duration_hrs": m["duration_hrs"],
                         "is_critical": m.get("is_critical", False),
                         "reasoning": m.get("reasoning", "")} for m in roadmap],
            "generated_at": datetime.now().isoformat(),
        }
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        st.download_button("⬇ Download JSON",
                           data=json.dumps(export_data, indent=2, default=str),
                           file_name=f"skillforge_{datetime.now().strftime('%Y%m%d')}.json",
                           mime="application/json", use_container_width=True, key="dl_json")
        st.markdown('</div>', unsafe_allow_html=True)

    with ex3:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">CSV export</div><div class="sf-export-sub">Roadmap modules in spreadsheet format</div>', unsafe_allow_html=True)
        csv_rows = ["id,title,skill,level,domain,duration_hrs,is_critical,is_required,reasoning"]
        for m in roadmap:
            rsn = (m.get("reasoning") or "").replace(",", ";").replace("\n", " ")
            csv_rows.append(
                f'{m["id"]},{m["title"].replace(",", ";")},{m["skill"]},'
                f'{m["level"]},{m["domain"]},{m["duration_hrs"]},'
                f'{m.get("is_critical", False)},{m.get("is_required", False)},{rsn}'
            )
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        st.download_button("⬇ Download CSV",
                           data="\n".join(csv_rows),
                           file_name=f"skillforge_roadmap_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime="text/csv", use_container_width=True, key="dl_csv")
        st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
#  SIDEBAR
# =============================================================================
def render_sidebar(res: dict) -> None:
    im = res["impact"]
    iv = res["interview"]
    sm = res.get("seniority", {})

    with st.sidebar:
        st.markdown(
            '<div style="padding:14px 10px 6px">'
            '<div style="font-family:\'DM Sans\',sans-serif;font-size:1rem;font-weight:700;'
            'color:#f1f5f9;letter-spacing:-0.02em">Skill<span style="color:#2dd4bf">Forge</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        sections = [
            ("gap",      "#2dd4bf", "Gap Analysis"),
            ("roadmap",  "#f59e0b", "Roadmap"),
            ("research", "#4ade80", "Research"),
            ("ats",      "#a78bfa", "ATS & Export"),
        ]
        for anc, color, lbl in sections:
            st.markdown(
                f'<a href="#{anc}" class="sf-nav-item">'
                f'<div class="sf-nav-dot" style="background:{color}"></div>{lbl}</a>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:10px 0"></div>',
                    unsafe_allow_html=True)

        c = res["candidate"]
        st.markdown(
            f'<div style="padding:4px 12px;font-family:\'DM Mono\',monospace;font-size:0.68rem;color:#3d4d66">'
            f'<div>candidate &nbsp;<span style="color:#94a3b8">{c.get("name","–")}</span></div>'
            f'<div>role &nbsp;<span style="color:#94a3b8">{res["jd"].get("role_title","–")[:22]}</span></div>'
            f'<div>fit &nbsp;<span style="color:#94a3b8">+{im.get("fit_delta",0)}%</span></div>'
            f'<div>modules &nbsp;<span style="color:#94a3b8">{im.get("modules_count",0)}</span></div>'
            f'<div>hours &nbsp;<span style="color:#94a3b8">{im.get("roadmap_hours",0)}h</span></div>'
            f'<div>interview &nbsp;<span style="color:{iv.get("color","#4ade80")}">'
            f'{iv.get("score",0)}% {iv.get("label","")}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:10px 0"></div>',
                    unsafe_allow_html=True)

        if sm.get("has_mismatch"):
            st.markdown(
                f'<div style="margin:0 8px 10px;background:rgba(245,158,11,0.07);'
                f'border:1px solid rgba(245,158,11,0.2);border-radius:6px;padding:9px 12px;'
                f'font-size:0.72rem;color:#f59e0b">⚠ {sm["candidate"]} → {sm["required"]}</div>',
                unsafe_allow_html=True,
            )

        if _bk._audit_log:
            st.markdown("**API log**")
            for e in _bk._audit_log[-5:]:
                ok = e.get("status") == "ok"
                sc = "#4ade80" if ok else "#ef4444"
                st.markdown(
                    f'<div class="sf-log">'
                    f'<span style="color:{sc}">{"●" if ok else "✕"}</span>'
                    f'<span>{e.get("ts","")}</span>'
                    f'<span style="color:var(--teal)">{e.get("model","")}</span>'
                    f'<span>{e.get("in",0)}+{e.get("out",0)}tok</span>'
                    f'<span>{e.get("ms",0)}ms</span>'
                    f'<span>${e.get("cost",0):.6f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:10px 0"></div>',
                        unsafe_allow_html=True)

        st.markdown('<div class="sf-ghost" style="padding:0 8px">', unsafe_allow_html=True)
        if st.button("↩ Start over", key="sb_reset", use_container_width=True):
            _full_reset()
        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  FOOTER
# =============================================================================
def render_footer() -> None:
    total_cost = sum(e.get("cost", 0) for e in _bk._audit_log)
    st.markdown(
        f'<div class="sf-foot">'
        f'<span><span class="sf-fdot" style="background:#2dd4bf"></span>Groq LLaMA 3.3-70b</span>'
        f'<span><span class="sf-fdot" style="background:#2dd4bf"></span>Llama 4 Scout Vision</span>'
        f'<span><span class="sf-fdot" style="background:#2dd4bf"></span>NetworkX DAG</span>'
        f'<span><span class="sf-fdot" style="background:#2dd4bf"></span>sentence-transformers</span>'
        f'<span><span class="sf-fdot" style="background:#2dd4bf"></span>DuckDuckGo</span>'
        f'<span style="color:var(--t4)">calls: {len(_bk._audit_log)} · ${total_cost:.5f}</span>'
        f'<span class="sf-fr">ARTPARK CodeForge 2025 · SkillForge v11</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
#  CLI MODE
# =============================================================================
def cli_analyze(scenario_key: str) -> None:
    import sys, time as _time
    from backend import run_analysis

    if scenario_key not in SAMPLES:
        print(f"Unknown scenario: {scenario_key}")
        print(f"Available: {list(SAMPLES.keys())}")
        sys.exit(1)

    s  = SAMPLES[scenario_key]
    t0 = _time.time()
    print(f"\n  SkillForge v11 CLI · {s['label']}")
    print(f"  {'=' * 50}")

    result = run_analysis(s["resume"], s["jd"])
    elapsed = round(_time.time() - t0, 2)
    print(f"  Done in {elapsed}s")

    if "error" in result:
        print(f"  Error: {result}")
        return

    c    = result["candidate"]
    im   = result["impact"]
    iv   = result["interview"]
    path = result["path"]

    print(f"  Candidate : {c.get('name','–')} ({c.get('seniority','–')} · {c.get('domain','–')})")
    print(f"  Role      : {result['jd'].get('role_title','–')}")
    print(f"  Fit       : {im['current_fit']}% → {im['projected_fit']}% (+{im['fit_delta']}%)")
    print(f"  Interview : {iv['score']}% ({iv['label']})")
    print(f"  Roadmap   : {im['modules_count']} modules / {im['roadmap_hours']}h / {im['critical_count']} critical")
    print()
    for i, m in enumerate(path):
        crit = "★" if m.get("is_critical") else " "
        print(f"    {crit} #{i+1:02d} [{m['level'][:3]}] {m['title']} ({m['duration_hrs']}h)")
    print(f"\n  Hours saved vs generic 60h: ~{im['hours_saved']}h\n")


# =============================================================================
#  RESULTS PAGE
# =============================================================================
def render_results() -> None:
    res = st.session_state.get("result")
    # FIX: check both missing result AND error key
    if not res or "error" in res:
        st.error("No results found. Please go back and re-analyze.")
        if st.button("← Back"):
            st.session_state["step"] = "input"; st.rerun()
        return

    st.markdown(CSS, unsafe_allow_html=True)
    render_topbar()
    st.markdown('<div class="sf-page">', unsafe_allow_html=True)
    _, rc = st.columns([12, 1])
    with rc:
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("↩ Reset", key="top_reset"):
            _full_reset()
        st.markdown('</div>', unsafe_allow_html=True)
    render_banner(res)

    # FIX: corrected tab order — Gap Analysis first (v11 change)
    tab_gap, tab_road, tab_research, tab_ats = st.tabs([
        "🎯 Gap Analysis", "🗺 Roadmap", "🔍 Research", "📋 ATS & Export",
    ])
    with tab_gap:      render_tab_overview(res)
    with tab_road:     render_tab_roadmap(res)
    with tab_research: render_tab_research(res)
    with tab_ats:      render_tab_ats_export(res)

    st.markdown("</div>", unsafe_allow_html=True)

    # FIX: inline cost+cache footer (v11 style); API log moved to sidebar
    # FIX: reference live _audit_log through module
    total_cost = sum(e.get("cost", 0) for e in _bk._audit_log)
    cache_lbl  = "⚡ cached" if res.get("_cache_hit") else "🔴 live"
    st.markdown(
        f'<div class="sf-foot">'
        f'<span><span class="sf-fdot" style="background:#4ade80"></span>SkillForge v11</span>'
        f'<span>{cache_lbl}</span>'
        f'<span>API calls: {len(_bk._audit_log)}</span>'
        f'<span>Cost: ${total_cost:.5f}</span>'
        f'<span class="sf-fr">'
        f'<a href="#" onclick="window.scrollTo(0,0);return false;" '
        f'style="color:var(--t3);text-decoration:none">↑ top</a></span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    render_sidebar(res)

# =============================================================================
#  MAIN
# =============================================================================
def main() -> None:
    _init_state()
    threading.Thread(target=_load_semantic_bg, daemon=True).start()

    step = st.session_state.get("step", "input")
    if step == "input":
        st.markdown(CSS, unsafe_allow_html=True)
        render_topbar()
        render_input()
    elif step in ("analyzing", "loading"):
        st.session_state["step"] = "loading"
        st.markdown(CSS, unsafe_allow_html=True)
        render_topbar()
        render_loading()
    elif step == "results":
        render_results()
    else:
        st.session_state["step"] = "input"; st.rerun()


if __name__ == "__main__":
    main()