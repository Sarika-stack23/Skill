# =============================================================================
#  main.py — SkillForge v13  |  All UI fixes applied
#  FIX 5: ATS rewrite score capped at 88 %
#  FIX: Interview metrics delta_color="off" — no wrong up-arrows
#  FIX: Sample buttons type="secondary" — proper Streamlit API
#  FIX: Job market insights bullet → teal ›
#  FIX: Peer percentile "Better than X%" framing
#  FIX: Shareable link — reads st.query_params on load, shows summary card
#  FIX: Telemetry bar → sidebar only, removed from main page
#  FIX: NetworkX DAG chip shows ON in results view
#  FIX: Tab underline — third CSS selector for full Streamlit compat
#  FIX: Hero gap removed, feature cards added, subtitle enlarged
# =============================================================================

import os, json, urllib.parse, threading, hashlib, shelve, io, pathlib
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

import backend as _bk
from backend import (
    CATALOG, CATALOG_BY_ID, CATALOG_SKILLS, SAMPLES, SKILL_GRAPH,
    MARKET_DEMAND, OBSOLESCENCE_RISK, TRANSFER_MAP, SENIORITY_MAP,
    MODEL_FAST, MODEL_VISION, CURRENT_YEAR, REPORTLAB,
    _parse_bytes, _load_semantic_bg, demand_label, _strip_mern_prefix,
    run_analysis_with_web, cache_bust, rewrite_resume, build_pdf,
    search_real_salary, search_skill_trends, search_job_market,
    search_course_links, ddg_search, _is_english, weeks_ready,
    radar_chart, animated_radar_chart, timeline_chart, salary_chart,
    roi_bar, weekly_plan, generate_interview_questions,
    build_ics_calendar,
    _TEAL, _AMBER, _RED, _GREEN,
)

def build_dag_data(path: List[dict], gp: List[dict]) -> dict:
    path_ids   = {m["id"] for m in path}
    req_skills = {g["skill"].lower() for g in gp if g["is_required"]}
    crit_ids   = {m["id"] for m in path if m.get("is_critical")}
    nodes = [
        {
            "id":       m["id"],
            "label":    m["title"][:22],
            "skill":    m["skill"],
            "level":    m["level"],
            "required": m.get("is_required", False) or m["skill"].lower() in req_skills,
            "critical": m["id"] in crit_ids,
            "hrs":      int(m.get("duration_hrs") or 0),
        }
        for m in path
    ]
    edges = [
        {"src": prereq_id, "dst": m["id"]}
        for m in path
        for prereq_id in (m.get("prereqs") or [])
        if prereq_id in path_ids
    ]
    return {"nodes": nodes, "edges": edges}


if not _bk.GROQ_CLIENT:
    st.error("**GROQ_API_KEY missing** — add it to `.env` → [console.groq.com](https://console.groq.com)")
    st.stop()

# =============================================================================
#  CSS — v13 + hero gap fix
# =============================================================================
CSS = """
<style>
/* ============================================================
   SKILLFORGE — DESIGN TOKENS
   ============================================================ */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

:root {
  --bg:       #0b0d14;
  --s1:       #131720;
  --s2:       #1a1f2e;
  --s3:       #222840;
  --border:   rgba(255,255,255,0.07);
  --bhi:      rgba(45,212,191,0.20);
  --teal:     #2dd4bf;
  --teal-bg:  rgba(45,212,191,0.08);
  --amber:    #f59e0b;
  --red:      #ef4444;
  --green:    #4ade80;
  --purple:   #a78bfa;
  --t1:       #f1f5f9;
  --t2:       #94a3b8;
  --t3:       #475569;
  --t4:       #2d3a52;
  --sans:     'DM Sans', sans-serif;
  --mono:     'DM Mono', 'IBM Plex Mono', monospace;
  --page-px:  40px;
}

/* ============================================================
   RESET
   ============================================================ */
*, *::before, *::after { box-sizing: border-box; }

/* ============================================================
   BASE — background, font, scrollbar
   ============================================================ */
html, body, [class*="css"] {
  font-family: var(--sans)  !important;
  background:  var(--bg)    !important;
  color:       var(--t2)    !important;
  font-size:   15px         !important;
}
.stApp { background: var(--bg) !important; }
::-webkit-scrollbar       { width: 3px; height: 3px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 99px; }

/* ============================================================
   STREAMLIT CHROME — hide header, toolbar, footer, status
   ============================================================ */
[data-testid="stHeader"],
header[data-testid="stHeader"]            { display: none !important; height: 0 !important; }
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],
[data-testid="stBottom"],
[data-testid="stAppRunningIndicator"],
.stDeployButton,
footer, #MainMenu                         { display: none !important; visibility: hidden !important; height: 0 !important; overflow: hidden !important; }

/* ============================================================
   STREAMLIT LAYOUT — kill top gap + side padding
   Cover every container name across Streamlit v1.28–v1.44+
   ============================================================ */
.block-container,
.stMainBlockContainer,
[data-testid="stAppViewBlockContainer"],
[data-testid="stMain"] > div,
section.main > div,
section.main {
  padding-top:    0    !important;
  padding-left:   0    !important;
  padding-right:  0    !important;
  padding-bottom: 0    !important;
  max-width:      100% !important;
}
[data-testid="stVerticalBlock"]          { gap: 0 !important; }
[data-testid="stVerticalBlockSeparator"] { display: none !important; }

/* ============================================================
   SIDEBAR
   ============================================================ */
section[data-testid="stSidebar"] > div:first-child {
  background:   var(--s1) !important;
  border-right: 1px solid var(--border) !important;
}

/* Force font on interactive elements */
button, select, input, label,
[data-testid="stCheckbox"] label,
[data-testid="stSelectbox"] label,
[data-testid="stExpander"] summary,
[data-testid="stTextInput"] input {
  font-family: var(--sans) !important;
}

/* ============================================================
   TOPBAR  — sticky, full-width, our custom bar
   ============================================================ */
.sf-top {
  height:          56px;
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  padding:         0 var(--page-px);
  border-bottom:   1px solid var(--border);
  position:        sticky;
  top:             0;
  z-index:         200;
  background:      rgba(11,13,20,0.96);
  backdrop-filter: blur(20px);
}
.sf-logo     { font-size: 1.25rem; font-weight: 700; color: var(--t1); letter-spacing: -0.03em; }
.sf-logo em  { color: var(--teal); font-style: normal; }
.sf-top-right { display: flex; align-items: center; gap: 8px; font-family: var(--mono); font-size: 0.65rem; color: var(--t3); }
.sf-chip     { padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border); color: var(--t3); font-size: 0.65rem; }
.sf-chip.on  { border-color: var(--bhi); color: var(--teal); }
.sf-chip.off { border-color: transparent; color: var(--t4); }

/* ============================================================
   PAGE WRAPPER  — horizontal padding lives here, not in Streamlit
   ============================================================ */
/* .sf-page padding is set via inline style on the div (Streamlit-safe) */
.sf-page     { max-width: 1280px; margin: 0 auto; }
.sf-page-pad { padding-top: 20px; padding-bottom: 72px; }

/* ============================================================
   HERO
   ============================================================ */
.sf-hero { padding: 12px 0 16px; }

.sf-eyebrow {
  font-family:    var(--mono);
  font-size:      0.68rem;
  font-weight:    500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color:          var(--teal);
  display:        flex;
  align-items:    center;
  gap:            10px;
  margin-bottom:  12px;
}
.sf-eyebrow::before { content: ''; width: 28px; height: 1px; background: var(--teal); }

.sf-h1 {
  font-size:      clamp(2.4rem, 5vw, 4rem);
  font-weight:    800;
  color:          var(--t1);
  line-height:    1.05;
  letter-spacing: -0.04em;
  margin-bottom:  16px;
}
.sf-h1 span { color: var(--teal); }

.sf-sub {
  font-size:     1.05rem;
  color:         var(--t2);
  line-height:   1.7;
  max-width:     580px;
  margin-bottom: 24px;
}

/* Feature cards */
.sf-feature-row {
  display:               grid;
  grid-template-columns: repeat(4, 1fr);
  gap:                   10px;
  margin-bottom:         4px;
}
@media (max-width: 860px) { .sf-feature-row { grid-template-columns: repeat(2,1fr); } }
@media (max-width: 500px) { .sf-feature-row { grid-template-columns: 1fr; } }
.sf-feat {
  display:       flex;
  align-items:   flex-start;
  gap:           11px;
  background:    rgba(45,212,191,0.04);
  border:        1px solid rgba(45,212,191,0.12);
  border-radius: 10px;
  padding:       14px 16px;
  transition:    border-color 0.15s, background 0.15s;
}
.sf-feat:hover  { border-color: rgba(45,212,191,0.28); background: rgba(45,212,191,0.07); }
.sf-feat-icon   { font-size: 1.3rem; margin-top: 1px; flex-shrink: 0; }
.sf-feat-title  { font-size: 0.86rem; font-weight: 700; color: var(--t1); margin-bottom: 4px; line-height: 1.2; }
.sf-feat-desc   { font-family: var(--mono); font-size: 0.64rem; color: var(--t3); line-height: 1.55; }

/* Misc input labels */
.sf-sample-lbl { font-family: var(--mono); font-size: 0.65rem; color: var(--t3); }
.sf-panel-hd   { font-size: 0.85rem; font-weight: 600; color: var(--t1); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.sf-panel-icon { font-size: 1rem; }
.sf-ready-badge { font-family: var(--mono); font-size: 0.6rem; padding: 2px 8px; border-radius: 3px; background: rgba(45,212,191,0.1); color: var(--teal); border: 1px solid var(--bhi); margin-left: auto; }
.sf-wc          { font-family: var(--mono); font-size: 0.65rem; color: var(--t3); margin-top: 8px; }

/* ============================================================
   HOW IT WORKS + STATS
   ============================================================ */
.sf-how {
  display:       flex;
  align-items:   center;
  margin:        0 0 12px;
  background:    var(--s1);
  border:        1px solid var(--border);
  border-radius: 12px;
  padding:       20px 24px;
}
.sf-how-step  { flex: 1; text-align: center; }
.sf-how-num   { font-family: var(--mono); font-size: 1.6rem; font-weight: 500; color: var(--teal); line-height: 1; margin-bottom: 6px; }
.sf-how-title { font-size: 0.9rem; font-weight: 700; color: var(--t1); margin-bottom: 4px; }
.sf-how-sub   { font-family: var(--mono); font-size: 0.65rem; color: var(--t3); line-height: 1.5; }
.sf-how-arrow { font-size: 1.2rem; color: var(--teal); opacity: 0.4; padding: 0 12px; flex-shrink: 0; }

.sf-stats-strip {
  display:         flex;
  align-items:     center;
  justify-content: center;
  margin:          0 0 14px;
  background:      rgba(45,212,191,0.04);
  border:          1px solid var(--bhi);
  border-radius:   10px;
  padding:         14px 24px;
}
.sf-stat     { text-align: center; flex: 1; }
.sf-stat-n   { display: block; font-family: var(--mono); font-size: 1.8rem; font-weight: 500; color: var(--teal); line-height: 1; margin-bottom: 4px; }
.sf-stat-l   { font-family: var(--mono); font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--t3); }
.sf-stat-div { width: 1px; height: 36px; background: var(--border); margin: 0 16px; flex-shrink: 0; }

/* ============================================================
   UPLOAD / TEXTAREA
   ============================================================ */
[data-testid="stFileUploadDropzone"] {
  background:    rgba(45,212,191,0.02) !important;
  border:        1.5px dashed rgba(45,212,191,0.14) !important;
  border-radius: 8px !important;
}
[data-testid="stFileUploadDropzone"]:hover {
  border-color: rgba(45,212,191,0.32) !important;
  background:   rgba(45,212,191,0.04) !important;
}
[data-testid="stFileUploadDropzone"] button {
  background: transparent !important; border: 1px solid var(--bhi) !important;
  color: var(--teal) !important; font-family: var(--mono) !important;
  font-size: 0.72rem !important; border-radius: 5px !important;
}
textarea {
  background: #0c0f1a !important; border: 1px solid var(--border) !important;
  border-radius: 8px !important; color: #b8ccd8 !important;
  font-family: var(--mono) !important; font-size: 0.82rem !important;
  resize: vertical !important; line-height: 1.6 !important;
}
textarea:focus        { border-color: var(--bhi) !important; outline: none !important; }
textarea::placeholder { color: var(--t4) !important; }

/* ============================================================
   BUTTONS
   ============================================================ */
.stButton > button {
  background: var(--teal) !important; border: none !important;
  border-radius: 8px !important; color: #061412 !important;
  font-family: var(--sans) !important; font-weight: 700 !important;
  font-size: 0.9rem !important; padding: 11px 0 !important;
  width: 100% !important; letter-spacing: 0.01em !important;
  transition: opacity 0.15s !important;
}
.stButton > button:hover    { opacity: 0.84 !important; }
.stButton > button:disabled { opacity: 0.30 !important; }
.stButton > button[kind="secondary"] {
  background: transparent !important; border: 1px solid var(--bhi) !important;
  color: var(--teal) !important; font-weight: 500 !important; font-size: 0.82rem !important;
}
.stButton > button[kind="secondary"]:hover { background: var(--teal-bg) !important; border-color: var(--teal) !important; }
.sf-ghost .stButton > button  { background: var(--s2) !important; border: 1px solid var(--border) !important; color: var(--t2) !important; font-weight: 500 !important; }
.sf-ghost .stButton > button:hover { border-color: rgba(255,255,255,0.15) !important; color: var(--t1) !important; }
.sf-danger .stButton > button { background: rgba(239,68,68,0.12) !important; border: 1px solid rgba(239,68,68,0.2) !important; color: var(--red) !important; }
[data-testid="stDownloadButton"] > button { background: var(--s2) !important; border: 1px solid var(--border) !important; color: var(--t2) !important; font-family: var(--sans) !important; font-weight: 500 !important; font-size: 0.82rem !important; }
[data-testid="stDownloadButton"] > button:hover { border-color: var(--bhi) !important; color: var(--teal) !important; }
[data-testid="stLinkButton"] > a {
  background: rgba(45,212,191,0.06) !important; border: 1px solid var(--bhi) !important;
  border-radius: 6px !important; color: var(--teal) !important;
  font-family: var(--mono) !important; font-size: 0.75rem !important;
  padding: 6px 12px !important; text-decoration: none !important;
  display: flex !important; align-items: center !important; gap: 6px !important; margin-top: 8px !important;
}
[data-testid="stLinkButton"] > a:hover { background: rgba(45,212,191,0.12) !important; border-color: var(--teal) !important; }

/* ============================================================
   TABS
   ============================================================ */
[data-testid="stTabs"] button,
[data-testid="stTabs"] [role="tab"] {
  font-family: var(--sans) !important; font-size: 0.88rem !important;
  font-weight: 500 !important; padding: 10px 16px !important;
  color: var(--t3) !important; border-bottom: 2px solid transparent !important;
  border-top: none !important; border-left: none !important; border-right: none !important;
  background: transparent !important; outline: none !important; box-shadow: none !important;
}
[data-testid="stTabs"] button[aria-selected="true"],
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--teal) !important; border-bottom: 2px solid var(--teal) !important;
  background: transparent !important; box-shadow: none !important;
}
[data-testid="stTabs"] button::after,
[data-testid="stTabs"] [role="tab"]::after { display: none !important; }
[data-testid="stTabs"] button p           { color: inherit !important; }

/* ============================================================
   METRICS
   ============================================================ */
[data-testid="stMetric"]       { background: var(--s2) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; padding: 13px 15px !important; }
[data-testid="stMetricValue"]  { font-family: var(--mono) !important; font-size: 1.5rem !important; color: var(--t1) !important; }
[data-testid="stMetricLabel"]  { font-family: var(--mono) !important; color: var(--t3) !important; font-size: 0.6rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; }
[data-testid="stMetricDelta"]  { font-family: var(--mono) !important; font-size: 0.7rem !important; }

/* ============================================================
   NATIVE WIDGETS
   ============================================================ */
[data-testid="stSelectbox"] > div > div { background: var(--s1) !important; border: 1px solid var(--border) !important; color: var(--t1) !important; font-family: var(--sans) !important; font-size: 0.85rem !important; }
[data-testid="stExpander"]              { background: var(--s1) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; margin-bottom: 5px !important; }
[data-testid="stExpander"] summary      { font-family: var(--sans) !important; color: var(--t2) !important; font-size: 0.85rem !important; }
[data-testid="stProgressBar"] > div > div { background: var(--teal) !important; }
[data-testid="stProgressBar"] > div       { background: rgba(255,255,255,0.05) !important; border-radius: 99px !important; }
[data-testid="stCheckbox"] > label       { background: transparent !important; color: var(--t2) !important; font-size: 0.82rem !important; }
[data-testid="stCheckbox"] > label > div[data-testid="stCheckboxContainer"] { background: var(--s2) !important; border: 1px solid var(--border) !important; border-radius: 4px !important; }

/* ============================================================
   RESULTS BANNER
   ============================================================ */
.sf-banner         { background: var(--s1); border: 1px solid var(--border); border-radius: 14px; padding: 28px 32px; margin: 16px 0; }
.sf-banner-top     { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.sf-candidate-name { font-size: 1.2rem; font-weight: 700; color: var(--t1); letter-spacing: -0.02em; }
.sf-candidate-sub  { font-family: var(--mono); font-size: 0.72rem; color: var(--t3); margin-top: 2px; }
.sf-cache-badge    { font-family: var(--mono); font-size: 0.6rem; padding: 2px 8px; border-radius: 3px; background: rgba(167,139,250,0.1); color: var(--purple); border: 1px solid rgba(167,139,250,0.2); margin-left: auto; margin-top: 4px; }
.sf-vision-badge   { font-family: var(--mono); font-size: 0.6rem; padding: 2px 8px; border-radius: 3px; background: rgba(45,212,191,0.1); color: var(--teal); border: 1px solid var(--bhi); margin-left: 8px; margin-top: 4px; }
.sf-scores         { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; margin-top: 20px; }
@media (max-width: 700px) { .sf-scores { grid-template-columns: 1fr; } }
.sf-score-card       { background: var(--s2); border: 1px solid var(--border); border-radius: 10px; padding: 20px 22px; text-align: center; }
.sf-score-num        { font-family: var(--mono); font-size: 3.2rem; font-weight: 500; line-height: 1; letter-spacing: -0.04em; color: var(--teal); }
.sf-score-lbl        { font-family: var(--mono); font-size: 0.62rem; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t3); margin-top: 6px; }
.sf-score-sub        { font-size: 0.78rem; color: var(--t2); margin-top: 5px; line-height: 1.4; }
.sf-hero-delta       { text-align: center; padding: 28px 0 20px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.sf-hero-delta-num   { font-family: var(--mono); font-size: 4rem; font-weight: 500; color: var(--green); line-height: 1; letter-spacing: -0.04em; }
.sf-hero-delta-label { font-family: var(--mono); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--t3); margin: 8px 0 6px; }
.sf-hero-delta-sub   { font-size: 0.9rem; color: var(--t2); }
.sf-ground-badge     { display: flex; align-items: center; gap: 10px; margin-top: 16px; padding: 10px 16px; background: rgba(45,212,191,0.04); border: 1px solid var(--bhi); border-radius: 7px; font-family: var(--mono); font-size: 0.68rem; color: var(--teal); }
.sf-ground-dot       { width: 7px; height: 7px; border-radius: 50%; background: var(--teal); flex-shrink: 0; animation: pulse 2s infinite; }
.sf-seniority-pill   { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 6px; background: rgba(245,158,11,0.06); border: 1px solid rgba(245,158,11,0.18); font-family: var(--mono); font-size: 0.72rem; color: var(--amber); margin-bottom: 12px; }

/* ============================================================
   SKILL CARDS
   ============================================================ */
.sf-skill-grid     { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px,1fr)); gap: 10px; margin-bottom: 8px; }
.sf-skill-card     { background: var(--s1); border: 1px solid var(--border); border-radius: 9px; padding: 14px 16px; transition: border-color 0.12s; cursor: default; }
.sf-skill-card:hover { border-color: rgba(255,255,255,0.12); }
.sf-skill-card.known   { border-left: 3px solid var(--teal); }
.sf-skill-card.partial { border-left: 3px solid var(--amber); }
.sf-skill-card.missing { border-left: 3px solid var(--red); }
.sf-skill-top    { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.sf-skill-name   { font-size: 0.88rem; font-weight: 600; color: var(--t1); }
.sf-st-badge     { font-family: var(--mono); font-size: 0.6rem; font-weight: 600; padding: 2px 8px; border-radius: 3px; }
.sf-st-known   { background: rgba(45,212,191,0.1); color: var(--teal);  border: 1px solid rgba(45,212,191,0.2); }
.sf-st-partial { background: rgba(245,158,11,0.1); color: var(--amber); border: 1px solid rgba(245,158,11,0.2); }
.sf-st-missing { background: rgba(239,68,68,0.1);  color: var(--red);   border: 1px solid rgba(239,68,68,0.2);  }
.sf-skill-bar      { height: 6px; background: rgba(255,255,255,0.05); border-radius: 99px; margin-bottom: 6px; }
.sf-skill-bar-fill { height: 100%; border-radius: 99px; }
.sf-skill-bottom   { display: flex; align-items: center; justify-content: space-between; }
.sf-skill-score    { font-family: var(--mono); font-size: 0.75rem; color: var(--t2); }
.sf-skill-demand   { font-family: var(--mono); font-size: 0.65rem; }
.sf-decay-tag      { font-family: var(--mono); font-size: 0.6rem; color: var(--amber); background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.2); border-radius: 3px; padding: 1px 5px; margin-top: 5px; display: inline-block; }
.sf-skill-ctx      { font-size: 0.72rem; color: var(--t3); margin-top: 6px; font-style: italic; line-height: 1.4; }

/* ============================================================
   ROADMAP MODULES
   ============================================================ */
.sf-phase-hd { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--t3); margin: 22px 0 10px; display: flex; align-items: center; gap: 10px; }
.sf-phase-hd::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.sf-mod       { background: var(--s1); border: 1px solid var(--border); border-left: 3px solid transparent; border-radius: 0 9px 9px 0; padding: 14px 16px 14px 14px; margin-bottom: 8px; }
.sf-mod.crit  { border-left-color: var(--red)   !important; }
.sf-mod.adv   { border-left-color: #f97316; }
.sf-mod.inter { border-left-color: var(--amber); }
.sf-mod.beg   { border-left-color: var(--teal);  }
.sf-mod.done  { opacity: 0.45; }
.sf-mod-row   { display: flex; align-items: flex-start; gap: 12px; }
.sf-mod-num   { font-family: var(--mono); font-size: 0.68rem; color: var(--t4); min-width: 28px; padding-top: 1px; flex-shrink: 0; }
.sf-mod-body  { flex: 1; min-width: 0; }
.sf-mod-title { font-size: 0.9rem; font-weight: 600; color: var(--t1); margin-bottom: 3px; line-height: 1.3; }
.sf-mod-meta  { font-family: var(--mono); font-size: 0.68rem; color: var(--t3); margin-bottom: 6px; }
.sf-mod-tags  { display: flex; gap: 5px; flex-wrap: wrap; }
.sf-tag       { font-family: var(--mono); font-size: 0.6rem; padding: 2px 8px; border-radius: 3px; background: var(--s2); color: var(--t2); border: 1px solid var(--border); }
.sf-tag-crit  { color: var(--red);  border-color: rgba(239,68,68,0.25);  background: rgba(239,68,68,0.06); }
.sf-tag-req   { color: var(--teal); border-color: var(--bhi);            background: var(--teal-bg); }
.sf-mod-hrs   { font-family: var(--mono); font-size: 0.8rem; color: var(--t2); white-space: nowrap; flex-shrink: 0; padding-top: 1px; }
.sf-mod-trace      { margin-top: 10px; padding: 10px 14px; background: rgba(45,212,191,0.04); border: 1px solid var(--bhi); border-radius: 7px; }
.sf-mod-trace-lbl  { font-family: var(--mono); font-size: 0.6rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--teal); margin-bottom: 5px; }
.sf-mod-trace-body { font-size: 0.78rem; color: var(--t2); line-height: 1.6; }

/* ============================================================
   ATS PANEL
   ============================================================ */
.sf-ats-row  { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 18px; }
@media (max-width: 600px) { .sf-ats-row { grid-template-columns: repeat(2,1fr); } }
.sf-ats-card { background: var(--s1); border: 1px solid var(--border); border-radius: 9px; padding: 18px 16px; text-align: center; }
.sf-ats-n    { font-family: var(--mono); font-size: 1.8rem; font-weight: 500; color: var(--t1); line-height: 1; }
.sf-ats-l    { font-family: var(--mono); font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--t3); margin-top: 5px; }
.sf-prog      { height: 3px; background: rgba(255,255,255,0.05); border-radius: 99px; overflow: hidden; margin-bottom: 20px; }
.sf-prog-fill { height: 100%; border-radius: 99px; background: var(--teal); }
.sf-tip   { display: flex; gap: 12px; margin-bottom: 10px; font-size: 0.82rem; color: var(--t2); line-height: 1.6; }
.sf-tip-n { font-family: var(--mono); font-size: 0.62rem; color: var(--teal); background: var(--teal-bg); border: 1px solid var(--bhi); border-radius: 3px; padding: 2px 7px; font-weight: 500; min-width: 26px; text-align: center; flex-shrink: 0; height: fit-content; }
.sf-talk  { font-size: 0.82rem; color: var(--t2); padding: 8px 0 8px 14px; border-left: 2px solid var(--teal); margin-bottom: 7px; line-height: 1.55; }
.sf-kw    { display: inline-block; font-family: var(--mono); font-size: 0.65rem; padding: 3px 9px; border-radius: 3px; margin: 3px; background: rgba(239,68,68,0.10); color: var(--red); border: 1px solid rgba(239,68,68,0.30); font-weight: 600; }

/* ============================================================
   EXPORT CARDS
   ============================================================ */
.sf-export-card { background: var(--s1); border: 1px solid var(--border); border-radius: 10px; padding: 20px 22px; height: 100%; }
.sf-export-hd   { font-size: 0.9rem; font-weight: 700; color: var(--t1); margin-bottom: 4px; }
.sf-export-sub  { font-size: 0.78rem; color: var(--t3); margin-bottom: 14px; line-height: 1.5; }
.sf-export-row  { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 0.72rem; padding: 5px 0; border-bottom: 1px solid var(--border); }
.sf-ek { color: var(--t3); }
.sf-ev { color: var(--t1); font-weight: 500; }

/* ============================================================
   RESEARCH
   ============================================================ */
.sf-search-result { background: var(--s1); border: 1px solid var(--border); border-radius: 9px; padding: 14px 16px; margin-bottom: 8px; }
.sf-search-title  { font-size: 0.9rem; font-weight: 600; color: var(--teal); text-decoration: none; }
.sf-search-title:hover { text-decoration: underline; }
.sf-search-url  { font-family: var(--mono); font-size: 0.65rem; color: var(--t4); margin: 3px 0 5px; }
.sf-search-body { font-size: 0.78rem; color: var(--t2); line-height: 1.55; }
.sf-insight     { background: rgba(45,212,191,0.03); border-left: 2px solid var(--teal); border-radius: 0 5px 5px 0; padding: 9px 13px; margin-bottom: 6px; font-size: 0.82rem; color: var(--t2); line-height: 1.55; }
.sf-trend-pill  { display: inline-flex; align-items: center; gap: 6px; background: var(--s2); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; margin: 4px; font-size: 0.78rem; }
.sf-empty-state { background: var(--s2); border: 1px solid var(--border); border-radius: 8px; padding: 20px 24px; text-align: center; font-family: var(--mono); font-size: 0.75rem; color: var(--t3); }
.sf-empty-icon  { font-size: 1.4rem; margin-bottom: 8px; }
.sf-empty-label { font-size: 0.82rem; color: var(--t2); margin-bottom: 4px; font-weight: 600; }

/* ============================================================
   TRANSFER ADVANTAGES
   ============================================================ */
.sf-xfer           { background: var(--s2); border: 1px solid var(--border); border-radius: 7px; padding: 10px 14px; margin-bottom: 6px; display: flex; align-items: center; gap: 10px; font-size: 0.78rem; color: var(--t2); }
.sf-xfer-pct       { font-family: var(--mono); font-weight: 500; font-size: 0.88rem; }
.sf-xfer.strong   .sf-xfer-pct { color: var(--teal);  font-size: 1rem;    }
.sf-xfer.moderate .sf-xfer-pct { color: var(--amber); font-size: 0.92rem; }
.sf-xfer.partial  .sf-xfer-pct { color: var(--t2);   font-size: 0.82rem; }
.sf-xfer-desc      { font-size: 0.72rem; color: var(--t3); margin-top: 2px; }

/* ============================================================
   LOADING SCREEN
   ============================================================ */
.sf-lstep        { display: flex; align-items: flex-start; gap: 14px; padding: 12px 16px; border-radius: 8px; margin-bottom: 6px; font-size: 0.85rem; }
.sf-lstep-done   { background: rgba(74,222,128,0.05);  border: 1px solid rgba(74,222,128,0.15); }
.sf-lstep-active { background: rgba(45,212,191,0.07);  border: 1px solid var(--bhi); }
.sf-lstep-wait   { background: var(--s1); border: 1px solid var(--border); opacity: 0.45; }
.sf-lstep-icon   { font-family: var(--mono); font-size: 1rem; min-width: 24px; text-align: center; margin-top: 1px; }
.sf-lstep-spin   { display: inline-block; animation: spin 1.2s linear infinite; }
.sf-lstep-title  { font-weight: 600; color: var(--t1); margin-bottom: 2px; }
.sf-lstep-sub    { font-family: var(--mono); font-size: 0.65rem; color: var(--t3); }
.sf-lprog      { height: 4px; background: rgba(255,255,255,0.05); border-radius: 99px; overflow: hidden; margin: 16px 0 24px; max-width: 560px; }
.sf-lprog-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--teal), var(--green)); transition: width 0.6s ease; }

/* ============================================================
   MISC / UTILITIES
   ============================================================ */
.sf-sh      { font-size: 1.15rem; font-weight: 700; color: var(--t1); letter-spacing: -0.02em; margin-bottom: 4px; }
.sf-ss      { font-family: var(--mono); font-size: 0.68rem; color: var(--t3); margin-bottom: 18px; }
.sf-divider { height: 1px; background: var(--border); margin: 28px 0; }
.sf-diff    { background: #090c16; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; font-family: var(--mono); font-size: 0.78rem; color: var(--t2); white-space: pre-wrap; line-height: 1.6; max-height: 320px; overflow-y: auto; }
.sf-log     { font-family: var(--mono); font-size: 0.68rem; color: var(--t3); padding: 5px 10px; background: var(--s1); border: 1px solid var(--border); border-radius: 4px; margin-bottom: 3px; display: flex; gap: 12px; }
.sf-impact-box   { background: var(--s1); border: 1px solid var(--border); border-radius: 10px; padding: 22px 28px; margin: 24px 0; }
.sf-impact-row   { display: flex; align-items: center; justify-content: center; gap: 0; margin-bottom: 12px; }
.sf-impact-item  { text-align: center; flex: 1; }
.sf-impact-lbl   { font-family: var(--mono); font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--t3); margin-bottom: 6px; }
.sf-impact-val   { font-family: var(--mono); font-size: 2rem; font-weight: 500; line-height: 1; }
.sf-impact-arrow { font-size: 1.2rem; color: var(--t4); padding: 0 20px; flex-shrink: 0; }
.sf-impact-sub   { font-family: var(--mono); font-size: 0.65rem; color: var(--t3); text-align: center; line-height: 1.6; }

/* ============================================================
   ANIMATIONS
   ============================================================ */
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
@keyframes spin  { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
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
        "interview_questions": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_RESET_KEYS = [
    "step", "resume_text", "resume_image", "jd_text", "result", "completed",
    "rw_result", "course_cache", "force_fresh", "search_query", "search_results",
    "res_paste", "jd_paste", "_resume_source", "_resume_fname", "_jd_source",
    "search_input", "_resume_hash", "interview_questions",
]


def _full_reset() -> None:
    for k in _RESET_KEYS:
        st.session_state.pop(k, None)
    st.rerun()


# =============================================================================
#  TOPBAR
# =============================================================================
def render_topbar(is_image_resume: bool = False, has_result: bool = False) -> None:
    vision_chip = (
        '<span class="sf-chip on">🖼 Vision OCR</span>'
        if is_image_resume
        else '<span class="sf-chip off">🖼 Vision OCR</span>'
    )
    dag_chip = (
        '<span class="sf-chip on">NetworkX DAG</span>'
        if has_result
        else '<span class="sf-chip off">NetworkX DAG</span>'
    )
    st.markdown(f"""
    <div class="sf-top">
      <div class="sf-logo" style="font-size:1.35rem">Skill<em>Forge</em></div>
      <div class="sf-top-right">
        <span class="sf-chip on">⚡ Groq-powered</span>
        {vision_chip}
        {dag_chip}
      </div>
    </div>""", unsafe_allow_html=True)


# =============================================================================
#  INPUT PAGE
# =============================================================================
def render_input() -> None:
    st.markdown('<div class="sf-page" style="padding:20px 40px 80px">', unsafe_allow_html=True)

    # ── Hero — tighter padding, bigger subtitle, feature cards fill the gap ──
    st.markdown("""
    <div class="sf-hero">
      <div class="sf-eyebrow">ARTPARK CodeForge · AI Adaptive Onboarding Engine</div>
      <div class="sf-h1">Skip what you know.<br><span>Learn what you need.</span></div>
      <div class="sf-sub">Upload your resume and target job description. SkillForge maps your exact skill gap and generates a dependency-ordered, personalized learning roadmap — powered by Groq LLaMA&nbsp;3.3 and a NetworkX DAG.</div>
      <div class="sf-feature-row">
        <div class="sf-feat"><span class="sf-feat-icon">🧠</span><div><div class="sf-feat-title">Skill Decay Model</div><div class="sf-feat-desc">Proficiency auto-adjusts for skills unused 2+ years</div></div></div>
        <div class="sf-feat"><span class="sf-feat-icon">🗺</span><div><div class="sf-feat-title">NetworkX DAG</div><div class="sf-feat-desc">Topological sort ensures foundational-first ordering</div></div></div>
        <div class="sf-feat"><span class="sf-feat-icon">🎯</span><div><div class="sf-feat-title">Zero Hallucinations</div><div class="sf-feat-desc">All recs strictly from the 47-course catalog</div></div></div>
        <div class="sf-feat"><span class="sf-feat-icon">⚡</span><div><div class="sf-feat-title">Critical Path DP</div><div class="sf-feat-desc">Node-weighted algo surfaces highest-ROI modules</div></div></div>
      </div>
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
      <div class="sf-stat"><span class="sf-stat-n">3</span><span class="sf-stat-l">Demo scenarios</span></div>
      <div class="sf-stat-div"></div>
      <div class="sf-stat"><span class="sf-stat-n">0</span><span class="sf-stat-l">Hallucinations</span></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div style="margin:0 0 8px"><span class="sf-sample-lbl">Try a sample →</span></div>', unsafe_allow_html=True)
    pc1, pc2, pc3, _ = st.columns([1, 1, 1, 2])
    for col, key, dlbl in zip([pc1, pc2, pc3], SAMPLES, ["Tech Role", "Data / AI Role", "Non-Tech Role"]):
        with col:
            if st.button(dlbl, key=f"pre_{key}", use_container_width=True, type="secondary"):
                for wk in _RESET_KEYS:
                    st.session_state.pop(wk, None)
                st.session_state["resume_text"]    = SAMPLES[key]["resume"]
                st.session_state["jd_text"]        = SAMPLES[key]["jd"]
                st.session_state["_resume_source"] = "paste"
                st.session_state["step"]           = "analyzing"
                st.rerun()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")

    with left:
        src_flag   = st.session_state.get("_resume_source", "")
        has_resume = bool(st.session_state.get("resume_text", "").strip() or st.session_state.get("resume_image"))
        badge      = '<span class="sf-ready-badge">✓ Ready</span>' if has_resume else ''
        st.markdown(f'<div class="sf-panel-hd"><span class="sf-panel-icon">📄</span> Your resume {badge}</div>', unsafe_allow_html=True)

        up_tab, paste_tab = st.tabs(["Upload Resume", "Paste Resume"])
        with up_tab:
            rf = st.file_uploader("Resume", type=["pdf","docx","jpg","jpeg","png","webp"],
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
                    elif ss_txt and not ss_txt.startswith("["):
                        st.success(f"✓ {rf.name} — {len(ss_txt.split())} words extracted")
                        st.caption(f"Preview: {ss_txt[:200]}…")
                    else:
                        st.error(f"Could not read {rf.name}. Try paste or JPG/PNG.")

        with paste_tab:
            if st.session_state.get("_resume_source") == "file":
                st.info("File loaded. Type here to switch to pasted text.")
                if st.button("Switch to paste mode", key="sw_paste"):
                    for k in ["_resume_source","_resume_hash","_resume_fname",
                               "resume_text","resume_image","result","rw_result"]:
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
            if st.button("Clear resume", key="clr_res"):
                for k in ["resume_text","resume_image","res_paste","_resume_source",
                           "_resume_fname","_resume_hash","result","rw_result"]:
                    st.session_state.pop(k, None)
                _init_state()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with right:
        has_jd   = bool(st.session_state.get("jd_text", "").strip())
        badge_jd = '<span class="sf-ready-badge">✓ Ready</span>' if has_jd else ''
        st.markdown(f'<div class="sf-panel-hd"><span class="sf-panel-icon">💼</span> Job description {badge_jd}</div>', unsafe_allow_html=True)

        jup_tab, jpaste_tab = st.tabs(["Upload JD", "Paste JD"])
        with jup_tab:
            jf = st.file_uploader("JD", type=["pdf","docx"], key="jd_file", label_visibility="collapsed")
            if jf is not None:
                try:
                    jf.seek(0); jraw = jf.read()
                except Exception:
                    jraw = b""
                if jraw:
                    jtxt, _ = _parse_bytes(jraw, jf.name)
                    if jtxt and not jtxt.startswith("["):
                        for k in ["result","rw_result","course_cache"]:
                            st.session_state.pop(k, None)
                        st.session_state.update({"jd_text": jtxt, "_jd_source": "file", "step": "input"})
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

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    opt1, opt2_col, _, btn_col = st.columns([1, 1.2, 0.6, 1.6])
    with opt1:
        cur_loc = st.session_state.get("sal_location", "India")
        idx_loc = _LOC_OPTS.index(cur_loc) if cur_loc in _LOC_OPTS else 0
        st.selectbox("Salary location", _LOC_OPTS, index=idx_loc, key="sal_location")
    with opt2_col:
        with st.expander("Advanced"):
            st.checkbox("Force fresh (skip cache)", key="force_fresh")
    with btn_col:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        resume_ready = bool(st.session_state.get("resume_text","").strip() or st.session_state.get("resume_image"))
        jd_ready     = bool(st.session_state.get("jd_text","").strip())
        if resume_ready and jd_ready:
            is_img = bool(st.session_state.get("resume_image"))
            lbl    = "Analyze image resume ⚡" if is_img else "Analyze skill gap ⚡"
            if st.button(lbl, key="go_btn", use_container_width=True):
                st.session_state["step"] = "analyzing"
                st.rerun()
        else:
            missing = (["resume"] if not resume_ready else []) + (["job description"] if not jd_ready else [])
            st.markdown(
                f'<p style="font-family:var(--mono);font-size:0.75rem;color:var(--t3);text-align:center;padding:12px 0">'
                f'Add {" and ".join(missing)} to continue</p>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  LOADING
# =============================================================================
def render_loading() -> None:
    st.markdown('<div class="sf-page" style="padding:20px 40px 80px">', unsafe_allow_html=True)
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    resume_text = st.session_state.get("resume_text", "")
    resume_img  = st.session_state.get("resume_image")
    jd_text     = st.session_state.get("jd_text", "") or st.session_state.get("jd_paste", "")
    source      = st.session_state.get("_resume_source", "paste")

    if not resume_text.strip() and not resume_img:
        st.error("No resume data. Please go back.")
        if st.button("Go back", key="back_no_resume"):
            st.session_state["step"] = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if not jd_text.strip():
        st.error("No job description. Please go back.")
        if st.button("Go back", key="back_no_jd"):
            st.session_state["step"] = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if source == "file" or st.session_state.get("force_fresh"):
        cache_bust(resume_text, resume_img, jd_text)
        st.session_state.pop("force_fresh", None)

    steps = [
        ("📄", "Parsing resume & job description",   "Extracting text, structure, metadata"),
        ("🔍", "Extracting skills with proficiency", "Scoring 0-10 per skill + regex fallback"),
        ("🧩", "Computing skill gap",                "Known, Partial, Missing classification"),
        ("🗺", "Building dependency roadmap",        "NetworkX DAG, topological sort"),
        ("🌐", "Fetching live market data",          "Salary, trends, job market"),
    ]
    st.markdown('<div style="max-width:560px;margin:40px auto 32px"><div style="font-family:var(--mono);font-size:0.65rem;letter-spacing:0.12em;text-transform:uppercase;color:var(--teal);margin-bottom:20px">Analyzing your profile</div></div>', unsafe_allow_html=True)
    slots = [st.empty() for _ in steps]
    prog  = st.empty()

    def show_steps(done: int) -> None:
        for i, (icon, title, sub) in enumerate(steps):
            if i < done:
                s = f'<div class="sf-lstep sf-lstep-done"><span class="sf-lstep-icon">✓</span><div><div class="sf-lstep-title">{title}</div><div class="sf-lstep-sub">{sub}</div></div></div>'
            elif i == done:
                s = f'<div class="sf-lstep sf-lstep-active"><span class="sf-lstep-icon sf-lstep-spin">{icon}</span><div><div class="sf-lstep-title">{title}</div><div class="sf-lstep-sub">{sub}</div></div></div>'
            else:
                s = f'<div class="sf-lstep sf-lstep-wait"><span class="sf-lstep-icon">○</span><div><div class="sf-lstep-title">{title}</div><div class="sf-lstep-sub">{sub}</div></div></div>'
            slots[i].markdown(s, unsafe_allow_html=True)
        pct = int(done / len(steps) * 100)
        prog.markdown(f'<div class="sf-lprog"><div class="sf-lprog-fill" style="width:{pct}%"></div></div>', unsafe_allow_html=True)

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
        elif "analysis_quality_failure" in str(err):
            st.error("Skill extraction failed for this resume. Please try again.")
        else:
            st.error(f"Analysis failed: {err}")
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("Back", key="retry_btn"):
            st.session_state["step"] = "input"
            st.rerun()
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

    fit_c        = "#64748b" if cur < 40 else _AMBER if cur < 65 else _GREEN
    cache_badge  = '<span class="sf-cache-badge">⚡ Cached</span>' if res.get("_cache_hit") else ""
    vision_badge = '<span class="sf-vision-badge">🖼 Vision OCR</span>' if res.get("_is_image") else ""
    hpd_val      = int(st.session_state.get("hpd", 2) or 2)
    hours_saved  = int(im.get("hours_saved") or 0)
    roadmap_longer = im.get("roadmap_longer", False)
    hours_narrative = (
        '<span style="color:var(--t3)">Comprehensive path for your gap level</span>'
        if roadmap_longer
        else (f'saves <strong style="color:var(--green)">~{hours_saved}h</strong> vs generic'
              if hours_saved > 0
              else '<span style="color:var(--t3)">vs 60h generic</span>')
    )

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
          <span style="color:var(--t3);margin-left:10px">· Complete in {weeks_ready(im.get("roadmap_hours",0) or 0, hpd_val)} at {hpd_val}h/day</span>
        </div>
      </div>
      <div class="sf-scores">
        <div class="sf-score-card">
          <div class="sf-score-lbl">Training hours</div>
          <div class="sf-score-num" style="color:var(--teal)">{im['roadmap_hours']}h</div>
          <div class="sf-score-sub">{hours_narrative}</div>
        </div>
        <div class="sf-score-card">
          <div class="sf-score-lbl">Interview readiness</div>
          <div class="sf-score-num" style="color:{iv_c}">{iv['score']}%</div>
          <div class="sf-score-sub">{iv['label']} · {iv.get('advice','')}</div>
        </div>
        <div class="sf-score-card">
          <div class="sf-score-lbl">ATS score</div>
          <div class="sf-score-num" style="color:var(--teal)">{ats}%</div>
          <div class="sf-score-sub">Grade <strong style="color:var(--teal)">{grade}</strong> · {int(ql.get('completeness_score') or 0)}% complete</div>
        </div>
      </div>
      <div class="sf-ground-badge">
        <span class="sf-ground-dot"></span>
        Catalog-grounded recommendations &nbsp;·&nbsp; All {im['modules_count']} modules from 47-course catalog &nbsp;·&nbsp; {im['critical_count']} on critical path
      </div>
    </div>""", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Modules",        im.get("modules_count", 0),   f"{im.get('critical_count', 0)} critical")
    saved_delta = f"~{hours_saved}h vs generic" if hours_saved > 0 else "tailored to your gaps"
    k2.metric("Training hours", f"{im['roadmap_hours']}h",    saved_delta)
    k3.metric("Done in",        weeks_ready(im.get("roadmap_hours",0) or 0, hpd_val), f"at {hpd_val}h/day")
    k4.metric("Skills covered", f"{im['gaps_addressed']}/{im['total_skills']}", f"{im['known_skills']} already known")

    sm = res.get("seniority", {})
    if sm.get("has_mismatch"):
        st.markdown(
            f'<div class="sf-seniority-pill">⚠ Seniority gap: {sm["candidate"]} → {sm["required"]} · leadership modules added</div>',
            unsafe_allow_html=True,
        )
    if im.get("decayed_skills", 0):
        st.markdown(
            f'<div style="font-family:var(--mono);font-size:0.72rem;color:var(--amber);margin-bottom:8px">⏱ {im["decayed_skills"]} skill(s) have decayed — proficiency adjusted</div>',
            unsafe_allow_html=True,
        )


# =============================================================================
#  TAB: GAP ANALYSIS
# =============================================================================
def render_tab_overview(res: dict) -> None:
    gp     = res["gap_profile"]
    trends = res.get("skill_trends", {}) or {}
    sal    = res.get("salary",       {}) or {}

    k_c = sum(1 for g in gp if g["status"] == "Known")
    p_c = sum(1 for g in gp if g["status"] == "Partial")
    m_c = sum(1 for g in gp if g["status"] == "Missing")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Skill gap</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sf-ss">{k_c} known · {p_c} partial · {m_c} missing</div>', unsafe_allow_html=True)

    col_flt, col_radar = st.columns([1.4, 1], gap="large")
    with col_flt:
        filt = st.selectbox("Filter", ["All","Missing","Partial","Known","Required only"],
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
            prof  = int(g.get("proficiency") or 0)
            pct   = prof / 10 * 100
            req   = "★ " if g["is_required"] else ""
            trend = trends.get(g["skill"]) or _bk.demand_label(g["skill"])
            tc    = _RED if "Hot" in trend else _AMBER if "Growing" in trend else "#3d4d66"
            decay = '<span class="sf-decay-tag">⏱ decayed</span>' if g.get("decayed") else ""
            ctx   = f'<div class="sf-skill-ctx">{g["context"]}</div>' if g.get("context") else ""
            co    = g.get("catalog_course")
            ctxt  = (f'<div style="font-family:var(--mono);font-size:0.65rem;color:var(--t3);margin-top:5px">📚 {co["title"]} · {co["duration_hrs"]}h · {co["level"]}</div>') if co else ""
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
                    f'<div style="font-family:var(--mono);font-size:0.7rem;color:var(--t3);margin-top:3px">{o["reason"]}</div></div>',
                    unsafe_allow_html=True,
                )

    with col_radar:
        st.plotly_chart(animated_radar_chart(gp), use_container_width=True,
                         config={"displayModeBar": False}, key="radar_overview")

        tf = res.get("transfers", [])
        if tf:
            st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:14px 0 8px">Transfer advantages</div>', unsafe_allow_html=True)
            for t in tf[:5]:
                strength = t.get("strength", "partial").lower()
                st.markdown(
                    f'<div class="sf-xfer {strength}">'
                    f'<div><span class="sf-xfer-pct">↗{t["transfer_pct"]}%</span></div>'
                    f'<div><div>{t["label"]}</div>'
                    f'<div class="sf-xfer-desc">{strength.title()} overlap · speeds up learning</div></div>'
                    f'</div>', unsafe_allow_html=True,
                )

        known_hot = sum(1 for g in gp if g["status"] == "Known"
                        and _bk.MARKET_DEMAND.get(g["skill"].lower(), 0) >= 3)
        total_hot = sum(1 for g in gp if _bk.MARKET_DEMAND.get(g["skill"].lower(), 0) >= 3)
        if total_hot > 0:
            pct_raw    = round(known_hot / total_hot * 100)
            percentile = max(10, min(90, 20 + pct_raw * 0.7))
            better_than = 100 - int(percentile)
            pct_label   = f"Top {better_than}%" if better_than <= 35 else f"Better than {better_than}%"
            pct_sub     = ("strong candidate for in-demand skills"
                           if better_than <= 35
                           else "of applicants — address gaps to rank higher")
            st.markdown(f"""
            <div style="margin-top:16px;background:rgba(167,139,250,0.06);border:1px solid rgba(167,139,250,0.2);
                        border-radius:8px;padding:12px 16px;">
              <div style="font-family:var(--mono);font-size:0.6rem;letter-spacing:0.1em;
                          text-transform:uppercase;color:var(--purple);margin-bottom:6px">Peer percentile</div>
              <div style="font-family:var(--mono);font-size:1.6rem;font-weight:500;color:var(--t1);line-height:1">
                {pct_label}
              </div>
              <div style="font-size:0.72rem;color:var(--t3);margin-top:4px">{pct_sub}</div>
            </div>""", unsafe_allow_html=True)

        try:
            sal_med = float(sal.get("median_lpa") or 0)
        except (TypeError, ValueError):
            sal_med = 0.0
        if sal and sal_med > 0:
            st.markdown(f'<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:16px 0 4px">Live salary — {res["jd"].get("role_title","")[:24]}</div>', unsafe_allow_html=True)
            st.plotly_chart(salary_chart(sal), use_container_width=True,
                             config={"displayModeBar": False}, key="salary_overview")
            st.caption(f"Source: {sal.get('source','web')} · {sal.get('note','')}")


# =============================================================================
#  TAB: ROADMAP
# =============================================================================
def render_tab_roadmap(res: dict) -> None:
    path = res["path"]

    candidate_key = (res.get("candidate",{}).get("name","") +
                     res.get("jd",{}).get("role_title","")).replace(" ","_")[:40]
    storage_key   = f"sf_progress_{candidate_key}"

    import streamlit.components.v1 as _components
    _components.html(f"""
    <script>
    (function() {{
      var saved = localStorage.getItem('{storage_key}');
      if (saved) {{
        window.parent.postMessage({{type:'sf_progress', data: saved, key:'{storage_key}'}}, '*');
      }}
    }})();
    </script>
    """, height=0)

    completed = set(st.session_state.get("completed", []))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    hd_l, hd_r = st.columns([2, 1])
    with hd_l:
        st.markdown('<div class="sf-sh">Learning roadmap</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-ss">Dependency-ordered · critical path highlighted</div>', unsafe_allow_html=True)
    with hd_r:
        hpd = st.select_slider("Pace (h/day)", options=[1,2,4,8],
                                value=int(st.session_state.get("hpd",2) or 2),
                                key="hpd_slider")
        st.session_state["hpd"] = hpd
        rem = sum(int(m.get("duration_hrs") or 0) for m in path if m["id"] not in completed)
        st.markdown(f'<p style="font-family:var(--mono);font-size:0.72rem;color:var(--t2);text-align:right">{rem}h remaining · <strong style="color:var(--teal)">{weeks_ready(rem, hpd)}</strong></p>', unsafe_allow_html=True)

    gap_skills_u = list({m["skill"] for m in path})
    if len(st.session_state.get("course_cache", {})) < len(gap_skills_u):
        if st.button(f"Load course links for all {len(gap_skills_u)} skills",
                     key="load_all_crs", type="secondary"):
            with st.spinner("Searching Coursera · Udemy · YouTube…"):
                cc: dict = {}
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {ex.submit(search_course_links, s): s for s in gap_skills_u[:10]}
                    for f in futs:
                        cc[futs[f]] = f.result()
            st.session_state["course_cache"] = cc
            st.success(f"✓ {len(cc)} skills with course links")
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    with st.expander("📅 Week 1 study plan", expanded=True):
        rem_path = [m for m in path if m["id"] not in completed]
        wp_quick = weekly_plan(rem_path, float(hpd))
        if wp_quick:
            w = wp_quick[0]
            st.markdown(f"**Week 1 · {w['total_hrs']:.0f}h of {hpd * 5}h weekly capacity**")
            for mx in w["modules"]:
                star = "★ " if mx.get("is_critical") else ""
                st.markdown(f"- {star}**{mx['title']}** · `{mx['hrs_this_week']:.0f}h`")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    mod_col, chart_col = st.columns([1.1, 1], gap="large")

    with mod_col:
        phases = [
            ("Foundation", [m for m in path if m["level"] == "Beginner"]),
            ("Build",      [m for m in path if m["level"] == "Intermediate"]),
            ("Advanced",   [m for m in path if m["level"] == "Advanced"]),
        ]
        idx = 0
        for phase_name, mods in phases:
            if not mods:
                continue
            phase_hrs = sum(int(m.get("duration_hrs") or 0) for m in mods)
            st.markdown(f'<div class="sf-phase-hd">{phase_name} <span style="font-weight:400;color:var(--t4)">{len(mods)} modules · {phase_hrs}h</span></div>', unsafe_allow_html=True)
            for m in mods:
                idx    += 1
                is_done = m["id"] in completed
                is_crit = m.get("is_critical", False)
                level   = m["level"]
                lc      = "crit" if is_crit else "adv" if level == "Advanced" else "inter" if level == "Intermediate" else "beg"
                dc      = " done" if is_done else ""

                chk = st.checkbox(
                    f"{m['title']} · {int(m.get('duration_hrs') or 0)}h · {m['level']}",
                    value=is_done, key=f"c_{m['id']}"
                )
                if chk:
                    completed.add(m["id"])
                else:
                    completed.discard(m["id"])
                st.session_state["completed"] = list(completed)
                _components.html(f"""
                <script>
                try {{ localStorage.setItem('{storage_key}', JSON.stringify({json.dumps(list(completed))})); }} catch(e) {{}}
                </script>""", height=0)

                prereqs_txt = ", ".join(m.get("prereqs", []) or []) or "none"
                tags = []
                if is_crit:              tags.append('<span class="sf-tag sf-tag-crit">★ critical</span>')
                if m.get("is_required"): tags.append('<span class="sf-tag sf-tag-req">required</span>')
                tags.append(f'<span class="sf-tag">{m["domain"]}</span>')

                reason_html = (
                    '<div class="sf-mod-trace"><span class="sf-mod-trace-lbl">AI Reasoning</span>'
                    f'<div class="sf-mod-trace-body">{m["reasoning"]}</div></div>'
                ) if m.get("reasoning") else ""

                st.markdown(
                    f'<div class="sf-mod {lc}{dc}">'
                    f'<div class="sf-mod-row">'
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
                        st.link_button(f"Coursera: {m['skill']}",
                                        f"https://www.coursera.org/search?query={q}",
                                        use_container_width=True)
                    with lc2:
                        st.link_button(f"YouTube: {m['skill']}",
                                        f"https://www.youtube.com/results?search_query={q}+tutorial",
                                        use_container_width=True)

    with chart_col:
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:8px">ROI ranking</div>', unsafe_allow_html=True)
        st.plotly_chart(roi_bar(res.get("roi", [])), use_container_width=True,
                         config={"displayModeBar": False}, key="roi_roadmap")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:10px">Training timeline</div>', unsafe_allow_html=True)
    st.plotly_chart(timeline_chart(path), use_container_width=True,
                     config={"displayModeBar": False}, key="timeline_roadmap")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:10px">Full weekly study plan</div>', unsafe_allow_html=True)
    rem_path2 = [m for m in path if m["id"] not in completed]
    wp = weekly_plan(rem_path2, float(hpd))
    for w in wp[:8]:
        with st.expander(f"Week {w['week']} — {w['total_hrs']:.0f}h"):
            for mx in w["modules"]:
                star = "★ " if mx.get("is_critical") else ""
                st.markdown(f"- {star}**{mx['title']}** · `{mx['hrs_this_week']:.0f}h` of `{mx['total_hrs']}h`")

    im     = res["impact"]
    saved  = im.get("hours_saved", 0)
    longer = im.get("roadmap_longer", False)
    save_note = (
        f"Personalized path covering your specific gap ({im['modules_count']} modules)"
        if longer
        else f"~{saved}h saved vs generic 60h onboarding"
    )
    st.markdown(f"""
    <div class="sf-impact-box">
      <div class="sf-impact-row">
        <div class="sf-impact-item"><div class="sf-impact-lbl">Generic onboarding</div><div class="sf-impact-val" style="color:var(--t3);text-decoration:line-through">60h</div></div>
        <div class="sf-impact-arrow">→</div>
        <div class="sf-impact-item"><div class="sf-impact-lbl">Your personalised path</div><div class="sf-impact-val" style="color:var(--teal)">{im['roadmap_hours']}h</div></div>
        <div class="sf-impact-arrow">→</div>
        <div class="sf-impact-item"><div class="sf-impact-lbl">Outcome</div><div class="sf-impact-val" style="color:var(--green);font-size:1.2rem">{'+' + str(saved) + 'h saved' if not longer else 'Tailored'}</div></div>
      </div>
      <div class="sf-impact-sub">{save_note} · {im['known_skills']} skills skipped · {im['critical_count']} critical nodes</div>
    </div>""", unsafe_allow_html=True)

    roadmap_hrs    = int(im.get("roadmap_hours", 0))
    train_cost_inr = roadmap_hrs * 500
    hire_cost_inr  = 1000000
    savings_inr    = max(0, hire_cost_inr - train_cost_inr)
    st.markdown(f"""
    <div style="background:rgba(45,212,191,0.04);border:1px solid rgba(45,212,191,0.15);border-radius:10px;padding:18px 24px;margin-top:12px">
      <div style="font-family:var(--mono);font-size:0.62rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--teal);margin-bottom:12px">💰 Business case: train vs hire</div>
      <div style="display:flex;gap:0;align-items:center">
        <div style="flex:1;text-align:center">
          <div style="font-family:var(--mono);font-size:1.4rem;font-weight:500;color:var(--t1)">₹{train_cost_inr:,}</div>
          <div style="font-family:var(--mono);font-size:0.6rem;color:var(--t3);margin-top:3px">Cost to train ({roadmap_hrs}h × ₹500/hr)</div>
        </div>
        <div style="color:var(--t4);padding:0 16px;font-size:1.2rem">vs</div>
        <div style="flex:1;text-align:center">
          <div style="font-family:var(--mono);font-size:1.4rem;font-weight:500;color:var(--t1)">₹{hire_cost_inr:,}</div>
          <div style="font-family:var(--mono);font-size:0.6rem;color:var(--t3);margin-top:3px">Est. cost to hire Mid-level externally</div>
        </div>
        <div style="color:var(--t4);padding:0 16px;font-size:1.2rem">→</div>
        <div style="flex:1;text-align:center">
          <div style="font-family:var(--mono);font-size:1.4rem;font-weight:500;color:var(--green)">₹{savings_inr:,}</div>
          <div style="font-family:var(--mono);font-size:0.6rem;color:var(--t3);margin-top:3px">Estimated savings by upskilling internally</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)


# =============================================================================
#  TAB: RESEARCH
# =============================================================================
def render_tab_research(res: dict) -> None:
    gp     = res["gap_profile"]
    sal    = res.get("salary",          {}) or {}
    mkt    = res.get("market_insights", []) or []
    trends = res.get("skill_trends",    {}) or {}
    jd     = res["jd"]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Web research</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">Live search — courses, salaries, market trends</div>', unsafe_allow_html=True)

    web_available = not bool(_bk._DDG_ERROR)
    q_col, btn_col = st.columns([5, 1])
    with q_col:
        if "search_input" not in st.session_state:
            st.session_state["search_input"] = st.session_state.get("search_query", "")
        st.text_input("Search",
                      placeholder='"React 2025" · "FastAPI salary Bangalore" · "Docker course"',
                      key="search_input", label_visibility="collapsed")
        st.session_state["search_query"] = st.session_state.get("search_input", "")
    with btn_col:
        do_search = st.button("Search", key="go_search", use_container_width=True)

    if not web_available:
        st.markdown('<div class="sf-empty-state"><div class="sf-empty-icon">🔌</div><div class="sf-empty-label">Web search unavailable</div><div>Install ddgs: <code>pip install ddgs</code></div></div>', unsafe_allow_html=True)
    else:
        gap_skills_s = [g["skill"] for g in gp if g["status"] != "Known"][:4]
        shortcuts    = [(s, f"{s} online course tutorial 2025") for s in gap_skills_s]

        if shortcuts:
            sc_cols = st.columns(len(shortcuts))
            for i, (lbl, q) in enumerate(shortcuts):
                with sc_cols[i]:
                    if st.button(lbl[:22], key=f"sc_{i}",
                                  use_container_width=True, type="secondary"):
                        st.session_state.pop("search_input", None)
                        st.session_state["search_query"]   = q
                        st.session_state["search_results"] = ddg_search(q, max_results=8)
                        st.rerun()

        if do_search and st.session_state.get("search_query", "").strip():
            with st.spinner("Searching…"):
                st.session_state["search_results"] = ddg_search(
                    st.session_state["search_query"], max_results=8
                )

        results = st.session_state.get("search_results", [])
        if results:
            shown = [r for r in results if _is_english(r.get("title","")) and _is_english(r.get("body",""))] or results
            st.markdown(f'<div style="font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin:10px 0 8px">{len(shown)} results</div>', unsafe_allow_html=True)
            for r in shown:
                href   = r.get("href", "")
                domain = href.split("/")[2] if href.count("/") >= 2 else href
                st.markdown(
                    f'<div class="sf-search-result"><a class="sf-search-title" href="{href}" target="_blank">{r.get("title","No title")}</a>'
                    f'<div class="sf-search-url">{domain}</div>'
                    f'<div class="sf-search-body">{r.get("body","")[:200]}</div></div>',
                    unsafe_allow_html=True,
                )
        elif do_search:
            st.markdown('<div class="sf-empty-state"><div class="sf-empty-icon">🔍</div><div class="sf-empty-label">No results found</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    sal_col, mkt_col = st.columns(2, gap="large")
    with sal_col:
        st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:10px">Salary benchmark</div>', unsafe_allow_html=True)
        try:
            sal_med = float(sal.get("median_lpa") or 0)
        except (TypeError, ValueError):
            sal_med = 0.0
        if sal and sal_med > 0:
            st.plotly_chart(salary_chart(sal), use_container_width=True,
                             config={"displayModeBar": False}, key="salary_research")
            st.caption(f"Source: {sal.get('source','web')} · {sal.get('note','')}")
        else:
            loc2 = st.selectbox("Location", _LOC_OPTS, key="sal_loc2")
            if st.button("Fetch salary data", key="sal_fetch",
                          use_container_width=True, type="secondary"):
                with st.spinner("Searching…"):
                    _sal_new = search_real_salary(jd.get("role_title",""), loc2)
                if _sal_new:
                    st.session_state["result"]["salary"] = _sal_new
                    st.rerun()
                else:
                    st.markdown('<div class="sf-empty-state"><div class="sf-empty-icon">💼</div><div class="sf-empty-label">No salary data found</div></div>', unsafe_allow_html=True)

    with mkt_col:
        st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:10px">Job market insights</div>', unsafe_allow_html=True)
        if mkt:
            for ins in mkt:
                st.markdown(
                    f'<div class="sf-insight"><span style="color:var(--teal);margin-right:8px;font-weight:bold">›</span>{ins}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="sf-empty-state"><div class="sf-empty-icon">📊</div><div class="sf-empty-label">Not fetched yet</div></div>', unsafe_allow_html=True)
            if st.button("Fetch insights", key="mkt_fetch", type="secondary"):
                with st.spinner("Searching…"):
                    st.session_state["result"]["market_insights"] = search_job_market(jd.get("role_title",""))
                st.rerun()

    if trends:
        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.9rem;font-weight:600;color:var(--t1);margin-bottom:10px">Skill demand signals</div>', unsafe_allow_html=True)
        pills = ""
        for skill, sig in trends.items():
            sc = _RED if "Hot" in sig else _AMBER if "Growing" in sig else "#3d4d66"
            pills += f'<span class="sf-trend-pill"><span style="color:var(--t1);font-weight:500">{skill[:14]}</span><span style="color:{sc}">&nbsp;{sig}</span></span>'
        st.markdown(f'<div style="line-height:2.6">{pills}</div>', unsafe_allow_html=True)
        if st.button("Re-fetch trends", key="refetch_trends", type="secondary"):
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
            if st.button("Find", key="crs_go", use_container_width=True, type="secondary"):
                with st.spinner(f"Searching {sel_s}…"):
                    cc = st.session_state.get("course_cache", {})
                    cc[sel_s] = search_course_links(sel_s)
                    st.session_state["course_cache"] = cc
                st.rerun()
        cached = st.session_state.get("course_cache", {}).get(sel_s, [])
        if cached:
            for crs in cached:
                st.markdown(
                    f'<div class="sf-search-result"><a class="sf-search-title" href="{crs["url"]}" target="_blank">{crs["icon"]} {crs["title"]}</a>'
                    f'<div class="sf-search-url">{crs["platform"]}</div>'
                    f'<div class="sf-search-body">{crs["snippet"]}</div></div>',
                    unsafe_allow_html=True,
                )
        elif sel_s in st.session_state.get("course_cache", {}):
            st.markdown(f'<div class="sf-empty-state"><div class="sf-empty-icon">📚</div><div class="sf-empty-label">No course links found for {sel_s}</div></div>', unsafe_allow_html=True)


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
      <div class="sf-ats-card"><div class="sf-ats-n">{ql.get('ats_score','–')}%</div><div class="sf-ats-l">ATS Score</div></div>
      <div class="sf-ats-card"><div class="sf-ats-n" style="color:var(--teal)">{ql.get('overall_grade','–')}</div><div class="sf-ats-l">Grade</div></div>
      <div class="sf-ats-card"><div class="sf-ats-n">{ql.get('completeness_score','–')}%</div><div class="sf-ats-l">Completeness</div></div>
      <div class="sf-ats-card"><div class="sf-ats-n">{ql.get('clarity_score','–')}%</div><div class="sf-ats-l">Clarity</div></div>
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
        for iss in (ql.get("ats_issues") or [])[:5]:
            st.warning(iss)
        if not ql.get("ats_issues"):
            st.success("No critical ATS issues found")

        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin:12px 0 6px">Missing keywords</div>', unsafe_allow_html=True)
        kws = ql.get("missing_keywords") or []
        if kws:
            st.markdown("".join(f'<span class="sf-kw">{k}</span>' for k in kws), unsafe_allow_html=True)
        else:
            st.markdown('<span style="font-family:var(--mono);font-size:0.72rem;color:var(--t3)">None identified</span>', unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Interview", f"{iv.get('score', 0)}%", iv.get("label","–"))
        c2.metric("Seniority gap",
                  f"{sm.get('gap_levels', 0)} level{'s' if sm.get('gap_levels',0)!=1 else ''}"
                  if sm.get('gap_levels',0) > 0 else "None")
        c3.metric("Time to level up",
                  f"~{cgm}mo" if cgm else "On track",
                  "est. to reach target seniority" if cgm else "")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:4px">AI resume rewrite</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin-bottom:12px">ATS-optimized · existing facts only · no disclaimers or gap admissions</div>', unsafe_allow_html=True)

    rtxt = st.session_state.get("resume_text", "")
    if not rtxt and st.session_state.get("resume_image"):
        ei = res.get("candidate", {})
        if ei.get("name"):
            rtxt = f"{ei.get('name','')}\n{ei.get('current_role','')}\n" + \
                   "\n".join(f"- {s['skill']} ({s['proficiency']}/10)"
                              for s in ei.get("skills", []))

    if rtxt:
        if st.button("Generate ATS-optimized rewrite ⚡", key="gen_rw", use_container_width=True):
            with st.spinner("Rewriting with LLaMA 3.3-70b…"):
                rw = rewrite_resume(rtxt, jd, kws)
            st.session_state["rw_result"] = rw
            kw_count_before = sum(1 for k in (kws or []) if k.lower() in rtxt.lower())
            kw_count_after  = sum(1 for k in (kws or []) if k.lower() in rw.lower())
            kw_total        = max(len(kws or []), 1)
            improvement     = min(25, round((kw_count_after - kw_count_before) / kw_total * 40))
            st.session_state["rw_ats_before"] = ats_pct
            st.session_state["rw_ats_after"]  = min(88, ats_pct + improvement)

        rw = st.session_state.get("rw_result")
        if rw:
            before_score = st.session_state.get("rw_ats_before", ats_pct)
            after_score  = st.session_state.get("rw_ats_after",  min(88, ats_pct + 10))
            delta        = after_score - before_score
            st.markdown(f"""
            <div style="display:flex;gap:12px;margin-bottom:14px;align-items:center">
              <div class="sf-ats-card" style="flex:1;text-align:center;padding:12px">
                <div class="sf-ats-n" style="font-size:1.4rem;color:var(--t3)">{before_score}%</div>
                <div class="sf-ats-l">Before rewrite</div>
              </div>
              <div style="font-size:1.4rem;color:var(--teal)">→</div>
              <div class="sf-ats-card" style="flex:1;text-align:center;padding:12px;border-color:rgba(45,212,191,0.3)">
                <div class="sf-ats-n" style="font-size:1.4rem;color:var(--teal)">{after_score}%</div>
                <div class="sf-ats-l">After rewrite</div>
              </div>
              <div style="font-family:var(--mono);font-size:1.2rem;color:var(--green);padding:0 8px">+{delta}%</div>
            </div>""", unsafe_allow_html=True)

            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown('<div style="font-family:var(--mono);font-size:0.62rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--t3);margin-bottom:6px">Original</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff">{rtxt[:1400]}</div>', unsafe_allow_html=True)
            with rc2:
                st.markdown('<div style="font-family:var(--mono);font-size:0.62rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--teal);margin-bottom:6px">Rewritten ✓</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff">{rw[:1400]}</div>', unsafe_allow_html=True)
            st.download_button("Download rewritten resume", data=rw,
                                file_name="skillforge_rewritten.txt", mime="text/plain",
                                key="dl_rewrite")
    elif st.session_state.get("resume_image"):
        st.info("Image resume detected — using extracted candidate info for rewrite.")

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Export</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">Download your personalised roadmap as PDF · JSON · CSV · Calendar</div>', unsafe_allow_html=True)

    import base64 as _b64
    share_payload = json.dumps({
        "name":    c.get("name",""),
        "role":    jd.get("role_title",""),
        "delta":   im.get("fit_delta",0),
        "hours":   im.get("roadmap_hours",0),
        "iv":      iv.get("score",0),
        "modules": im.get("modules_count",0),
    }, separators=(',',':'))
    share_b64 = _b64.urlsafe_b64encode(share_payload.encode()).decode()
    share_url = f"?share={share_b64}"
    st.markdown(f"""
    <div style="background:var(--s2);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;align-items:center;gap:12px">
      <span style="font-family:var(--mono);font-size:0.68rem;color:var(--t3)">🔗 Share this roadmap</span>
      <code style="flex:1;font-family:var(--mono);font-size:0.65rem;color:var(--teal);background:var(--s1);padding:4px 10px;border-radius:4px;border:1px solid var(--border);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{share_url[:80]}…</code>
      <span style="font-family:var(--mono);font-size:0.6rem;color:var(--t4)">Copy URL to share</span>
    </div>""", unsafe_allow_html=True)

    ex1, ex2, ex3, ex4 = st.columns(4, gap="medium")
    export_meta = [
        ("Candidate", c.get("name", "–")),
        ("Role",      jd.get("role_title", "–")),
        ("ATS score", f"{ql.get('ats_score','–')}%"),
        ("Modules",   im.get("modules_count", 0)),
        ("Training",  f"{im['roadmap_hours']}h"),
    ]

    with ex1:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">PDF report</div><div class="sf-export-sub">Full roadmap · AI reasoning · ATS audit</div>', unsafe_allow_html=True)
        for k, v in export_meta:
            st.markdown(f'<div class="sf-export-row"><span class="sf-ek">{k}</span><span class="sf-ev">{v}</span></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if REPORTLAB:
            pdf_buf = build_pdf(c, jd, gp, roadmap, im, ql, iv)
            nm = (c.get("name","candidate") or "candidate").replace(" ","_")
            st.download_button("Download PDF", data=pdf_buf,
                                file_name=f"skillforge_{nm}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf", use_container_width=True, key="dl_pdf")
        else:
            st.caption("`pip install reportlab` to enable PDF")
        st.markdown('</div>', unsafe_allow_html=True)

    with ex2:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">JSON export</div><div class="sf-export-sub">Complete structured result for integrations</div>', unsafe_allow_html=True)
        for k, v in export_meta:
            st.markdown(f'<div class="sf-export-row"><span class="sf-ek">{k}</span><span class="sf-ev">{v}</span></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        export_data = {
            "candidate": c, "jd": jd, "impact": im, "interview": iv,
            "gap_profile": [{k2: v2 for k2, v2 in g.items() if k2 != "catalog_course"} for g in gp],
            "roadmap": [{"id": m["id"], "title": m["title"], "skill": m["skill"],
                          "level": m["level"], "duration_hrs": m["duration_hrs"],
                          "is_critical": m.get("is_critical", False),
                          "is_required": m.get("is_required", False),
                          "reasoning": m.get("reasoning","")} for m in roadmap],
            "generated_at": datetime.now().isoformat(),
        }
        st.download_button("Download JSON",
                            data=json.dumps(export_data, indent=2, default=str),
                            file_name=f"skillforge_{datetime.now().strftime('%Y%m%d')}.json",
                            mime="application/json", use_container_width=True, key="dl_json")
        st.markdown('</div>', unsafe_allow_html=True)

    with ex3:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">CSV export</div><div class="sf-export-sub">Roadmap modules for tracking progress</div>', unsafe_allow_html=True)
        for k, v in export_meta:
            st.markdown(f'<div class="sf-export-row"><span class="sf-ek">{k}</span><span class="sf-ev">{v}</span></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        csv_rows = ["id,title,skill,level,domain,duration_hrs,is_critical,is_required,reasoning"]
        for m in roadmap:
            rsn = (m.get("reasoning") or f"Addresses gap in {m['skill']}.").replace(",",";").replace("\n"," ")
            title_clean = m["title"].replace(",",";").strip()
            csv_rows.append(
                f'{m["id"]},{title_clean},{m["skill"]},'
                f'{m["level"]},{m["domain"]},{m["duration_hrs"]},'
                f'{m.get("is_critical",False)},{m.get("is_required",False)},{rsn}'
            )
        st.download_button("Download CSV", data="\n".join(csv_rows),
                            file_name=f"skillforge_roadmap_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv", use_container_width=True, key="dl_csv")
        st.markdown('</div>', unsafe_allow_html=True)

    with ex4:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">📅 Calendar</div><div class="sf-export-sub">One session/day · 7 PM · no midnight slots</div>', unsafe_allow_html=True)
        for k, v in export_meta:
            st.markdown(f'<div class="sf-export-row"><span class="sf-ek">{k}</span><span class="sf-ev">{v}</span></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        hpd_val  = int(st.session_state.get("hpd", 2) or 2)
        ics_data = build_ics_calendar(roadmap, hpd=hpd_val)
        nm       = (c.get("name","candidate") or "candidate").replace(" ","_")
        st.download_button("Download .ics Calendar", data=ics_data,
                            file_name=f"skillforge_{nm}_schedule.ics",
                            mime="text/calendar", use_container_width=True, key="dl_ics")
        st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
#  TAB: 3D DAG VIEW
# =============================================================================
def render_tab_dag(res: dict) -> None:
    path = res.get("path", [])
    gp   = res.get("gap_profile", [])

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Dependency graph</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">3D force-directed graph · drag to rotate · scroll to zoom · click nodes for details</div>', unsafe_allow_html=True)

    dag_data     = build_dag_data(path, gp)
    dag_html_path = pathlib.Path(__file__).parent / "components" / "dag_3d.html"
    if dag_html_path.exists():
        dag_html = dag_html_path.read_text()
        data_script = f"<script>window.SKILLFORGE_DAG = {json.dumps(dag_data)};</script>"
        dag_html    = dag_html.replace("</head>", data_script + "\n</head>")
        import streamlit.components.v1 as components
        components.html(dag_html, height=520, scrolling=False)
    else:
        st.warning("DAG component not found. Ensure `components/dag_3d.html` exists.")

    crit_count  = sum(1 for m in path if m.get("is_critical"))
    req_count   = sum(1 for m in path if m.get("is_required"))
    prereq_count = len(path) - req_count
    st.markdown(f"""
    <div style="display:flex;gap:20px;margin-top:14px;font-family:var(--mono);font-size:0.72rem;color:var(--t3)">
      <span><span style="color:#ef4444">●</span> {crit_count} critical path nodes</span>
      <span><span style="color:#2dd4bf">●</span> {req_count} required skill modules</span>
      <span><span style="color:#475569">●</span> {prereq_count} prerequisite modules</span>
      <span style="margin-left:auto">{len(dag_data['edges'])} dependency edges</span>
    </div>""", unsafe_allow_html=True)

    with st.expander("Dependency chain details"):
        for edge in dag_data["edges"]:
            src_m = next((m for m in path if m["id"] == edge["src"]), None)
            dst_m = next((m for m in path if m["id"] == edge["dst"]), None)
            if src_m and dst_m:
                st.markdown(
                    f'<div style="font-family:var(--mono);font-size:0.72rem;color:var(--t3);'
                    f'padding:4px 0;border-bottom:1px solid var(--border)">'
                    f'<span style="color:var(--t2)">{src_m["title"]}</span>'
                    f' → <span style="color:var(--teal)">{dst_m["title"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# =============================================================================
#  TAB: INTERVIEW PREP
# =============================================================================
def render_tab_interview_prep(res: dict) -> None:
    gp        = res.get("gap_profile", [])
    candidate = res.get("candidate",   {})
    jd        = res.get("jd",          {})
    iv        = res.get("interview",   {})

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="sf-sh">Interview prep</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-ss">AI-generated questions per skill · calibrated to your seniority level</div>', unsafe_allow_html=True)

    score = iv.get("score", 0)
    label = iv.get("label", "–")

    col1, col2, col3 = st.columns(3)
    col1.metric("Readiness score",       f"{score}%",                     label,        delta_color="off")
    col2.metric("Skills you can answer", str(iv.get("req_known", 0)),     "ready now",  delta_color="off")
    col3.metric("Skills needing prep",   str(iv.get("req_missing", 0)),   "study first",delta_color="off")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    preppable = [g for g in gp if g["status"] in ("Known","Partial") and g["is_required"]]
    missing   = [g for g in gp if g["status"] == "Missing" and g["is_required"]]

    if missing:
        st.markdown(
            f'<div class="sf-seniority-pill" style="background:rgba(239,68,68,0.06);'
            f'border-color:rgba(239,68,68,0.2);color:var(--red)">'
            f'⚠ {len(missing)} required skill(s) need learning before interview: '
            f'{", ".join(g["skill"] for g in missing)}</div>',
            unsafe_allow_html=True,
        )

    if not preppable:
        st.info("Complete some roadmap modules first, then return here to generate interview questions.")
        return

    iq = st.session_state.get("interview_questions", {})

    if st.button("Generate interview questions ⚡", key="gen_iq", use_container_width=True):
        with st.spinner("Generating targeted questions with LLaMA 3.3-70b…"):
            questions = generate_interview_questions(gp, candidate, jd)
        st.session_state["interview_questions"] = questions
        iq = questions
        if questions:
            st.success(f"✓ Generated questions for {len(questions)} skills")

    if iq:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        for g in preppable:
            skill  = g["skill"]
            prof   = g["proficiency"]
            status = g["status"]
            bc     = "sf-st-known" if status == "Known" else "sf-st-partial"
            qs     = iq.get(skill, [])
            with st.expander(f"{skill}  ·  {prof}/10", expanded=(status=="Known")):
                st.markdown(
                    f'<span class="sf-st-badge {bc}" style="margin-bottom:10px;display:inline-block">{status}</span>'
                    f'<div style="font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin-bottom:12px">'
                    f'{_strip_mern_prefix(g.get("context",""))}</div>',
                    unsafe_allow_html=True,
                )
                if qs:
                    for i, q in enumerate(qs[:3], 1):
                        st.markdown(
                            f'<div style="background:var(--s2);border:1px solid var(--border);'
                            f'border-left:3px solid var(--teal);border-radius:0 8px 8px 0;'
                            f'padding:12px 16px;margin-bottom:8px;">'
                            f'<div style="font-family:var(--mono);font-size:0.62rem;color:var(--teal);margin-bottom:5px">Q{i}</div>'
                            f'<div style="font-size:0.88rem;color:var(--t1);line-height:1.5">{q}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        f'<div class="sf-empty-state"><div class="sf-empty-icon">💬</div>'
                        f'<div class="sf-empty-label">No questions yet</div>'
                        f'<div>Click "Generate interview questions" above</div></div>',
                        unsafe_allow_html=True,
                    )

        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.88rem;font-weight:600;color:var(--t1);margin-bottom:10px">Your strongest talking points</div>', unsafe_allow_html=True)
        for g in gp:
            if g["status"] == "Known" and g["is_required"] and g.get("context"):
                st.markdown(
                    f'<div class="sf-talk">→ <strong>{g["skill"]}</strong> ({g["proficiency"]}/10): '
                    f'{_strip_mern_prefix(g["context"])}</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        for g in preppable:
            col_c = _TEAL if g["status"] == "Known" else _AMBER
            st.markdown(
                f'<div style="background:var(--s1);border:1px solid var(--border);'
                f'border-left:3px solid {col_c};border-radius:0 9px 9px 0;'
                f'padding:12px 16px;margin-bottom:8px;">'
                f'<div style="font-size:0.88rem;font-weight:600;color:var(--t1)">{g["skill"]} · {g["proficiency"]}/10</div>'
                f'<div style="font-family:var(--mono);font-size:0.68rem;color:var(--t3);margin-top:4px">'
                f'{_strip_mern_prefix(g.get("context","No context available"))}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# =============================================================================
#  SIDEBAR
# =============================================================================
def render_sidebar(res: dict) -> None:
    im = res["impact"]
    iv = res["interview"]

    with st.sidebar:
        st.markdown(
            '<div style="padding:14px 10px 6px">'
            '<div style="font-family:\'DM Sans\',sans-serif;font-size:1rem;font-weight:700;'
            'color:#f1f5f9;letter-spacing:-0.02em">Skill<span style="color:#2dd4bf">Forge</span></div></div>',
            unsafe_allow_html=True,
        )

        c = res["candidate"]
        st.markdown(
            f'<div style="padding:4px 12px;font-family:\'DM Mono\',monospace;font-size:0.68rem;color:#3d4d66">'
            f'<div>candidate &nbsp;<span style="color:#94a3b8">{c.get("name","–")}</span></div>'
            f'<div>fit &nbsp;<span style="color:#94a3b8">+{im.get("fit_delta",0)}%</span></div>'
            f'<div>modules &nbsp;<span style="color:#94a3b8">{im.get("modules_count",0)}</span></div>'
            f'<div>hours &nbsp;<span style="color:#94a3b8">{im.get("roadmap_hours",0)}h</span></div>'
            f'<div>interview &nbsp;<span style="color:{iv.get("color","#4ade80")}">{iv.get("score",0)}% {iv.get("label","")}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:10px 0"></div>', unsafe_allow_html=True)

        if _bk._audit_log:
            total_cost = sum(e.get("cost", 0) for e in _bk._audit_log)
            cache_lbl  = "cached" if res.get("_cache_hit") else "live"
            st.markdown('<div style="font-family:var(--mono);font-size:0.6rem;color:var(--t4);padding:0 12px 4px">API log</div>', unsafe_allow_html=True)
            for e in _bk._audit_log[-4:]:
                ok = e.get("status") == "ok"
                sc = "#4ade80" if ok else "#ef4444"
                st.markdown(
                    f'<div class="sf-log"><span style="color:{sc}">{"●" if ok else "✕"}</span>'
                    f'<span>{e.get("ts","")}</span>'
                    f'<span style="color:#2dd4bf">{e.get("model","")}</span>'
                    f'<span>{e.get("in",0)}+{e.get("out",0)}tok</span>'
                    f'<span>${e.get("cost",0):.5f}</span></div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div style="font-family:var(--mono);font-size:0.58rem;color:var(--t4);padding:2px 12px 8px">'
                f'SkillForge v13 · {cache_lbl} · {len(_bk._audit_log)} calls · ${total_cost:.5f}</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:10px 0"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-ghost" style="padding:0 8px">', unsafe_allow_html=True)
        if st.button("Start over", key="sb_reset", use_container_width=True):
            _full_reset()
        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  RESULTS PAGE
# =============================================================================
def render_results() -> None:
    res = st.session_state.get("result")
    if not res or "error" in res:
        st.error("No results found. Please go back and re-analyze.")
        if st.button("Back"):
            st.session_state["step"] = "input"
            st.rerun()
        return

    GAP_KILLER = '<style>div[data-testid="stAppViewBlockContainer"]{padding-top:0!important}section.main{padding-top:0!important}.block-container{padding-top:0!important}.stMainBlockContainer{padding-top:0!important}</style>'
    is_image = bool(res.get("_is_image"))
    st.markdown(CSS + GAP_KILLER, unsafe_allow_html=True)
    render_topbar(is_image_resume=is_image, has_result=True)
    st.markdown('<div class="sf-page sf-page-pad" style="padding:20px 40px 80px">', unsafe_allow_html=True)
    _, rc = st.columns([12, 1])
    with rc:
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("Reset", key="top_reset"):
            _full_reset()
        st.markdown("</div>", unsafe_allow_html=True)

    render_banner(res)

    tab_gap, tab_road, tab_dag, tab_prep, tab_research, tab_ats = st.tabs([
        "Gap Analysis", "Roadmap", "🔗 DAG View",
        "🎤 Interview Prep", "Research", "ATS & Export",
    ])
    with tab_gap:      render_tab_overview(res)
    with tab_road:     render_tab_roadmap(res)
    with tab_dag:      render_tab_dag(res)
    with tab_prep:     render_tab_interview_prep(res)
    with tab_research: render_tab_research(res)
    with tab_ats:      render_tab_ats_export(res)

    st.markdown("</div>", unsafe_allow_html=True)
    render_sidebar(res)


# =============================================================================
#  MAIN
# =============================================================================
def main() -> None:
    _init_state()
    threading.Thread(target=_load_semantic_bg, daemon=True).start()

    _params = st.query_params
    if "share" in _params and st.session_state.get("step") == "input":
        import base64 as _b64
        try:
            _payload = json.loads(_b64.urlsafe_b64decode(_params["share"]).decode())
            st.markdown(CSS, unsafe_allow_html=True)
            render_topbar()
            st.markdown(f"""
            <div style="max-width:640px;margin:60px auto;background:var(--s1);
                        border:1px solid var(--border);border-radius:14px;padding:32px 36px">
              <div style="font-family:var(--mono);font-size:0.65rem;color:var(--teal);
                          letter-spacing:0.12em;margin-bottom:12px">SHARED ROADMAP</div>
              <div style="font-size:1.4rem;font-weight:700;color:var(--t1);margin-bottom:4px">
                {_payload.get('name','Candidate')}
              </div>
              <div style="font-family:var(--mono);font-size:0.8rem;color:var(--t3);margin-bottom:20px">
                {_payload.get('role','')}
              </div>
              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
                <div style="text-align:center;background:var(--s2);border-radius:8px;padding:14px">
                  <div style="font-family:var(--mono);font-size:1.6rem;color:var(--green)">+{_payload.get('delta',0)}%</div>
                  <div style="font-size:0.65rem;color:var(--t3)">FIT DELTA</div>
                </div>
                <div style="text-align:center;background:var(--s2);border-radius:8px;padding:14px">
                  <div style="font-family:var(--mono);font-size:1.6rem;color:var(--teal)">{_payload.get('hours',0)}h</div>
                  <div style="font-size:0.65rem;color:var(--t3)">TRAINING</div>
                </div>
                <div style="text-align:center;background:var(--s2);border-radius:8px;padding:14px">
                  <div style="font-family:var(--mono);font-size:1.6rem;color:var(--amber)">{_payload.get('iv',0)}%</div>
                  <div style="font-size:0.65rem;color:var(--t3)">INTERVIEW</div>
                </div>
                <div style="text-align:center;background:var(--s2);border-radius:8px;padding:14px">
                  <div style="font-family:var(--mono);font-size:1.6rem;color:var(--purple)">{_payload.get('modules',0)}</div>
                  <div style="font-size:0.65rem;color:var(--t3)">MODULES</div>
                </div>
              </div>
              <div style="margin-top:24px;font-size:0.82rem;color:var(--t3)">
                Analyse your own résumé at SkillForge ↓
              </div>
            </div>""", unsafe_allow_html=True)
            st.stop()
        except Exception:
            pass

    # Inject CSS + gap-killer as one combined block so it fires before any layout
    GAP_KILLER = '<style>div[data-testid="stAppViewBlockContainer"]{padding-top:0!important}section.main{padding-top:0!important}.block-container{padding-top:0!important}.stMainBlockContainer{padding-top:0!important}</style>'

    step = st.session_state.get("step", "input")
    if step == "input":
        st.markdown(CSS + GAP_KILLER, unsafe_allow_html=True)
        render_topbar()
        render_input()
    elif step in ("analyzing", "loading"):
        st.session_state["step"] = "loading"
        st.markdown(CSS + GAP_KILLER, unsafe_allow_html=True)
        render_topbar()
        render_loading()
    elif step == "results":
        render_results()
    else:
        st.session_state["step"] = "input"
        st.rerun()


if __name__ == "__main__":
    main()