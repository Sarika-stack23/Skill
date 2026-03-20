# =============================================================================
#  main.py — AI-Adaptive Onboarding Engine  ·  SkillForge  v2
#  Stack : Plotly Dash · Groq LLaMA 3.3 · NetworkX · ReportLab
#  Run   : python main.py          (needs GROQ_API_KEY in .env)
#
#  NEW FEATURES v2:
#   1. Dark / Light mode toggle in nav bar
#   2. Skill Decay Model — skills get rusty over time
#   3. Role Fit Score — before vs after delta (like a credit score)
#   4. Seniority Mismatch Warning — auto-adds leadership modules
#   5. "Ready in X weeks" estimator — hours/day dropdown
#   6. Critical Path Highlighting — most important modules in red
#   7. Domain Color Badges — Tech / Non-Tech / Soft pills on every card
#   8. One-Click Sample Inputs — 3 preset demo scenarios
# =============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 · IMPORTS & CONFIG
# ──────────────────────────────────────────────────────────────────────────────
import os, json, base64, io, re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise SystemExit(
        "\n  ERROR: GROQ_API_KEY is missing.\n"
        "  Add it to your .env file:\n"
        "    GROQ_API_KEY=gsk_...\n"
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
    print("  → Loading sentence-transformers model…")
    _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    SEMANTIC = True
except Exception:
    SEMANTIC = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    REPORTLAB = True
except Exception:
    REPORTLAB = False

GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 · COURSE CATALOG
# ──────────────────────────────────────────────────────────────────────────────
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

CATALOG_BY_ID  = {c["id"]: c for c in CATALOG}
CATALOG_SKILLS = [c["skill"].lower() for c in CATALOG]

_bad_prereqs = [(c["id"], p) for c in CATALOG for p in c["prereqs"] if p not in CATALOG_BY_ID]
if _bad_prereqs:
    raise SystemExit(f"CATALOG ERROR — broken prereq references: {_bad_prereqs}")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2B · SAMPLE INPUTS  (Feature 8)
# ──────────────────────────────────────────────────────────────────────────────
SAMPLES = {
    "junior_swe": {
        "label": "Junior SWE",
        "resume": """John Smith
Junior Software Developer | 1 year experience
Skills: Python (basic), HTML/CSS, some JavaScript
Education: B.Tech Computer Science 2023
Projects: Built a simple todo app using Flask. Familiar with Git basics.
No professional cloud or DevOps experience.""",
        "jd": """Software Engineer Full Stack
We are looking for a Mid-level Software Engineer.
Required Skills: Python, React, FastAPI, Docker, SQL, REST APIs, AWS
Preferred Skills: Kubernetes, CI/CD, TypeScript
Seniority: Mid | Domain: Tech"""
    },
    "senior_ds": {
        "label": "Senior Data Scientist",
        "resume": """Priya Patel
Senior Data Scientist | 7 years experience
Skills: Python (expert, used daily), Machine Learning (expert), Deep Learning (PyTorch),
SQL (advanced), Data Analysis (Pandas, NumPy), Statistics (PhD level),
Data Visualization (Matplotlib, Seaborn, Plotly), AWS (SageMaker)
Last used NLP: 2022. Last used MLOps: 2021 (basic exposure only).
Led team of 5 data scientists. Published 3 ML papers.""",
        "jd": """Lead Data Scientist AI Products
Required Skills: Python, Machine Learning, Deep Learning, NLP, MLOps, SQL, AWS
Preferred Skills: GCP, Kubernetes, Leadership, Strategic Planning
Seniority: Lead | Domain: Tech
We need someone to own the full ML lifecycle from research to production."""
    },
    "hr_manager": {
        "label": "HR Manager",
        "resume": """Amara Johnson
HR Coordinator | 3 years experience
Skills: Human Resources (intermediate), Recruitment (good), Microsoft Office
Some experience with performance reviews but no formal training.
No experience with L&D strategy, budgeting, or employee relations handling.
Domain: Non-Tech""",
        "jd": """HR Manager People and Culture
Required Skills: Human Resources, Recruitment, Performance Management, Employee Relations
Preferred Skills: L&D Strategy, Budgeting, Communication, Leadership, Project Management
Seniority: Senior | Domain: Non-Tech
You will lead a team of 3 HR coordinators and own the full employee lifecycle."""
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 · SKILL DEPENDENCY GRAPH
# ──────────────────────────────────────────────────────────────────────────────
def _build_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    for c in CATALOG:
        G.add_node(c["id"], **c)
        for p in c["prereqs"]:
            G.add_edge(p, c["id"])
    return G

SKILL_GRAPH = _build_graph()


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 · UTILITIES
# ──────────────────────────────────────────────────────────────────────────────
def _pdf_text(raw: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        return f"[PDF error: {e}]"

def _docx_text(raw: bytes) -> str:
    try:
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return f"[DOCX error: {e}]"

def parse_upload(contents: str, filename: str) -> str:
    if not contents:
        return ""
    _, b64 = contents.split(",", 1)
    raw = base64.b64decode(b64)
    if filename.lower().endswith(".pdf"):
        return _pdf_text(raw)
    if filename.lower().endswith(".docx"):
        return _docx_text(raw)
    return raw.decode("utf-8", errors="ignore")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 · GROQ API
# ──────────────────────────────────────────────────────────────────────────────
def _groq(prompt: str, system: str = "You are an expert HR analyst. Always respond with valid JSON only, no markdown fences.") -> dict:
    import time
    def _call():
        r = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system},
                      {"role": "user",   "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
        )
        raw = r.choices[0].message.content.strip()
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        return json.loads(raw)
    try:
        return _call()
    except json.JSONDecodeError:
        return {"error": "JSON parse failed"}
    except Exception as e:
        # Auto-retry once on Groq rate limit (429)
        if "429" in str(e) or "rate_limit" in str(e):
            time.sleep(4)
            try:
                return _call()
            except json.JSONDecodeError:
                return {"error": "JSON parse failed after retry"}
            except Exception as e2:
                return {"error": str(e2)}
        return {"error": str(e)}


def parse_resume(text: str) -> dict:
    prompt = f"""Extract structured data from this resume. Return ONLY valid JSON:
{{
  "name": "<full name or Unknown>",
  "current_role": "<latest job title>",
  "years_experience": <integer>,
  "seniority": "<Junior|Mid|Senior|Lead>",
  "domain": "<Tech|Non-Tech|Hybrid>",
  "skills": [
    {{"skill": "<name>", "proficiency": <0-10>, "year_last_used": <year as integer or 0 if unknown>, "context": "<one-line evidence>"}}
  ]
}}

Resume (first 3000 chars):
{text[:3000]}"""
    return _groq(prompt)


def parse_jd(text: str) -> dict:
    prompt = f"""Extract structured data from this job description. Return ONLY valid JSON:
{{
  "role_title": "<title>",
  "seniority_required": "<Junior|Mid|Senior|Lead>",
  "domain": "<Tech|Non-Tech|Hybrid>",
  "required_skills": ["<skill1>", "<skill2>"],
  "preferred_skills": ["<skill3>"]
}}

JD (first 3000 chars):
{text[:3000]}"""
    return _groq(prompt)


def generate_reasoning(module: dict, gap_skill: str, candidate_name: str) -> str:
    prompt = f"""Write a 2-sentence reasoning trace explaining why {candidate_name} needs this training module.
Module: {module['title']}
Skill addressed: {module['skill']}
Identified gap: {gap_skill}
Return ONLY valid JSON: {{"reasoning": "<2 sentences>"}}"""
    res = _groq(prompt, system="You are an L&D expert. Respond with JSON only.")
    return res.get("reasoning", f"Addresses the identified gap in {gap_skill}, critical for the target role.")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6 · SEMANTIC SKILL MATCHING
# ──────────────────────────────────────────────────────────────────────────────
if SEMANTIC:
    print("  → Pre-computing catalog embeddings…")
    _CATALOG_EMBS = _ST_MODEL.encode(CATALOG_SKILLS)
else:
    _CATALOG_EMBS = None


def _semantic_match(skill: str, threshold: float = 0.52) -> tuple[int, float]:
    sl = (skill.lower()
          .replace(".js","").replace(".py","").replace(".ts","")
          .replace("(","").replace(")","").strip())
    for i, cs in enumerate(CATALOG_SKILLS):
        if sl == cs or sl in cs or cs in sl:
            return i, 1.0
    if SEMANTIC and _CATALOG_EMBS is not None:
        emb_q = _ST_MODEL.encode([sl])
        sims  = cosine_similarity(emb_q, _CATALOG_EMBS)[0]
        best  = int(np.argmax(sims))
        if sims[best] >= threshold:
            return best, float(sims[best])
    tokens = set(sl.split())
    best_score, best_idx = 0.0, -1
    for i, cs in enumerate(CATALOG_SKILLS):
        overlap = len(tokens & set(cs.split())) / max(len(tokens), 1)
        if overlap > best_score:
            best_score, best_idx = overlap, i
    return (best_idx, best_score) if best_score >= 0.4 else (-1, 0.0)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6B · SKILL DECAY MODEL  (Feature 2)
# ──────────────────────────────────────────────────────────────────────────────
CURRENT_YEAR = datetime.now().year

def apply_skill_decay(proficiency: int, year_last_used: int) -> tuple[int, bool]:
    """
    Skills get rusty. If not used in >2 years, reduce proficiency.
    decay_factor = max(0.5, 1 - (years_since / 5))
    A skill unused for 3 years drops to 80%, 5 years drops to 50%.
    """
    if year_last_used <= 0 or year_last_used >= CURRENT_YEAR - 1:
        return proficiency, False
    years_since = CURRENT_YEAR - year_last_used
    if years_since <= 2:
        return proficiency, False
    decay_factor = max(0.5, 1 - (years_since / 5))
    adjusted = round(proficiency * decay_factor)
    return adjusted, adjusted < proficiency


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7 · GAP ANALYZER
# ──────────────────────────────────────────────────────────────────────────────
def analyze_gap(resume_data: dict, jd_data: dict) -> list[dict]:
    resume_skills = {s["skill"].lower(): s for s in resume_data.get("skills", [])}
    required  = jd_data.get("required_skills", [])
    preferred = jd_data.get("preferred_skills", [])
    all_skills = [(s, True) for s in required] + [(s, False) for s in preferred]

    gap_profile = []
    for skill, is_required in all_skills:
        sl = (skill.lower()
              .replace(".js","").replace(".py","").replace(".ts","")
              .replace("(","").replace(")","").strip())
        status, proficiency, context, decayed, original_prof = "Missing", 0, "", False, 0

        if sl in resume_skills:
            d = resume_skills[sl]
            raw_prof  = d.get("proficiency", 0)
            yr_used   = d.get("year_last_used", 0)
            proficiency, decayed = apply_skill_decay(raw_prof, yr_used)
            original_prof = raw_prof
            context   = d.get("context", "")
            status    = "Known" if proficiency >= 7 else "Partial"
        else:
            for rk, rd in resume_skills.items():
                if sl in rk or rk in sl:
                    raw_prof  = rd.get("proficiency", 0)
                    yr_used   = rd.get("year_last_used", 0)
                    proficiency, decayed = apply_skill_decay(raw_prof, yr_used)
                    original_prof = raw_prof
                    context   = rd.get("context", "")
                    status    = "Known" if proficiency >= 7 else "Partial"
                    break

        idx, sim = _semantic_match(skill)
        catalog_course = CATALOG[idx] if idx >= 0 else None

        gap_profile.append({
            "skill":         skill,
            "status":        status,
            "proficiency":   proficiency,
            "original_prof": original_prof,
            "decayed":       decayed,
            "is_required":   is_required,
            "context":       context,
            "catalog_course":catalog_course,
            "similarity":    sim,
        })
    return gap_profile


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7B · SENIORITY MISMATCH  (Feature 4)
# ──────────────────────────────────────────────────────────────────────────────
SENIORITY_MAP = {"Junior": 0, "Mid": 1, "Senior": 2, "Lead": 3}

def check_seniority_mismatch(resume_data: dict, jd_data: dict) -> dict:
    cand_s = resume_data.get("seniority", "Mid")
    req_s  = jd_data.get("seniority_required", "Mid")
    cand_l = SENIORITY_MAP.get(cand_s, 1)
    req_l  = SENIORITY_MAP.get(req_s, 1)
    gap    = req_l - cand_l
    return {
        "has_mismatch":   gap > 0,
        "gap_levels":     gap,
        "candidate":      cand_s,
        "required":       req_s,
        "add_leadership": gap >= 1,
        "add_strategic":  gap >= 2,
    }


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 8 · ADAPTIVE PATH GENERATOR  (with critical path, Feature 6)
# ──────────────────────────────────────────────────────────────────────────────
def generate_path(gap_profile: list[dict], resume_data: dict, jd_data: dict = None) -> list[dict]:
    modules_needed: set[str]   = set()
    id_to_gap: dict[str, dict] = {}

    for gap in gap_profile:
        if gap["status"] == "Known":
            continue
        course = gap.get("catalog_course")
        if not course:
            continue
        cid = course["id"]
        modules_needed.add(cid)
        id_to_gap[cid] = gap
        try:
            for anc in nx.ancestors(SKILL_GRAPH, cid):
                anc_data = CATALOG_BY_ID.get(anc)
                if not anc_data:
                    continue
                anc_skill = anc_data["skill"].lower()
                already_known = any(
                    g["status"] == "Known" and g["skill"].lower() in anc_skill
                    for g in gap_profile
                )
                if not already_known:
                    modules_needed.add(anc)
        except Exception:
            pass

    # Feature 4: Auto-inject leadership modules on seniority mismatch
    if jd_data:
        sm = check_seniority_mismatch(resume_data, jd_data)
        if sm["add_leadership"]:
            modules_needed.update(["LD01", "LD02"])
        if sm["add_strategic"]:
            modules_needed.add("LD03")

    sub = SKILL_GRAPH.subgraph(modules_needed)
    try:
        ordered = list(nx.topological_sort(sub))
    except nx.NetworkXUnfeasible:
        ordered = list(modules_needed)

    # Feature 6: Find critical path (longest dependency chain)
    critical_ids = set()
    try:
        if len(sub.nodes) > 0:
            critical_ids = set(nx.dag_longest_path(sub))
    except Exception:
        pass

    path = []
    seen = set()
    for cid in ordered:
        if cid in seen:
            continue
        seen.add(cid)
        course = CATALOG_BY_ID.get(cid)
        if not course:
            continue
        gap      = id_to_gap.get(cid, {})
        priority = (0 if gap.get("is_required") else 1, gap.get("proficiency", 0))
        path.append({
            **course,
            "gap_skill":   gap.get("skill", course["skill"]),
            "gap_status":  gap.get("status", "Prereq"),
            "priority":    priority,
            "reasoning":   "",
            "is_critical": cid in critical_ids,
        })

    path.sort(key=lambda x: x["priority"])
    return path


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9 · IMPACT SCORER  (with Role Fit Score delta, Feature 3)
# ──────────────────────────────────────────────────────────────────────────────
STANDARD_ONBOARDING_HRS = 60

def calculate_impact(gap_profile: list[dict], path: list[dict]) -> dict:
    total   = len(gap_profile)
    known   = sum(1 for g in gap_profile if g["status"] == "Known")
    partial = sum(1 for g in gap_profile if g["status"] == "Partial")
    covered = len({m["gap_skill"] for m in path})
    decayed_count = sum(1 for g in gap_profile if g.get("decayed"))

    roadmap_hrs   = sum(m["duration_hrs"] for m in path)
    hours_saved   = max(0, STANDARD_ONBOARDING_HRS - roadmap_hrs)
    current_fit   = min(100, round((known / max(total, 1)) * 100))
    projected_fit = min(100, round(((known + covered) / max(total, 1)) * 100))

    return {
        "total_skills":       total,
        "known_skills":       known,
        "partial_skills":     partial,
        "gaps_addressed":     covered,
        "roadmap_hours":      roadmap_hrs,
        "hours_saved":        hours_saved,
        "role_readiness_pct": projected_fit,
        "current_fit":        current_fit,
        "projected_fit":      projected_fit,
        "fit_delta":          projected_fit - current_fit,
        "modules_count":      len(path),
        "decayed_skills":     decayed_count,
        "critical_count":     sum(1 for m in path if m.get("is_critical")),
    }


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9B · READINESS ESTIMATOR  (Feature 5)
# ──────────────────────────────────────────────────────────────────────────────
def weeks_to_ready(roadmap_hours: int, hours_per_day: float) -> str:
    if hours_per_day <= 0:
        return "—"
    days  = roadmap_hours / hours_per_day
    weeks = days / 5
    if weeks < 1:
        return f"{int(days)} days"
    elif weeks < 4:
        return f"{weeks:.1f} weeks"
    else:
        return f"{(weeks/4):.1f} months"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 10 · CHARTS
# ──────────────────────────────────────────────────────────────────────────────
_DARK_BG    = "rgba(0,0,0,0)"
_FONT_DARK  = dict(color="#C9D1D9", family="'Space Grotesk', sans-serif")
_FONT_LIGHT = dict(color="#1A202C", family="'Space Grotesk', sans-serif")


def radar_chart(gap_profile: list[dict], dark_mode: bool = True) -> go.Figure:
    items  = gap_profile[:10]
    if not items:
        return go.Figure()
    theta      = [g["skill"][:18] for g in items]
    resume     = [g["proficiency"] for g in items]
    jd_req     = [10] * len(items)
    pre_decay  = [g.get("original_prof", g["proficiency"]) for g in items]
    grid = "#1E2A3A" if dark_mode else "#E2E8F0"
    font = _FONT_DARK if dark_mode else _FONT_LIGHT
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=jd_req,    theta=theta, fill="toself",
                                  name="JD Requirement",    line=dict(color="#FF6B6B", width=2), opacity=0.25))
    fig.add_trace(go.Scatterpolar(r=pre_decay, theta=theta, fill="toself",
                                  name="Before decay",      line=dict(color="#FFE66D", width=1, dash="dot"), opacity=0.18))
    fig.add_trace(go.Scatterpolar(r=resume,    theta=theta, fill="toself",
                                  name="Skills (adjusted)", line=dict(color="#4ECDC4", width=2), opacity=0.75))
    fig.update_layout(
        polar=dict(
            bgcolor=_DARK_BG,
            radialaxis=dict(visible=True, range=[0,10], gridcolor=grid, color="#555"),
            angularaxis=dict(gridcolor=grid)
        ),
        paper_bgcolor=_DARK_BG, plot_bgcolor=_DARK_BG,
        font=font, showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.78, y=1.18, font=dict(size=10)),
        margin=dict(l=30, r=30, t=40, b=30),
    )
    return fig


def timeline_chart(path: list[dict], dark_mode: bool = True) -> go.Figure:
    if not path:
        return go.Figure()
    font    = _FONT_DARK if dark_mode else _FONT_LIGHT
    plot_bg = "rgba(15,22,36,0.6)" if dark_mode else "rgba(240,245,255,0.8)"
    grid    = "#1E2A3A" if dark_mode else "#E2E8F0"

    def bar_color(m):
        if m.get("is_critical"):
            return "#FF6B6B"
        return {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF9A9A"}.get(m["level"],"#888")

    shown = set()
    fig   = go.Figure()
    for i, m in enumerate(path):
        col     = bar_color(m)
        lvl_key = "Critical Path" if m.get("is_critical") else m["level"]
        show    = lvl_key not in shown
        shown.add(lvl_key)
        label   = f"{'⚡ ' if m.get('is_critical') else ''}#{i+1} {m['title'][:35]}"
        fig.add_trace(go.Bar(
            x=[m["duration_hrs"]], y=[label], orientation="h",
            marker=dict(color=col, opacity=0.88, line=dict(width=0)),
            name=lvl_key, legendgroup=lvl_key, showlegend=show,
            hovertemplate=(f"<b>{m['title']}</b><br>Skill: {m['skill']}<br>"
                           f"Level: {m['level']}<br>Domain: {m['domain']}<br>"
                           f"Duration: {m['duration_hrs']}h"
                           f"{'<br><b>⚡ Critical Path</b>' if m.get('is_critical') else ''}"
                           "<extra></extra>")
        ))
    fig.update_layout(
        paper_bgcolor=_DARK_BG, plot_bgcolor=plot_bg, font=font,
        xaxis=dict(title="Hours", gridcolor=grid, color="#555", zeroline=False),
        yaxis=dict(gridcolor=grid, tickfont=dict(size=10)),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(320, len(path)*44),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.03),
        barmode="overlay",
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 11 · PDF EXPORT
# ──────────────────────────────────────────────────────────────────────────────
def build_pdf(resume_data, jd_data, gap_profile, path, impact) -> io.BytesIO:
    buf = io.BytesIO()
    if not REPORTLAB:
        return buf
    doc    = SimpleDocTemplate(buf, pagesize=letter, topMargin=48, bottomMargin=48,
                                leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    TEAL   = rl_colors.HexColor("#2A9D8F")
    DARK   = rl_colors.HexColor("#1A1A2E")

    H1 = ParagraphStyle("H1", parent=styles["Title"],    fontSize=20, spaceAfter=4,  textColor=TEAL)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceAfter=6,  textColor=DARK, spaceBefore=14)
    BD = ParagraphStyle("BD", parent=styles["Normal"],   fontSize=10, spaceAfter=5)
    IT = ParagraphStyle("IT", parent=styles["Normal"],   fontSize=9,  spaceAfter=4,
                         leftIndent=18, textColor=rl_colors.HexColor("#555555"), italics=True)

    story = [
        Paragraph("SkillForge — Adaptive Onboarding Report v2", H1),
        Paragraph(
            f"Candidate: <b>{resume_data.get('name','—')}</b>   ·   "
            f"Role: <b>{jd_data.get('role_title','—')}</b>   ·   "
            f"Generated: {datetime.now().strftime('%d %b %Y')}", BD),
        Spacer(1, 14),
        Paragraph("Impact Summary", H2),
    ]

    impact_rows = [
        ["Role Fit (Current)",    f"{impact['current_fit']}%"],
        ["Role Fit (Projected)",  f"{impact['projected_fit']}% (+{impact['fit_delta']}%)"],
        ["Skills Addressed",      f"{impact['gaps_addressed']} / {impact['total_skills']}"],
        ["Training Hours",        f"{impact['roadmap_hours']} hrs"],
        ["Hours Saved",           f"~{impact['hours_saved']} hrs vs. standard onboarding"],
        ["Modules",               str(impact["modules_count"])],
        ["Critical Path Modules", str(impact.get("critical_count",0))],
        ["Decay-Adjusted Skills", str(impact.get("decayed_skills",0))],
    ]
    tbl = Table([["Metric","Value"]] + impact_rows, colWidths=[200,260])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), TEAL),
        ("TEXTCOLOR",     (0,0),(-1,0), rl_colors.white),
        ("FONTSIZE",      (0,0),(-1,-1), 10),
        ("GRID",          (0,0),(-1,-1), 0.4, rl_colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [rl_colors.whitesmoke, rl_colors.white]),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
    ]))
    story += [tbl, Spacer(1,18), Paragraph("Personalized Learning Roadmap", H2)]

    for i, m in enumerate(path):
        prefix = "[CRITICAL] " if m.get("is_critical") else ""
        story.append(Paragraph(
            f"<b>{i+1}. {prefix}{m['title']}</b>  —  {m['level']} · {m['duration_hrs']}h · {m['domain']}", BD))
        if m.get("reasoning"):
            story.append(Paragraph(f"↳ {m['reasoning']}", IT))

    story += [Spacer(1,16), Paragraph("Skill Gap Overview", H2)]
    gap_rows = [["Skill","Status","Proficiency","Type","Decayed?"]]
    for g in gap_profile:
        gap_rows.append([g["skill"], g["status"], f"{g['proficiency']}/10",
                         "Required" if g["is_required"] else "Preferred",
                         "Yes" if g.get("decayed") else "No"])
    gt = Table(gap_rows, colWidths=[140,65,75,75,60])
    gt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), DARK),
        ("TEXTCOLOR",     (0,0),(-1,0), rl_colors.white),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("GRID",          (0,0),(-1,-1), 0.3, rl_colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [rl_colors.whitesmoke, rl_colors.white]),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
    ]))
    story.append(gt)
    doc.build(story)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 12 · DASH APP  (layout + CSS)
# ──────────────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&"
        "family=JetBrains+Mono:wght@400;600&display=swap",
    ],
    suppress_callback_exceptions=True,
)
server = app.server

app.index_string = """<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>SkillForge — AI Adaptive Onboarding</title>
  {%favicon%}
  {%css%}
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{background:#070B14;font-family:'Space Grotesk',sans-serif;color:#C9D1D9;min-height:100vh;transition:background .3s,color .3s}

    /* LIGHT MODE */
    body.light-mode{background:#F0F4F8;color:#1A202C}
    body.light-mode .nav-bar{background:rgba(240,244,248,.97);border-bottom-color:#CBD5E0}
    body.light-mode .glass-card{background:#fff;border-color:#E2E8F0}
    body.light-mode .upload-box{background:rgba(78,205,196,.05);border-color:rgba(78,205,196,.3)}
    body.light-mode .logo-sub,.body.light-mode .nav-pill{color:#718096}
    body.light-mode .hero-sub{color:#4A5568}
    body.light-mode .upload-hint,.body.light-mode .section-s,.body.light-mode .mod-meta{color:#718096}
    body.light-mode .impact-lbl{color:#718096}
    body.light-mode .prog-track{background:rgba(0,0,0,.08)}
    body.light-mode .nav-tabs{border-bottom-color:#E2E8F0 !important}
    body.light-mode .nav-tabs .nav-link{color:#718096 !important}
    body.light-mode textarea.form-control{background:#F7FAFC !important;border-color:#E2E8F0 !important;color:#1A202C !important}
    body.light-mode .theme-btn{background:rgba(0,0,0,.07);color:#4A5568;border-color:rgba(0,0,0,.12)}
    body.light-mode .sample-btn{background:#EBF8FF;color:#2B6CB0;border-color:#BEE3F8}
    body.light-mode .warn-banner{background:rgba(255,193,7,.12);border-color:rgba(255,193,7,.4);color:#92400E}
    body.light-mode .mod-meta{color:#718096}
    body.light-mode .section-s{color:#718096}

    /* NAV */
    .nav-bar{background:rgba(7,11,20,.95);border-bottom:1px solid #161D2E;backdrop-filter:blur(12px);position:sticky;top:0;z-index:100;padding:12px 0;transition:background .3s}
    .logo-mark{font-family:'JetBrains Mono',monospace;font-size:1.45rem;font-weight:700;color:#4ECDC4;letter-spacing:-.03em}
    .logo-sub{font-size:.6rem;color:#3D4F6B;letter-spacing:.18em;text-transform:uppercase;margin-top:1px}
    .nav-pill{font-size:.72rem;color:#3D4F6B;background:rgba(78,205,196,.07);border:1px solid rgba(78,205,196,.15);border-radius:99px;padding:3px 10px}

    /* THEME TOGGLE (Feature 1) */
    .theme-btn{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);border-radius:99px;color:#C9D1D9;font-size:.78rem;padding:5px 14px;cursor:pointer;transition:all .2s;font-family:'Space Grotesk',sans-serif}
    .theme-btn:hover{background:rgba(78,205,196,.15);border-color:#4ECDC4;color:#4ECDC4}

    /* SAMPLE BUTTONS (Feature 8) */
    .sample-btn{background:rgba(78,205,196,.08);border:1px solid rgba(78,205,196,.2);border-radius:8px;color:#4ECDC4;font-size:.75rem;padding:6px 14px;cursor:pointer;transition:all .2s;font-family:'Space Grotesk',sans-serif;font-weight:600}
    .sample-btn:hover{background:rgba(78,205,196,.18);transform:translateY(-1px)}

    /* HERO */
    .hero-title{font-size:2.4rem;font-weight:700;line-height:1.15;background:linear-gradient(135deg,#E6EDF3 0%,#4ECDC4 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .hero-sub{color:#6B7A99;font-size:1rem;margin-top:10px;max-width:560px}

    /* CARDS */
    .glass-card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:24px;transition:border-color .2s,box-shadow .2s,background .3s}
    .glass-card:hover{border-color:rgba(78,205,196,.25);box-shadow:0 0 24px rgba(78,205,196,.06)}

    /* UPLOAD */
    .upload-box{border:2px dashed rgba(78,205,196,.25);border-radius:10px;padding:28px 16px;text-align:center;cursor:pointer;transition:all .2s;background:rgba(78,205,196,.03)}
    .upload-box:hover{border-color:#4ECDC4;background:rgba(78,205,196,.07)}
    .upload-icon{font-size:1.6rem;margin-bottom:6px}
    .upload-hint{font-size:.78rem;color:#3D4F6B;margin-top:4px}

    /* BUTTON */
    .btn-run{background:linear-gradient(135deg,#4ECDC4,#44B8B0);border:none;border-radius:10px;color:#070B14;font-weight:700;font-size:.95rem;padding:13px 0;width:100%;font-family:'Space Grotesk',sans-serif;cursor:pointer;transition:all .2s}
    .btn-run:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(78,205,196,.3)}
    .btn-run:active{transform:translateY(0)}

    /* BADGES */
    .badge-known  {background:rgba(78,205,196,.15);color:#4ECDC4;border:1px solid rgba(78,205,196,.4)}
    .badge-partial{background:rgba(255,230,109,.12);color:#FFE66D;border:1px solid rgba(255,230,109,.4)}
    .badge-missing{background:rgba(255,107,107,.12);color:#FF6B6B;border:1px solid rgba(255,107,107,.4)}
    .skill-badge{font-size:.7rem;border-radius:4px;padding:2px 8px;font-weight:600;letter-spacing:.03em}

    /* DOMAIN BADGES (Feature 7) */
    .domain-tech   {font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(78,205,196,.12);color:#4ECDC4;border:1px solid rgba(78,205,196,.3)}
    .domain-nontech{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(255,230,109,.12);color:#FFE66D;border:1px solid rgba(255,230,109,.3)}
    .domain-soft   {font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(167,139,250,.12);color:#A78BFA;border:1px solid rgba(167,139,250,.3)}

    /* DECAY BADGE (Feature 2) */
    .decay-badge{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(255,152,0,.12);color:#FFA726;border:1px solid rgba(255,152,0,.3)}

    /* SENIORITY WARNING (Feature 4) */
    .warn-banner{background:rgba(255,193,7,.08);border:1px solid rgba(255,193,7,.3);border-radius:10px;padding:12px 16px;color:#FFD54F;font-size:.84rem;margin-bottom:16px}

    /* CRITICAL BADGE (Feature 6) */
    .critical-badge{font-size:.65rem;border-radius:99px;padding:1px 8px;font-weight:600;background:rgba(255,107,107,.15);color:#FF6B6B;border:1px solid rgba(255,107,107,.3)}

    /* IMPACT */
    .impact-num{font-family:'JetBrains Mono',monospace;font-size:2.2rem;font-weight:700;color:#4ECDC4;line-height:1}
    .impact-lbl{font-size:.68rem;color:#3D4F6B;text-transform:uppercase;letter-spacing:.06em;margin-top:5px}

    /* ROLE FIT SCORE (Feature 3) */
    .fit-score-box{text-align:center;padding:16px 12px}
    .fit-num-big{font-family:'JetBrains Mono',monospace;font-size:3rem;font-weight:700;line-height:1}
    .fit-delta{font-size:.85rem;color:#4ECDC4;font-weight:600;margin-top:4px}
    .fit-lbl-sm{font-size:.68rem;color:#3D4F6B;text-transform:uppercase;letter-spacing:.06em}

    /* PROGRESS */
    .prog-track{background:rgba(255,255,255,.06);border-radius:99px;height:7px}
    .prog-fill{background:linear-gradient(90deg,#4ECDC4,#44B8B0);border-radius:99px;height:7px;transition:width 1.2s ease}

    /* MODULE CARD */
    .mod-card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);border-left:3px solid #4ECDC4;border-radius:8px;padding:14px;margin-bottom:10px}
    .mod-card.adv{border-left-color:#FF6B6B}
    .mod-card.int{border-left-color:#FFE66D}
    .mod-card.critical{border-left-color:#FF6B6B;box-shadow:0 0 12px rgba(255,107,107,.15)}
    .mod-title{font-weight:600;font-size:.9rem}
    .mod-meta{font-size:.75rem;color:#555F7A;margin-top:4px}
    .mod-why{font-size:.78rem;color:#7B8DA6;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.05);font-style:italic}

    /* TABS */
    .nav-tabs{border-bottom:1px solid #161D2E !important;margin-bottom:24px}
    .nav-tabs .nav-link{color:#4A5568 !important;border:none !important;font-size:.88rem;padding:10px 20px}
    .nav-tabs .nav-link.active{color:#4ECDC4 !important;background:transparent !important;border-bottom:2px solid #4ECDC4 !important}

    /* PROFILE ROW */
    .prof-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px}
    .prof-key{font-size:.78rem;color:#4A5568}
    .prof-val{font-size:.82rem;color:#C9D1D9;font-weight:500}

    /* SPINNER */
    .spinner-wrap{display:none;position:fixed;inset:0;background:rgba(7,11,20,.88);z-index:9999;align-items:center;justify-content:center;flex-direction:column;gap:14px}
    .spin{width:46px;height:46px;border:3px solid rgba(78,205,196,.2);border-top-color:#4ECDC4;border-radius:50%;animation:spin .75s linear infinite}
    @keyframes spin{to{transform:rotate(360deg)}}
    .fade-up{animation:fadeUp .45s ease}
    @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

    /* MISC */
    .section-h{font-size:1.15rem;font-weight:600;color:#E6EDF3;margin-bottom:4px}
    .section-s{font-size:.78rem;color:#3D4F6B;margin-bottom:16px}
    textarea.form-control{background:rgba(255,255,255,.03) !important;border:1px solid rgba(255,255,255,.07) !important;color:#C9D1D9 !important;font-size:.82rem}
    textarea.form-control:focus{border-color:rgba(78,205,196,.4) !important;box-shadow:none !important}
    ::-webkit-scrollbar{width:4px}
    ::-webkit-scrollbar-track{background:transparent}
    ::-webkit-scrollbar-thumb{background:#1E2A3A;border-radius:99px}
  </style>
</head>
<body id="body-root">
  {%app_entry%}
  <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""

# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Store(id="s-resume"),
    dcc.Store(id="s-jd"),
    dcc.Store(id="s-results"),
    dcc.Store(id="s-theme", data="dark"),
    dcc.Download(id="dl-pdf"),

    # Spinner
    html.Div([
        html.Div(className="spin"),
        html.P("Running AI analysis with Groq…", style={"color":"#4ECDC4","fontSize":".88rem","margin":0}),
        html.P("Parsing skills · Mapping gaps · Generating roadmap", style={"color":"#3D4F6B","fontSize":".75rem","margin":0}),
    ], id="spinner", className="spinner-wrap"),

    # Nav
    html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div("SkillForge", className="logo-mark"),
                    html.Div("SKILL GAP · LEARNING PATHWAYS", className="logo-sub"),
                ], width="auto"),
                dbc.Col(html.Div([
                    html.Span("Groq LLaMA 3.3",  className="nav-pill"),
                    html.Span("NetworkX Pathing", className="nav-pill ms-2"),
                    html.Span("Semantic Match",   className="nav-pill ms-2"),
                    html.Span("Skill Decay",      className="nav-pill ms-2"),
                    html.Button("☀ Light", id="btn-theme", className="theme-btn ms-3", n_clicks=0),
                ], className="d-flex align-items-center justify-content-end")),
            ], align="center")
        ], fluid=True)
    ], className="nav-bar"),

    # Main
    dbc.Container([
        # Hero
        html.Div([
            html.H1("Map Your Path to Role Mastery", className="hero-title"),
            html.P("Upload your resume and the target job description — the AI identifies "
                   "your exact skill gaps and builds a dependency-aware learning roadmap.",
                   className="hero-sub"),
        ], style={"padding":"48px 0 24px","textAlign":"center"}),

        # Feature 8: Sample inputs
        html.Div([
            html.P("Try a sample:", style={"fontSize":".78rem","color":"#3D4F6B","marginBottom":"8px","textAlign":"center"}),
            html.Div([
                html.Button("👨‍💻 Junior SWE",          id="sample-junior", className="sample-btn me-2", n_clicks=0),
                html.Button("🧠 Senior Data Scientist",  id="sample-senior", className="sample-btn me-2", n_clicks=0),
                html.Button("👔 HR Manager",             id="sample-hr",     className="sample-btn",      n_clicks=0),
            ], style={"textAlign":"center"}),
        ], style={"marginBottom":"28px"}),

        # Upload row
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div("📄", className="upload-icon"),
                    html.P("Resume", style={"fontWeight":"600","marginBottom":"2px"}),
                    dcc.Upload(id="up-resume",
                               children=html.Div(["Drop or ",html.Span("browse",style={"color":"#4ECDC4","textDecoration":"underline"})]),
                               className="upload-box"),
                    html.P("PDF or DOCX", className="upload-hint"),
                    html.Div(id="fn-resume", style={"fontSize":".75rem","color":"#4ECDC4","marginTop":"6px","textAlign":"center"}),
                ], className="glass-card", style={"textAlign":"center"}),
            ], md=4),
            dbc.Col([
                html.Div([
                    html.Div("💼", className="upload-icon"),
                    html.P("Job Description", style={"fontWeight":"600","marginBottom":"2px"}),
                    dcc.Upload(id="up-jd",
                               children=html.Div(["Drop or ",html.Span("browse",style={"color":"#4ECDC4","textDecoration":"underline"})]),
                               className="upload-box"),
                    html.P("PDF, DOCX or paste below", className="upload-hint"),
                    html.Div(id="fn-jd", style={"fontSize":".75rem","color":"#4ECDC4","marginTop":"6px","textAlign":"center"}),
                    dbc.Textarea(id="jd-paste", placeholder="…or paste the JD text here", rows=3, style={"marginTop":"10px"}),
                ], className="glass-card", style={"textAlign":"center"}),
            ], md=5),
            dbc.Col([
                html.Div([
                    html.Div("⚡", className="upload-icon"),
                    html.P("Analyze", style={"fontWeight":"600","marginBottom":"2px"}),
                    html.P("AI-powered gap analysis", className="upload-hint", style={"marginBottom":"20px"}),
                    html.Button("Analyze →", id="btn-run", className="btn-run", n_clicks=0),
                    html.Div(id="run-err", style={"fontSize":".75rem","color":"#FF6B6B","marginTop":"8px","textAlign":"center"}),
                ], className="glass-card", style={"textAlign":"center"}),
            ], md=3),
        ], className="g-3 mb-5"),

        # Results
        html.Div(id="results-wrap", style={"display":"none"}, className="fade-up", children=[
            dbc.Tabs([
                dbc.Tab(label="📊  Skill Gap",       tab_id="tab-gap"),
                dbc.Tab(label="🗺️  Learning Roadmap", tab_id="tab-road"),
                dbc.Tab(label="📋  Export Report",    tab_id="tab-rep"),
            ], id="tabs", active_tab="tab-gap", className="mb-0"),
            html.Div(id="tab-body", style={"paddingTop":"24px"}),
        ]),

        html.Div(style={"height":"80px"}),
    ], fluid=True, style={"maxWidth":"1200px","padding":"0 24px"}),
])


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 13 · CALLBACKS
# ──────────────────────────────────────────────────────────────────────────────

# Feature 1: Dark/Light mode toggle
app.clientside_callback(
    """
    function(n, theme) {
        var body = document.getElementById('body-root');
        var btn  = document.getElementById('btn-theme');
        if (!body) return theme || 'dark';
        if (theme === 'dark') {
            body.classList.add('light-mode');
            if (btn) btn.innerText = '🌙 Dark';
            return 'light';
        } else {
            body.classList.remove('light-mode');
            if (btn) btn.innerText = '☀ Light';
            return 'dark';
        }
    }
    """,
    Output("s-theme", "data"),
    Input("btn-theme", "n_clicks"),
    State("s-theme", "data"),
    prevent_initial_call=True,
)

# Spinner
app.clientside_callback(
    """
    function(n_clicks, results_data) {
        var ctx = window.dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || ctx.triggered.length === 0) return {display:'none'};
        if (ctx.triggered[0].prop_id === 'btn-run.n_clicks' && n_clicks > 0) return {display:'flex'};
        return {display:'none'};
    }
    """,
    Output("spinner", "style"),
    Input("btn-run",   "n_clicks"),
    Input("s-results", "data"),
    prevent_initial_call=True,
)

# Upload callbacks
@app.callback(Output("fn-resume","children"), Output("s-resume","data"),
              Input("up-resume","contents"), State("up-resume","filename"),
              prevent_initial_call=True)
def cb_resume(contents, filename):
    if not contents: return "", None
    return f"✓ {filename}", {"text": parse_upload(contents, filename), "filename": filename}

@app.callback(Output("fn-jd","children"), Output("s-jd","data"),
              Input("up-jd","contents"), State("up-jd","filename"),
              prevent_initial_call=True)
def cb_jd(contents, filename):
    if not contents: return "", None
    return f"✓ {filename}", {"text": parse_upload(contents, filename), "filename": filename}


# Feature 8: Sample inputs
@app.callback(
    Output("s-resume", "data", allow_duplicate=True),
    Output("s-jd",     "data", allow_duplicate=True),
    Output("jd-paste", "value"),
    Output("fn-resume","children", allow_duplicate=True),
    Output("fn-jd",    "children", allow_duplicate=True),
    Input("sample-junior","n_clicks"),
    Input("sample-senior","n_clicks"),
    Input("sample-hr",    "n_clicks"),
    prevent_initial_call=True,
)
def cb_samples(n1, n2, n3):
    triggered = ctx.triggered_id
    key_map = {"sample-junior":"junior_swe","sample-senior":"senior_ds","sample-hr":"hr_manager"}
    key = key_map.get(triggered)
    if not key: raise PreventUpdate
    s = SAMPLES[key]
    return ({"text": s["resume"], "filename": f"{key}.txt"},
            {"text": s["jd"],     "filename": f"{key}_jd.txt"},
            s["jd"],
            f"✓ {s['label']} resume loaded",
            f"✓ {s['label']} JD loaded")


# Main run callback
@app.callback(
    Output("s-results",    "data"),
    Output("results-wrap", "style"),
    Output("run-err",      "children"),
    Input("btn-run",  "n_clicks"),
    State("s-resume", "data"),
    State("s-jd",     "data"),
    State("jd-paste", "value"),
    prevent_initial_call=True,
)
def cb_run(n, resume_store, jd_store, jd_paste):
    if not n: raise PreventUpdate
    resume_text   = (resume_store or {}).get("text","")
    jd_text_final = (jd_store or {}).get("text","") or jd_paste or ""
    if not resume_text:   return no_update, {"display":"none"}, "⚠ Upload a resume first."
    if not jd_text_final: return no_update, {"display":"none"}, "⚠ Upload or paste a job description."

    resume_data = parse_resume(resume_text)
    jd_data     = parse_jd(jd_text_final)
    if "error" in resume_data: return no_update, {"display":"none"}, f"⚠ {resume_data['error']}"
    if "error" in jd_data:     return no_update, {"display":"none"}, f"⚠ {jd_data['error']}"

    gap_profile = analyze_gap(resume_data, jd_data)
    path        = generate_path(gap_profile, resume_data, jd_data)

    cname  = resume_data.get("name","the candidate")
    subset = path[:12]
    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_map = {ex.submit(generate_reasoning, m, m["gap_skill"], cname): i
                   for i, m in enumerate(subset)}
        for f in as_completed(fut_map):
            idx = fut_map[f]
            try:    subset[idx]["reasoning"] = f.result()
            except: subset[idx]["reasoning"] = f"Addresses gap in {subset[idx]['gap_skill']}."

    impact    = calculate_impact(gap_profile, path)
    seniority = check_seniority_mismatch(resume_data, jd_data)

    return (
        {"resume_data": resume_data, "jd_data": jd_data,
         "gap_profile": gap_profile, "path": path,
         "impact": impact, "seniority": seniority},
        {"display":"block"}, "",
    )


# Tab renderer
@app.callback(
    Output("tab-body","children"),
    Input("tabs",    "active_tab"),
    Input("s-theme", "data"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_tabs(tab, theme, results):
    if not results: raise PreventUpdate
    dark = (theme == "dark")
    rd = results["resume_data"]; jd = results["jd_data"]
    gp = results["gap_profile"]; pt = results["path"]
    im = results["impact"];      sm = results.get("seniority",{})

    # Seniority warning
    warn_banner = None
    if sm.get("has_mismatch"):
        warn_banner = html.Div([
            html.Span("⚠ Seniority Gap Detected: ", style={"fontWeight":"700"}),
            f"Candidate is {sm['candidate']}, role requires {sm['required']}. "
            "Leadership modules have been automatically added to the roadmap."
        ], className="warn-banner")

    def domain_badge(domain):
        cls = {"Tech":"domain-tech","Non-Tech":"domain-nontech","Soft":"domain-soft"}.get(domain,"domain-tech")
        return html.Span(domain, className=cls, style={"marginLeft":"6px"})

    # ── TAB: SKILL GAP ────────────────────────────────────────────────────
    if tab == "tab-gap":
        known   = [g for g in gp if g["status"]=="Known"]
        partial = [g for g in gp if g["status"]=="Partial"]
        missing = [g for g in gp if g["status"]=="Missing"]
        decayed = [g for g in gp if g.get("decayed")]

        def skill_row(g):
            cls   = {"Known":"badge-known","Partial":"badge-partial","Missing":"badge-missing"}[g["status"]]
            decay = html.Span("↓ decayed", className="decay-badge ms-1") if g.get("decayed") else None
            return html.Div([
                html.Span(g["skill"], style={"fontSize":".85rem","fontWeight":"500"}),
                html.Span(g["status"], className=f"skill-badge {cls}", style={"marginLeft":"8px"}),
                html.Span(f"{g['proficiency']}/10", style={"fontSize":".72rem","color":"#3D4F6B",
                                                            "marginLeft":"8px","fontFamily":"JetBrains Mono,monospace"}),
                decay,
            ], style={"marginBottom":"9px","display":"flex","alignItems":"center","flexWrap":"wrap"})

        return html.Div([warn_banner, dbc.Row([
            dbc.Col([html.Div([
                html.P("Skill Gap Radar", className="section-h"),
                html.P(f"{rd.get('name','Candidate')}  vs  {jd.get('role_title','Target Role')}", className="section-s"),
                dcc.Graph(figure=radar_chart(gp, dark), config={"displayModeBar":False}, style={"height":"360px"}),
            ], className="glass-card")], md=6),
            dbc.Col([html.Div([
                html.P("All Skills", className="section-h"),
                html.P(f"{len(known)} Known · {len(partial)} Partial · {len(missing)} Missing"
                       + (f" · {len(decayed)} decay-adjusted" if decayed else ""), className="section-s"),
                html.Div([skill_row(g) for g in gp], style={"maxHeight":"320px","overflowY":"auto"}),
            ], className="glass-card")], md=6),
            dbc.Col([html.Div([
                html.P("Candidate", className="section-h", style={"marginBottom":"12px"}),
                *[html.Div([html.Span(k,className="prof-key"),html.Span(str(v),className="prof-val")],className="prof-row")
                  for k,v in [("Name",rd.get("name","—")),("Role",rd.get("current_role","—")),
                               ("Seniority",rd.get("seniority","—")),("Experience",f"{rd.get('years_experience','—')} yrs"),
                               ("Domain",rd.get("domain","—"))]],
            ], className="glass-card")], md=4),
            dbc.Col([html.Div([
                html.P("Target Role", className="section-h", style={"marginBottom":"12px"}),
                *[html.Div([html.Span(k,className="prof-key"),html.Span(str(v),className="prof-val")],className="prof-row")
                  for k,v in [("Title",jd.get("role_title","—")),("Seniority",jd.get("seniority_required","—")),
                               ("Domain",jd.get("domain","—")),("Required",len(jd.get("required_skills",[]))),
                               ("Preferred",len(jd.get("preferred_skills",[])))]],
            ], className="glass-card")], md=4),
            dbc.Col([html.Div([
                html.P("Gap Summary", className="section-h", style={"marginBottom":"12px"}),
                *[html.Div([html.Span(str(n),style={"fontFamily":"JetBrains Mono,monospace","fontWeight":"700",
                                                     "fontSize":"1.5rem","color":col}),
                             html.Span(f"  {lbl}",style={"color":"#3D4F6B","fontSize":".85rem"})],
                            style={"marginBottom":"10px"})
                  for n,col,lbl in [(len(known),"#4ECDC4","Known"),(len(partial),"#FFE66D","Partial"),
                                    (len(missing),"#FF6B6B","Missing"),(len(decayed),"#FFA726","Decay-adjusted")]],
            ], className="glass-card")], md=4),
        ], className="g-3")])

    # ── TAB: ROADMAP ──────────────────────────────────────────────────────
    if tab == "tab-road":
        lc = {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF6B6B"}

        def mod_card(i, m):
            col   = lc.get(m["level"],"#888")
            is_cr = m.get("is_critical",False)
            xtra  = " critical" if is_cr else (" adv" if m["level"]=="Advanced" else " int" if m["level"]=="Intermediate" else "")
            return html.Div([
                html.Div([
                    html.Span(f"#{i+1}", style={"fontFamily":"JetBrains Mono,monospace","fontSize":".72rem","color":"#3D4F6B","marginRight":"10px"}),
                    html.Span(m["title"], className="mod-title"),
                    html.Span(m["level"], style={"marginLeft":"auto","fontSize":".68rem","color":col,"border":f"1px solid {col}40","borderRadius":"4px","padding":"2px 8px","background":"rgba(255,255,255,.04)"}),
                    html.Span(f"{m['duration_hrs']}h", style={"fontFamily":"JetBrains Mono,monospace","fontSize":".72rem","color":"#3D4F6B","marginLeft":"10px"}),
                ], style={"display":"flex","alignItems":"center"}),
                html.Div([
                    html.Span(f"Skill: {m['skill']}  ·  Gap: {m.get('gap_status','—')}", className="mod-meta"),
                    domain_badge(m["domain"]),
                    (html.Span("⚡ critical path", className="critical-badge ms-1") if is_cr else None),
                ], style={"display":"flex","alignItems":"center","flexWrap":"wrap","marginTop":"4px"}),
                (html.Div(m["reasoning"], className="mod-why") if m.get("reasoning") else None),
            ], className=f"mod-card{xtra}")

        fit_card = html.Div([
            html.P("Role Fit Score", className="section-h", style={"marginBottom":"16px","textAlign":"center"}),
            dbc.Row([
                dbc.Col([html.Div([
                    html.Div(f"{im['current_fit']}", className="fit-num-big", style={"color":"#FF6B6B"}),
                    html.Div("Current fit", className="fit-lbl-sm"),
                ], className="fit-score-box")]),
                dbc.Col([html.Div("→", style={"fontSize":"2rem","color":"#3D4F6B","textAlign":"center","paddingTop":"8px"})], width="auto"),
                dbc.Col([html.Div([
                    html.Div(f"{im['projected_fit']}", className="fit-num-big", style={"color":"#4ECDC4"}),
                    html.Div("After roadmap", className="fit-lbl-sm"),
                    html.Div(f"+{im['fit_delta']}% improvement", className="fit-delta"),
                ], className="fit-score-box")]),
            ], align="center", className="g-0"),
        ], className="glass-card mb-3")

        ready_row = html.Div([
            html.Div(style={"height":"14px"}),
            html.Div([
                html.Span("Study pace: ", style={"fontSize":".8rem","color":"#3D4F6B","marginRight":"8px"}),
                dcc.Dropdown(id="pace-dd",
                    options=[{"label":"1h/day","value":1},{"label":"2h/day","value":2},
                             {"label":"4h/day","value":4},{"label":"8h/day","value":8}],
                    value=2, clearable=False,
                    style={"width":"120px","display":"inline-block","verticalAlign":"middle","fontSize":".8rem"}),
                html.Span(id="ready-estimate",
                          style={"marginLeft":"12px","color":"#4ECDC4","fontWeight":"600",
                                 "fontFamily":"JetBrains Mono,monospace","fontSize":".9rem"}),
            ], style={"display":"flex","alignItems":"center"}),
        ])

        return html.Div([warn_banner, dbc.Row([
            dbc.Col([fit_card], md=5),
            dbc.Col([html.Div([
                html.P("Impact Summary", className="section-h", style={"marginBottom":"18px"}),
                dbc.Row([
                    dbc.Col([html.Div(f"~{im['hours_saved']}h",className="impact-num"),html.Div("Hours Saved",className="impact-lbl")],className="text-center"),
                    dbc.Col([html.Div(f"{im['roadmap_hours']}h",className="impact-num"),html.Div("Training Time",className="impact-lbl")],className="text-center"),
                    dbc.Col([html.Div(str(im["modules_count"]),className="impact-num"),html.Div("Modules",className="impact-lbl")],className="text-center"),
                    dbc.Col([html.Div(str(im.get("critical_count",0)),className="impact-num",style={"color":"#FF6B6B"}),html.Div("Critical Path",className="impact-lbl")],className="text-center"),
                ], className="g-2"),
                html.Div(style={"height":"14px"}),
                html.Div("Skill Coverage", style={"fontSize":".72rem","color":"#3D4F6B","marginBottom":"5px"}),
                html.Div(className="prog-track",children=[html.Div(className="prog-fill",style={"width":f"{im['projected_fit']}%"})]),
                ready_row,
            ], className="glass-card mb-3")], md=7),
            dbc.Col([html.Div([
                html.P("Training Timeline", className="section-h"),
                html.P(f"{im['modules_count']} modules · {im['roadmap_hours']}h total · {im.get('critical_count',0)} critical", className="section-s"),
                dcc.Graph(figure=timeline_chart(pt, dark), config={"displayModeBar":False}, style={"overflowY":"auto"}),
            ], className="glass-card")], md=7),
            dbc.Col([html.Div([
                html.P("Modules & Reasoning", className="section-h"),
                html.P("Why each module was assigned", className="section-s"),
                html.Div([mod_card(i,m) for i,m in enumerate(pt)], style={"maxHeight":"560px","overflowY":"auto"}),
            ], className="glass-card")], md=5),
        ], className="g-3")])

    # ── TAB: REPORT ───────────────────────────────────────────────────────
    if tab == "tab-rep":
        checklist = [
            "Groq LLaMA 3.3 — Resume & JD Parsing",
            "Skill Decay Model — skills get rusty over time",
            "Skill Gap Analysis with Proficiency Scores (0-10)",
            "Semantic Skill Matching (embedding + substring)",
            "Dependency-Aware Path (NetworkX topological sort)",
            "Critical Path Highlighting — key modules in red",
            "Original Adaptive Algorithm — not just an LLM",
            "Seniority Mismatch Warning — auto leadership inject",
            "AI Reasoning Trace per Module (Groq-generated)",
            "Role Fit Score — before vs after delta",
            "Confidence Band on Radar Chart (Plotly)",
            "Interactive Training Timeline (Plotly)",
            "Domain Color Badges — Tech / Non-Tech / Soft",
            "Readiness Estimator — ready in X weeks at Y h/day",
            "One-Click Sample Inputs — 3 demo scenarios",
            "Dark / Light Mode Toggle",
            "Impact: Hours Saved · Role Readiness %",
            "PDF Export via ReportLab",
            "Zero Hallucinations — catalog-only recommendations",
        ]
        return dbc.Row([
            dbc.Col([html.Div([
                html.P("Download PDF Report", className="section-h"),
                html.P("Full roadmap with reasoning traces.", className="section-s"),
                html.Div([
                    *[html.Div([
                        html.Span("●",style={"color":"#4ECDC4","marginRight":"8px"}),
                        html.Span(k,style={"fontSize":".82rem","color":"#3D4F6B"}),
                        html.Span(str(v),style={"fontSize":".82rem","color":"#C9D1D9","marginLeft":"4px","fontWeight":"500"}),
                    ], style={"marginBottom":"7px"})
                      for k,v in [("Candidate:",    rd.get("name","—")),
                                   ("Role:",         jd.get("role_title","—")),
                                   ("Current Fit:",  f"{im['current_fit']}%"),
                                   ("Projected Fit:",f"{im['projected_fit']}% (+{im['fit_delta']}%)"),
                                   ("Modules:",      im["modules_count"]),
                                   ("Training Hrs:", f"{im['roadmap_hours']}h"),
                                   ("Hours Saved:",  f"~{im['hours_saved']}h"),
                                   ("Decay-adj:",    im.get("decayed_skills",0)),]]
                ], style={"background":"rgba(78,205,196,.05)","border":"1px solid rgba(78,205,196,.15)","borderRadius":"10px","padding":"16px","marginBottom":"20px"}),
                html.Button("⬇  Download PDF Report", id="btn-pdf", n_clicks=0, className="btn-run"),
                html.Div(id="pdf-status", style={"fontSize":".75rem","color":"#3D4F6B","marginTop":"8px","textAlign":"center"}),
            ], className="glass-card")], md=5),
            dbc.Col([html.Div([
                html.P("Feature Checklist", className="section-h"),
                html.P("Everything built into this submission", className="section-s"),
                *[html.Div([
                    html.Span("✓",style={"color":"#4ECDC4","marginRight":"10px","fontWeight":"700"}),
                    html.Span(item,style={"fontSize":".84rem"}),
                ], style={"marginBottom":"9px"}) for item in checklist],
            ], className="glass-card")], md=7),
        ], className="g-3")


# Feature 5: Readiness estimator callback
@app.callback(
    Output("ready-estimate","children"),
    Input("pace-dd",   "value"),
    State("s-results", "data"),
    prevent_initial_call=True,
)
def cb_ready(pace, results):
    if not results or not pace: raise PreventUpdate
    return f"Ready in ~{weeks_to_ready(results['impact']['roadmap_hours'], pace)}"


# PDF export
@app.callback(
    Output("dl-pdf",     "data"),
    Output("pdf-status", "children"),
    Input("btn-pdf",  "n_clicks"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_pdf(n, results):
    if not results: raise PreventUpdate
    if not REPORTLAB: return no_update, "⚠ Install reportlab: pip install reportlab"
    buf  = build_pdf(results["resume_data"], results["jd_data"],
                     results["gap_profile"], results["path"], results["impact"])
    name = results["resume_data"].get("name","candidate").replace(" ","_")
    fn   = f"skillforge_roadmap_{name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return dcc.send_bytes(buf.read(), fn), f"✓ Downloading {fn}"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 14 · RUN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  SkillForge — AI Adaptive Onboarding Engine  v2")
    print("  ─────────────────────────────────────────────")
    print("  → http://localhost:8050")
    print(f"  → Semantic matching : {'sentence-transformers ✓' if SEMANTIC else 'substring fallback'}")
    print(f"  → PDF export        : {'reportlab ✓' if REPORTLAB else 'not installed'}")
    print(f"  → Groq API key      : {'set ✓' if os.getenv('GROQ_API_KEY') else 'MISSING'}")
    print("  → New v2 features   : Skill Decay · Role Fit Score · Critical Path")
    print("                        Seniority Warning · Readiness Estimator")
    print("                        Domain Badges · Sample Inputs · Dark/Light Mode\n")
    app.run(debug=True, port=8050)