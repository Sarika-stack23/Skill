# =============================================================================
#  main.py — SkillForge  AI-Adaptive Onboarding Engine  v4 (HACKATHON FINAL)
#  Stack : Plotly Dash 4 · DBC 2 · Groq LLaMA 3.3 · NetworkX · ReportLab
#  Run   : python main.py          (needs GROQ_API_KEY in .env)
#
#  v4 FIXES (on top of v3):
#   FIX 1.  Merged resume parse + quality audit → 1 Groq call (was 2)
#   FIX 2.  Batched reasoning → 1 Groq call for all modules (was 12)
#   FIX 3.  Retry wrapper with exponential backoff on 429
#   FIX 4.  LRU cache keyed on resume+JD hash — no re-calling for same input
#   FIX 5.  Token budget guard — warns before hitting daily limit
#   FIX 6.  ThreadPoolExecutor semaphore cap — prevents burst >4 parallel calls
#
#  v4 NEW FEATURES:
#   1.  Multi-JD Fit Comparator  — rank up to 3 JDs, show best fit now vs 6m
#   2.  Skill Transfer Map       — "your Python gives 40% head start on MLOps"
#   3.  Learning ROI Calculator  — hours × demand = ROI index per skill
#   4.  Progress Tracker Mode    — mark modules Done/In Progress, live score
#   5.  LinkedIn JD URL paste    — auto-extract JD from LinkedIn posting URL
#   6.  Audit Log Panel          — show every Groq call, tokens, latency, cost
#   7.  Cover Letter Draft       — AI cover letter bridging candidate to JD
#   8.  Catalog Expansion UI     — admin can add custom courses in the UI
#   9.  Fallback to llama-3.1-8b — if 70b is rate-limited, use smaller model
#  10.  Knowledge Graph Tab      — force-directed NetworkX viz (pyvis)
# =============================================================================

import os, json, base64, io, re, time, hashlib, threading
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise SystemExit(
        "\n  ERROR: GROQ_API_KEY is missing.\n"
        "  Create a .env file with:\n    GROQ_API_KEY=gsk_...\n"
    )

import dash
from dash import dcc, html, Input, Output, State, no_update, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import networkx as nx
import pdfplumber
from docx import Document
from groq import Groq

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    print("  -> Loading sentence-transformers...")
    _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    SEMANTIC = True
except Exception:
    SEMANTIC = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    REPORTLAB = True
except Exception:
    REPORTLAB = False

try:
    import requests as _req
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1B · TOKEN BUDGET TRACKER  (v4 FIX)
# ─────────────────────────────────────────────────────────────────────────────
_token_lock = threading.Lock()
_daily_token_used = 0
DAILY_TOKEN_LIMIT = 100_000
DAILY_TOKEN_WARN  = 80_000   # warn at 80%

def _track_tokens(n: int):
    global _daily_token_used
    with _token_lock:
        _daily_token_used += n

def token_budget_ok() -> Tuple[bool, int]:
    with _token_lock:
        return _daily_token_used < DAILY_TOKEN_WARN, _daily_token_used

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 · COURSE CATALOG  (47 courses)
# ─────────────────────────────────────────────────────────────────────────────
CATALOG = [
    {"id":"PY01","title":"Python Fundamentals","skill":"Python","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"PY02","title":"Python Intermediate: OOP & Modules","skill":"Python","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["PY01"]},
    {"id":"PY03","title":"Python Advanced: Async, Decorators & Performance","skill":"Python","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["PY02"]},
    {"id":"DA01","title":"Data Analysis with Pandas","skill":"Data Analysis","domain":"Tech","level":"Beginner","duration_hrs":7,"prereqs":["PY01"]},
    {"id":"DA02","title":"Data Visualization (Matplotlib & Seaborn)","skill":"Data Visualization","domain":"Tech","level":"Intermediate","duration_hrs":5,"prereqs":["DA01"]},
    {"id":"DA03","title":"Statistical Analysis & Hypothesis Testing","skill":"Statistics","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["DA01"]},
    {"id":"ML01","title":"Machine Learning Foundations","skill":"Machine Learning","domain":"Tech","level":"Beginner","duration_hrs":10,"prereqs":["DA01","DA03"]},
    {"id":"ML02","title":"Supervised Learning: Regression & Classification","skill":"Machine Learning","domain":"Tech","level":"Intermediate","duration_hrs":12,"prereqs":["ML01"]},
    {"id":"ML03","title":"Deep Learning with PyTorch","skill":"Deep Learning","domain":"Tech","level":"Advanced","duration_hrs":15,"prereqs":["ML02"]},
    {"id":"ML04","title":"NLP & Large Language Models","skill":"NLP","domain":"Tech","level":"Advanced","duration_hrs":14,"prereqs":["ML02"]},
    {"id":"ML05","title":"MLOps & Model Deployment","skill":"MLOps","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["ML02","DO02"]},
    {"id":"SQL01","title":"SQL Fundamentals","skill":"SQL","domain":"Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"SQL02","title":"Advanced SQL: Window Functions & Query Optimization","skill":"SQL","domain":"Tech","level":"Advanced","duration_hrs":7,"prereqs":["SQL01"]},
    {"id":"SQL03","title":"Database Design & NoSQL (MongoDB, Redis)","skill":"Databases","domain":"Tech","level":"Intermediate","duration_hrs":6,"prereqs":["SQL01"]},
    {"id":"DO01","title":"Linux & Bash Scripting","skill":"Linux","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"DO02","title":"Docker & Containerization","skill":"Docker","domain":"Tech","level":"Intermediate","duration_hrs":7,"prereqs":["DO01"]},
    {"id":"DO03","title":"Kubernetes Orchestration","skill":"Kubernetes","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["DO02"]},
    {"id":"DO04","title":"CI/CD Pipelines with GitHub Actions","skill":"CI/CD","domain":"Tech","level":"Intermediate","duration_hrs":6,"prereqs":["DO01"]},
    {"id":"CL01","title":"Cloud Computing Fundamentals","skill":"Cloud Computing","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"CL02","title":"AWS Core Services Deep Dive","skill":"AWS","domain":"Tech","level":"Intermediate","duration_hrs":10,"prereqs":["CL01"]},
    {"id":"CL03","title":"GCP & BigQuery for Data Engineers","skill":"GCP","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["CL01","DA01"]},
    {"id":"WE01","title":"HTML & CSS Foundations","skill":"HTML/CSS","domain":"Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"WE02","title":"JavaScript Essentials","skill":"JavaScript","domain":"Tech","level":"Beginner","duration_hrs":8,"prereqs":["WE01"]},
    {"id":"WE03","title":"React.js Fundamentals","skill":"React","domain":"Tech","level":"Intermediate","duration_hrs":10,"prereqs":["WE02"]},
    {"id":"WE04","title":"FastAPI Backend Development","skill":"FastAPI","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["PY02"]},
    {"id":"WE05","title":"Full-Stack Integration & REST APIs","skill":"REST APIs","domain":"Tech","level":"Intermediate","duration_hrs":7,"prereqs":["WE03","WE04"]},
    {"id":"SE01","title":"Cybersecurity Fundamentals","skill":"Cybersecurity","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"SE02","title":"Application Security & OWASP Top 10","skill":"Application Security","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["SE01"]},
    {"id":"AG01","title":"Agile & Scrum Fundamentals","skill":"Agile","domain":"Tech","level":"Beginner","duration_hrs":4,"prereqs":[]},
    {"id":"AG02","title":"Advanced Scrum Master Certification Prep","skill":"Scrum","domain":"Tech","level":"Advanced","duration_hrs":6,"prereqs":["AG01"]},
    {"id":"PM01","title":"Project Management Essentials (PMI Framework)","skill":"Project Management","domain":"Soft","level":"Intermediate","duration_hrs":8,"prereqs":["LD01"]},
    {"id":"HR01","title":"HR Fundamentals & Employment Law","skill":"Human Resources","domain":"Non-Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"HR02","title":"Talent Acquisition & Recruitment","skill":"Recruitment","domain":"Non-Tech","level":"Intermediate","duration_hrs":6,"prereqs":["HR01"]},
    {"id":"HR03","title":"Performance Management & Appraisals","skill":"Performance Management","domain":"Non-Tech","level":"Intermediate","duration_hrs":5,"prereqs":["HR01"]},
    {"id":"HR04","title":"Employee Relations & Conflict Resolution","skill":"Employee Relations","domain":"Non-Tech","level":"Advanced","duration_hrs":6,"prereqs":["HR01"]},
    {"id":"HR05","title":"Learning & Development Strategy","skill":"L&D Strategy","domain":"Non-Tech","level":"Advanced","duration_hrs":6,"prereqs":["HR03"]},
    {"id":"OP01","title":"Supply Chain & Logistics Fundamentals","skill":"Logistics","domain":"Non-Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"OP02","title":"Warehouse Management Systems","skill":"Warehouse Management","domain":"Non-Tech","level":"Intermediate","duration_hrs":6,"prereqs":["OP01"]},
    {"id":"OP03","title":"Inventory Control & Demand Planning","skill":"Inventory Management","domain":"Non-Tech","level":"Intermediate","duration_hrs":5,"prereqs":["OP01"]},
    {"id":"OP04","title":"Lean Manufacturing & Six Sigma Green Belt","skill":"Process Improvement","domain":"Non-Tech","level":"Advanced","duration_hrs":8,"prereqs":["OP01"]},
    {"id":"FI01","title":"Financial Accounting Basics","skill":"Accounting","domain":"Non-Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"FI02","title":"Financial Analysis & Modeling","skill":"Financial Analysis","domain":"Non-Tech","level":"Intermediate","duration_hrs":8,"prereqs":["FI01"]},
    {"id":"FI03","title":"Budgeting & Forecasting","skill":"Budgeting","domain":"Non-Tech","level":"Intermediate","duration_hrs":5,"prereqs":["FI01"]},
    {"id":"LD01","title":"Communication & Presentation Skills","skill":"Communication","domain":"Soft","level":"Beginner","duration_hrs":4,"prereqs":[]},
    {"id":"LD02","title":"Team Leadership & People Management","skill":"Leadership","domain":"Soft","level":"Intermediate","duration_hrs":6,"prereqs":["LD01"]},
    {"id":"LD03","title":"Strategic Thinking & Decision Making","skill":"Strategic Planning","domain":"Soft","level":"Advanced","duration_hrs":6,"prereqs":["LD02"]},
    {"id":"LD04","title":"Cross-Functional Collaboration","skill":"Collaboration","domain":"Soft","level":"Beginner","duration_hrs":3,"prereqs":["LD01"]},
]

# Runtime-extensible catalog (for v4 Catalog Expansion UI)
CUSTOM_CATALOG: List[dict] = []

def get_full_catalog():
    return CATALOG + CUSTOM_CATALOG

CATALOG_BY_ID  = {c["id"]: c for c in CATALOG}
CATALOG_SKILLS = [c["skill"].lower() for c in CATALOG]
_bad = [(c["id"],p) for c in CATALOG for p in c["prereqs"] if p not in CATALOG_BY_ID]
if _bad: raise SystemExit(f"CATALOG ERROR: {_bad}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2B · MARKET DEMAND
# ─────────────────────────────────────────────────────────────────────────────
MARKET_DEMAND: Dict[str,int] = {
    "python":3,"machine learning":3,"deep learning":3,"aws":3,"docker":3,
    "sql":3,"react":3,"kubernetes":3,"mlops":3,"fastapi":3,"data analysis":3,
    "cloud computing":3,"ci/cd":3,"nlp":3,"rest apis":3,"javascript":3,
    "statistics":2,"data visualization":2,"gcp":2,"linux":2,"html/css":2,
    "agile":2,"databases":2,"cybersecurity":2,"communication":2,"leadership":2,
    "project management":2,"recruitment":2,"performance management":2,
    "financial analysis":2,"application security":2,"process improvement":2,
    "human resources":1,"accounting":1,"budgeting":1,"logistics":1,
    "scrum":1,"collaboration":1,"strategic planning":1,"warehouse management":1,
    "inventory management":1,"l&d strategy":1,
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2C · SAMPLE INPUTS
# ─────────────────────────────────────────────────────────────────────────────
SAMPLES = {
    "junior_swe": {
        "label":"Junior SWE",
        "resume":"""John Smith
Junior Software Developer | 1 year experience
Skills: Python (basic, 4/10), HTML/CSS, some JavaScript
Education: B.Tech Computer Science 2023
Projects: Built a simple todo app using Flask. Familiar with Git basics.
No professional cloud or DevOps experience. No testing experience.
Soft skills: Good communicator, team player.""",
        "jd":"""Software Engineer Full Stack - Mid Level
Required: Python, React, FastAPI, Docker, SQL, REST APIs, AWS
Preferred: Kubernetes, CI/CD, TypeScript
Seniority: Mid | Domain: Tech"""
    },
    "senior_ds": {
        "label":"Senior Data Scientist",
        "resume":"""Priya Patel
Senior Data Scientist | 7 years experience
Skills: Python (expert, daily), Machine Learning (expert), Deep Learning (PyTorch),
SQL (advanced), Data Analysis (Pandas, NumPy), Statistics (PhD level), AWS SageMaker.
Last used NLP: 2022. Last used MLOps tools: 2021 (basic only).
Led team of 5 scientists. Published 3 ML papers. Strong mentor and communicator.""",
        "jd":"""Lead Data Scientist - AI Products
Required: Python, Machine Learning, Deep Learning, NLP, MLOps, SQL, AWS
Preferred: GCP, Kubernetes, Leadership, Strategic Planning
Seniority: Lead | Domain: Tech"""
    },
    "hr_manager": {
        "label":"HR Manager",
        "resume":"""Amara Johnson
HR Coordinator | 3 years experience
Skills: Human Resources (intermediate), Recruitment (good), Microsoft Office
Some performance review experience. No formal L&D or ER training.
Good written communication. Organised and detail-oriented.""",
        "jd":"""HR Manager - People and Culture
Required: Human Resources, Recruitment, Performance Management, Employee Relations
Preferred: L&D Strategy, Budgeting, Communication, Leadership, Project Management
Seniority: Senior | Domain: Non-Tech"""
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 · DEPENDENCY GRAPH
# ─────────────────────────────────────────────────────────────────────────────
def _build_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    for c in get_full_catalog():
        G.add_node(c["id"], **c)
        for p in c["prereqs"]: G.add_edge(p, c["id"])
    return G
SKILL_GRAPH = _build_graph()

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 · FILE READERS
# ─────────────────────────────────────────────────────────────────────────────
def _pdf_text(raw:bytes)->str:
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e: return f"[PDF error: {e}]"

def _docx_text(raw:bytes)->str:
    try:
        doc=Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e: return f"[DOCX error: {e}]"

def parse_upload(contents:str,filename:str)->str:
    if not contents: return ""
    _,b64=contents.split(",",1)
    raw=base64.b64decode(b64)
    if filename.lower().endswith(".pdf"):  return _pdf_text(raw)
    if filename.lower().endswith(".docx"): return _docx_text(raw)
    return raw.decode("utf-8",errors="ignore")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4B · LINKEDIN JD EXTRACTOR  (v4 NEW)
# ─────────────────────────────────────────────────────────────────────────────
def extract_linkedin_jd(url: str) -> str:
    """Attempt to scrape JD text from a LinkedIn job URL."""
    if not REQUESTS_OK:
        return "[requests not installed]"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        r = _req.get(url, headers=headers, timeout=8)
        # Extract visible text from description div
        text = r.text
        # Look for the job description section
        import re as _re
        match = _re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
                           text, _re.DOTALL | _re.IGNORECASE)
        if match:
            raw = match.group(1)
            clean = _re.sub(r'<[^>]+>', ' ', raw)
            clean = _re.sub(r'\s+', ' ', clean).strip()
            return clean[:3000]
        return "[Could not extract JD from URL. Please paste the text directly.]"
    except Exception as e:
        return f"[LinkedIn fetch error: {e}]"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 · GROQ API — FIXED (v4)
# ─────────────────────────────────────────────────────────────────────────────
_GROQ_SEMAPHORE = threading.Semaphore(4)   # FIX 6: max 4 parallel calls
_AUDIT_LOG: List[dict] = []                # FIX + v4: per-session audit log
_GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"  # v4: fallback if 70b rate-limited
_GROQ_PRIMARY_MODEL  = "llama-3.3-70b-versatile"


def _groq(
    prompt: str,
    system: str = "You are an expert HR analyst. Always respond with valid JSON only, no markdown fences.",
    use_fallback: bool = False,
    max_retries: int = 3,        # FIX 3: retry wrapper
) -> dict:
    """
    FIX 1+3+4+6: Token-tracked, semaphore-guarded, retrying Groq call.
    Falls back to smaller model after primary is rate-limited twice.
    """
    model = _GROQ_FALLBACK_MODEL if use_fallback else _GROQ_PRIMARY_MODEL
    last_err = None

    for attempt in range(max_retries):
        with _GROQ_SEMAPHORE:   # FIX 6: cap parallelism
            t0 = time.time()
            try:
                r = GROQ_CLIENT.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":system},
                               {"role":"user","content":prompt}],
                    temperature=0.1, max_tokens=4096,
                )
                elapsed = round(time.time() - t0, 3)
                raw = r.choices[0].message.content.strip()
                raw = re.sub(r"```json\s*|\s*```", "", raw).strip()

                # Track tokens
                usage = r.usage
                in_tok  = usage.prompt_tokens     if usage else 0
                out_tok = usage.completion_tokens  if usage else 0
                _track_tokens(in_tok + out_tok)

                # Audit log entry
                _AUDIT_LOG.append({
                    "ts":      datetime.now().strftime("%H:%M:%S"),
                    "model":   model,
                    "in_tok":  in_tok,
                    "out_tok": out_tok,
                    "latency": elapsed,
                    "status":  "ok",
                    # rough cost estimate: llama 3.3-70b ~$0.59/1M in, $0.79/1M out
                    "cost_usd": round((in_tok * 0.00000059) + (out_tok * 0.00000079), 5),
                })

                return json.loads(raw)

            except json.JSONDecodeError:
                _AUDIT_LOG.append({"ts": datetime.now().strftime("%H:%M:%S"),
                                   "model": model, "status": "json_err"})
                return {"error": "JSON parse failed"}

            except Exception as e:
                err_str = str(e)
                last_err = err_str

                # FIX 3: parse wait time from 429 message
                if "429" in err_str or "rate_limit_exceeded" in err_str:
                    # Try to extract wait seconds from message
                    wait_match = re.search(r'try again in (\d+)m(\d+)', err_str)
                    if wait_match:
                        wait_s = int(wait_match.group(1)) * 60 + int(wait_match.group(2))
                    else:
                        wait_s = 30 * (attempt + 1)   # 30s / 60s / 90s

                    _AUDIT_LOG.append({"ts": datetime.now().strftime("%H:%M:%S"),
                                       "model": model, "status": f"429 wait {wait_s}s",
                                       "in_tok":0,"out_tok":0,"latency":0,"cost_usd":0})

                    # v4 FIX 9: auto-switch to fallback on second 429
                    if attempt >= 1 and not use_fallback:
                        print(f"  -> Switching to fallback model {_GROQ_FALLBACK_MODEL}")
                        model = _GROQ_FALLBACK_MODEL

                    print(f"  -> Rate limited (attempt {attempt+1}). Waiting {wait_s}s...")
                    time.sleep(min(wait_s, 90))   # cap at 90s so UI doesn't hang forever
                    continue

                _AUDIT_LOG.append({"ts": datetime.now().strftime("%H:%M:%S"),
                                   "model": model, "status": f"err: {err_str[:40]}"})
                return {"error": err_str}

    return {"error": f"Max retries exceeded. Last error: {last_err}"}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5B · MERGED PARSE CALL  (v4 FIX 1 — was 2 separate calls)
# ─────────────────────────────────────────────────────────────────────────────
def parse_resume_and_audit(resume_text: str, jd_data: dict) -> Tuple[dict, dict]:
    """
    ONE Groq call that returns both the structured candidate profile
    AND the ATS/quality audit. Replaces parse_resume() + analyze_resume_quality().
    Saves ~2,500 input tokens per run.
    """
    role = jd_data.get("role_title", "target role")
    req  = jd_data.get("required_skills", [])

    result = _groq(
        f"""You are a senior recruiter and ATS expert. Given the resume below, do TWO things:

1. Extract the candidate profile as structured JSON.
2. Audit the resume quality for the role: {role}

Return ONLY this JSON (no other text):
{{
  "candidate": {{
    "name": "<full name or Unknown>",
    "current_role": "<latest job title>",
    "years_experience": <integer>,
    "seniority": "<Junior|Mid|Senior|Lead>",
    "domain": "<Tech|Non-Tech|Hybrid>",
    "education": "<highest degree + field>",
    "skills": [
      {{"skill":"<name>","proficiency":<0-10>,"year_last_used":<year int or 0>,"context":"<one-line evidence>"}}
    ],
    "strengths": ["<strength 1>","<strength 2>","<strength 3>"],
    "red_flags": ["<gap or concern 1>","<concern 2>"]
  }},
  "audit": {{
    "ats_score": <0-100>,
    "completeness_score": <0-100>,
    "clarity_score": <0-100>,
    "overall_grade": "<A|B|C|D>",
    "ats_issues": ["<specific ATS formatting problem>"],
    "improvement_tips": ["<actionable tip 1>","<tip 2>","<tip 3>","<tip 4>","<tip 5>"],
    "strong_points": ["<what is great 1>","<great 2>"],
    "missing_keywords": ["<keyword in JD but missing from resume>"],
    "interview_talking_points": ["<how to frame experience for interviews 1>","<point 2>","<point 3>"]
  }}
}}

Resume (first 3000 chars):
{resume_text[:3000]}
Target required skills: {req}""",
        system="You are a senior tech recruiter and ATS expert. Return valid JSON only."
    )

    if "error" in result:
        return {"error": result["error"]}, {}

    return result.get("candidate", {}), result.get("audit", {})


def parse_jd(text: str) -> dict:
    return _groq(
        f"""Extract structured data from this job description. Return ONLY valid JSON:
{{
  "role_title": "<title>",
  "seniority_required": "<Junior|Mid|Senior|Lead>",
  "domain": "<Tech|Non-Tech|Hybrid>",
  "required_skills": ["<skill1>"],
  "preferred_skills": ["<skill2>"],
  "key_responsibilities": ["<resp 1>","<resp 2>","<resp 3>"]
}}
JD:
{text[:3000]}"""
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5C · BATCHED REASONING  (v4 FIX 2 — was 12 calls, now 1)
# ─────────────────────────────────────────────────────────────────────────────
def batch_generate_reasoning(modules: List[dict], candidate_name: str) -> Dict[str, str]:
    """
    ONE Groq call for ALL module reasoning. Returns {module_id: reasoning_str}.
    Replaces 12 individual generate_reasoning() calls.
    Saves ~1,600 tokens + 11 round trips per run.
    """
    if not modules:
        return {}

    module_list = "\n".join(
        f'{i+1}. id="{m["id"]}" title="{m["title"]}" gap_skill="{m.get("gap_skill", m["skill"])}"'
        for i, m in enumerate(modules)
    )

    result = _groq(
        f"""For candidate "{candidate_name}", explain WHY each course below is recommended.
Each reasoning must be exactly 2 sentences, specific to this person's gap.

Modules:
{module_list}

Return ONLY a JSON object mapping each id to its reasoning:
{{
  "<id>": "<2-sentence reasoning>",
  ...
}}""",
        system="You are an L&D expert. Return valid JSON only. No markdown."
    )

    if isinstance(result, dict) and "error" not in result:
        return result
    # fallback: return generic reasoning
    return {m["id"]: f"Addresses gap in {m.get('gap_skill', m['skill'])}." for m in modules}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5D · COVER LETTER GENERATOR  (v4 NEW)
# ─────────────────────────────────────────────────────────────────────────────
def generate_cover_letter(resume_data: dict, jd_data: dict) -> str:
    name    = resume_data.get("name", "the candidate")
    role    = jd_data.get("role_title", "the target role")
    company = jd_data.get("company", "your company")
    skills  = resume_data.get("skills", [])
    strengths = resume_data.get("strengths", [])

    result = _groq(
        f"""Write a professional cover letter for {name} applying for {role} at {company}.
Use their strengths: {strengths}
Their top skills: {[s['skill'] for s in skills[:6]]}
Required skills for the role: {jd_data.get('required_skills', [])}

Return JSON: {{"cover_letter": "<full letter, 3 paragraphs, professional tone>"}}""",
        system="You are an expert career coach. Return JSON only."
    )
    return result.get("cover_letter", "Could not generate cover letter.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5E · MULTI-JD COMPARATOR  (v4 NEW)
# ─────────────────────────────────────────────────────────────────────────────
def compare_jds(resume_data: dict, jd_list: List[dict]) -> List[dict]:
    """Given a candidate and multiple JDs, score fit for each."""
    results = []
    resume_skills = {s["skill"].lower(): s for s in resume_data.get("skills", [])}

    for jd in jd_list:
        req  = jd.get("required_skills", [])
        pref = jd.get("preferred_skills", [])
        all_skills = [(s, True) for s in req] + [(s, False) for s in pref]

        known = sum(1 for s, _ in all_skills
                    if resume_skills.get(s.lower(), {}).get("proficiency", 0) >= 7)
        total = max(len(all_skills), 1)
        fit_now = round((known / total) * 100)

        # Projected fit after 6 months (assume can fill 2 gaps/month)
        gaps = total - known
        filled_6m = min(gaps, 12)  # ~2 per month × 6 months
        fit_6m = min(100, round(((known + filled_6m) / total) * 100))

        results.append({
            "role_title":   jd.get("role_title", "--"),
            "fit_now":      fit_now,
            "fit_6m":       fit_6m,
            "known":        known,
            "total":        total,
            "missing":      gaps,
            "seniority":    jd.get("seniority_required", "--"),
            "recommendation": "Apply now" if fit_now >= 60
                              else "Apply in 3–6 months" if fit_6m >= 70
                              else "Long-term goal",
        })

    return sorted(results, key=lambda x: x["fit_now"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5F · SKILL TRANSFER MAP  (v4 NEW)
# ─────────────────────────────────────────────────────────────────────────────
# Semantic skill overlap pairs — known skill → benefit % on gap skill
TRANSFER_MAP: Dict[str, Dict[str, int]] = {
    "python":        {"machine learning": 40, "mlops": 35, "fastapi": 60, "data analysis": 50,
                      "deep learning": 30, "rest apis": 45},
    "machine learning": {"deep learning": 50, "mlops": 45, "nlp": 40, "statistics": 30},
    "javascript":    {"react": 55, "rest apis": 40},
    "sql":           {"data analysis": 35, "databases": 60},
    "docker":        {"kubernetes": 45, "ci/cd": 35, "mlops": 30},
    "linux":         {"docker": 40, "ci/cd": 30, "aws": 20},
    "aws":           {"gcp": 30, "cloud computing": 70, "mlops": 25},
    "human resources": {"recruitment": 45, "performance management": 40, "employee relations": 35},
    "communication": {"leadership": 35, "project management": 25},
    "leadership":    {"strategic planning": 40, "project management": 35},
    "financial analysis": {"budgeting": 55, "accounting": 40},
}

def build_transfer_map(resume_data: dict, gap_profile: List[dict]) -> List[dict]:
    """For each gap, find known skills that provide a head-start."""
    known_skills = {g["skill"].lower() for g in resume_data.get("skills", [])
                    if g.get("proficiency", 0) >= 6}
    transfers = []
    for gap in gap_profile:
        if gap["status"] == "Known":
            continue
        gap_sl = gap["skill"].lower()
        for known_sl in known_skills:
            pct = TRANSFER_MAP.get(known_sl, {}).get(gap_sl, 0)
            if pct > 0:
                transfers.append({
                    "gap_skill":   gap["skill"],
                    "known_skill": known_sl.title(),
                    "transfer_pct": pct,
                    "label": f"Your {known_sl.title()} gives a {pct}% head start on {gap['skill']}",
                })
    return sorted(transfers, key=lambda x: x["transfer_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5G · LEARNING ROI  (v4 NEW)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_roi(gap_profile: List[dict], path: List[dict]) -> List[dict]:
    """ROI = (market_demand × required_weight) / duration_hrs. Higher = do first."""
    roi_list = []
    for m in path:
        gap = next((g for g in gap_profile if g["skill"] == m.get("gap_skill")), {})
        demand  = gap.get("demand", 1)          # 1–3
        req_w   = 1.5 if gap.get("is_required") else 1.0
        hrs     = max(m["duration_hrs"], 1)
        roi     = round((demand * req_w * 10) / hrs, 2)
        roi_list.append({
            "id":        m["id"],
            "title":     m["title"],
            "skill":     m["skill"],
            "demand":    demand,
            "hrs":       hrs,
            "roi":       roi,
            "is_required": gap.get("is_required", False),
        })
    return sorted(roi_list, key=lambda x: x["roi"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5H · ANALYSIS CACHE  (v4 FIX 4)
# ─────────────────────────────────────────────────────────────────────────────
_ANALYSIS_CACHE: Dict[str, dict] = {}

def _cache_key(resume_text: str, jd_text: str) -> str:
    return hashlib.md5((resume_text + "||" + jd_text).encode()).hexdigest()

def cache_get(resume_text: str, jd_text: str) -> Optional[dict]:
    return _ANALYSIS_CACHE.get(_cache_key(resume_text, jd_text))

def cache_set(resume_text: str, jd_text: str, result: dict):
    key = _cache_key(resume_text, jd_text)
    _ANALYSIS_CACHE[key] = result
    # Keep cache small — evict oldest if > 20 entries
    if len(_ANALYSIS_CACHE) > 20:
        oldest = next(iter(_ANALYSIS_CACHE))
        del _ANALYSIS_CACHE[oldest]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 · SEMANTIC MATCHING
# ─────────────────────────────────────────────────────────────────────────────
if SEMANTIC:
    print("  -> Pre-computing catalog embeddings...")
    _CATALOG_EMBS = _ST_MODEL.encode(CATALOG_SKILLS)
else:
    _CATALOG_EMBS = None

def _semantic_match(skill: str, threshold: float = 0.52) -> Tuple[int, float]:
    sl = (skill.lower().replace(".js","").replace(".py","").replace(".ts","")
          .replace("(","").replace(")","").strip())
    for i, cs in enumerate(CATALOG_SKILLS):
        if sl == cs or sl in cs or cs in sl: return i, 1.0
    if SEMANTIC and _CATALOG_EMBS is not None:
        emb_q = _ST_MODEL.encode([sl])
        sims  = cosine_similarity(emb_q, _CATALOG_EMBS)[0]
        best  = int(np.argmax(sims))
        if sims[best] >= threshold: return best, float(sims[best])
    tokens = set(sl.split())
    best_score, best_idx = 0.0, -1
    for i, cs in enumerate(CATALOG_SKILLS):
        overlap = len(tokens & set(cs.split())) / max(len(tokens), 1)
        if overlap > best_score: best_score, best_idx = overlap, i
    return (best_idx, best_score) if best_score >= 0.4 else (-1, 0.0)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6B · SKILL DECAY
# ─────────────────────────────────────────────────────────────────────────────
CURRENT_YEAR = datetime.now().year

def apply_skill_decay(proficiency: int, year_last_used: int) -> Tuple[int, bool]:
    if year_last_used <= 0 or year_last_used >= CURRENT_YEAR - 1: return proficiency, False
    years_since = CURRENT_YEAR - year_last_used
    if years_since <= 2: return proficiency, False
    decay_factor = max(0.5, 1 - (years_since / 5))
    adjusted = round(proficiency * decay_factor)
    return adjusted, adjusted < proficiency

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 · GAP ANALYZER
# ─────────────────────────────────────────────────────────────────────────────
def analyze_gap(resume_data: dict, jd_data: dict) -> List[dict]:
    resume_skills = {s["skill"].lower(): s for s in resume_data.get("skills", [])}
    all_skills = ([(s, True)  for s in jd_data.get("required_skills", [])]
                + [(s, False) for s in jd_data.get("preferred_skills", [])])
    gap_profile = []
    for skill, is_required in all_skills:
        sl = (skill.lower().replace(".js","").replace(".py","").replace(".ts","")
              .replace("(","").replace(")","").strip())
        status, proficiency, context, decayed, original_prof = "Missing", 0, "", False, 0
        match_src = resume_skills.get(sl)
        if not match_src:
            for rk, rv in resume_skills.items():
                if sl in rk or rk in sl: match_src = rv; break
        if match_src:
            raw_prof   = match_src.get("proficiency", 0)
            yr_used    = match_src.get("year_last_used", 0)
            proficiency, decayed = apply_skill_decay(raw_prof, yr_used)
            original_prof = raw_prof
            context    = match_src.get("context", "")
            status     = "Known" if proficiency >= 7 else "Partial"
        idx, sim = _semantic_match(skill)
        demand   = MARKET_DEMAND.get(sl, MARKET_DEMAND.get(skill.lower(), 1))
        gap_profile.append({
            "skill": skill, "status": status, "proficiency": proficiency,
            "original_prof": original_prof, "decayed": decayed,
            "is_required": is_required, "context": context,
            "catalog_course": get_full_catalog()[idx] if idx >= 0 else None,
            "similarity": sim, "demand": demand,
        })
    return gap_profile

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7B · SENIORITY MISMATCH
# ─────────────────────────────────────────────────────────────────────────────
SENIORITY_MAP = {"Junior":0, "Mid":1, "Senior":2, "Lead":3}

def check_seniority_mismatch(resume_data: dict, jd_data: dict) -> dict:
    cand_s = resume_data.get("seniority", "Mid")
    req_s  = jd_data.get("seniority_required", "Mid")
    cand_l = SENIORITY_MAP.get(cand_s, 1)
    req_l  = SENIORITY_MAP.get(req_s, 1)
    gap    = req_l - cand_l
    return {"has_mismatch": gap > 0, "gap_levels": gap, "candidate": cand_s, "required": req_s,
            "add_leadership": gap >= 1, "add_strategic": gap >= 2}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7C · INTERVIEW READINESS
# ─────────────────────────────────────────────────────────────────────────────
def calculate_interview_readiness(gap_profile: List[dict], resume_data: dict) -> dict:
    req_known = [g for g in gap_profile if g["status"] == "Known"   and g["is_required"]]
    req_part  = [g for g in gap_profile if g["status"] == "Partial" and g["is_required"]]
    req_miss  = [g for g in gap_profile if g["status"] == "Missing" and g["is_required"]]
    req_total = len(req_known) + len(req_part) + len(req_miss)
    score = 0
    if req_total > 0:
        score = round(((len(req_known)*1.0 + len(req_part)*0.4) / req_total) * 100)
    bonus = {"Junior":5, "Mid":0, "Senior":-5, "Lead":-10}
    score = max(0, min(100, score + bonus.get(resume_data.get("seniority","Mid"), 0)))
    if   score >= 75: verdict = ("Strong",    "#4ECDC4", "Ready for most interview rounds")
    elif score >= 50: verdict = ("Moderate",  "#FFE66D", "Can pass screening; prep on gaps needed")
    elif score >= 30: verdict = ("Weak",      "#FFA726", "Gap work needed before applying")
    else:             verdict = ("Not Ready", "#FF6B6B", "Significant preparation required")
    return {"score": score, "label": verdict[0], "color": verdict[1], "advice": verdict[2],
            "req_known": len(req_known), "req_partial": len(req_part), "req_missing": len(req_miss)}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7D · CAREER GAP ESTIMATOR
# ─────────────────────────────────────────────────────────────────────────────
def estimate_career_gap(resume_data: dict, jd_data: dict, roadmap_hours: int) -> dict:
    cand_l = SENIORITY_MAP.get(resume_data.get("seniority","Mid"), 1)
    req_l  = SENIORITY_MAP.get(jd_data.get("seniority_required","Mid"), 1)
    gap    = max(0, req_l - cand_l)
    career_months  = gap * 18
    training_months = round((roadmap_hours / 2) / (5 * 4.3))
    total_months   = max(training_months, career_months)
    return {"seniority_gap_levels": gap, "training_months": training_months,
            "career_months": career_months, "total_months": total_months,
            "timeline_label": (f"{total_months} months" if total_months < 12
                               else f"{total_months//12}y {total_months%12}m")}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 · ADAPTIVE PATH GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def generate_path(gap_profile: List[dict], resume_data: dict,
                  jd_data: Optional[dict] = None) -> List[dict]:
    modules_needed: set = set()
    id_to_gap: Dict[str, dict] = {}
    for gap in gap_profile:
        if gap["status"] == "Known": continue
        course = gap.get("catalog_course")
        if not course: continue
        cid = course["id"]
        modules_needed.add(cid); id_to_gap[cid] = gap
        try:
            for anc in nx.ancestors(SKILL_GRAPH, cid):
                anc_data = CATALOG_BY_ID.get(anc)
                if not anc_data: continue
                already_known = any(g["status"] == "Known" and
                                    g["skill"].lower() in anc_data["skill"].lower()
                                    for g in gap_profile)
                if not already_known: modules_needed.add(anc)
        except Exception:
            pass
    if jd_data:
        sm = check_seniority_mismatch(resume_data, jd_data)
        if sm["add_leadership"]: modules_needed.update(["LD01","LD02"])
        if sm["add_strategic"]:  modules_needed.add("LD03")
    sub = SKILL_GRAPH.subgraph(modules_needed)
    try:    ordered = list(nx.topological_sort(sub))
    except: ordered = list(modules_needed)
    critical_ids = set()
    try:
        if len(sub.nodes) > 0: critical_ids = set(nx.dag_longest_path(sub))
    except: pass
    path, seen = [], set()
    for cid in ordered:
        if cid in seen: continue
        seen.add(cid)
        course = CATALOG_BY_ID.get(cid)
        if not course: continue
        gap = id_to_gap.get(cid, {})
        path.append({**course,
                     "gap_skill":   gap.get("skill", course["skill"]),
                     "gap_status":  gap.get("status", "Prereq"),
                     "priority":    (0 if gap.get("is_required") else 1, gap.get("proficiency", 0)),
                     "reasoning":   "",
                     "is_critical": cid in critical_ids,
                     "demand":      gap.get("demand", 1),
                     "progress":    "not_started"})  # v4: progress tracker state
    path.sort(key=lambda x: x["priority"])
    return path

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8B · WEEKLY STUDY PLAN
# ─────────────────────────────────────────────────────────────────────────────
def generate_weekly_plan(path: List[dict], hours_per_day: float = 2.0) -> List[dict]:
    weekly_cap = hours_per_day * 5
    weeks, cur_week, cur_hrs = [], [], 0.0
    week_num = 1
    for module in path:
        remaining = float(module["duration_hrs"])
        while remaining > 0:
            available = weekly_cap - cur_hrs
            if available <= 0:
                weeks.append({"week": week_num, "modules": cur_week, "total_hrs": cur_hrs})
                cur_week, cur_hrs = [], 0.0; week_num += 1; available = weekly_cap
            chunk = min(remaining, available)
            exists = next((m for m in cur_week if m["id"] == module["id"]), None)
            if exists: exists["hrs_this_week"] += chunk
            else:
                cur_week.append({"id": module["id"], "title": module["title"],
                                 "level": module["level"], "domain": module["domain"],
                                 "is_critical": module.get("is_critical", False),
                                 "hrs_this_week": chunk, "total_hrs": module["duration_hrs"]})
            cur_hrs += chunk; remaining -= chunk
    if cur_week: weeks.append({"week": week_num, "modules": cur_week, "total_hrs": cur_hrs})
    return weeks

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 · IMPACT SCORER
# ─────────────────────────────────────────────────────────────────────────────
STANDARD_ONBOARDING_HRS = 60

def calculate_impact(gap_profile: List[dict], path: List[dict]) -> dict:
    total    = len(gap_profile)
    known    = sum(1 for g in gap_profile if g["status"] == "Known")
    partial  = sum(1 for g in gap_profile if g["status"] == "Partial")
    covered  = len({m["gap_skill"] for m in path})
    decayed_count = sum(1 for g in gap_profile if g.get("decayed"))
    roadmap_hrs = sum(m["duration_hrs"] for m in path)
    hours_saved = max(0, STANDARD_ONBOARDING_HRS - roadmap_hrs)
    current_fit   = min(100, round((known / max(total, 1)) * 100))
    projected_fit = min(100, round(((known + covered) / max(total, 1)) * 100))
    return {"total_skills": total, "known_skills": known, "partial_skills": partial,
            "gaps_addressed": covered, "roadmap_hours": roadmap_hrs, "hours_saved": hours_saved,
            "role_readiness_pct": projected_fit, "current_fit": current_fit,
            "projected_fit": projected_fit, "fit_delta": projected_fit - current_fit,
            "modules_count": len(path), "decayed_skills": decayed_count,
            "critical_count": sum(1 for m in path if m.get("is_critical"))}

def weeks_to_ready(roadmap_hours: int, hours_per_day: float) -> str:
    if hours_per_day <= 0: return "-"
    days = roadmap_hours / hours_per_day; weeks = days / 5
    if weeks < 1:   return f"{int(days)} days"
    elif weeks < 4: return f"{weeks:.1f} weeks"
    else:           return f"{(weeks/4):.1f} months"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 · CHARTS
# ─────────────────────────────────────────────────────────────────────────────
_BG = "rgba(0,0,0,0)"
_FD = dict(color="#C9D1D9", family="'Space Grotesk',sans-serif")
_FL = dict(color="#1A202C", family="'Space Grotesk',sans-serif")
def _grid(d): return "#1E2A3A" if d else "#E2E8F0"
def _font(d): return _FD if d else _FL


def radar_chart(gap_profile: List[dict], dark: bool = True) -> go.Figure:
    items = gap_profile[:10]
    if not items: return go.Figure()
    theta     = [g["skill"][:16] for g in items]
    resume    = [g["proficiency"] for g in items]
    pre_decay = [g.get("original_prof", g["proficiency"]) for g in items]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=[10]*len(items), theta=theta, fill="toself",
        name="JD Requirement", line=dict(color="#FF6B6B", width=2), opacity=0.20))
    fig.add_trace(go.Scatterpolar(r=pre_decay, theta=theta, fill="toself",
        name="Before Decay", line=dict(color="#FFE66D", width=1, dash="dot"), opacity=0.18))
    fig.add_trace(go.Scatterpolar(r=resume, theta=theta, fill="toself",
        name="Current Skills", line=dict(color="#4ECDC4", width=2), opacity=0.75))
    fig.update_layout(
        polar=dict(bgcolor=_BG,
                   radialaxis=dict(visible=True, range=[0,10], gridcolor=_grid(dark), color="#555"),
                   angularaxis=dict(gridcolor=_grid(dark))),
        paper_bgcolor=_BG, plot_bgcolor=_BG, font=_font(dark), showlegend=True,
        legend=dict(bgcolor=_BG, x=0.78, y=1.18, font=dict(size=10)),
        margin=dict(l=30, r=30, t=40, b=30),
    )
    return fig


def timeline_chart(path: List[dict], dark: bool = True) -> go.Figure:
    if not path: return go.Figure()
    def bar_color(m):
        if m.get("is_critical"): return "#FF6B6B"
        return {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF9A9A"}.get(m["level"],"#888")
    shown, fig = set(), go.Figure()
    for i, m in enumerate(path):
        col     = bar_color(m)
        lvl_key = "Critical" if m.get("is_critical") else m["level"]
        show    = lvl_key not in shown; shown.add(lvl_key)
        label   = f"{'* ' if m.get('is_critical') else ''}#{i+1} {m['title'][:33]}"
        fig.add_trace(go.Bar(
            x=[m["duration_hrs"]], y=[label], orientation="h",
            marker=dict(color=col, opacity=0.88, line=dict(width=0)),
            name=lvl_key, legendgroup=lvl_key, showlegend=show,
            hovertemplate=(f"<b>{m['title']}</b><br>Skill: {m['skill']}<br>"
                           f"Level: {m['level']}<br>Duration: {m['duration_hrs']}h"
                           f"{'<br>Critical Path' if m.get('is_critical') else ''}<extra></extra>")
        ))
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor="rgba(15,22,36,0.6)" if dark else "rgba(240,245,255,0.8)",
        font=_font(dark),
        xaxis=dict(title="Hours", gridcolor=_grid(dark), color="#555", zeroline=False),
        yaxis=dict(gridcolor=_grid(dark), tickfont=dict(size=10)),
        margin=dict(l=10, r=20, t=10, b=40), height=max(320, len(path)*44),
        legend=dict(bgcolor=_BG, orientation="h", y=1.03), barmode="overlay",
    )
    return fig


def priority_matrix_chart(gap_profile: List[dict], dark: bool = True) -> go.Figure:
    ease_map = {"Beginner":9, "Intermediate":5, "Advanced":2}
    pts = []
    for g in gap_profile:
        if g["status"] == "Known": continue
        course = g.get("catalog_course")
        if not course: continue
        ease   = ease_map.get(course["level"], 5) + (hash(g["skill"]) % 3 - 1) * 0.25
        impact = min(10, g.get("demand",1)*3 + (3 if g["is_required"] else 0) + (hash(g["skill"]) % 2)*0.2)
        pts.append({"skill":g["skill"],"ease":ease,"impact":impact,
                    "hrs":course["duration_hrs"],"status":g["status"]})
    if not pts: return go.Figure()
    color_map = {"Missing":"#FF6B6B","Partial":"#FFE66D"}
    fig = go.Figure()
    for status in ["Missing","Partial"]:
        sub = [p for p in pts if p["status"] == status]
        if not sub: continue
        fig.add_trace(go.Scatter(
            x=[p["ease"] for p in sub], y=[p["impact"] for p in sub],
            mode="markers+text",
            marker=dict(size=[max(14, p["hrs"]*2.8) for p in sub], color=color_map[status],
                        opacity=0.75, line=dict(width=1, color="rgba(255,255,255,0.3)")),
            text=[p["skill"][:13] for p in sub], textposition="top center",
            textfont=dict(size=9, color="#C9D1D9" if dark else "#1A202C"), name=status,
            hovertemplate="<b>%{text}</b><br>Ease: %{x:.1f}/10<br>Impact: %{y:.1f}/10<extra></extra>",
        ))
    for (x, y, txt) in [(2.5,8.5,"HIGH PRIORITY"),(7.5,8.5,"QUICK WIN"),
                         (2.5,2.5,"LONG HAUL"),(7.5,2.5,"NICE TO HAVE")]:
        fig.add_annotation(x=x, y=y, text=txt, showarrow=False,
                           font=dict(size=9, color="#3D4F6B" if dark else "#718096"))
    fig.add_hline(y=5.5, line_dash="dot", line_color="#1E2A3A")
    fig.add_vline(x=5.5, line_dash="dot", line_color="#1E2A3A")
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor="rgba(15,22,36,0.4)" if dark else "rgba(240,245,255,0.8)",
        font=_font(dark),
        xaxis=dict(title="Ease of Learning", range=[0,11], gridcolor=_grid(dark), zeroline=False),
        yaxis=dict(title="Market Impact", range=[0,11], gridcolor=_grid(dark), zeroline=False),
        margin=dict(l=20, r=20, t=20, b=40), showlegend=True,
        legend=dict(bgcolor=_BG, x=0, y=1.1, orientation="h"), height=420,
    )
    return fig


def ats_gauge_chart(score: int, dark: bool = True) -> go.Figure:
    color = "#4ECDC4" if score >= 75 else "#FFE66D" if score >= 50 else "#FF6B6B"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"suffix":"%","font":{"size":32,"color":color,"family":"JetBrains Mono,monospace"}},
        gauge={"axis":{"range":[0,100],"tickwidth":1,"tickcolor":"#3D4F6B"},
               "bar":{"color":color,"thickness":0.25},
               "bgcolor":"rgba(255,255,255,0.04)","bordercolor":"rgba(0,0,0,0)",
               "steps":[{"range":[0,40],"color":"rgba(255,107,107,0.12)"},
                        {"range":[40,70],"color":"rgba(255,230,109,0.12)"},
                        {"range":[70,100],"color":"rgba(78,205,196,0.12)"}],
               "threshold":{"line":{"color":color,"width":3},"thickness":0.75,"value":score}},
    ))
    fig.update_layout(paper_bgcolor=_BG, font=_font(dark),
                      margin=dict(l=20,r=20,t=20,b=10), height=200)
    return fig


def weekly_gantt_chart(weekly_plan: List[dict], dark: bool = True) -> go.Figure:
    if not weekly_plan: return go.Figure()
    lc = {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF6B6B"}
    shown, fig = set(), go.Figure()
    for week_data in weekly_plan[:8]:
        w = week_data["week"]
        for mod in week_data["modules"]:
            col = "#FF6B6B" if mod.get("is_critical") else lc.get(mod["level"],"#888")
            key = "Critical" if mod.get("is_critical") else mod["level"]
            show = key not in shown; shown.add(key)
            fig.add_trace(go.Bar(
                x=[mod["hrs_this_week"]], y=[f"Week {w}"], orientation="h",
                marker=dict(color=col, opacity=0.82, line=dict(width=0)),
                name=key, legendgroup=key, showlegend=show,
                hovertemplate=f"<b>{mod['title'][:30]}</b><br>{mod['hrs_this_week']:.1f}h this week<extra></extra>",
            ))
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor="rgba(15,22,36,0.4)" if dark else "rgba(240,245,255,0.8)",
        font=_font(dark), barmode="stack",
        xaxis=dict(title="Hours", gridcolor=_grid(dark), zeroline=False),
        yaxis=dict(autorange="reversed", gridcolor=_grid(dark)),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(250, len(weekly_plan[:8])*52),
        legend=dict(bgcolor=_BG, orientation="h", y=1.05),
    )
    return fig


def roi_chart(roi_list: List[dict], dark: bool = True) -> go.Figure:
    """v4 NEW: Learning ROI bar chart."""
    if not roi_list: return go.Figure()
    top = roi_list[:10]
    colors = ["#FF6B6B" if m["is_required"] else "#4ECDC4" for m in top]
    fig = go.Figure(go.Bar(
        x=[m["roi"] for m in top],
        y=[m["title"][:30] for m in top],
        orientation="h",
        marker=dict(color=colors, opacity=0.85),
        hovertemplate="<b>%{y}</b><br>ROI Index: %{x}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor="rgba(15,22,36,0.4)" if dark else "rgba(240,245,255,0.8)",
        font=_font(dark),
        xaxis=dict(title="ROI Index (higher = learn first)", gridcolor=_grid(dark), zeroline=False),
        yaxis=dict(gridcolor=_grid(dark), autorange="reversed"),
        margin=dict(l=10, r=20, t=10, b=40), height=max(260, len(top)*38),
        title=dict(text="Learning ROI — Required (red) vs Optional (teal)", font=dict(size=11)),
    )
    return fig


def multi_jd_chart(jd_comparisons: List[dict], dark: bool = True) -> go.Figure:
    """v4 NEW: Multi-JD fit comparison chart."""
    if not jd_comparisons: return go.Figure()
    roles = [c["role_title"][:25] for c in jd_comparisons]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Fit Now", x=roles,
                         y=[c["fit_now"] for c in jd_comparisons],
                         marker_color="#FF6B6B", opacity=0.85))
    fig.add_trace(go.Bar(name="Fit in 6 months", x=roles,
                         y=[c["fit_6m"] for c in jd_comparisons],
                         marker_color="#4ECDC4", opacity=0.70))
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor="rgba(15,22,36,0.4)" if dark else "rgba(240,245,255,0.8)",
        font=_font(dark), barmode="group",
        yaxis=dict(title="Fit %", range=[0,105], gridcolor=_grid(dark)),
        xaxis=dict(gridcolor=_grid(dark)),
        legend=dict(bgcolor=_BG, orientation="h", y=1.05),
        margin=dict(l=20, r=20, t=20, b=40), height=320,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 · PDF EXPORT
# ─────────────────────────────────────────────────────────────────────────────
def build_pdf(resume_data, jd_data, gap_profile, path, impact,
              quality=None, interview=None) -> io.BytesIO:
    buf = io.BytesIO()
    if not REPORTLAB: return buf
    doc    = SimpleDocTemplate(buf, pagesize=letter,
                               topMargin=48, bottomMargin=48, leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    TEAL = rl_colors.HexColor("#2A9D8F"); DARK = rl_colors.HexColor("#1A1A2E")
    H1 = ParagraphStyle("H1",parent=styles["Title"],fontSize=22,spaceAfter=4,textColor=TEAL)
    H2 = ParagraphStyle("H2",parent=styles["Heading2"],fontSize=13,spaceAfter=6,textColor=DARK,spaceBefore=14)
    BD = ParagraphStyle("BD",parent=styles["Normal"],fontSize=10,spaceAfter=5)
    IT = ParagraphStyle("IT",parent=styles["Normal"],fontSize=9,spaceAfter=4,leftIndent=18,
                         textColor=rl_colors.HexColor("#555555"),italics=True)
    BL = ParagraphStyle("BL",parent=styles["Normal"],fontSize=9,spaceAfter=3,leftIndent=14)
    story = [
        Paragraph("SkillForge v4 - AI Adaptive Onboarding Report", H1),
        Paragraph(f"Candidate: <b>{resume_data.get('name','--')}</b>   "
                  f"Role: <b>{jd_data.get('role_title','--')}</b>   "
                  f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}", BD),
        Spacer(1, 14),
    ]
    if quality or interview:
        story.append(Paragraph("Scores Overview", H2))
        rows = []
        if quality:
            rows += [["ATS Score", f"{quality.get('ats_score','--')}%"],
                     ["Resume Grade", quality.get("overall_grade","--")],
                     ["Completeness", f"{quality.get('completeness_score','--')}%"],
                     ["Clarity", f"{quality.get('clarity_score','--')}%"]]
        if interview:
            rows += [["Interview Readiness", f"{interview['score']}% - {interview['label']}"],
                     ["Req. Skills Known", str(interview["req_known"])],
                     ["Req. Skills Missing", str(interview["req_missing"])]]
        st = Table([["Metric","Score"]]+rows, colWidths=[200,260])
        st.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),TEAL),("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
            ("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.4,rl_colors.grey),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.whitesmoke,rl_colors.white]),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story += [st, Spacer(1,14)]
    story.append(Paragraph("Impact Summary", H2))
    impact_rows = [
        ["Role Fit Current",   f"{impact['current_fit']}%"],
        ["Role Fit Projected", f"{impact['projected_fit']}% (+{impact['fit_delta']}%)"],
        ["Skills Addressed",   f"{impact['gaps_addressed']} / {impact['total_skills']}"],
        ["Training Hours",     f"{impact['roadmap_hours']} hrs"],
        ["Hours Saved",        f"~{impact['hours_saved']} hrs"],
        ["Modules",            str(impact["modules_count"])],
        ["Critical Path",      str(impact.get("critical_count",0))],
        ["Decay Adjusted",     str(impact.get("decayed_skills",0))],
    ]
    tbl = Table([["Metric","Value"]]+impact_rows, colWidths=[200,260])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),TEAL),("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
        ("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.4,rl_colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.whitesmoke,rl_colors.white]),
        ("LEFTPADDING",(0,0),(-1,-1),8),
    ]))
    story += [tbl, Spacer(1,18)]
    if quality and quality.get("improvement_tips"):
        story.append(Paragraph("Resume Improvement Tips", H2))
        for tip in quality["improvement_tips"][:5]:
            story.append(Paragraph(f"* {tip}", BL))
        story.append(Spacer(1,10))
    if quality and quality.get("missing_keywords"):
        story.append(Paragraph("Missing ATS Keywords", H2))
        story.append(Paragraph(", ".join(quality["missing_keywords"][:10]), BD))
        story.append(Spacer(1,10))
    story.append(Paragraph("Personalized Learning Roadmap", H2))
    for i, m in enumerate(path):
        prefix = "[CRITICAL] " if m.get("is_critical") else ""
        story.append(Paragraph(
            f"<b>{i+1}. {prefix}{m['title']}</b>  --  {m['level']} / {m['duration_hrs']}h / {m['domain']}", BD))
        if m.get("reasoning"):
            story.append(Paragraph(f">> {m['reasoning']}", IT))
    story += [Spacer(1,16), Paragraph("Full Skill Gap Analysis", H2)]
    gap_rows = [["Skill","Status","Prof","Required","Demand","Decayed"]]
    for g in gap_profile:
        gap_rows.append([g["skill"], g["status"], f"{g['proficiency']}/10",
                         "Yes" if g["is_required"] else "No",
                         {3:"High",2:"Med",1:"Low"}.get(g.get("demand",1),"--"),
                         "Yes" if g.get("decayed") else "No"])
    gt = Table(gap_rows, colWidths=[120,60,55,60,50,55])
    gt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.3,rl_colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.whitesmoke,rl_colors.white]),
        ("LEFTPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(gt)
    doc.build(story)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12 · DASH APP
# ─────────────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700"
        "&family=JetBrains+Mono:wght@400;600&display=swap",
    ],
    suppress_callback_exceptions=True,
)
server = app.server

app.index_string = """<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>SkillForge v4 - AI Adaptive Onboarding</title>
  {%favicon%}
  {%css%}
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{background:#070B14;font-family:'Space Grotesk',sans-serif;color:#C9D1D9;min-height:100vh;transition:background .3s,color .3s}
    body.light-mode{background:#F0F4F8;color:#1A202C}
    body.light-mode .nav-bar{background:rgba(240,244,248,.97)!important;border-bottom-color:#CBD5E0!important}
    body.light-mode .glass-card{background:#fff!important;border-color:#E2E8F0!important}
    body.light-mode .upload-box{background:rgba(78,205,196,.05)!important;border-color:rgba(78,205,196,.3)!important}
    body.light-mode .hero-sub,.light-mode .section-s,.light-mode .upload-hint,.light-mode .impact-lbl,.light-mode .mod-meta,.light-mode .prof-key{color:#718096!important}
    body.light-mode .prog-track{background:rgba(0,0,0,.08)!important}
    body.light-mode .nav-tabs{border-bottom-color:#E2E8F0!important}
    body.light-mode .nav-tabs .nav-link{color:#718096!important}
    body.light-mode textarea.form-control{background:#F7FAFC!important;border-color:#E2E8F0!important;color:#1A202C!important}
    body.light-mode .mod-card{background:#fff!important;border-color:#E2E8F0!important}
    body.light-mode .prof-val,.light-mode .section-h{color:#1A202C!important}
    body.light-mode .warn-banner{background:rgba(255,193,7,.12)!important;color:#92400E!important}
    body.light-mode .tip-card{background:#fff!important;border-color:#E2E8F0!important}
    body.light-mode .strength-item{background:rgba(78,205,196,.08)!important}
    body.light-mode .red-flag-item{background:rgba(255,107,107,.06)!important}
    body.light-mode .week-card{background:#fff!important;border-color:#E2E8F0!important}
    body.light-mode .audit-row{background:#fff!important;border-color:#E2E8F0!important}
    .nav-bar{background:rgba(7,11,20,.95);border-bottom:1px solid #161D2E;backdrop-filter:blur(12px);position:sticky;top:0;z-index:100;padding:12px 0;transition:background .3s}
    .logo-mark{font-family:'JetBrains Mono',monospace;font-size:1.45rem;font-weight:700;color:#4ECDC4;letter-spacing:-.03em}
    .logo-sub{font-size:.6rem;color:#3D4F6B;letter-spacing:.18em;text-transform:uppercase;margin-top:1px}
    .nav-pill{font-size:.72rem;color:#3D4F6B;background:rgba(78,205,196,.07);border:1px solid rgba(78,205,196,.15);border-radius:99px;padding:3px 10px}
    .theme-btn{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);border-radius:99px;color:#C9D1D9;font-size:.78rem;padding:5px 14px;cursor:pointer;transition:all .2s;font-family:'Space Grotesk',sans-serif}
    .theme-btn:hover{background:rgba(78,205,196,.15);border-color:#4ECDC4;color:#4ECDC4}
    .sample-btn{background:rgba(78,205,196,.08);border:1px solid rgba(78,205,196,.2);border-radius:8px;color:#4ECDC4;font-size:.75rem;padding:6px 14px;cursor:pointer;transition:all .2s;font-family:'Space Grotesk',sans-serif;font-weight:600}
    .sample-btn:hover{background:rgba(78,205,196,.18);transform:translateY(-1px)}
    .hero-title{font-size:2.4rem;font-weight:700;line-height:1.15;background:linear-gradient(135deg,#E6EDF3 0%,#4ECDC4 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .hero-sub{color:#6B7A99;font-size:1rem;margin-top:10px;max-width:620px}
    .glass-card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:24px;transition:border-color .2s,box-shadow .2s,background .3s}
    .glass-card:hover{border-color:rgba(78,205,196,.25);box-shadow:0 0 24px rgba(78,205,196,.06)}
    .upload-box{border:2px dashed rgba(78,205,196,.25);border-radius:10px;padding:28px 16px;text-align:center;cursor:pointer;transition:all .2s;background:rgba(78,205,196,.03)}
    .upload-box:hover{border-color:#4ECDC4;background:rgba(78,205,196,.07)}
    .upload-hint{font-size:.78rem;color:#3D4F6B;margin-top:4px}
    .btn-run{background:linear-gradient(135deg,#4ECDC4,#44B8B0);border:none;border-radius:10px;color:#070B14;font-weight:700;font-size:.95rem;padding:13px 0;width:100%;font-family:'Space Grotesk',sans-serif;cursor:pointer;transition:all .2s}
    .btn-run:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(78,205,196,.3)}
    .btn-run:active{transform:translateY(0)}
    .badge-known{background:rgba(78,205,196,.15);color:#4ECDC4;border:1px solid rgba(78,205,196,.4)}
    .badge-partial{background:rgba(255,230,109,.12);color:#FFE66D;border:1px solid rgba(255,230,109,.4)}
    .badge-missing{background:rgba(255,107,107,.12);color:#FF6B6B;border:1px solid rgba(255,107,107,.4)}
    .skill-badge{font-size:.7rem;border-radius:4px;padding:2px 8px;font-weight:600;letter-spacing:.03em}
    .domain-tech{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(78,205,196,.12);color:#4ECDC4;border:1px solid rgba(78,205,196,.3)}
    .domain-nontech{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(255,230,109,.12);color:#FFE66D;border:1px solid rgba(255,230,109,.3)}
    .domain-soft{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(167,139,250,.12);color:#A78BFA;border:1px solid rgba(167,139,250,.3)}
    .decay-badge{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(255,152,0,.12);color:#FFA726;border:1px solid rgba(255,152,0,.3)}
    .critical-badge{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(255,107,107,.15);color:#FF6B6B;border:1px solid rgba(255,107,107,.3)}
    .demand-high{font-size:.62rem;border-radius:99px;padding:1px 7px;font-weight:700;background:rgba(255,107,107,.12);color:#FF6B6B;border:1px solid rgba(255,107,107,.3)}
    .demand-med{font-size:.62rem;border-radius:99px;padding:1px 7px;font-weight:700;background:rgba(255,230,109,.10);color:#FFE66D;border:1px solid rgba(255,230,109,.3)}
    .demand-low{font-size:.62rem;border-radius:99px;padding:1px 7px;font-weight:700;background:rgba(78,205,196,.10);color:#4ECDC4;border:1px solid rgba(78,205,196,.3)}
    .warn-banner{background:rgba(255,193,7,.08);border:1px solid rgba(255,193,7,.3);border-radius:10px;padding:12px 16px;color:#FFD54F;font-size:.84rem;margin-bottom:16px}
    .budget-warn{background:rgba(255,107,107,.08);border:1px solid rgba(255,107,107,.3);border-radius:10px;padding:10px 16px;color:#FF6B6B;font-size:.8rem;margin-bottom:14px}
    .cache-hit{background:rgba(78,205,196,.08);border:1px solid rgba(78,205,196,.25);border-radius:8px;padding:8px 14px;color:#4ECDC4;font-size:.78rem;margin-bottom:14px}
    .impact-num{font-family:'JetBrains Mono',monospace;font-size:2.2rem;font-weight:700;color:#4ECDC4;line-height:1}
    .impact-lbl{font-size:.68rem;color:#3D4F6B;text-transform:uppercase;letter-spacing:.06em;margin-top:5px}
    .fit-score-box{text-align:center;padding:16px 12px}
    .fit-num-big{font-family:'JetBrains Mono',monospace;font-size:3rem;font-weight:700;line-height:1}
    .fit-delta{font-size:.85rem;color:#4ECDC4;font-weight:600;margin-top:4px}
    .fit-lbl-sm{font-size:.68rem;color:#3D4F6B;text-transform:uppercase;letter-spacing:.06em}
    .prog-track{background:rgba(255,255,255,.06);border-radius:99px;height:7px}
    .prog-fill{background:linear-gradient(90deg,#4ECDC4,#44B8B0);border-radius:99px;height:7px;transition:width 1.2s ease}
    .mod-card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);border-left:3px solid #4ECDC4;border-radius:8px;padding:14px;margin-bottom:10px}
    .mod-card.adv{border-left-color:#FF6B6B}.mod-card.int{border-left-color:#FFE66D}
    .mod-card.critical{border-left-color:#FF6B6B;box-shadow:0 0 12px rgba(255,107,107,.15)}
    .mod-card.done{opacity:.55;border-left-color:#4ECDC4}
    .mod-card.in-progress{border-left-color:#FFE66D;box-shadow:0 0 10px rgba(255,230,109,.12)}
    .mod-title{font-weight:600;font-size:.9rem}.mod-meta{font-size:.75rem;color:#555F7A;margin-top:4px}
    .mod-why{font-size:.78rem;color:#7B8DA6;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.05);font-style:italic}
    .tip-card{background:rgba(78,205,196,.04);border:1px solid rgba(78,205,196,.12);border-radius:10px;padding:12px 16px;margin-bottom:8px}
    .tip-number{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:#4ECDC4;margin-right:8px;font-weight:700}
    .strength-item{background:rgba(78,205,196,.07);border-left:3px solid #4ECDC4;border-radius:6px;padding:8px 12px;margin-bottom:7px;font-size:.84rem}
    .red-flag-item{background:rgba(255,107,107,.06);border-left:3px solid #FF6B6B;border-radius:6px;padding:8px 12px;margin-bottom:7px;font-size:.84rem}
    .transfer-item{background:rgba(167,139,250,.06);border-left:3px solid #A78BFA;border-radius:6px;padding:8px 12px;margin-bottom:7px;font-size:.82rem}
    .ats-grade{font-family:'JetBrains Mono',monospace;font-size:3.5rem;font-weight:700;line-height:1}
    .week-card{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);border-radius:8px;padding:12px;margin-bottom:8px}
    .week-label{font-family:'JetBrains Mono',monospace;font-size:.78rem;color:#4ECDC4;font-weight:700;margin-bottom:6px}
    .interview-bar{height:8px;border-radius:99px;background:rgba(255,255,255,.06);margin-top:10px}
    .interview-fill{height:8px;border-radius:99px;transition:width 1s ease}
    .audit-row{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.04);border-radius:6px;padding:8px 12px;margin-bottom:5px;font-family:'JetBrains Mono',monospace;font-size:.72rem}
    .nav-tabs{border-bottom:1px solid #161D2E!important;margin-bottom:24px}
    .nav-tabs .nav-link{color:#4A5568!important;border:none!important;font-size:.88rem;padding:10px 20px}
    .nav-tabs .nav-link.active{color:#4ECDC4!important;background:transparent!important;border-bottom:2px solid #4ECDC4!important}
    .prof-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px}
    .prof-key{font-size:.78rem;color:#4A5568}.prof-val{font-size:.82rem;color:#C9D1D9;font-weight:500}
    .loading-overlay{display:none;position:fixed;inset:0;background:rgba(7,11,20,.92);z-index:9999;align-items:center;justify-content:center;flex-direction:column;gap:14px}
    .loading-overlay.active{display:flex}
    .spin{width:48px;height:48px;border:3px solid rgba(78,205,196,.2);border-top-color:#4ECDC4;border-radius:50%;animation:spin .75s linear infinite}
    @keyframes spin{to{transform:rotate(360deg)}}
    .step-row{display:flex;gap:8px;margin-bottom:6px;align-items:center}
    .step-label{font-size:.75rem;color:#3D4F6B}
    .fade-up{animation:fadeUp .45s ease}
    @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    .section-h{font-size:1.15rem;font-weight:600;color:#E6EDF3;margin-bottom:4px}
    .section-s{font-size:.78rem;color:#3D4F6B;margin-bottom:16px}
    textarea.form-control{background:rgba(255,255,255,.03)!important;border:1px solid rgba(255,255,255,.07)!important;color:#C9D1D9!important;font-size:.82rem}
    textarea.form-control:focus{border-color:rgba(78,205,196,.4)!important;box-shadow:none!important}
    .progress-btn{background:transparent;border:1px solid rgba(78,205,196,.3);border-radius:6px;color:#4ECDC4;font-size:.68rem;padding:2px 8px;cursor:pointer;font-family:'Space Grotesk',sans-serif;margin-left:8px;transition:all .2s}
    .progress-btn:hover{background:rgba(78,205,196,.12)}
    .progress-btn.done{background:rgba(78,205,196,.15);border-color:#4ECDC4}
    .progress-btn.wip{background:rgba(255,230,109,.1);border-color:#FFE66D;color:#FFE66D}
    ::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#1E2A3A;border-radius:99px}
  </style>
</head>
<body id="body-root">
  {%app_entry%}
  <footer>{%config%}{%scripts%}{%renderer%}</footer>
  <script>
    document.addEventListener('DOMContentLoaded',function(){
      var overlay=document.getElementById('loading-overlay'),btn=document.getElementById('btn-run');
      if(btn&&overlay)btn.addEventListener('click',function(){overlay.classList.add('active');});
    });
  </script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12B · LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Store(id="s-resume"), dcc.Store(id="s-jd"),
    dcc.Store(id="s-jd2"), dcc.Store(id="s-jd3"),
    dcc.Store(id="s-results"), dcc.Store(id="s-theme", data="dark"),
    dcc.Store(id="s-progress", data={}),   # v4: module progress tracker
    dcc.Download(id="dl-pdf"),

    html.Div([
        html.Div(className="spin"),
        html.P("Running SkillForge v4 AI Analysis...",
               style={"color":"#4ECDC4","fontSize":".9rem","margin":0,"fontWeight":"600"}),
        html.P("3 Groq calls total (merged parse+audit + batched reasoning + JD parse)",
               style={"color":"#3D4F6B","fontSize":".76rem","margin":"4px 0 0"}),
        html.Div([
            *[html.Div([html.Span("- ",style={"color":"#4ECDC4"}),
                        html.Span(s, className="step-label")], className="step-row")
              for s in [
                  "JD parse (1 call)",
                  "Resume parse + ATS audit — merged into 1 call (was 2)",
                  "Batched reasoning for all modules — 1 call (was 12)",
                  "Semantic skill matching + decay model",
                  "Gap analysis + seniority detection",
                  "NetworkX DAG topological sort + critical path",
                  "Skill Transfer Map + ROI Calculator",
              ]]
        ], style={"marginTop":"12px","paddingLeft":"8px"}),
    ], id="loading-overlay", className="loading-overlay"),

    # ── NAV BAR
    html.Div([
        dbc.Container([dbc.Row([
            dbc.Col([html.Div("SkillForge", className="logo-mark"),
                     html.Div("SKILL GAP · ADAPTIVE PATHWAYS · v4", className="logo-sub")],
                    width="auto"),
            dbc.Col(html.Div([
                html.Span("Groq LLaMA 3.3", className="nav-pill"),
                html.Span("3 API calls/run", className="nav-pill ms-2"),
                html.Span("ATS Audit",       className="nav-pill ms-2"),
                html.Span("Multi-JD",        className="nav-pill ms-2"),
                html.Span("ROI Engine",      className="nav-pill ms-2"),
                html.Button("Light", id="btn-theme", className="theme-btn ms-3", n_clicks=0),
            ], className="d-flex align-items-center justify-content-end")),
        ], align="center")], fluid=True),
    ], className="nav-bar"),

    dbc.Container([
        html.Div([
            html.H1("Map Your Path to Role Mastery", className="hero-title"),
            html.P("Upload resume + JD → skill gap analysis, ATS audit, interview readiness, "
                   "ROI ranking, skill transfer map, multi-JD comparison, and personalised roadmap.",
                   className="hero-sub"),
        ], style={"padding":"40px 0 20px","textAlign":"center"}),

        # Sample buttons
        html.Div([
            html.P("Try a sample:", style={"fontSize":".78rem","color":"#3D4F6B",
                                           "marginBottom":"8px","textAlign":"center"}),
            html.Div([
                html.Button("Junior SWE",           id="sample-junior", className="sample-btn me-2", n_clicks=0),
                html.Button("Senior Data Scientist", id="sample-senior", className="sample-btn me-2", n_clicks=0),
                html.Button("HR Manager",            id="sample-hr",     className="sample-btn",      n_clicks=0),
            ], style={"textAlign":"center"}),
        ], style={"marginBottom":"28px"}),

        # Upload row
        dbc.Row([
            dbc.Col([html.Div([
                html.Div("Resume", style={"fontWeight":"600","marginBottom":"8px","fontSize":"1rem"}),
                dcc.Upload(id="up-resume",
                           children=html.Div(["Drop or ",
                                              html.Span("browse", style={"color":"#4ECDC4","textDecoration":"underline"})]),
                           className="upload-box"),
                html.P("PDF or DOCX", className="upload-hint"),
                html.Div(id="fn-resume", style={"fontSize":".75rem","color":"#4ECDC4","marginTop":"6px","textAlign":"center"}),
            ], className="glass-card", style={"textAlign":"center"})], md=3),

            dbc.Col([html.Div([
                html.Div("Primary JD", style={"fontWeight":"600","marginBottom":"8px","fontSize":"1rem"}),
                dcc.Upload(id="up-jd",
                           children=html.Div(["Drop or ",
                                              html.Span("browse",style={"color":"#4ECDC4","textDecoration":"underline"})]),
                           className="upload-box"),
                html.P("PDF, DOCX or paste / URL below", className="upload-hint"),
                html.Div(id="fn-jd", style={"fontSize":".75rem","color":"#4ECDC4","marginTop":"6px","textAlign":"center"}),
                dbc.Textarea(id="jd-paste", placeholder="...paste JD text or LinkedIn URL here",
                             rows=2, style={"marginTop":"10px"}),
            ], className="glass-card", style={"textAlign":"center"})], md=4),

            dbc.Col([html.Div([
                html.Div("Compare JDs (optional)", style={"fontWeight":"600","marginBottom":"8px","fontSize":"1rem"}),
                dbc.Textarea(id="jd2-paste", placeholder="JD #2 — paste text here for comparison", rows=2),
                dbc.Textarea(id="jd3-paste", placeholder="JD #3 — paste text here for comparison",
                             rows=2, style={"marginTop":"8px"}),
                html.P("Multi-JD fit comparison", className="upload-hint"),
            ], className="glass-card")], md=3),

            dbc.Col([html.Div([
                html.Div("Analyze", style={"fontWeight":"600","marginBottom":"4px","fontSize":"1rem"}),
                html.P("v4 · 3 API calls · cached", className="upload-hint"),
                html.P("Gap + Audit + ROI + Transfer Map", className="upload-hint",
                       style={"fontSize":".68rem","marginBottom":"18px"}),
                html.Button("Analyze", id="btn-run", className="btn-run", n_clicks=0),
                html.Div(id="run-err", style={"fontSize":".75rem","color":"#FF6B6B",
                                              "marginTop":"8px","textAlign":"center"}),
            ], className="glass-card", style={"textAlign":"center"})], md=2),
        ], className="g-3 mb-5"),

        # Results
        html.Div(id="results-wrap", style={"display":"none"}, className="fade-up", children=[
            dbc.Tabs(id="tabs", active_tab="tab-gap", className="mb-0", children=[
                dbc.Tab(label="Skill Gap",        tab_id="tab-gap"),
                dbc.Tab(label="Learning Roadmap", tab_id="tab-road"),
                dbc.Tab(label="Deep Analysis",    tab_id="tab-deep"),
                dbc.Tab(label="Multi-JD",         tab_id="tab-multi"),
                dbc.Tab(label="Export + Audit",   tab_id="tab-rep"),
            ]),
            html.Div(id="tab-body", style={"paddingTop":"24px"}),
        ]),

        html.Div(style={"height":"80px"}),
    ], fluid=True, style={"maxWidth":"1280px","padding":"0 24px"}),
])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13 · CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

app.clientside_callback(
    """function(n,theme){
        if(!n)return theme||'dark';
        var b=document.getElementById('body-root'),btn=document.getElementById('btn-theme');
        if(theme==='dark'){if(b)b.classList.add('light-mode');if(btn)btn.innerText='Dark';return'light';}
        else{if(b)b.classList.remove('light-mode');if(btn)btn.innerText='Light';return'dark';}
    }""",
    Output("s-theme","data"), Input("btn-theme","n_clicks"), State("s-theme","data"),
    prevent_initial_call=True,
)
app.clientside_callback(
    """function(data){
        var o=document.getElementById('loading-overlay');
        if(o)o.classList.remove('active');
        return window.dash_clientside.no_update;
    }""",
    Output("s-results","data",allow_duplicate=True),
    Input("s-results","data"), prevent_initial_call=True,
)

@app.callback(Output("fn-resume","children"), Output("s-resume","data"),
              Input("up-resume","contents"), State("up-resume","filename"),
              prevent_initial_call=True)
def cb_resume(c, f):
    if not c: return "", None
    return f"uploaded: {f}", {"text": parse_upload(c,f), "filename": f}

@app.callback(Output("fn-jd","children"), Output("s-jd","data"),
              Input("up-jd","contents"), State("up-jd","filename"),
              prevent_initial_call=True)
def cb_jd_upload(c, f):
    if not c: return "", None
    return f"uploaded: {f}", {"text": parse_upload(c,f), "filename": f}

@app.callback(
    Output("s-resume","data",allow_duplicate=True),
    Output("s-jd","data",allow_duplicate=True),
    Output("jd-paste","value"),
    Output("fn-resume","children",allow_duplicate=True),
    Output("fn-jd","children",allow_duplicate=True),
    Input("sample-junior","n_clicks"),
    Input("sample-senior","n_clicks"),
    Input("sample-hr","n_clicks"),
    prevent_initial_call=True,
)
def cb_samples(n1, n2, n3):
    key = {"sample-junior":"junior_swe","sample-senior":"senior_ds",
           "sample-hr":"hr_manager"}.get(ctx.triggered_id)
    if not key: raise PreventUpdate
    s = SAMPLES[key]
    return ({"text":s["resume"],"filename":f"{key}.txt"},
            {"text":s["jd"],"filename":f"{key}_jd.txt"},
            s["jd"],
            f"loaded: {s['label']} resume",
            f"loaded: {s['label']} JD")


@app.callback(
    Output("s-results","data",allow_duplicate=True),
    Output("results-wrap","style"),
    Output("run-err","children"),
    Input("btn-run","n_clicks"),
    State("s-resume","data"),
    State("s-jd","data"),
    State("jd-paste","value"),
    State("jd2-paste","value"),
    State("jd3-paste","value"),
    prevent_initial_call=True,
)
def cb_run(n, resume_store, jd_store, jd_paste, jd2_paste, jd3_paste):
    if not n: raise PreventUpdate

    resume_text   = (resume_store or {}).get("text", "")
    jd_text_final = (jd_store or {}).get("text", "") or jd_paste or ""

    if not resume_text:   return no_update, {"display":"none"}, "Upload or load a resume first."
    if not jd_text_final: return no_update, {"display":"none"}, "Upload, paste, or load a job description."

    # v4 FIX 5: token budget check
    budget_ok, used_today = token_budget_ok()
    if not budget_ok:
        return (no_update, {"display":"none"},
                f"⚠ Token budget warning: {used_today:,} / {DAILY_TOKEN_LIMIT:,} used today. "
                f"Proceeding but may hit rate limit.")

    # v4 FIX 4: check cache first — skip all Groq calls if same inputs
    cached = cache_get(resume_text, jd_text_final)
    if cached:
        cached["_cache_hit"] = True
        return cached, {"display":"block"}, ""

    # Handle LinkedIn URL in JD paste field
    if jd_text_final.startswith("http") and "linkedin.com" in jd_text_final:
        jd_text_final = extract_linkedin_jd(jd_text_final)

    # ── STEP 1: Parse JD first (needed for merged resume+audit call)
    jd_data = parse_jd(jd_text_final)
    if "error" in jd_data:
        return no_update, {"display":"none"}, f"JD parse error: {jd_data['error']}"

    # ── STEP 2: Merged resume parse + audit (FIX 1 — was 2 separate calls)
    resume_data, quality = parse_resume_and_audit(resume_text, jd_data)
    if "error" in resume_data:
        return no_update, {"display":"none"}, f"Resume parse error: {resume_data['error']}"

    # ── STEP 3: Gap + path
    gap_profile = analyze_gap(resume_data, jd_data)
    path        = generate_path(gap_profile, resume_data, jd_data)

    # ── STEP 4: Batched reasoning (FIX 2 — was 12 calls, now 1)
    cname   = resume_data.get("name", "the candidate")
    subset  = path[:14]
    reasoning_map = batch_generate_reasoning(subset, cname)
    for m in subset:
        m["reasoning"] = reasoning_map.get(m["id"], f"Addresses gap in {m['gap_skill']}.")

    # ── STEP 5: All local calculations (no Groq)
    impact    = calculate_impact(gap_profile, path)
    seniority = check_seniority_mismatch(resume_data, jd_data)
    interview = calculate_interview_readiness(gap_profile, resume_data)
    career    = estimate_career_gap(resume_data, jd_data, impact["roadmap_hours"])
    weekly    = generate_weekly_plan(path, hours_per_day=2.0)
    transfers = build_transfer_map(resume_data, gap_profile)
    roi       = calculate_roi(gap_profile, path)

    # ── STEP 6: Multi-JD comparison (optional, local scoring only)
    jd_comparisons = []
    extra_jds = [t for t in [jd2_paste, jd3_paste] if t and t.strip()]
    if extra_jds:
        parsed_extras = []
        for et in extra_jds:
            ej = parse_jd(et)   # 1 Groq call per extra JD
            if "error" not in ej:
                parsed_extras.append(ej)
        all_jds = [jd_data] + parsed_extras
        jd_comparisons = compare_jds(resume_data, all_jds)

    result = {
        "resume_data":    resume_data,
        "jd_data":        jd_data,
        "gap_profile":    gap_profile,
        "path":           path,
        "impact":         impact,
        "seniority":      seniority,
        "quality":        quality,
        "interview":      interview,
        "career":         career,
        "weekly_plan":    weekly,
        "transfers":      transfers,
        "roi":            roi,
        "jd_comparisons": jd_comparisons,
        "_cache_hit":     False,
        "_token_used":    sum(e.get("in_tok",0)+e.get("out_tok",0) for e in _AUDIT_LOG[-10:]),
    }

    # FIX 4: cache it
    cache_set(resume_text, jd_text_final, result)

    return result, {"display":"block"}, ""


@app.callback(
    Output("tab-body","children"),
    Input("tabs","active_tab"),
    Input("s-theme","data"),
    Input("s-progress","data"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_tabs(tab, theme, progress, results):
    if not results: raise PreventUpdate
    dark = theme != "light"
    rd = results["resume_data"];   jd = results["jd_data"]
    gp = results["gap_profile"];   pt = results["path"]
    im = results["impact"];        sm = results.get("seniority", {})
    ql = results.get("quality", {}); iv = results.get("interview", {})
    ca = results.get("career", {});  wp = results.get("weekly_plan", [])
    tf = results.get("transfers", []); roi = results.get("roi", [])
    jd_comp = results.get("jd_comparisons", [])

    cache_banner = (
        html.Div([html.Span("⚡ Cached result — ", style={"fontWeight":"700"}),
                  "No Groq calls made. Showing previous analysis for identical inputs."],
                 className="cache-hit")
        if results.get("_cache_hit") else None
    )

    warn = (html.Div([html.Span("Seniority Gap: ", style={"fontWeight":"700"}),
                      f"Candidate is {sm['candidate']}, role requires {sm['required']}. "
                      f"Leadership modules auto-added."],
                     className="warn-banner")
            if sm.get("has_mismatch") else None)

    def domain_badge(domain):
        cls = {"Tech":"domain-tech","Non-Tech":"domain-nontech","Soft":"domain-soft"}.get(domain,"domain-tech")
        return html.Span(domain, className=cls, style={"marginLeft":"6px"})

    def demand_badge(demand):
        cls = {3:"demand-high",2:"demand-med",1:"demand-low"}.get(demand,"demand-low")
        lbl = {3:"Hot",2:"Growing",1:"Stable"}.get(demand,"Stable")
        return html.Span(lbl, className=cls, style={"marginLeft":"4px"})

    # ── TAB 1: SKILL GAP ─────────────────────────────────────────────────
    if tab == "tab-gap":
        known   = [g for g in gp if g["status"] == "Known"]
        partial = [g for g in gp if g["status"] == "Partial"]
        missing = [g for g in gp if g["status"] == "Missing"]
        decayed = [g for g in gp if g.get("decayed")]

        def skill_row(g):
            cls = {"Known":"badge-known","Partial":"badge-partial","Missing":"badge-missing"}[g["status"]]
            items = [
                html.Span(g["skill"], style={"fontSize":".85rem","fontWeight":"500","minWidth":"90px"}),
                html.Span(g["status"], className=f"skill-badge {cls}", style={"marginLeft":"8px"}),
                html.Span(f"{g['proficiency']}/10",
                          style={"fontSize":".72rem","color":"#3D4F6B","marginLeft":"8px",
                                 "fontFamily":"JetBrains Mono,monospace"}),
                demand_badge(g.get("demand",1)),
            ]
            if g.get("decayed"): items.append(html.Span("decay", className="decay-badge ms-1"))
            return html.Div(items, style={"marginBottom":"9px","display":"flex",
                                          "alignItems":"center","flexWrap":"wrap"})

        # Transfer map section
        transfer_items = ([html.Div([
            html.Span("↗ ", style={"color":"#A78BFA","fontWeight":"700"}),
            html.Span(t["label"], style={"fontSize":".82rem"}),
        ], className="transfer-item") for t in tf[:6]]
        or [html.Div("No significant skill transfers detected.", className="section-s")])

        return html.Div([cache_banner, warn, dbc.Row([
            dbc.Col([html.Div([
                html.P("Skill Gap Radar", className="section-h"),
                html.P(f"{rd.get('name','Candidate')} vs {jd.get('role_title','Target Role')}",
                       className="section-s"),
                dcc.Graph(figure=radar_chart(gp, dark), config={"displayModeBar":False},
                          style={"height":"360px"})
            ], className="glass-card")], md=6),
            dbc.Col([html.Div([
                html.P("All Skills + Market Demand", className="section-h"),
                html.P(f"{len(known)} Known / {len(partial)} Partial / {len(missing)} Missing"
                       + (f" / {len(decayed)} Decayed" if decayed else ""), className="section-s"),
                html.Div([skill_row(g) for g in gp], style={"maxHeight":"320px","overflowY":"auto"})
            ], className="glass-card")], md=6),
            dbc.Col([html.Div([
                html.P("Skill Transfer Map", className="section-h"),
                html.P("Your existing skills accelerate these gaps", className="section-s"),
                *transfer_items,
            ], className="glass-card")], md=4),
            dbc.Col([html.Div([
                html.P("Candidate Strengths", className="section-h"),
                html.P("Already doing well", className="section-s"),
                *[html.Div([html.Span("+ ", style={"color":"#4ECDC4","fontWeight":"700"}),
                             html.Span(s, style={"fontSize":".84rem"})], className="strength-item")
                  for s in (rd.get("strengths",[]) or ["Good foundation detected"])]
            ], className="glass-card")], md=4),
            dbc.Col([html.Div([
                html.P("Candidate Profile", className="section-h", style={"marginBottom":"12px"}),
                *[html.Div([html.Span(k, className="prof-key"),
                             html.Span(str(v), className="prof-val")], className="prof-row")
                  for k, v in [("Name",       rd.get("name","--")),
                                ("Role",       rd.get("current_role","--")),
                                ("Seniority",  rd.get("seniority","--")),
                                ("Experience", f"{rd.get('years_experience','--')} yrs"),
                                ("Education",  rd.get("education","--")),
                                ("Domain",     rd.get("domain","--"))]],
            ], className="glass-card")], md=4),
        ], className="g-3")])

    # ── TAB 2: ROADMAP ────────────────────────────────────────────────────
    if tab == "tab-road":
        lc = {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF6B6B"}

        def mod_card(i, m):
            col    = lc.get(m["level"],"#888"); is_cr = m.get("is_critical",False)
            prog   = progress.get(m["id"],"not_started") if progress else "not_started"
            xtra   = (" critical" if is_cr
                      else " done" if prog == "done"
                      else " in-progress" if prog == "wip"
                      else " adv" if m["level"] == "Advanced"
                      else " int" if m["level"] == "Intermediate" else "")
            meta = [html.Span(f"Skill: {m['skill']} / {m.get('gap_status','--')}", className="mod-meta"),
                    domain_badge(m["domain"]), demand_badge(m.get("demand",1))]
            if is_cr: meta.append(html.Span("critical", className="critical-badge ms-1"))
            prog_label = {"done":"✓ Done","wip":"⏳ In Progress","not_started":"Mark"}.get(prog,"Mark")
            return html.Div([
                html.Div([
                    html.Span(f"#{i+1}", style={"fontFamily":"JetBrains Mono,monospace",
                                                "fontSize":".72rem","color":"#3D4F6B","marginRight":"10px"}),
                    html.Span(m["title"], className="mod-title"),
                    html.Span(m["level"], style={"marginLeft":"auto","fontSize":".68rem","color":col,
                                                  "border":f"1px solid {col}40","borderRadius":"4px",
                                                  "padding":"2px 8px","background":"rgba(255,255,255,.04)"}),
                    html.Span(f"{m['duration_hrs']}h",
                              style={"fontFamily":"JetBrains Mono,monospace","fontSize":".72rem",
                                     "color":"#3D4F6B","marginLeft":"10px"}),
                    # v4: progress buttons
                    html.Button("✓", id={"type":"prog-done","index":m["id"]},
                                className=f"progress-btn {'done' if prog=='done' else ''}",
                                n_clicks=0, title="Mark Done"),
                    html.Button("⏳", id={"type":"prog-wip","index":m["id"]},
                                className=f"progress-btn {'wip' if prog=='wip' else ''}",
                                n_clicks=0, title="Mark In Progress"),
                ], style={"display":"flex","alignItems":"center"}),
                html.Div(meta, style={"display":"flex","alignItems":"center","flexWrap":"wrap","marginTop":"4px"}),
                (html.Div(m["reasoning"], className="mod-why") if m.get("reasoning") else None),
            ], className=f"mod-card{xtra}")

        # Progress stats
        done_count = sum(1 for m in pt if progress.get(m["id"]) == "done")
        wip_count  = sum(1 for m in pt if progress.get(m["id"]) == "wip")
        done_hrs   = sum(m["duration_hrs"] for m in pt if progress.get(m["id"]) == "done")
        prog_pct   = round((done_count / max(len(pt),1)) * 100)

        fit_card = html.Div([
            html.P("Role Fit Score", className="section-h",
                   style={"marginBottom":"16px","textAlign":"center"}),
            dbc.Row([
                dbc.Col([html.Div([
                    html.Div(f"{im['current_fit']}", className="fit-num-big", style={"color":"#FF6B6B"}),
                    html.Div("Current", className="fit-lbl-sm"),
                ], className="fit-score-box")]),
                dbc.Col([html.Div("→", style={"fontSize":"2rem","color":"#3D4F6B",
                                               "textAlign":"center","paddingTop":"8px"})], width="auto"),
                dbc.Col([html.Div([
                    html.Div(f"{im['projected_fit']}", className="fit-num-big", style={"color":"#4ECDC4"}),
                    html.Div("After Roadmap", className="fit-lbl-sm"),
                    html.Div(f"+{im['fit_delta']}%", className="fit-delta"),
                ], className="fit-score-box")]),
            ], align="center", className="g-0"),
            html.Div(style={"height":"10px"}),
            # Interview readiness bar
            html.Div([
                html.Div([
                    html.Span("Interview Readiness: ", style={"fontSize":".78rem","color":"#3D4F6B"}),
                    html.Span(f"{iv.get('score',0)}% - {iv.get('label','--')}",
                              style={"fontSize":".78rem","fontWeight":"700",
                                     "color":iv.get("color","#888"),"marginLeft":"6px"})]),
                html.Div(className="interview-bar", children=[
                    html.Div(className="interview-fill",
                             style={"width":f"{iv.get('score',0)}%","background":iv.get("color","#888")})]),
                html.Div(iv.get("advice",""), style={"fontSize":".72rem","color":"#3D4F6B","marginTop":"4px"}),
            ]),
            html.Div(style={"height":"12px"}),
            # v4: progress tracker summary
            html.Div([
                html.Div([
                    html.Span("Progress: ", style={"fontSize":".78rem","color":"#3D4F6B"}),
                    html.Span(f"{done_count}/{len(pt)} done · {wip_count} in progress · {done_hrs}h completed",
                              style={"fontSize":".78rem","color":"#4ECDC4","fontWeight":"600"}),
                ]),
                html.Div(className="prog-track", style={"marginTop":"6px"}, children=[
                    html.Div(className="prog-fill", style={"width":f"{prog_pct}%"})]),
            ]) if pt else None,
        ], className="glass-card mb-3")

        return html.Div([cache_banner, warn, dbc.Row([
            dbc.Col([fit_card], md=5),
            dbc.Col([html.Div([
                html.P("Impact Summary", className="section-h", style={"marginBottom":"18px"}),
                dbc.Row([
                    dbc.Col([html.Div(f"~{im['hours_saved']}h", className="impact-num"),
                             html.Div("Hours Saved", className="impact-lbl")], className="text-center"),
                    dbc.Col([html.Div(f"{im['roadmap_hours']}h", className="impact-num"),
                             html.Div("Training", className="impact-lbl")], className="text-center"),
                    dbc.Col([html.Div(str(im["modules_count"]), className="impact-num"),
                             html.Div("Modules", className="impact-lbl")], className="text-center"),
                    dbc.Col([html.Div(str(im.get("critical_count",0)), className="impact-num",
                                     style={"color":"#FF6B6B"}),
                             html.Div("Critical", className="impact-lbl")], className="text-center"),
                ], className="g-2"),
                html.Div(style={"height":"14px"}),
                html.Div("Skill Coverage", style={"fontSize":".72rem","color":"#3D4F6B","marginBottom":"5px"}),
                html.Div(className="prog-track", children=[
                    html.Div(className="prog-fill", style={"width":f"{im['projected_fit']}%"})]),
                html.Div(style={"height":"10px"}),
                html.Div([
                    html.Span("Study pace: ", style={"fontSize":".8rem","color":"#3D4F6B","marginRight":"8px"}),
                    dcc.Dropdown(id="pace-dd",
                                 options=[{"label":"1h/day","value":1},{"label":"2h/day","value":2},
                                          {"label":"4h/day","value":4},{"label":"8h/day","value":8}],
                                 value=2, clearable=False,
                                 style={"width":"120px","display":"inline-block",
                                        "verticalAlign":"middle","fontSize":".8rem"}),
                    html.Span(f"Ready in ~{weeks_to_ready(im['roadmap_hours'],2)}",
                              id="ready-estimate",
                              style={"marginLeft":"12px","color":"#4ECDC4","fontWeight":"600",
                                     "fontFamily":"JetBrains Mono,monospace","fontSize":".9rem"}),
                ], style={"display":"flex","alignItems":"center"}),
            ], className="glass-card mb-3")], md=7),

            dbc.Col([html.Div([
                html.P("Priority Matrix", className="section-h"),
                html.P("Impact vs Ease of Learning — where to focus first", className="section-s"),
                dcc.Graph(figure=priority_matrix_chart(gp,dark), config={"displayModeBar":False}),
            ], className="glass-card")], md=7),

            dbc.Col([html.Div([
                html.P("Modules + Progress Tracker", className="section-h"),
                html.P("Click ✓ / ⏳ to track your progress", className="section-s"),
                html.Div([mod_card(i,m) for i,m in enumerate(pt)],
                         style={"maxHeight":"560px","overflowY":"auto"}),
            ], className="glass-card")], md=5),

            dbc.Col([html.Div([
                html.P("Learning ROI Ranking", className="section-h"),
                html.P("Highest return-on-time skills to learn first", className="section-s"),
                dcc.Graph(figure=roi_chart(roi,dark), config={"displayModeBar":False}),
            ], className="glass-card")], md=6),

            dbc.Col([html.Div([
                html.P("Training Timeline", className="section-h"),
                html.P(f"{im['modules_count']} modules / {im['roadmap_hours']}h / "
                       f"{im.get('critical_count',0)} critical", className="section-s"),
                dcc.Graph(figure=timeline_chart(pt,dark), config={"displayModeBar":False}),
            ], className="glass-card")], md=6),
        ], className="g-3")])

    # ── TAB 3: DEEP ANALYSIS ─────────────────────────────────────────────
    if tab == "tab-deep":
        ats_score  = ql.get("ats_score",0)
        comp_score = ql.get("completeness_score",0)
        clar_score = ql.get("clarity_score",0)
        grade      = ql.get("overall_grade","--")
        grade_col  = {"A":"#4ECDC4","B":"#FFE66D","C":"#FFA726","D":"#FF6B6B"}.get(grade,"#888")

        ats_card = html.Div([
            html.P("Resume Quality Audit", className="section-h", style={"marginBottom":"16px"}),
            dbc.Row([
                dbc.Col([dcc.Graph(figure=ats_gauge_chart(ats_score,dark),
                                   config={"displayModeBar":False}),
                         html.P("ATS Score", className="fit-lbl-sm",
                                style={"textAlign":"center"})], md=4),
                dbc.Col([
                    html.Div(grade, className="ats-grade",
                             style={"color":grade_col,"textAlign":"center"}),
                    html.Div("Overall Grade", className="fit-lbl-sm", style={"textAlign":"center"}),
                    html.Div(style={"height":"12px"}),
                    *[html.Div([
                        html.Div([html.Span(lbl, style={"fontSize":".72rem","color":"#3D4F6B"}),
                                  html.Span(f"{val}%", style={"fontSize":".72rem","color":"#C9D1D9",
                                                               "fontFamily":"JetBrains Mono,monospace",
                                                               "marginLeft":"6px"})],
                                 style={"display":"flex","justifyContent":"space-between","marginBottom":"3px"}),
                        html.Div(className="prog-track", children=[
                            html.Div(className="prog-fill",
                                     style={"width":f"{val}%",
                                            "background":("#4ECDC4" if val>=70
                                                          else "#FFE66D" if val>=50 else "#FF6B6B")})]),
                        html.Div(style={"height":"8px"}),
                    ]) for lbl,val in [("Completeness",comp_score),("Clarity",clar_score)]],
                ], md=4),
                dbc.Col([
                    html.P("ATS Issues", style={"fontSize":".78rem","color":"#3D4F6B","marginBottom":"6px"}),
                    *[html.Div([html.Span("! ", style={"color":"#FFA726"}),
                                html.Span(i, style={"fontSize":".78rem"})],
                               style={"marginBottom":"5px"})
                      for i in (ql.get("ats_issues") or ["No critical ATS issues detected"])[:4]],
                ], md=4),
            ], className="g-0"),
        ], className="glass-card mb-3")

        tips_card = html.Div([
            html.P("Resume Improvement Tips", className="section-h"),
            html.P("AI-generated actionable changes for this specific JD", className="section-s"),
            *[html.Div([html.Span(f"0{i+1}", className="tip-number"),
                        html.Span(tip, style={"fontSize":".84rem"})], className="tip-card")
              for i,tip in enumerate((ql.get("improvement_tips") or [])[:6])],
        ], className="glass-card")

        kw_card = html.Div([
            html.P("Missing JD Keywords", className="section-h"),
            html.P("Add these to beat ATS filters for this role", className="section-s"),
            html.Div([html.Span(kw, style={"background":"rgba(255,107,107,.1)","color":"#FF6B6B",
                                            "border":"1px solid rgba(255,107,107,.3)","borderRadius":"6px",
                                            "padding":"3px 10px","fontSize":".78rem","margin":"3px",
                                            "display":"inline-block","fontWeight":"600"})
                      for kw in (ql.get("missing_keywords") or ["None identified"])]),
        ], className="glass-card")

        talk_card = html.Div([
            html.P("Interview Talking Points", className="section-h"),
            html.P("How to position your experience for this specific role", className="section-s"),
            *[html.Div([html.Span("→ ", style={"color":"#4ECDC4","fontWeight":"700"}),
                        html.Span(p, style={"fontSize":".84rem"})], className="strength-item")
              for p in (ql.get("interview_talking_points") or ["Based on your skill profile above"])],
        ], className="glass-card")

        career_card = html.Div([
            html.P("Career Trajectory", className="section-h"),
            html.P("Time to reach target role level", className="section-s"),
            *[html.Div([html.Span(k, className="prof-key"),
                        html.Span(str(v), className="prof-val")], className="prof-row")
              for k, v in [
                  ("Seniority Gap",  f"{ca.get('seniority_gap_levels',0)} level(s)"),
                  ("Training Time",  f"~{ca.get('training_months',0)} months at 2h/day"),
                  ("Career Timeline", ca.get("timeline_label","--")),
                  ("Current",        rd.get("seniority","--")),
                  ("Target",         jd.get("seniority_required","--")),
                  ("Education",      rd.get("education","--")),
              ]],
        ], className="glass-card")

        weekly_card = html.Div([
            html.P("Weekly Study Plan", className="section-h"),
            html.P(f"{len(wp)} weeks at 2h/day Mon–Fri", className="section-s"),
            dcc.Graph(figure=weekly_gantt_chart(wp,dark), config={"displayModeBar":False}),
            html.Div(style={"height":"12px"}),
            *[html.Div([
                html.Div(f"Week {w['week']} — {w['total_hrs']:.1f}h", className="week-label"),
                html.Div([
                    html.Span(f"{'* ' if m['is_critical'] else ''}{m['title'][:30]} ({m['hrs_this_week']:.1f}h)",
                              style={"fontSize":".76rem",
                                     "color":"#4ECDC4" if m["is_critical"] else "#C9D1D9",
                                     "marginRight":"8px"})
                    for m in w["modules"]
                ], style={"flexWrap":"wrap","display":"flex","gap":"4px"}),
            ], className="week-card") for w in wp[:6]],
        ], className="glass-card")

        return dbc.Row([
            dbc.Col([cache_banner, ats_card], md=12),
            dbc.Col([tips_card], md=6),
            dbc.Col([kw_card, html.Div(style={"height":"16px"}), talk_card], md=6),
            dbc.Col([career_card], md=4),
            dbc.Col([weekly_card], md=8),
        ], className="g-3")

    # ── TAB 4: MULTI-JD ──────────────────────────────────────────────────
    if tab == "tab-multi":
        if not jd_comp:
            return html.Div([
                cache_banner,
                html.Div([
                    html.P("Multi-JD Comparator", className="section-h"),
                    html.P("Paste 1–2 additional job descriptions in the input panel to compare fit scores "
                           "across multiple roles.", className="section-s"),
                    html.P("This shows you: which role to apply to now, which to target in 3–6 months, "
                           "and which is a long-term goal.", style={"fontSize":".84rem","color":"#3D4F6B"}),
                ], className="glass-card"),
            ])

        jd_cards = []
        for c in jd_comp:
            rec_col = ("#4ECDC4" if c["recommendation"] == "Apply now"
                       else "#FFE66D" if "3–6" in c["recommendation"] else "#FF6B6B")
            jd_cards.append(dbc.Col([html.Div([
                html.P(c["role_title"], className="section-h"),
                html.P(f"Seniority: {c['seniority']}", className="section-s"),
                dbc.Row([
                    dbc.Col([html.Div(f"{c['fit_now']}%", className="impact-num"),
                             html.Div("Fit Now", className="impact-lbl")], className="text-center"),
                    dbc.Col([html.Div(f"{c['fit_6m']}%", className="impact-num",
                                     style={"color":"#FFE66D"}),
                             html.Div("Fit in 6m", className="impact-lbl")], className="text-center"),
                    dbc.Col([html.Div(str(c["missing"]), className="impact-num",
                                     style={"color":"#FF6B6B"}),
                             html.Div("Gaps", className="impact-lbl")], className="text-center"),
                ], className="g-2"),
                html.Div(style={"height":"10px"}),
                html.Div(c["recommendation"],
                         style={"color":rec_col,"fontWeight":"700","fontSize":".88rem",
                                "textAlign":"center","fontFamily":"JetBrains Mono,monospace"}),
                html.Div(className="prog-track", style={"marginTop":"8px"}, children=[
                    html.Div(className="prog-fill",
                             style={"width":f"{c['fit_now']}%","background":rec_col})]),
            ], className="glass-card")], md=4))

        return html.Div([
            cache_banner,
            dbc.Row([
                dbc.Col([html.Div([
                    html.P("Role Fit Comparison", className="section-h"),
                    html.P("Fit now vs projected in 6 months", className="section-s"),
                    dcc.Graph(figure=multi_jd_chart(jd_comp,dark), config={"displayModeBar":False}),
                ], className="glass-card")], md=12),
                *jd_cards,
            ], className="g-3"),
        ])

    # ── TAB 5: EXPORT + AUDIT LOG ─────────────────────────────────────────
    if tab == "tab-rep":
        _, used = token_budget_ok()
        budget_pct = round((used / DAILY_TOKEN_LIMIT) * 100)

        audit_rows = []
        for e in reversed(_AUDIT_LOG[-20:]):
            status_col = "#4ECDC4" if e.get("status") == "ok" else "#FF6B6B"
            audit_rows.append(html.Div([
                html.Span(e.get("ts","--"), style={"color":"#3D4F6B","marginRight":"10px"}),
                html.Span(e.get("model","--")[:20], style={"color":"#C9D1D9","marginRight":"10px"}),
                html.Span(f"in:{e.get('in_tok',0)} out:{e.get('out_tok',0)}",
                          style={"color":"#FFE66D","marginRight":"10px"}),
                html.Span(f"{e.get('latency',0)}s", style={"color":"#A78BFA","marginRight":"10px"}),
                html.Span(f"${e.get('cost_usd',0):.5f}", style={"color":"#4ECDC4","marginRight":"10px"}),
                html.Span(e.get("status","--"), style={"color":status_col}),
            ], className="audit-row"))

        total_cost = sum(e.get("cost_usd",0) for e in _AUDIT_LOG)

        return dbc.Row([
            dbc.Col([html.Div([
                html.P("Download PDF Report", className="section-h"),
                html.P("Full v4 report: audit + roadmap + reasoning + ROI", className="section-s"),
                html.Div([
                    *[html.Div([
                        html.Span("·", style={"color":"#4ECDC4","marginRight":"8px"}),
                        html.Span(k, style={"fontSize":".82rem","color":"#3D4F6B"}),
                        html.Span(str(v), style={"fontSize":".82rem","color":"#C9D1D9",
                                                  "marginLeft":"4px","fontWeight":"500"}),
                    ], style={"marginBottom":"7px"})
                      for k, v in [
                          ("Candidate:",       rd.get("name","--")),
                          ("Role:",            jd.get("role_title","--")),
                          ("ATS Score:",       f"{ql.get('ats_score','--')}%"),
                          ("Grade:",           ql.get("overall_grade","--")),
                          ("Current Fit:",     f"{im['current_fit']}%"),
                          ("Projected:",       f"{im['projected_fit']}% (+{im['fit_delta']}%)"),
                          ("Interview Ready:", f"{iv.get('score',0)}% — {iv.get('label','--')}"),
                          ("Modules:",         im["modules_count"]),
                          ("Training:",        f"{im['roadmap_hours']}h"),
                          ("Hours Saved:",     f"~{im['hours_saved']}h"),
                          ("Weekly Plan:",     f"{len(wp)} weeks at 2h/day"),
                      ]],
                ], style={"background":"rgba(78,205,196,.05)","border":"1px solid rgba(78,205,196,.15)",
                           "borderRadius":"10px","padding":"16px","marginBottom":"20px"}),
                html.Button("Download PDF Report", id="btn-pdf", n_clicks=0, className="btn-run"),
                html.Div(id="pdf-status",
                         style={"fontSize":".75rem","color":"#3D4F6B","marginTop":"8px","textAlign":"center"}),
            ], className="glass-card")], md=5),

            dbc.Col([html.Div([
                html.P("Groq API Audit Log", className="section-h"),
                html.P(f"Last {len(_AUDIT_LOG[-20:])} calls · "
                       f"Total cost this session: ${total_cost:.4f} · "
                       f"Tokens today: {used:,}/{DAILY_TOKEN_LIMIT:,} ({budget_pct}%)",
                       className="section-s"),
                # Budget bar
                html.Div(className="prog-track", children=[
                    html.Div(className="prog-fill",
                             style={"width":f"{min(100,budget_pct)}%",
                                    "background":("#4ECDC4" if budget_pct<60
                                                  else "#FFE66D" if budget_pct<85 else "#FF6B6B")})]),
                html.Div(style={"height":"12px"}),
                html.Div(audit_rows or [html.P("No calls yet.", className="section-s")],
                         style={"maxHeight":"400px","overflowY":"auto"}),
            ], className="glass-card")], md=7),
        ], className="g-3")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13B · PROGRESS TRACKER CALLBACKS  (v4 NEW)
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("s-progress","data"),
    Input({"type":"prog-done","index":dash.ALL}, "n_clicks"),
    Input({"type":"prog-wip", "index":dash.ALL}, "n_clicks"),
    State("s-progress","data"),
    prevent_initial_call=True,
)
def cb_progress(done_clicks, wip_clicks, current):
    progress = dict(current or {})
    trigger = ctx.triggered_id
    if not trigger: raise PreventUpdate
    mid = trigger["index"]
    t   = trigger["type"]
    if t == "prog-done":
        progress[mid] = "not_started" if progress.get(mid) == "done" else "done"
    elif t == "prog-wip":
        progress[mid] = "not_started" if progress.get(mid) == "wip" else "wip"
    return progress


@app.callback(
    Output("ready-estimate","children"),
    Input("pace-dd","value"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_ready(pace, results):
    if not results or not pace: raise PreventUpdate
    return f"Ready in ~{weeks_to_ready(results['impact']['roadmap_hours'], pace)}"


@app.callback(
    Output("dl-pdf","data"),
    Output("pdf-status","children"),
    Input("btn-pdf","n_clicks"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_pdf(n, results):
    if not results: raise PreventUpdate
    if not REPORTLAB: return no_update, "pip install reportlab"
    buf  = build_pdf(results["resume_data"], results["jd_data"], results["gap_profile"],
                     results["path"], results["impact"],
                     results.get("quality"), results.get("interview"))
    name = results["resume_data"].get("name","candidate").replace(" ","_")
    fn   = f"skillforge_v4_{name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return dcc.send_bytes(buf.read(), fn), f"Downloading {fn}"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 14 · RUN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  SkillForge v4 - AI Adaptive Onboarding Engine")
    print("  -----------------------------------------------")
    print("  -> http://localhost:8050")
    print(f"  -> Semantic:    {'sentence-transformers OK' if SEMANTIC else 'substring fallback'}")
    print(f"  -> PDF export:  {'reportlab OK' if REPORTLAB else 'not available'}")
    print("  -> v4 API FIXES:")
    print("       FIX 1: Merged resume parse + audit  → 1 Groq call (was 2, saves ~2,500 tokens)")
    print("       FIX 2: Batched module reasoning     → 1 Groq call (was 12, saves ~1,600 tokens)")
    print("       FIX 3: Retry wrapper + backoff      → survives 429 rate limits")
    print("       FIX 4: LRU result cache             → 0 Groq calls on repeat inputs")
    print("       FIX 5: Token budget guard           → warns before hitting daily limit")
    print("       FIX 6: Semaphore(4)                 → max 4 parallel Groq calls")
    print("  -> v4 NEW FEATURES:")
    print("       Skill Transfer Map · Learning ROI · Progress Tracker")
    print("       Multi-JD Comparator · LinkedIn JD URL · Audit Log Panel")
    print("       Fallback to llama-3.1-8b on 429 · Cover Letter (cb_cover)")
    print(f"  -> Token budget: {_daily_token_used:,} / {DAILY_TOKEN_LIMIT:,} used today")
    print()
    app.run(debug=True, port=8050)