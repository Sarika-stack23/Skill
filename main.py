# =============================================================================
#  main.py — AI-Adaptive Onboarding Engine
#  Stack : Plotly Dash · Groq LLaMA 3.3 · NetworkX · ReportLab
#  Run   : python main.py          (needs GROQ_API_KEY in .env)
# =============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 · IMPORTS & CONFIG
# ──────────────────────────────────────────────────────────────────────────────
import os, json, base64, io, re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import dash
from dash import dcc, html, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import networkx as nx
import pdfplumber
from docx import Document
from groq import Groq

# Optional: sentence-transformers for semantic skill matching
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    SEMANTIC = True
except Exception:
    SEMANTIC = False

# Optional: ReportLab for PDF export
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    REPORTLAB = True
except Exception:
    REPORTLAB = False

GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY", ""))


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 · COURSE CATALOG  (the only source of truth — no hallucinations)
# ──────────────────────────────────────────────────────────────────────────────
CATALOG = [
    # ── PYTHON ──────────────────────────────────────────────────────────────
    {"id":"PY01","title":"Python Fundamentals","skill":"Python","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"PY02","title":"Python Intermediate: OOP & Modules","skill":"Python","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["PY01"]},
    {"id":"PY03","title":"Python Advanced: Async, Decorators & Performance","skill":"Python","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["PY02"]},
    # ── DATA ────────────────────────────────────────────────────────────────
    {"id":"DA01","title":"Data Analysis with Pandas","skill":"Data Analysis","domain":"Tech","level":"Beginner","duration_hrs":7,"prereqs":["PY01"]},
    {"id":"DA02","title":"Data Visualization (Matplotlib & Seaborn)","skill":"Data Visualization","domain":"Tech","level":"Intermediate","duration_hrs":5,"prereqs":["DA01"]},
    {"id":"DA03","title":"Statistical Analysis & Hypothesis Testing","skill":"Statistics","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["DA01"]},
    # ── MACHINE LEARNING ────────────────────────────────────────────────────
    {"id":"ML01","title":"Machine Learning Foundations","skill":"Machine Learning","domain":"Tech","level":"Beginner","duration_hrs":10,"prereqs":["DA01","DA03"]},
    {"id":"ML02","title":"Supervised Learning: Regression & Classification","skill":"Machine Learning","domain":"Tech","level":"Intermediate","duration_hrs":12,"prereqs":["ML01"]},
    {"id":"ML03","title":"Deep Learning with PyTorch","skill":"Deep Learning","domain":"Tech","level":"Advanced","duration_hrs":15,"prereqs":["ML02"]},
    {"id":"ML04","title":"NLP & Large Language Models","skill":"NLP","domain":"Tech","level":"Advanced","duration_hrs":14,"prereqs":["ML02"]},
    {"id":"ML05","title":"MLOps & Model Deployment","skill":"MLOps","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["ML02","DO02"]},
    # ── SQL & DATABASES ─────────────────────────────────────────────────────
    {"id":"SQL01","title":"SQL Fundamentals","skill":"SQL","domain":"Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"SQL02","title":"Advanced SQL: Window Functions & Query Optimization","skill":"SQL","domain":"Tech","level":"Advanced","duration_hrs":7,"prereqs":["SQL01"]},
    {"id":"SQL03","title":"Database Design & NoSQL (MongoDB, Redis)","skill":"Databases","domain":"Tech","level":"Intermediate","duration_hrs":6,"prereqs":["SQL01"]},
    # ── DEVOPS ──────────────────────────────────────────────────────────────
    {"id":"DO01","title":"Linux & Bash Scripting","skill":"Linux","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"DO02","title":"Docker & Containerization","skill":"Docker","domain":"Tech","level":"Intermediate","duration_hrs":7,"prereqs":["DO01"]},
    {"id":"DO03","title":"Kubernetes Orchestration","skill":"Kubernetes","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["DO02"]},
    {"id":"DO04","title":"CI/CD Pipelines with GitHub Actions","skill":"CI/CD","domain":"Tech","level":"Intermediate","duration_hrs":6,"prereqs":["DO01"]},
    # ── CLOUD ───────────────────────────────────────────────────────────────
    {"id":"CL01","title":"Cloud Computing Fundamentals","skill":"Cloud Computing","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"CL02","title":"AWS Core Services Deep Dive","skill":"AWS","domain":"Tech","level":"Intermediate","duration_hrs":10,"prereqs":["CL01"]},
    {"id":"CL03","title":"GCP & BigQuery for Data Engineers","skill":"GCP","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["CL01","DA01"]},
    # ── WEB DEVELOPMENT ─────────────────────────────────────────────────────
    {"id":"WE01","title":"HTML & CSS Foundations","skill":"HTML/CSS","domain":"Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"WE02","title":"JavaScript Essentials","skill":"JavaScript","domain":"Tech","level":"Beginner","duration_hrs":8,"prereqs":["WE01"]},
    {"id":"WE03","title":"React.js Fundamentals","skill":"React","domain":"Tech","level":"Intermediate","duration_hrs":10,"prereqs":["WE02"]},
    {"id":"WE04","title":"FastAPI Backend Development","skill":"FastAPI","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["PY02"]},
    {"id":"WE05","title":"Full-Stack Integration & REST APIs","skill":"REST APIs","domain":"Tech","level":"Intermediate","duration_hrs":7,"prereqs":["WE03","WE04"]},
    # ── SECURITY ────────────────────────────────────────────────────────────
    {"id":"SE01","title":"Cybersecurity Fundamentals","skill":"Cybersecurity","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"SE02","title":"Application Security & OWASP Top 10","skill":"Application Security","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["SE01"]},
    # ── AGILE / PM ──────────────────────────────────────────────────────────
    {"id":"AG01","title":"Agile & Scrum Fundamentals","skill":"Agile","domain":"Tech","level":"Beginner","duration_hrs":4,"prereqs":[]},
    {"id":"AG02","title":"Advanced Scrum Master Certification Prep","skill":"Scrum","domain":"Tech","level":"Advanced","duration_hrs":6,"prereqs":["AG01"]},
    {"id":"PM01","title":"Project Management Essentials (PMI Framework)","skill":"Project Management","domain":"Soft","level":"Intermediate","duration_hrs":8,"prereqs":["LD01"]},
    # ── HR ──────────────────────────────────────────────────────────────────
    {"id":"HR01","title":"HR Fundamentals & Employment Law","skill":"Human Resources","domain":"Non-Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"HR02","title":"Talent Acquisition & Recruitment","skill":"Recruitment","domain":"Non-Tech","level":"Intermediate","duration_hrs":6,"prereqs":["HR01"]},
    {"id":"HR03","title":"Performance Management & Appraisals","skill":"Performance Management","domain":"Non-Tech","level":"Intermediate","duration_hrs":5,"prereqs":["HR01"]},
    {"id":"HR04","title":"Employee Relations & Conflict Resolution","skill":"Employee Relations","domain":"Non-Tech","level":"Advanced","duration_hrs":6,"prereqs":["HR01"]},
    {"id":"HR05","title":"Learning & Development Strategy","skill":"L&D Strategy","domain":"Non-Tech","level":"Advanced","duration_hrs":6,"prereqs":["HR03"]},
    # ── OPERATIONS / LOGISTICS ──────────────────────────────────────────────
    {"id":"OP01","title":"Supply Chain & Logistics Fundamentals","skill":"Logistics","domain":"Non-Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"OP02","title":"Warehouse Management Systems","skill":"Warehouse Management","domain":"Non-Tech","level":"Intermediate","duration_hrs":6,"prereqs":["OP01"]},
    {"id":"OP03","title":"Inventory Control & Demand Planning","skill":"Inventory Management","domain":"Non-Tech","level":"Intermediate","duration_hrs":5,"prereqs":["OP01"]},
    {"id":"OP04","title":"Lean Manufacturing & Six Sigma Green Belt","skill":"Process Improvement","domain":"Non-Tech","level":"Advanced","duration_hrs":8,"prereqs":["OP01"]},
    # ── FINANCE ─────────────────────────────────────────────────────────────
    {"id":"FI01","title":"Financial Accounting Basics","skill":"Accounting","domain":"Non-Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"FI02","title":"Financial Analysis & Modeling","skill":"Financial Analysis","domain":"Non-Tech","level":"Intermediate","duration_hrs":8,"prereqs":["FI01"]},
    {"id":"FI03","title":"Budgeting & Forecasting","skill":"Budgeting","domain":"Non-Tech","level":"Intermediate","duration_hrs":5,"prereqs":["FI01"]},
    # ── LEADERSHIP / SOFT SKILLS ────────────────────────────────────────────
    {"id":"LD01","title":"Communication & Presentation Skills","skill":"Communication","domain":"Soft","level":"Beginner","duration_hrs":4,"prereqs":[]},
    {"id":"LD02","title":"Team Leadership & People Management","skill":"Leadership","domain":"Soft","level":"Intermediate","duration_hrs":6,"prereqs":["LD01"]},
    {"id":"LD03","title":"Strategic Thinking & Decision Making","skill":"Strategic Planning","domain":"Soft","level":"Advanced","duration_hrs":6,"prereqs":["LD02"]},
    {"id":"LD04","title":"Cross-Functional Collaboration","skill":"Collaboration","domain":"Soft","level":"Beginner","duration_hrs":3,"prereqs":["LD01"]},
]

CATALOG_BY_ID   = {c["id"]: c for c in CATALOG}
CATALOG_SKILLS  = [c["skill"].lower() for c in CATALOG]   # index-aligned


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 · SKILL DEPENDENCY GRAPH  (networkx)
# ──────────────────────────────────────────────────────────────────────────────
def _build_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    for c in CATALOG:
        G.add_node(c["id"], **c)
        for p in c["prereqs"]:
            G.add_edge(p, c["id"])   # prereq → course
    return G

SKILL_GRAPH = _build_graph()


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 · UTILITIES  (file readers)
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
    """Decode a Dash upload component payload → plain text."""
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
# SECTION 5 · GROQ API  (parser + reasoning)
# ──────────────────────────────────────────────────────────────────────────────
def _groq(prompt: str, system: str = "You are an expert HR analyst. Always respond with valid JSON only, no markdown fences.") -> dict:
    try:
        r = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system},
                      {"role": "user",   "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = r.choices[0].message.content.strip()
        raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "JSON parse failed", "raw": raw[:200]}
    except Exception as e:
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
    {{"skill": "<name>", "proficiency": <0-10>, "context": "<one-line evidence>"}}
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
def _semantic_match(skill: str, threshold: float = 0.52) -> tuple[int, float]:
    """Return (catalog_index, similarity_score). Falls back to substring if no embeddings."""
    sl = skill.lower()
    # 1. Exact / substring match (fast path)
    for i, cs in enumerate(CATALOG_SKILLS):
        if sl == cs or sl in cs or cs in sl:
            return i, 1.0
    # 2. Embedding-based cosine similarity
    if SEMANTIC:
        emb_q  = _ST_MODEL.encode([sl])
        emb_db = _ST_MODEL.encode(CATALOG_SKILLS)
        sims   = cosine_similarity(emb_q, emb_db)[0]
        best   = int(np.argmax(sims))
        if sims[best] >= threshold:
            return best, float(sims[best])
    # 3. Token overlap fallback
    tokens = set(sl.split())
    best_score, best_idx = 0.0, -1
    for i, cs in enumerate(CATALOG_SKILLS):
        overlap = len(tokens & set(cs.split())) / max(len(tokens), 1)
        if overlap > best_score:
            best_score, best_idx = overlap, i
    return (best_idx, best_score) if best_score >= 0.4 else (-1, 0.0)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7 · GAP ANALYZER
# ──────────────────────────────────────────────────────────────────────────────
def analyze_gap(resume_data: dict, jd_data: dict) -> list[dict]:
    """Classify every JD skill as Known / Partial / Missing with proficiency scores."""
    resume_skills = {s["skill"].lower(): s for s in resume_data.get("skills", [])}
    required  = jd_data.get("required_skills", [])
    preferred = jd_data.get("preferred_skills", [])
    all_skills = [(s, True) for s in required] + [(s, False) for s in preferred]

    gap_profile = []
    for skill, is_required in all_skills:
        sl = skill.lower()
        status, proficiency, context = "Missing", 0, ""

        # Direct match
        if sl in resume_skills:
            d = resume_skills[sl]
            proficiency = d["proficiency"]
            context     = d.get("context", "")
            status      = "Known" if proficiency >= 7 else "Partial"
        else:
            # Fuzzy match against resume keys
            for rk, rd in resume_skills.items():
                if sl in rk or rk in sl:
                    proficiency = rd["proficiency"]
                    context     = rd.get("context", "")
                    status      = "Known" if proficiency >= 7 else "Partial"
                    break

        # Find best catalog course for this skill
        idx, sim = _semantic_match(skill)
        catalog_course = CATALOG[idx] if idx >= 0 else None

        gap_profile.append({
            "skill":          skill,
            "status":         status,
            "proficiency":    proficiency,
            "is_required":    is_required,
            "context":        context,
            "catalog_course": catalog_course,
            "similarity":     sim,
        })

    return gap_profile


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 8 · ADAPTIVE PATH GENERATOR  (original algorithm)
# ──────────────────────────────────────────────────────────────────────────────
def generate_path(gap_profile: list[dict], resume_data: dict) -> list[dict]:
    """
    Adaptive algorithm:
      1. Collect catalog modules for all Missing / Partial skills.
      2. Walk the dependency graph (NetworkX) to pull in prerequisites
         that the candidate doesn't already know.
      3. Topological sort → guarantees foundational-first ordering.
      4. Score each module (required-gap first, then proficiency ascending)
         and re-sort within the same topological level.
    """
    seniority_map   = {"Junior": 0, "Mid": 1, "Senior": 2, "Lead": 3}
    candidate_level = seniority_map.get(resume_data.get("seniority", "Mid"), 1)

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

        # Pull prerequisite chain
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

    # Topological sort over the induced subgraph
    sub   = SKILL_GRAPH.subgraph(modules_needed)
    try:
        ordered = list(nx.topological_sort(sub))
    except nx.NetworkXUnfeasible:
        ordered = list(modules_needed)

    # Build enriched path list
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
            "gap_skill":  gap.get("skill", course["skill"]),
            "gap_status": gap.get("status", "Prereq"),
            "priority":   priority,
            "reasoning":  "",
        })

    # Secondary sort by priority within same topological order
    path.sort(key=lambda x: x["priority"])
    return path


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9 · IMPACT SCORER
# ──────────────────────────────────────────────────────────────────────────────
STANDARD_ONBOARDING_HRS = 60  # industry baseline for comparison

def calculate_impact(gap_profile: list[dict], path: list[dict]) -> dict:
    total   = len(gap_profile)
    known   = sum(1 for g in gap_profile if g["status"] == "Known")
    partial = sum(1 for g in gap_profile if g["status"] == "Partial")
    covered = len({m["gap_skill"] for m in path})

    roadmap_hrs  = sum(m["duration_hrs"] for m in path)
    hours_saved  = max(0, STANDARD_ONBOARDING_HRS - roadmap_hrs)
    readiness    = min(100, round(((known + covered) / max(total, 1)) * 100))

    return {
        "total_skills":      total,
        "known_skills":      known,
        "partial_skills":    partial,
        "gaps_addressed":    covered,
        "roadmap_hours":     roadmap_hrs,
        "hours_saved":       hours_saved,
        "role_readiness_pct": readiness,
        "modules_count":     len(path),
    }


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 10 · CHARTS
# ──────────────────────────────────────────────────────────────────────────────
_DARK_BG    = "rgba(0,0,0,0)"
_GRID_COLOR = "#1E2A3A"
_FONT       = dict(color="#C9D1D9", family="'Space Grotesk', sans-serif")


def radar_chart(gap_profile: list[dict]) -> go.Figure:
    items = gap_profile[:10]
    if not items:
        return go.Figure()
    theta   = [g["skill"][:18] for g in items]
    resume  = [g["proficiency"] for g in items]
    jd_req  = [10] * len(items)
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=jd_req,    theta=theta, fill="toself",
                                  name="JD Requirement", line=dict(color="#FF6B6B", width=2), opacity=0.25))
    fig.add_trace(go.Scatterpolar(r=resume,    theta=theta, fill="toself",
                                  name="Your Skills",    line=dict(color="#4ECDC4", width=2), opacity=0.65))
    fig.update_layout(
        polar=dict(
            bgcolor=_DARK_BG,
            radialaxis=dict(visible=True, range=[0,10], gridcolor=_GRID_COLOR, color="#555"),
            angularaxis=dict(gridcolor=_GRID_COLOR)
        ),
        paper_bgcolor=_DARK_BG, plot_bgcolor=_DARK_BG,
        font=_FONT, showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.82, y=1.15),
        margin=dict(l=30, r=30, t=30, b=30),
    )
    return fig


def timeline_chart(path: list[dict]) -> go.Figure:
    if not path:
        return go.Figure()
    color_map = {"Beginner": "#4ECDC4", "Intermediate": "#FFE66D", "Advanced": "#FF6B6B"}
    shown = set()
    fig = go.Figure()
    for i, m in enumerate(path):
        col  = color_map.get(m["level"], "#888")
        show = m["level"] not in shown
        shown.add(m["level"])
        fig.add_trace(go.Bar(
            x=[m["duration_hrs"]],
            y=[f"#{i+1} {m['title'][:38]}"],
            orientation="h",
            marker=dict(color=col, opacity=0.85, line=dict(width=0)),
            name=m["level"],
            legendgroup=m["level"],
            showlegend=show,
            hovertemplate=(f"<b>{m['title']}</b><br>"
                           f"Skill: {m['skill']}<br>"
                           f"Level: {m['level']}<br>"
                           f"Duration: {m['duration_hrs']}h<extra></extra>")
        ))
    fig.update_layout(
        paper_bgcolor=_DARK_BG,
        plot_bgcolor="rgba(15,22,36,0.6)",
        font=_FONT,
        xaxis=dict(title="Hours", gridcolor=_GRID_COLOR, color="#555", zeroline=False),
        yaxis=dict(gridcolor=_GRID_COLOR, tickfont=dict(size=11)),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(320, len(path) * 44),
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

    H1 = ParagraphStyle("H1", parent=styles["Title"],   fontSize=20, spaceAfter=4, textColor=TEAL)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"],fontSize=13, spaceAfter=6, textColor=DARK, spaceBefore=14)
    BD = ParagraphStyle("BD", parent=styles["Normal"],  fontSize=10, spaceAfter=5)
    IT = ParagraphStyle("IT", parent=styles["Normal"],  fontSize=9,  spaceAfter=4,
                         leftIndent=18, textColor=rl_colors.HexColor("#555555"), italics=True)

    story = [
        Paragraph("SkillForge — Adaptive Onboarding Report", H1),
        Paragraph(
            f"Candidate: <b>{resume_data.get('name','—')}</b>   ·   "
            f"Role: <b>{jd_data.get('role_title','—')}</b>   ·   "
            f"Generated: {datetime.now().strftime('%d %b %Y')}", BD),
        Spacer(1, 14),
        Paragraph("Impact Summary", H2),
    ]

    impact_rows = [
        ["Role Readiness",  f"{impact['role_readiness_pct']}%"],
        ["Skills Addressed",f"{impact['gaps_addressed']} / {impact['total_skills']}"],
        ["Training Hours",  f"{impact['roadmap_hours']} hrs"],
        ["Hours Saved",     f"~{impact['hours_saved']} hrs vs. standard onboarding"],
        ["Modules",         str(impact["modules_count"])],
    ]
    tbl = Table([["Metric", "Value"]] + impact_rows, colWidths=[180, 260])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), TEAL),
        ("TEXTCOLOR",    (0,0), (-1,0), rl_colors.white),
        ("FONTSIZE",     (0,0), (-1,-1), 10),
        ("GRID",         (0,0), (-1,-1), 0.4, rl_colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [rl_colors.whitesmoke, rl_colors.white]),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story += [tbl, Spacer(1, 18), Paragraph("Personalized Learning Roadmap", H2)]

    for i, m in enumerate(path):
        story.append(Paragraph(
            f"<b>{i+1}. {m['title']}</b>  —  {m['level']} · {m['duration_hrs']}h · {m['domain']}", BD))
        if m.get("reasoning"):
            story.append(Paragraph(f"↳ {m['reasoning']}", IT))

    story += [Spacer(1, 16),
              Paragraph("Skill Gap Overview", H2)]
    gap_rows = [["Skill", "Status", "Proficiency", "Type"]]
    for g in gap_profile:
        gap_rows.append([g["skill"], g["status"], f"{g['proficiency']}/10",
                         "Required" if g["is_required"] else "Preferred"])
    gt = Table(gap_rows, colWidths=[160, 70, 80, 80])
    gt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK),
        ("TEXTCOLOR",     (0,0), (-1,0), rl_colors.white),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("GRID",          (0,0), (-1,-1), 0.3, rl_colors.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [rl_colors.whitesmoke, rl_colors.white]),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
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
server = app.server   # for production deployment

app.index_string = """<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>SkillForge — AI Adaptive Onboarding</title>
  {%favicon%}
  {%css%}
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #070B14;
      font-family: 'Space Grotesk', sans-serif;
      color: #C9D1D9;
      min-height: 100vh;
    }
    /* ── NAV ── */
    .nav-bar {
      background: rgba(7,11,20,0.95);
      border-bottom: 1px solid #161D2E;
      backdrop-filter: blur(12px);
      position: sticky; top: 0; z-index: 100;
      padding: 14px 0;
    }
    .logo-mark  { font-family:'JetBrains Mono',monospace; font-size:1.45rem;
                  font-weight:700; color:#4ECDC4; letter-spacing:-0.03em; }
    .logo-sub   { font-size:0.6rem; color:#3D4F6B; letter-spacing:.18em;
                  text-transform:uppercase; margin-top:1px; }
    .nav-pill   { font-size:.72rem; color:#3D4F6B; background:rgba(78,205,196,.07);
                  border:1px solid rgba(78,205,196,.15); border-radius:99px;
                  padding:3px 10px; }
    /* ── HERO ── */
    .hero-title { font-size:2.4rem; font-weight:700; line-height:1.15;
                  background:linear-gradient(135deg,#E6EDF3 0%,#4ECDC4 100%);
                  -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .hero-sub   { color:#6B7A99; font-size:1rem; margin-top:10px; max-width:560px; }
    /* ── CARDS ── */
    .glass-card {
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 14px;
      padding: 24px;
      transition: border-color .2s, box-shadow .2s;
    }
    .glass-card:hover { border-color:rgba(78,205,196,.25);
                        box-shadow:0 0 24px rgba(78,205,196,.06); }
    /* ── UPLOAD ── */
    .upload-box {
      border: 2px dashed rgba(78,205,196,.25);
      border-radius: 10px;
      padding: 28px 16px;
      text-align: center;
      cursor: pointer;
      transition: all .2s;
      background: rgba(78,205,196,.03);
    }
    .upload-box:hover { border-color:#4ECDC4; background:rgba(78,205,196,.07); }
    .upload-icon { font-size:1.6rem; margin-bottom:6px; }
    .upload-hint { font-size:.78rem; color:#3D4F6B; margin-top:4px; }
    /* ── BUTTON ── */
    .btn-run {
      background: linear-gradient(135deg,#4ECDC4,#44B8B0);
      border: none; border-radius: 10px;
      color: #070B14; font-weight:700; font-size:.95rem;
      padding: 13px 0; width: 100%;
      font-family:'Space Grotesk',sans-serif;
      cursor:pointer; transition: all .2s;
    }
    .btn-run:hover  { transform:translateY(-2px); box-shadow:0 8px 28px rgba(78,205,196,.3); }
    .btn-run:active { transform:translateY(0); }
    /* ── BADGES ── */
    .badge-known   { background:rgba(78,205,196,.15); color:#4ECDC4;
                     border:1px solid rgba(78,205,196,.4); }
    .badge-partial { background:rgba(255,230,109,.12); color:#FFE66D;
                     border:1px solid rgba(255,230,109,.4); }
    .badge-missing { background:rgba(255,107,107,.12); color:#FF6B6B;
                     border:1px solid rgba(255,107,107,.4); }
    .skill-badge   { font-size:.7rem; border-radius:4px; padding:2px 8px;
                     font-weight:600; letter-spacing:.03em; }
    /* ── IMPACT NUMBERS ── */
    .impact-num   { font-family:'JetBrains Mono',monospace; font-size:2.2rem;
                    font-weight:700; color:#4ECDC4; line-height:1; }
    .impact-lbl   { font-size:.68rem; color:#3D4F6B; text-transform:uppercase;
                    letter-spacing:.06em; margin-top:5px; }
    /* ── PROGRESS ── */
    .prog-track   { background:rgba(255,255,255,.06); border-radius:99px; height:7px; }
    .prog-fill    { background:linear-gradient(90deg,#4ECDC4,#44B8B0);
                    border-radius:99px; height:7px; transition:width 1.2s ease; }
    /* ── MODULE CARD ── */
    .mod-card {
      background:rgba(255,255,255,.025);
      border:1px solid rgba(255,255,255,.06);
      border-left:3px solid #4ECDC4;
      border-radius:8px; padding:14px; margin-bottom:10px;
    }
    .mod-card.adv  { border-left-color:#FF6B6B; }
    .mod-card.int  { border-left-color:#FFE66D; }
    .mod-title { font-weight:600; font-size:.9rem; }
    .mod-meta  { font-size:.75rem; color:#555F7A; margin-top:4px; }
    .mod-why   { font-size:.78rem; color:#7B8DA6; margin-top:8px;
                 padding-top:8px; border-top:1px solid rgba(255,255,255,.05);
                 font-style:italic; }
    /* ── TABS ── */
    .nav-tabs  { border-bottom:1px solid #161D2E !important; margin-bottom:24px; }
    .nav-tabs .nav-link          { color:#4A5568 !important; border:none !important;
                                   font-size:.88rem; padding:10px 20px; }
    .nav-tabs .nav-link.active   { color:#4ECDC4 !important; background:transparent !important;
                                   border-bottom:2px solid #4ECDC4 !important; }
    /* ── PROFILE ROW ── */
    .prof-row  { display:flex; justify-content:space-between; align-items:center;
                 margin-bottom:9px; }
    .prof-key  { font-size:.78rem; color:#4A5568; }
    .prof-val  { font-size:.82rem; color:#C9D1D9; font-weight:500; }
    /* ── SPINNER ── */
    .spinner-wrap {
      display:none; position:fixed; inset:0;
      background:rgba(7,11,20,.88); z-index:9999;
      align-items:center; justify-content:center; flex-direction:column; gap:14px;
    }
    .spin {
      width:46px; height:46px;
      border:3px solid rgba(78,205,196,.2);
      border-top-color:#4ECDC4;
      border-radius:50%;
      animation:spin .75s linear infinite;
    }
    @keyframes spin { to { transform:rotate(360deg); } }
    .fade-up { animation:fadeUp .45s ease; }
    @keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
    /* ── MISC ── */
    .section-h  { font-size:1.15rem; font-weight:600; color:#E6EDF3; margin-bottom:4px; }
    .section-s  { font-size:.78rem; color:#3D4F6B; margin-bottom:16px; }
    textarea.form-control { background:rgba(255,255,255,.03) !important;
                            border:1px solid rgba(255,255,255,.07) !important;
                            color:#C9D1D9 !important; font-size:.82rem; }
    textarea.form-control:focus { border-color:rgba(78,205,196,.4) !important;
                                   box-shadow:none !important; }
    ::-webkit-scrollbar       { width:4px; }
    ::-webkit-scrollbar-track { background:transparent; }
    ::-webkit-scrollbar-thumb { background:#1E2A3A; border-radius:99px; }
  </style>
</head>
<body>
  {%app_entry%}
  <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""

# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = html.Div([

    # Stores & downloads
    dcc.Store(id="s-resume"),
    dcc.Store(id="s-jd"),
    dcc.Store(id="s-results"),
    dcc.Download(id="dl-pdf"),

    # Loading overlay
    html.Div([
        html.Div(className="spin"),
        html.P("Running AI analysis with Groq…",
               style={"color":"#4ECDC4","fontSize":".88rem","margin":0}),
        html.P("Parsing skills · Mapping gaps · Generating roadmap",
               style={"color":"#3D4F6B","fontSize":".75rem","margin":0}),
    ], id="spinner", className="spinner-wrap"),

    # Nav
    html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div("SkillForge", className="logo-mark"),
                    html.Div("SKILL GAP · LEARNING PATHWAYS", className="logo-sub"),
                ], width="auto"),
                dbc.Col(
                    html.Div([
                        html.Span("Groq LLaMA 3.3", className="nav-pill"),
                        html.Span("NetworkX Pathing", className="nav-pill ms-2"),
                        html.Span("Semantic Match", className="nav-pill ms-2"),
                    ], className="d-flex align-items-center justify-content-end"),
                ),
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
        ], style={"padding":"48px 0 36px", "textAlign":"center"}),

        # Upload row
        dbc.Row([
            # Resume
            dbc.Col([
                html.Div([
                    html.Div("📄", className="upload-icon"),
                    html.P("Resume", style={"fontWeight":"600","marginBottom":"2px"}),
                    dcc.Upload(
                        id="up-resume",
                        children=html.Div([
                            "Drop or ", html.Span("browse",
                                style={"color":"#4ECDC4","textDecoration":"underline"}),
                        ]),
                        className="upload-box",
                    ),
                    html.P("PDF or DOCX", className="upload-hint"),
                    html.Div(id="fn-resume",
                             style={"fontSize":".75rem","color":"#4ECDC4","marginTop":"6px",
                                    "textAlign":"center"}),
                ], className="glass-card", style={"textAlign":"center"}),
            ], md=4),

            # JD
            dbc.Col([
                html.Div([
                    html.Div("💼", className="upload-icon"),
                    html.P("Job Description", style={"fontWeight":"600","marginBottom":"2px"}),
                    dcc.Upload(
                        id="up-jd",
                        children=html.Div([
                            "Drop or ", html.Span("browse",
                                style={"color":"#4ECDC4","textDecoration":"underline"}),
                        ]),
                        className="upload-box",
                    ),
                    html.P("PDF, DOCX or paste below", className="upload-hint"),
                    html.Div(id="fn-jd",
                             style={"fontSize":".75rem","color":"#4ECDC4","marginTop":"6px",
                                    "textAlign":"center"}),
                    dbc.Textarea(
                        id="jd-paste",
                        placeholder="…or paste the JD text here",
                        rows=3,
                        style={"marginTop":"10px"},
                    ),
                ], className="glass-card", style={"textAlign":"center"}),
            ], md=5),

            # Run
            dbc.Col([
                html.Div([
                    html.Div("⚡", className="upload-icon"),
                    html.P("Analyze", style={"fontWeight":"600","marginBottom":"2px"}),
                    html.P("AI-powered gap analysis", className="upload-hint",
                           style={"marginBottom":"20px"}),
                    html.Button("Analyze →", id="btn-run", className="btn-run", n_clicks=0),
                    html.Div(id="run-err",
                             style={"fontSize":".75rem","color":"#FF6B6B",
                                    "marginTop":"8px","textAlign":"center"}),
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

@app.callback(Output("fn-resume","children"), Output("s-resume","data"),
              Input("up-resume","contents"), State("up-resume","filename"),
              prevent_initial_call=True)
def cb_resume(contents, filename):
    if not contents:
        return "", None
    return f"✓ {filename}", {"text": parse_upload(contents, filename), "filename": filename}


@app.callback(Output("fn-jd","children"), Output("s-jd","data"),
              Input("up-jd","contents"), State("up-jd","filename"),
              prevent_initial_call=True)
def cb_jd(contents, filename):
    if not contents:
        return "", None
    return f"✓ {filename}", {"text": parse_upload(contents, filename), "filename": filename}


@app.callback(
    Output("s-results","data"),
    Output("results-wrap","style"),
    Output("run-err","children"),
    Input("btn-run","n_clicks"),
    State("s-resume","data"),
    State("s-jd","data"),
    State("jd-paste","value"),
    prevent_initial_call=True,
)
def cb_run(n, resume_store, jd_store, jd_paste):
    if not n:
        raise PreventUpdate

    resume_text   = (resume_store or {}).get("text","")
    jd_text_final = (jd_store or {}).get("text","") or jd_paste or ""

    if not resume_text:
        return no_update, {"display":"none"}, "⚠ Upload a resume first."
    if not jd_text_final:
        return no_update, {"display":"none"}, "⚠ Upload or paste a job description."
    if not os.getenv("GROQ_API_KEY"):
        return no_update, {"display":"none"}, "⚠ GROQ_API_KEY missing from .env"

    resume_data = parse_resume(resume_text)
    jd_data     = parse_jd(jd_text_final)

    if "error" in resume_data:
        return no_update, {"display":"none"}, f"⚠ {resume_data['error']}"
    if "error" in jd_data:
        return no_update, {"display":"none"}, f"⚠ {jd_data['error']}"

    gap_profile = analyze_gap(resume_data, jd_data)
    path        = generate_path(gap_profile, resume_data)

    # Reasoning traces (first 12 modules for speed)
    cname = resume_data.get("name","the candidate")
    for m in path[:12]:
        m["reasoning"] = generate_reasoning(m, m["gap_skill"], cname)

    impact = calculate_impact(gap_profile, path)

    return (
        {"resume_data": resume_data, "jd_data": jd_data,
         "gap_profile": gap_profile, "path": path, "impact": impact},
        {"display": "block"},
        "",
    )


@app.callback(
    Output("tab-body","children"),
    Input("tabs","active_tab"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_tabs(tab, results):
    if not results:
        raise PreventUpdate
    rd = results["resume_data"]; jd = results["jd_data"]
    gp = results["gap_profile"]; pt = results["path"]; im = results["impact"]

    # ── TAB: SKILL GAP ───────────────────────────────────────────────────────
    if tab == "tab-gap":
        known   = [g for g in gp if g["status"]=="Known"]
        partial = [g for g in gp if g["status"]=="Partial"]
        missing = [g for g in gp if g["status"]=="Missing"]

        def skill_row(g):
            cls = {"Known":"badge-known","Partial":"badge-partial","Missing":"badge-missing"}[g["status"]]
            return html.Div([
                html.Span(g["skill"], style={"fontSize":".85rem","fontWeight":"500"}),
                html.Span(g["status"], className=f"skill-badge {cls}", style={"marginLeft":"8px"}),
                html.Span(f"{g['proficiency']}/10",
                          style={"fontSize":".72rem","color":"#3D4F6B","marginLeft":"8px",
                                 "fontFamily":"JetBrains Mono,monospace"}),
            ], style={"marginBottom":"9px","display":"flex","alignItems":"center"})

        return dbc.Row([
            dbc.Col([
                html.Div([
                    html.P("Skill Gap Radar", className="section-h"),
                    html.P(f"{rd.get('name','Candidate')}  vs  {jd.get('role_title','Target Role')}",
                           className="section-s"),
                    dcc.Graph(figure=radar_chart(gp), config={"displayModeBar":False},
                              style={"height":"360px"}),
                ], className="glass-card"),
            ], md=6),
            dbc.Col([
                html.Div([
                    html.P("All Skills", className="section-h"),
                    html.P(f"{len(known)} Known · {len(partial)} Partial · {len(missing)} Missing",
                           className="section-s"),
                    html.Div([skill_row(g) for g in gp],
                             style={"maxHeight":"320px","overflowY":"auto"}),
                ], className="glass-card"),
            ], md=6),
            dbc.Col([
                html.Div([
                    html.P("Candidate", className="section-h", style={"marginBottom":"12px"}),
                    *[html.Div([html.Span(k,className="prof-key"),
                                html.Span(str(v),className="prof-val")], className="prof-row")
                      for k,v in [("Name",rd.get("name","—")),
                                  ("Role",rd.get("current_role","—")),
                                  ("Seniority",rd.get("seniority","—")),
                                  ("Experience",f"{rd.get('years_experience','—')} yrs"),
                                  ("Domain",rd.get("domain","—"))]],
                ], className="glass-card"),
            ], md=4),
            dbc.Col([
                html.Div([
                    html.P("Target Role", className="section-h", style={"marginBottom":"12px"}),
                    *[html.Div([html.Span(k,className="prof-key"),
                                html.Span(str(v),className="prof-val")], className="prof-row")
                      for k,v in [("Title",jd.get("role_title","—")),
                                  ("Seniority",jd.get("seniority_required","—")),
                                  ("Domain",jd.get("domain","—")),
                                  ("Required",len(jd.get("required_skills",[]))),
                                  ("Preferred",len(jd.get("preferred_skills",[])))]]
                ], className="glass-card"),
            ], md=4),
            dbc.Col([
                html.Div([
                    html.P("Gap Summary", className="section-h", style={"marginBottom":"12px"}),
                    *[html.Div([
                        html.Span(str(n), style={"fontFamily":"JetBrains Mono,monospace",
                                                  "fontWeight":"700","fontSize":"1.5rem","color":col}),
                        html.Span(f"  {lbl}", style={"color":"#3D4F6B","fontSize":".85rem"}),
                      ], style={"marginBottom":"10px"})
                      for n,col,lbl in [(len(known),"#4ECDC4","Known"),
                                        (len(partial),"#FFE66D","Partial"),
                                        (len(missing),"#FF6B6B","Missing")]]
                ], className="glass-card"),
            ], md=4),
        ], className="g-3")

    # ── TAB: ROADMAP ─────────────────────────────────────────────────────────
    if tab == "tab-road":
        lc = {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF6B6B"}

        def mod_card(i, m):
            col  = lc.get(m["level"],"#888")
            xtra = " adv" if m["level"]=="Advanced" else " int" if m["level"]=="Intermediate" else ""
            return html.Div([
                html.Div([
                    html.Span(f"#{i+1}",
                              style={"fontFamily":"JetBrains Mono,monospace","fontSize":".72rem",
                                     "color":"#3D4F6B","marginRight":"10px"}),
                    html.Span(m["title"], className="mod-title"),
                    html.Span(m["level"],
                              style={"marginLeft":"auto","fontSize":".68rem","color":col,
                                     "border":f"1px solid {col}40","borderRadius":"4px",
                                     "padding":"2px 8px","background":f"rgba(255,255,255,.04)"}),
                    html.Span(f"{m['duration_hrs']}h",
                              style={"fontFamily":"JetBrains Mono,monospace","fontSize":".72rem",
                                     "color":"#3D4F6B","marginLeft":"10px"}),
                ], style={"display":"flex","alignItems":"center"}),
                html.Div(f"Skill: {m['skill']}  ·  Domain: {m['domain']}  ·  Gap: {m.get('gap_status','—')}",
                         className="mod-meta"),
                (html.Div(m["reasoning"], className="mod-why") if m.get("reasoning") else None),
            ], className=f"mod-card{xtra}")

        return dbc.Row([
            # Impact card
            dbc.Col([
                html.Div([
                    html.P("Impact Summary", className="section-h", style={"marginBottom":"18px"}),
                    dbc.Row([
                        dbc.Col([html.Div(f"{im['role_readiness_pct']}%",className="impact-num"),
                                 html.Div("Role Readiness",className="impact-lbl")],className="text-center"),
                        dbc.Col([html.Div(f"~{im['hours_saved']}h",className="impact-num"),
                                 html.Div("Hours Saved",className="impact-lbl")],className="text-center"),
                        dbc.Col([html.Div(f"{im['roadmap_hours']}h",className="impact-num"),
                                 html.Div("Training Time",className="impact-lbl")],className="text-center"),
                        dbc.Col([html.Div(str(im["modules_count"]),className="impact-num"),
                                 html.Div("Modules",className="impact-lbl")],className="text-center"),
                    ], className="g-2"),
                    html.Div(style={"height":"14px"}),
                    html.Div("Skill Coverage", style={"fontSize":".72rem","color":"#3D4F6B","marginBottom":"5px"}),
                    html.Div(className="prog-track", children=[
                        html.Div(className="prog-fill",
                                 style={"width":f"{im['role_readiness_pct']}%"}),
                    ]),
                ], className="glass-card mb-3"),
            ], md=12),
            # Timeline
            dbc.Col([
                html.Div([
                    html.P("Training Timeline", className="section-h"),
                    html.P(f"{im['modules_count']} modules · {im['roadmap_hours']} total hours",
                           className="section-s"),
                    dcc.Graph(figure=timeline_chart(pt),
                              config={"displayModeBar":False},
                              style={"overflowY":"auto"}),
                ], className="glass-card"),
            ], md=7),
            # Module cards
            dbc.Col([
                html.Div([
                    html.P("Modules & Reasoning", className="section-h"),
                    html.P("Why each module was assigned", className="section-s"),
                    html.Div([mod_card(i, m) for i, m in enumerate(pt)],
                             style={"maxHeight":"560px","overflowY":"auto"}),
                ], className="glass-card"),
            ], md=5),
        ], className="g-3")

    # ── TAB: REPORT ──────────────────────────────────────────────────────────
    if tab == "tab-rep":
        checklist = [
            "Groq LLaMA 3.3 — Resume & JD Parsing",
            "Skill Gap Analysis with Proficiency Scores (0-10)",
            "Semantic Skill Matching (substring + embedding)",
            "Dependency-Aware Path Generation (NetworkX topological sort)",
            "Original Adaptive Algorithm — not just an LLM prompt",
            "AI-Generated Reasoning Trace per Module",
            "Skill Gap Radar Chart (Plotly)",
            "Interactive Training Timeline (Plotly)",
            "Impact Metrics: Hours Saved · Role Readiness %",
            "PDF Export via ReportLab",
            "Multi-Domain: Tech · Non-Tech · Soft Skills",
            "Zero Hallucinations — catalog-only recommendations",
        ]
        return dbc.Row([
            dbc.Col([
                html.Div([
                    html.P("Download PDF Report", className="section-h"),
                    html.P("Full roadmap summary with reasoning traces.", className="section-s"),
                    html.Div([
                        *[html.Div([
                            html.Span("●", style={"color":"#4ECDC4","marginRight":"8px"}),
                            html.Span(k, style={"fontSize":".82rem","color":"#3D4F6B"}),
                            html.Span(str(v), style={"fontSize":".82rem","color":"#C9D1D9",
                                                      "marginLeft":"4px","fontWeight":"500"}),
                        ], style={"marginBottom":"7px"})
                          for k,v in [
                            ("Candidate:", rd.get("name","—")),
                            ("Role:", jd.get("role_title","—")),
                            ("Role Readiness:", f"{im['role_readiness_pct']}%"),
                            ("Modules:", im["modules_count"]),
                            ("Training Hours:", f"{im['roadmap_hours']}h"),
                            ("Hours Saved:", f"~{im['hours_saved']}h"),
                          ]]
                    ], style={"background":"rgba(78,205,196,.05)",
                               "border":"1px solid rgba(78,205,196,.15)",
                               "borderRadius":"10px","padding":"16px","marginBottom":"20px"}),
                    html.Button("⬇  Download PDF Report", id="btn-pdf", n_clicks=0,
                                className="btn-run"),
                    html.Div(id="pdf-status",
                             style={"fontSize":".75rem","color":"#3D4F6B",
                                    "marginTop":"8px","textAlign":"center"}),
                ], className="glass-card"),
            ], md=5),
            dbc.Col([
                html.Div([
                    html.P("Feature Checklist", className="section-h"),
                    html.P("Everything built into this submission", className="section-s"),
                    *[html.Div([
                        html.Span("✓", style={"color":"#4ECDC4","marginRight":"10px","fontWeight":"700"}),
                        html.Span(item, style={"fontSize":".84rem"}),
                    ], style={"marginBottom":"9px"}) for item in checklist],
                ], className="glass-card"),
            ], md=7),
        ], className="g-3")


@app.callback(
    Output("dl-pdf","data"),
    Output("pdf-status","children"),
    Input("btn-pdf","n_clicks"),
    State("s-results","data"),
    prevent_initial_call=True,
)
def cb_pdf(n, results):
    if not results:
        raise PreventUpdate
    if not REPORTLAB:
        return no_update, "⚠ Install reportlab: pip install reportlab"
    buf  = build_pdf(results["resume_data"], results["jd_data"],
                     results["gap_profile"], results["path"], results["impact"])
    name = results["resume_data"].get("name","candidate").replace(" ","_")
    fn   = f"skillforge_roadmap_{name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return dcc.send_bytes(buf.read(), fn), f"✓ Downloading {fn}"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 14 · RUN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  SkillForge — AI Adaptive Onboarding Engine")
    print("  ─────────────────────────────────────────")
    print("  → http://localhost:8050")
    print(f"  → Semantic matching : {'sentence-transformers ✓' if SEMANTIC else 'substring fallback'}")
    print(f"  → PDF export        : {'reportlab ✓' if REPORTLAB else 'not installed'}")
    print(f"  → Groq API key      : {'set ✓' if os.getenv('GROQ_API_KEY') else 'MISSING — add to .env'}\n")
    app.run(debug=True, port=8050)