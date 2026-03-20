# =============================================================================
#  main.py — SkillForge v5  |  Streamlit Edition
#  UI:  Matches screenshot exactly — dark theme, 3-column card layout
#  API: Groq key lives in .env ONLY — never exposed to frontend
#  Run: streamlit run main.py
#  FIX: Sample buttons now correctly populate text areas via session_state
# =============================================================================

import os, sys, json, io, re, time, hashlib, shelve, threading, argparse, base64
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="SkillForge — Skill Gap · Learning Pathways",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Backend imports ───────────────────────────────────────────────────────────
import plotly.graph_objects as go
import networkx as nx
import pdfplumber
from docx import Document
from groq import Groq

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    REPORTLAB = True
except Exception:
    REPORTLAB = False

# ── Semantic matching (background load, optional) ─────────────────────────────
SEMANTIC = False
_ST      = None
_CEMBS   = None

def _load_semantic_bg():
    global SEMANTIC, _ST, _CEMBS
    try:
        from sentence_transformers import SentenceTransformer
        _ST    = SentenceTransformer("all-MiniLM-L6-v2")
        _CEMBS = _ST.encode([c["skill"].lower() for c in CATALOG])
        SEMANTIC = True
    except Exception:
        pass

# ── Groq client — key from .env ONLY, never shown in UI ──────────────────────
_GROQ_KEY = os.getenv("GROQ_API_KEY", "")
if not _GROQ_KEY:
    st.error(
        "**GROQ_API_KEY missing** — create a `.env` file with:\n\n"
        "```\nGROQ_API_KEY=gsk_your_key_here\n```\n\n"
        "Get a free key at [console.groq.com](https://console.groq.com)"
    )
    st.stop()

GROQ_CLIENT  = Groq(api_key=_GROQ_KEY)
MODEL_FAST   = "meta-llama/llama-4-scout-17b-16e-instruct"
MODEL_MICRO  = "llama-3.1-8b-instant"
CURRENT_YEAR = datetime.now().year

# =============================================================================
#  CATALOG — 47 courses
# =============================================================================
CATALOG: List[Dict] = [
    {"id":"PY01","title":"Python Fundamentals","skill":"Python","domain":"Tech","level":"Beginner","duration_hrs":6,"prereqs":[]},
    {"id":"PY02","title":"Python Intermediate: OOP & Modules","skill":"Python","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["PY01"]},
    {"id":"PY03","title":"Python Advanced: Async & Decorators","skill":"Python","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["PY02"]},
    {"id":"DA01","title":"Data Analysis with Pandas","skill":"Data Analysis","domain":"Tech","level":"Beginner","duration_hrs":7,"prereqs":["PY01"]},
    {"id":"DA02","title":"Data Visualization (Matplotlib & Seaborn)","skill":"Data Visualization","domain":"Tech","level":"Intermediate","duration_hrs":5,"prereqs":["DA01"]},
    {"id":"DA03","title":"Statistical Analysis & Hypothesis Testing","skill":"Statistics","domain":"Tech","level":"Intermediate","duration_hrs":8,"prereqs":["DA01"]},
    {"id":"ML01","title":"Machine Learning Foundations","skill":"Machine Learning","domain":"Tech","level":"Beginner","duration_hrs":10,"prereqs":["DA01","DA03"]},
    {"id":"ML02","title":"Supervised Learning: Regression & Classification","skill":"Machine Learning","domain":"Tech","level":"Intermediate","duration_hrs":12,"prereqs":["ML01"]},
    {"id":"ML03","title":"Deep Learning with PyTorch","skill":"Deep Learning","domain":"Tech","level":"Advanced","duration_hrs":15,"prereqs":["ML02"]},
    {"id":"ML04","title":"NLP & Large Language Models","skill":"NLP","domain":"Tech","level":"Advanced","duration_hrs":14,"prereqs":["ML02"]},
    {"id":"ML05","title":"MLOps & Model Deployment","skill":"MLOps","domain":"Tech","level":"Advanced","duration_hrs":10,"prereqs":["ML02","DO02"]},
    {"id":"SQL01","title":"SQL Fundamentals","skill":"SQL","domain":"Tech","level":"Beginner","duration_hrs":5,"prereqs":[]},
    {"id":"SQL02","title":"Advanced SQL: Window Functions & Optimization","skill":"SQL","domain":"Tech","level":"Advanced","duration_hrs":7,"prereqs":["SQL01"]},
    {"id":"SQL03","title":"Database Design & NoSQL","skill":"Databases","domain":"Tech","level":"Intermediate","duration_hrs":6,"prereqs":["SQL01"]},
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
    {"id":"PM01","title":"Project Management Essentials (PMI)","skill":"Project Management","domain":"Soft","level":"Intermediate","duration_hrs":8,"prereqs":["LD01"]},
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

MARKET_DEMAND: Dict[str, int] = {
    "python":3,"machine learning":3,"deep learning":3,"aws":3,"docker":3,
    "sql":3,"react":3,"kubernetes":3,"mlops":3,"fastapi":3,"data analysis":3,
    "cloud computing":3,"ci/cd":3,"nlp":3,"rest apis":3,"javascript":3,
    "statistics":2,"data visualization":2,"gcp":2,"linux":2,"html/css":2,
    "agile":2,"databases":2,"cybersecurity":2,"communication":2,"leadership":2,
    "project management":2,"recruitment":2,"performance management":2,
    "financial analysis":2,"application security":2,"process improvement":2,
    "human resources":1,"accounting":1,"budgeting":1,"logistics":1,"scrum":1,
    "collaboration":1,"strategic planning":1,"warehouse management":1,
    "inventory management":1,"l&d strategy":1,
}
OBSOLESCENCE_RISK: Dict[str, str] = {
    "jquery":"Replaced by vanilla JS and React",
    "php":"Declining; Python/Node dominant",
    "hadoop":"Replaced by Spark + cloud-native",
    "excel vba":"Power Query and Python replacing VBA",
    "manual testing":"AI-assisted automation replacing manual QA",
    "waterfall":"Industry fully shifted to Agile/DevOps",
}
TRANSFER_MAP: Dict[str, Dict[str, int]] = {
    "python":{"machine learning":40,"mlops":35,"fastapi":60,"data analysis":50,"deep learning":30,"rest apis":45},
    "machine learning":{"deep learning":50,"mlops":45,"nlp":40,"statistics":30},
    "javascript":{"react":55,"rest apis":40},
    "sql":{"data analysis":35,"databases":60},
    "docker":{"kubernetes":45,"ci/cd":35,"mlops":30},
    "linux":{"docker":40,"ci/cd":30,"aws":20},
    "aws":{"gcp":30,"cloud computing":70,"mlops":25},
    "human resources":{"recruitment":45,"performance management":40,"employee relations":35},
    "communication":{"leadership":35,"project management":25},
    "leadership":{"strategic planning":40},
    "financial analysis":{"budgeting":55,"accounting":40},
}
SENIORITY_MAP = {"Junior":0,"Mid":1,"Senior":2,"Lead":3}

SAMPLES = {
    "junior_swe":{
        "label":"👨‍💻 Junior SWE",
        "resume":"John Smith\nJunior Software Developer | 1 year experience\nSkills: Python (basic, 4/10), HTML/CSS, some JavaScript\nEducation: B.Tech Computer Science 2023\nProjects: Built a todo app using Flask. Familiar with Git basics.\nNo professional cloud or DevOps experience.",
        "jd":"Software Engineer Full Stack - Mid Level\nRequired: Python, React, FastAPI, Docker, SQL, REST APIs, AWS\nPreferred: Kubernetes, CI/CD\nSeniority: Mid | Domain: Tech",
    },
    "senior_ds":{
        "label":"🧪 Senior Data Scientist",
        "resume":"Priya Patel\nSenior Data Scientist | 7 years experience\nSkills: Python (expert, 9/10), Machine Learning (expert), Deep Learning (PyTorch, 8/10), SQL (advanced, 8/10), AWS SageMaker (7/10)\nLast used NLP: 2022. Last used MLOps: 2021.\nLed team of 5. Published 3 ML papers.",
        "jd":"Lead Data Scientist - AI Products\nRequired: Python, Machine Learning, Deep Learning, NLP, MLOps, SQL, AWS\nPreferred: GCP, Kubernetes, Leadership\nSeniority: Lead | Domain: Tech",
    },
    "hr_manager":{
        "label":"💼 HR Manager",
        "resume":"Amara Johnson\nHR Coordinator | 3 years experience\nSkills: Human Resources (intermediate, 6/10), Recruitment (good, 7/10), Microsoft Office\nSome performance review experience. No formal L&D training.",
        "jd":"HR Manager - People and Culture\nRequired: Human Resources, Recruitment, Performance Management, Employee Relations\nPreferred: L&D Strategy, Communication, Leadership\nSeniority: Senior | Domain: Non-Tech",
    },
}

# =============================================================================
#  DEPENDENCY GRAPH
# =============================================================================
def _build_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    for c in CATALOG:
        G.add_node(c["id"], **c)
        for p in c["prereqs"]:
            G.add_edge(p, c["id"])
    return G

SKILL_GRAPH = _build_graph()

# =============================================================================
#  FILE PARSERS
# =============================================================================
def parse_uploaded_file(f) -> Tuple[str, Optional[str]]:
    """Streamlit UploadedFile → (text, image_b64|None)"""
    if f is None:
        return "", None
    name = f.name.lower()
    raw  = f.read()
    if name.endswith(".pdf"):
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages), None
        except Exception as e:
            return f"[PDF error: {e}]", None
    if name.endswith(".docx"):
        try:
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs), None
        except Exception as e:
            return f"[DOCX error: {e}]", None
    if any(name.endswith(x) for x in [".jpg",".jpeg",".png",".webp"]):
        media = ("image/jpeg" if name.endswith((".jpg",".jpeg"))
                 else "image/png" if name.endswith(".png") else "image/webp")
        b64 = base64.b64encode(raw).decode()
        return "", f"data:{media};base64,{b64}"
    return raw.decode("utf-8", errors="ignore"), None

# =============================================================================
#  GROQ — server-side only
# =============================================================================
_audit_log: List[dict] = []

def _groq_call(prompt: str, system: str, model: str = MODEL_FAST,
               max_tokens: int = 2800, image_b64: Optional[str] = None) -> dict:
    content: Any = prompt
    if image_b64:
        content = [{"type":"image_url","image_url":{"url":image_b64}},{"type":"text","text":prompt}]
    messages = [{"role":"system","content":system},{"role":"user","content":content}]
    t0 = time.time()
    try:
        r = GROQ_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1,
            max_tokens=max_tokens,
            response_format={"type":"json_object"},
        )
        usage   = r.usage
        in_tok  = usage.prompt_tokens     if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        cached_d= getattr(usage,"prompt_tokens_details",None)
        cached_c= getattr(cached_d,"cached_tokens",0) if cached_d else 0
        cost    = round((in_tok*0.00000011)+(out_tok*0.00000034),6)
        _audit_log.append({
            "ts":datetime.now().strftime("%H:%M:%S"),
            "model":model.split("/")[-1][:22],
            "in":in_tok,"out":out_tok,"cached":cached_c,
            "ms":round((time.time()-t0)*1000),
            "cost":cost,"status":"ok",
            "tier":"default",
        })
        return json.loads(r.choices[0].message.content or "{}")
    except json.JSONDecodeError as e:
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),
                            "model":model.split("/")[-1][:22],
                            "status":f"json_err:{e}","in":0,"out":0,"cached":0,"ms":0,"cost":0,"tier":"?"})
        return {"error":"json_parse_failed"}
    except Exception as e:
        err = str(e)
        wait_s = 0
        if "429" in err or "rate_limit_exceeded" in err:
            m = re.search(r"try again in (\d+)m([\d.]+)s", err)
            if m: wait_s = int(m.group(1))*60+float(m.group(2))
            _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),
                                "model":model.split("/")[-1][:22],
                                "status":f"429 wait:{int(wait_s)}s","in":0,"out":0,"cached":0,"ms":0,"cost":0,"tier":"?"})
            return {"error":"rate_limited","wait_seconds":int(wait_s),
                    "message":f"Rate limited. Retry in {int(wait_s//60)}m{int(wait_s%60)}s."}
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),
                            "model":model.split("/")[-1][:22],
                            "status":f"err:{err[:40]}","in":0,"out":0,"cached":0,"ms":0,"cost":0,"tier":"?"})
        return {"error":err}

_MEGA_SYS = """You are a world-class senior tech recruiter, ATS specialist, and L&D expert.
Extract ALL sections in ONE response as valid JSON. Be precise and evidence-based. No hallucinations.
Return ONLY the JSON object — no preamble, no markdown."""

def mega_call(resume_text: str, jd_text: str,
              modules_hint: Optional[List[dict]] = None,
              resume_image_b64: Optional[str] = None) -> dict:
    reasoning_block = ""
    if modules_hint:
        reasoning_block = '\n  "reasoning": {"<module_id>": "<2-sentence why this candidate needs this module>"},'

    prompt = f"""Analyze this resume and job description.

RESUME ({'IMAGE' if resume_image_b64 else 'TEXT'}):
{resume_text[:2000] if not resume_image_b64 else '[See attached image]'}

JOB DESCRIPTION:
{jd_text[:1200]}

Return EXACTLY this JSON:
{{
  "candidate": {{
    "name": "<full name or Unknown>",
    "current_role": "<latest title>",
    "years_experience": <int>,
    "seniority": "<Junior|Mid|Senior|Lead>",
    "domain": "<Tech|Non-Tech|Hybrid>",
    "education": "<degree + field>",
    "skills": [{{"skill":"<n>","proficiency":<0-10>,"year_last_used":<year or 0>,"context":"<1-line evidence>"}}],
    "strengths": ["<s1>","<s2>","<s3>"],
    "red_flags": ["<f1>","<f2>"]
  }},
  "jd": {{
    "role_title": "<title>",
    "seniority_required": "<Junior|Mid|Senior|Lead>",
    "domain": "<Tech|Non-Tech|Hybrid>",
    "required_skills": ["<skill>"],
    "preferred_skills": ["<skill>"],
    "key_responsibilities": ["<resp>"]
  }},
  "audit": {{
    "ats_score": <0-100>,
    "completeness_score": <0-100>,
    "clarity_score": <0-100>,
    "overall_grade": "<A|B|C|D>",
    "ats_issues": ["<issue>"],
    "improvement_tips": ["<tip1>","<tip2>","<tip3>","<tip4>","<tip5>"],
    "missing_keywords": ["<kw>"],
    "interview_talking_points": ["<pt1>","<pt2>","<pt3>"]
  }}{reasoning_block}
}}"""
    return _groq_call(prompt=prompt, system=_MEGA_SYS, model=MODEL_FAST,
                      max_tokens=2800, image_b64=resume_image_b64)

def fetch_live_salary(role: str, location: str = "India") -> dict:
    r = _groq_call(
        f'Search current salary for "{role}" in {location} as of 2026. '
        f'Return JSON: {{"min_lpa":<n>,"max_lpa":<n>,"median_lpa":<n>,"currency":"INR","source":"<site>","note":"<caveats>"}}',
        system="Salary research assistant. Return JSON only.",
        model=MODEL_FAST, max_tokens=300,
    )
    return r if "error" not in r else {"min_lpa":0,"max_lpa":0,"median_lpa":0,"note":"unavailable"}

def rewrite_resume(resume_text: str, jd: dict, missing_kw: List[str]) -> str:
    r = _groq_call(
        f'Rewrite this resume for the target role. Naturally add these missing keywords: {missing_kw[:8]}. '
        f'Keep all facts true. Return JSON: {{"rewritten_resume":"<text>"}}\n\n'
        f'Resume:\n{resume_text[:1500]}\n\nTarget: {jd.get("role_title","--")}  Required: {jd.get("required_skills",[])}',
        system="Expert resume writer. Return JSON only.", model=MODEL_FAST, max_tokens=1500,
    )
    return r.get("rewritten_resume","Could not rewrite resume.")

# =============================================================================
#  CACHE
# =============================================================================
_CACHE_PATH = "/tmp/skillforge_v5_st"
def _ckey(r: str, j: str) -> str: return hashlib.md5((r+"||"+j).encode()).hexdigest()
def cache_get(r: str, j: str) -> Optional[dict]:
    try:
        with shelve.open(_CACHE_PATH) as db: return db.get(_ckey(r,j))
    except Exception: return None
def cache_set(r: str, j: str, v: dict):
    try:
        with shelve.open(_CACHE_PATH) as db: db[_ckey(r,j)] = v
    except Exception: pass

# =============================================================================
#  ANALYSIS ENGINE — pure Python, <50ms, zero API calls
# =============================================================================
def _match_skill(skill: str) -> int:
    sl = skill.lower().replace(".js","").replace(".ts","").replace("(","").replace(")","").strip()
    for i, cs in enumerate(CATALOG_SKILLS):
        if sl == cs or sl in cs or cs in sl: return i
    if SEMANTIC and _ST and _CEMBS is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            sims = cosine_similarity(_ST.encode([sl]), _CEMBS)[0]
            best = int(np.argmax(sims))
            if sims[best] >= 0.52: return best
        except Exception: pass
    tokens = set(sl.split()); best_s, best_i = 0.0, -1
    for i, cs in enumerate(CATALOG_SKILLS):
        ov = len(tokens & set(cs.split())) / max(len(tokens), 1)
        if ov > best_s: best_s, best_i = ov, i
    return best_i if best_s >= 0.4 else -1

def skill_decay(p: int, yr: int) -> Tuple[int, bool]:
    if yr <= 0 or yr >= CURRENT_YEAR - 1: return p, False
    yrs = CURRENT_YEAR - yr
    if yrs <= 2: return p, False
    a = round(p * max(0.5, 1 - yrs/5))
    return a, a < p

def analyze_gap(candidate: dict, jd: dict) -> List[dict]:
    rs = {s["skill"].lower(): s for s in candidate.get("skills",[])}
    all_s = [(s,True) for s in jd.get("required_skills",[])] + [(s,False) for s in jd.get("preferred_skills",[])]
    out = []
    for skill, req in all_s:
        sl = skill.lower().replace(".js","").replace(".ts","").strip()
        status, prof, ctx, dec, orig = "Missing", 0, "", False, 0
        src = rs.get(sl) or next((v for k,v in rs.items() if sl in k or k in sl), None)
        if src:
            raw_p = src.get("proficiency",0); prof,dec = skill_decay(raw_p,src.get("year_last_used",0))
            orig, ctx = raw_p, src.get("context",""); status = "Known" if prof >= 7 else "Partial"
        idx = _match_skill(skill)
        demand = MARKET_DEMAND.get(sl, MARKET_DEMAND.get(skill.lower(),1))
        obs = OBSOLESCENCE_RISK.get(sl)
        out.append({"skill":skill,"status":status,"proficiency":prof,"original_prof":orig,
                    "decayed":dec,"is_required":req,"context":ctx,
                    "catalog_course":CATALOG[idx] if idx>=0 else None,
                    "demand":demand,"obsolescence_risk":obs})
    return out

def seniority_check(c: dict, jd: dict) -> dict:
    cs, rs = c.get("seniority","Mid"), jd.get("seniority_required","Mid")
    gap = SENIORITY_MAP.get(rs,1) - SENIORITY_MAP.get(cs,1)
    return {"has_mismatch":gap>0,"gap_levels":gap,"candidate":cs,"required":rs,
            "add_leadership":gap>=1,"add_strategic":gap>=2}

def build_path(gp: List[dict], c: dict, jd: Optional[dict]=None) -> List[dict]:
    needed: set = set(); id2gap: Dict[str,dict] = {}
    for g in gp:
        if g["status"] == "Known": continue
        co = g.get("catalog_course")
        if not co: continue
        needed.add(co["id"]); id2gap[co["id"]] = g
        try:
            for anc in nx.ancestors(SKILL_GRAPH, co["id"]):
                ad = CATALOG_BY_ID.get(anc)
                if ad and not any(x["status"]=="Known" and x["skill"].lower() in ad["skill"].lower() for x in gp):
                    needed.add(anc)
        except Exception: pass
    if jd:
        sm = seniority_check(c, jd)
        if sm["add_leadership"]: needed.update(["LD01","LD02"])
        if sm["add_strategic"]:  needed.add("LD03")
    sub = SKILL_GRAPH.subgraph(needed)
    try: ordered = list(nx.topological_sort(sub))
    except Exception: ordered = list(needed)
    crit = set()
    try:
        if sub.nodes: crit = set(nx.dag_longest_path(sub))
    except Exception: pass
    path, seen = [], set()
    for cid in ordered:
        if cid in seen: continue
        seen.add(cid); co = CATALOG_BY_ID.get(cid)
        if not co: continue
        g = id2gap.get(cid, {})
        path.append({**co,"gap_skill":g.get("skill",co["skill"]),"gap_status":g.get("status","Prereq"),
                     "priority":(0 if g.get("is_required") else 1, g.get("proficiency",0)),
                     "reasoning":"","is_critical":cid in crit,"demand":g.get("demand",1),
                     "is_required":g.get("is_required",False)})
    path.sort(key=lambda x: x["priority"])
    return path

def calc_impact(gp: List[dict], path: List[dict]) -> dict:
    tot = len(gp); known = sum(1 for g in gp if g["status"]=="Known")
    covered = len({m["gap_skill"] for m in path}); rhrs = sum(m["duration_hrs"] for m in path)
    cur  = min(100, round(known/max(tot,1)*100))
    proj = min(100, round((known+covered)/max(tot,1)*100))
    return {"total_skills":tot,"known_skills":known,"gaps_addressed":covered,
            "roadmap_hours":rhrs,"hours_saved":max(0,60-rhrs),
            "current_fit":cur,"projected_fit":proj,"fit_delta":proj-cur,
            "modules_count":len(path),"critical_count":sum(1 for m in path if m.get("is_critical")),
            "decayed_skills":sum(1 for g in gp if g.get("decayed"))}

def interview_readiness(gp: List[dict], c: dict) -> dict:
    rk=[g for g in gp if g["status"]=="Known"   and g["is_required"]]
    rp=[g for g in gp if g["status"]=="Partial" and g["is_required"]]
    rm=[g for g in gp if g["status"]=="Missing" and g["is_required"]]
    tot=max(len(rk)+len(rp)+len(rm),1)
    sc=max(0,min(100,round((len(rk)+len(rp)*0.4)/tot*100)
                    +{"Junior":5,"Mid":0,"Senior":-5,"Lead":-10}.get(c.get("seniority","Mid"),0)))
    if sc>=75:   v=("Strong",   "#4ECDC4","Ready for most rounds")
    elif sc>=50: v=("Moderate", "#FFE66D","Pass screening; prep gaps")
    elif sc>=30: v=("Weak",     "#FFA726","Gap work before applying")
    else:        v=("Not Ready","#FF6B6B","Significant prep needed")
    return {"score":sc,"label":v[0],"color":v[1],"advice":v[2],
            "req_known":len(rk),"req_partial":len(rp),"req_missing":len(rm)}

def weekly_plan(path: List[dict], hpd: float=2.0) -> List[dict]:
    cap,weeks,cur,hrs,wn = hpd*5,[],[],0.0,1
    for m in path:
        rem=float(m["duration_hrs"])
        while rem>0:
            avail=cap-hrs
            if avail<=0:
                weeks.append({"week":wn,"modules":cur,"total_hrs":hrs}); cur,hrs=[],0.0; wn+=1; avail=cap
            chunk=min(rem,avail)
            ex=next((x for x in cur if x["id"]==m["id"]),None)
            if ex: ex["hrs_this_week"]+=chunk
            else:  cur.append({"id":m["id"],"title":m["title"],"level":m["level"],
                                "domain":m["domain"],"is_critical":m.get("is_critical",False),
                                "hrs_this_week":chunk,"total_hrs":m["duration_hrs"]})
            hrs+=chunk; rem-=chunk
    if cur: weeks.append({"week":wn,"modules":cur,"total_hrs":hrs})
    return weeks

def transfer_map(c: dict, gp: List[dict]) -> List[dict]:
    known={g["skill"].lower() for g in c.get("skills",[]) if g.get("proficiency",0)>=6}
    out=[]
    for g in gp:
        if g["status"]=="Known": continue
        sl=g["skill"].lower()
        for k in known:
            pct=TRANSFER_MAP.get(k,{}).get(sl,0)
            if pct: out.append({"gap_skill":g["skill"],"known_skill":k.title(),"transfer_pct":pct,
                                  "label":f"Your {k.title()} → {pct}% head start on {g['skill']}"})
    return sorted(out,key=lambda x:x["transfer_pct"],reverse=True)

def roi_rank(gp: List[dict], path: List[dict]) -> List[dict]:
    out=[]
    for m in path:
        g=next((x for x in gp if x["skill"]==m.get("gap_skill")),{})
        roi=round((g.get("demand",1)*(1.5 if g.get("is_required") else 1)*10)/max(m["duration_hrs"],1),2)
        out.append({"id":m["id"],"title":m["title"],"skill":m["skill"],"roi":roi,
                    "hrs":m["duration_hrs"],"is_required":g.get("is_required",False)})
    return sorted(out,key=lambda x:x["roi"],reverse=True)

def weeks_ready(hrs: int, hpd: float) -> str:
    if hpd<=0: return "-"
    w=(hrs/hpd)/5
    if w<1:   return f"{int(hrs/hpd)} days"
    elif w<4: return f"{w:.1f} weeks"
    return f"{(w/4):.1f} months"

# =============================================================================
#  FULL ANALYSIS PIPELINE
# =============================================================================
def run_analysis(resume_text: str, jd_text: str, resume_image_b64: Optional[str]=None) -> dict:
    cache_k = resume_text or "img"
    cached  = cache_get(cache_k, jd_text)
    if cached:
        cached["_cache_hit"] = True; return cached

    kws = [w.strip() for w in jd_text.split() if len(w)>3][:20]
    potential_mods = [c for c in CATALOG if any(
        kw.lower() in c["skill"].lower() or c["skill"].lower() in kw.lower() for kw in kws)][:10]

    raw = mega_call(resume_text=resume_text, jd_text=jd_text,
                    modules_hint=potential_mods, resume_image_b64=resume_image_b64)
    if "error" in raw: return raw

    candidate  = raw.get("candidate",{})
    jd_data    = raw.get("jd",{})
    quality    = raw.get("audit",{})
    rsn_map    = raw.get("reasoning",{})

    if not candidate or not jd_data: return {"error":"parse_failed — empty candidate or JD"}

    gp   = analyze_gap(candidate, jd_data)
    path = build_path(gp, candidate, jd_data)
    for m in path: m["reasoning"] = rsn_map.get(m["id"], f"Addresses gap in {m['gap_skill']}.")
    im   = calc_impact(gp, path)
    sm   = seniority_check(candidate, jd_data)
    iv   = interview_readiness(gp, candidate)
    wp   = weekly_plan(path)
    tf   = transfer_map(candidate, gp)
    roi  = roi_rank(gp, path)
    obs  = [{"skill":g["skill"],"status":g["status"],"reason":OBSOLESCENCE_RISK[g["skill"].lower()]}
            for g in gp if OBSOLESCENCE_RISK.get(g["skill"].lower())]
    cgm  = max(0, SENIORITY_MAP.get(jd_data.get("seniority_required","Mid"),1)
                  -SENIORITY_MAP.get(candidate.get("seniority","Mid"),1)) * 18

    result = {"candidate":candidate,"jd":jd_data,"gap_profile":gp,"path":path,
              "impact":im,"seniority":sm,"quality":quality,"interview":iv,
              "weekly_plan":wp,"transfers":tf,"roi":roi,"obsolescence":obs,
              "career_months":cgm,"_cache_hit":False}
    cache_set(cache_k, jd_text, result)
    return result

# =============================================================================
#  PDF EXPORT
# =============================================================================
def build_pdf(c, jd, gp, path, im, ql=None, iv=None) -> io.BytesIO:
    buf = io.BytesIO()
    if not REPORTLAB: return buf
    doc    = SimpleDocTemplate(buf, pagesize=letter, topMargin=48, bottomMargin=48, leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    TEAL   = rl_colors.HexColor("#4ECDC4")
    BD = ParagraphStyle("BD", parent=styles["Normal"], fontSize=10, spaceAfter=5)
    H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=20, spaceAfter=4, textColor=TEAL)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, spaceBefore=14)
    IT = ParagraphStyle("IT", parent=styles["Normal"], fontSize=9, spaceAfter=4, leftIndent=18,
                         textColor=rl_colors.HexColor("#555"), italics=True)
    story = [
        Paragraph("SkillForge v5 — AI Adaptive Onboarding Report", H1),
        Paragraph(f"Candidate: <b>{c.get('name','--')}</b>  |  Role: <b>{jd.get('role_title','--')}</b>  "
                  f"|  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}", BD),
        Spacer(1,14),
    ]
    if ql or iv:
        story.append(Paragraph("Scores", H2))
        rows = []
        if ql: rows += [["ATS Score",f"{ql.get('ats_score','--')}%"],["Grade",ql.get("overall_grade","--")],
                         ["Completeness",f"{ql.get('completeness_score','--')}%"],["Clarity",f"{ql.get('clarity_score','--')}%"]]
        if iv: rows += [["Interview Ready",f"{iv['score']}% — {iv['label']}"],
                         ["Known",str(iv["req_known"])],["Missing",str(iv["req_missing"])]]
        t = Table([["Metric","Value"]]+rows, colWidths=[200,260])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),TEAL),("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
            ("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.4,rl_colors.grey),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.whitesmoke,rl_colors.white]),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story += [t, Spacer(1,14)]
    story.append(Paragraph("Learning Roadmap", H2))
    for i,m in enumerate(path):
        story.append(Paragraph(
            f"<b>{i+1}. {'[CRITICAL] ' if m.get('is_critical') else ''}{m['title']}</b>"
            f" — {m['level']} / {m['duration_hrs']}h", BD))
        if m.get("reasoning"): story.append(Paragraph(f"→ {m['reasoning']}", IT))
    doc.build(story); buf.seek(0)
    return buf

# =============================================================================
#  PLOTLY CHARTS
# =============================================================================
_PLOTBG = "rgba(0,0,0,0)"
_GRID   = "#1E2A3A"

def radar_chart(gp: List[dict]) -> go.Figure:
    items = gp[:10]
    if not items: return go.Figure()
    theta = [g["skill"][:14] for g in items]
    fig = go.Figure(data=[
        go.Scatterpolar(r=[10]*len(items), theta=theta, fill="toself", name="JD Required",
                        line=dict(color="#FF6B6B",width=2), opacity=0.20),
        go.Scatterpolar(r=[g.get("original_prof",g["proficiency"]) for g in items], theta=theta,
                        fill="toself", name="Before Decay",
                        line=dict(color="#FFE66D",width=1,dash="dot"), opacity=0.18),
        go.Scatterpolar(r=[g["proficiency"] for g in items], theta=theta, fill="toself",
                        name="Current", line=dict(color="#4ECDC4",width=2), opacity=0.75),
    ])
    fig.update_layout(
        polar=dict(bgcolor=_PLOTBG,
                   radialaxis=dict(visible=True,range=[0,10],gridcolor=_GRID,tickfont=dict(size=9,color="#555")),
                   angularaxis=dict(gridcolor=_GRID)),
        paper_bgcolor=_PLOTBG, plot_bgcolor=_PLOTBG,
        font=dict(color="#C9D1D9",family="sans-serif"),
        showlegend=True, legend=dict(bgcolor=_PLOTBG,x=0.78,y=1.15,font=dict(size=10)),
        margin=dict(l=30,r=30,t=40,b=30), height=360,
    )
    return fig

def timeline_chart(path: List[dict]) -> go.Figure:
    if not path: return go.Figure()
    lc = {"Critical":"#FF6B6B","Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF9A9A"}
    shown, fig = set(), go.Figure()
    for i,m in enumerate(path):
        k = "Critical" if m.get("is_critical") else m["level"]
        show = k not in shown; shown.add(k)
        fig.add_trace(go.Bar(
            x=[m["duration_hrs"]], y=[f"#{i+1} {m['title'][:28]}"], orientation="h",
            marker=dict(color=lc.get(k,"#888"),opacity=0.88,line=dict(width=0)),
            name=k, legendgroup=k, showlegend=show,
            hovertemplate=f"<b>{m['title']}</b><br>{m['level']} · {m['duration_hrs']}h<extra></extra>",
        ))
    fig.update_layout(
        paper_bgcolor=_PLOTBG, plot_bgcolor="rgba(15,22,36,0.6)",
        font=dict(color="#C9D1D9"),
        xaxis=dict(title="Hours",gridcolor=_GRID,zeroline=False),
        yaxis=dict(gridcolor=_GRID,tickfont=dict(size=10)),
        margin=dict(l=10,r=20,t=10,b=40), height=max(300,len(path)*40),
        legend=dict(bgcolor=_PLOTBG,orientation="h",y=1.03), barmode="overlay",
    )
    return fig

def roi_chart(roi_list: List[dict]) -> go.Figure:
    if not roi_list: return go.Figure()
    top = roi_list[:10]
    fig = go.Figure(go.Bar(
        x=[m["roi"] for m in top], y=[m["title"][:28] for m in top], orientation="h",
        marker=dict(color=["#FF6B6B" if m["is_required"] else "#4ECDC4" for m in top],opacity=0.85),
        hovertemplate="<b>%{y}</b><br>ROI: %{x}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_PLOTBG, plot_bgcolor="rgba(15,22,36,0.4)", font=dict(color="#C9D1D9"),
        xaxis=dict(title="ROI Index (higher = learn first)",gridcolor=_GRID,zeroline=False),
        yaxis=dict(gridcolor=_GRID,autorange="reversed"),
        margin=dict(l=10,r=20,t=10,b=40), height=max(260,len(top)*36),
    )
    return fig

def priority_matrix(gp: List[dict]) -> go.Figure:
    ease_map={"Beginner":9,"Intermediate":5,"Advanced":2}
    pts=[{"skill":g["skill"],
           "ease":ease_map.get((g.get("catalog_course") or {}).get("level","Intermediate"),5),
           "impact":min(10,g.get("demand",1)*3+(3 if g["is_required"] else 0)),
           "hrs":(g.get("catalog_course") or {}).get("duration_hrs",6),"status":g["status"]}
          for g in gp if g["status"]!="Known" and g.get("catalog_course")]
    if not pts: return go.Figure()
    fig=go.Figure()
    for sl,col in [("Missing","#FF6B6B"),("Partial","#FFE66D")]:
        sub=[p for p in pts if p["status"]==sl]
        if not sub: continue
        fig.add_trace(go.Scatter(
            x=[p["ease"] for p in sub], y=[p["impact"] for p in sub], mode="markers+text",
            marker=dict(size=[max(14,p["hrs"]*2.8) for p in sub],color=col,opacity=0.75),
            text=[p["skill"][:13] for p in sub], textposition="top center",
            textfont=dict(size=9,color="#C9D1D9"), name=sl,
            hovertemplate="<b>%{text}</b><br>Ease:%{x:.1f} Impact:%{y:.1f}<extra></extra>",
        ))
    for x,y,t in [(2.5,8.5,"HIGH PRIORITY"),(7.5,8.5,"QUICK WIN"),(2.5,2.5,"LONG HAUL"),(7.5,2.5,"NICE TO HAVE")]:
        fig.add_annotation(x=x,y=y,text=t,showarrow=False,font=dict(size=9,color="#3D4F6B"))
    fig.add_hline(y=5.5,line_dash="dot",line_color=_GRID)
    fig.add_vline(x=5.5,line_dash="dot",line_color=_GRID)
    fig.update_layout(
        paper_bgcolor=_PLOTBG, plot_bgcolor="rgba(15,22,36,0.4)", font=dict(color="#C9D1D9"),
        xaxis=dict(title="Ease (Beginner=easy)",range=[0,11],gridcolor=_GRID,zeroline=False),
        yaxis=dict(title="Impact (Demand × Req)",range=[0,11],gridcolor=_GRID,zeroline=False),
        margin=dict(l=20,r=20,t=20,b=40), showlegend=True, height=400,
        legend=dict(bgcolor=_PLOTBG,x=0,y=1.1,orientation="h"),
    )
    return fig

def salary_chart(s: dict) -> go.Figure:
    if not s or not s.get("median_lpa"): return go.Figure()
    fig = go.Figure(go.Bar(
        x=["Min","Median","Max"],
        y=[s.get("min_lpa",0),s.get("median_lpa",0),s.get("max_lpa",0)],
        marker_color=["#4ECDC4","#FFE66D","#FF6B6B"], opacity=0.88,
        text=[f"₹{v}L" for v in [s.get("min_lpa",0),s.get("median_lpa",0),s.get("max_lpa",0)]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>₹%{y}L/yr<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_PLOTBG, plot_bgcolor="rgba(15,22,36,0.4)", font=dict(color="#C9D1D9"),
        yaxis=dict(title="LPA (₹ Lakhs/yr)",gridcolor=_GRID),
        xaxis=dict(gridcolor=_GRID), margin=dict(l=20,r=20,t=30,b=40), height=280,
    )
    return fig

# =============================================================================
#  STREAMLIT CSS
# =============================================================================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    background: #0f1623 !important;
    color: #c9d1d9 !important;
}
.stApp { background: #0f1623 !important; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none !important; }
footer { display: none !important; }
#MainMenu { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2a3a50; border-radius: 99px; }

.sf-nav {
    background: rgba(10,14,26,0.97);
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 0 32px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 1000;
    backdrop-filter: blur(12px);
}
.sf-logo { display: flex; flex-direction: column; }
.sf-logo-main {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 1.3rem; font-weight: 800;
    color: #4ECDC4; letter-spacing: -0.03em;
}
.sf-logo-sub {
    font-size: 0.56rem; letter-spacing: 0.18em;
    text-transform: uppercase; color: #3d4f6b;
    margin-top: -1px;
}
.sf-nav-right { display: flex; gap: 8px; align-items: center; }
.sf-pill {
    font-size: 0.68rem; padding: 4px 11px;
    border-radius: 99px;
    border: 1px solid rgba(255,255,255,0.1);
    color: #6b7a99;
    background: transparent;
    white-space: nowrap;
}
.sf-pill.active {
    border-color: rgba(78,205,196,0.4);
    color: #4ECDC4;
    background: rgba(78,205,196,0.06);
}
.sf-pill.light-btn {
    border-color: rgba(255,255,255,0.15);
    color: #c9d1d9;
    cursor: pointer;
}

.sf-hero {
    text-align: center;
    padding: 64px 24px 48px;
}
.sf-hero h1 {
    font-size: clamp(2.2rem, 4.5vw, 3.8rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 0 0 16px;
    color: #e6edf3;
}
.sf-hero h1 span { color: #4ECDC4; }
.sf-hero p {
    color: #8892a4;
    font-size: 1rem;
    max-width: 540px;
    margin: 0 auto;
    line-height: 1.65;
}

.sf-samples {
    text-align: center;
    padding: 0 24px 32px;
}
.sf-samples-label {
    font-size: 0.75rem; color: #4a5568;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

[data-testid="stFileUploadDropzone"] {
    background: rgba(78,205,196,0.03) !important;
    border: 1.5px dashed rgba(78,205,196,0.3) !important;
    border-radius: 10px !important;
    padding: 20px !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: rgba(78,205,196,0.6) !important;
    background: rgba(78,205,196,0.06) !important;
}
[data-testid="stFileUploadDropzone"] label {
    color: #8892a4 !important;
    font-size: 0.88rem !important;
}
[data-testid="stFileUploadDropzone"] button {
    background: transparent !important;
    border: 1px solid rgba(78,205,196,0.4) !important;
    color: #4ECDC4 !important;
    border-radius: 6px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.stButton > button {
    background: #4ECDC4 !important;
    border: none !important;
    border-radius: 10px !important;
    color: #0a0e1a !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 14px 0 !important;
    width: 100% !important;
    transition: all 0.2s !important;
    letter-spacing: -0.01em !important;
}
.stButton > button:hover {
    background: #3dbdb5 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(78,205,196,0.3) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

textarea {
    background: #0f1623 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    color: #c9d1d9 !important;
    font-size: 0.82rem !important;
    font-family: 'JetBrains Mono', monospace !important;
    resize: vertical !important;
}
textarea:focus {
    border-color: rgba(78,205,196,0.45) !important;
    box-shadow: none !important;
}
textarea::placeholder { color: #3d4f6b !important; }

.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.07) !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    color: #4a5568 !important;
    font-size: 0.85rem !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    padding: 10px 20px !important;
    border-radius: 0 !important;
}
.stTabs [aria-selected="true"] {
    color: #4ECDC4 !important;
    border-bottom: 2px solid #4ECDC4 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 20px !important; }

[data-testid="stMetric"] {
    background: #141c2e !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
    padding: 14px 16px !important;
}
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.8rem !important;
    color: #4ECDC4 !important;
    font-weight: 500 !important;
}
[data-testid="stMetricLabel"] {
    color: #4a5568 !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

[data-testid="stExpander"] {
    background: #141c2e !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    margin-bottom: 6px !important;
}
[data-testid="stExpander"] summary {
    color: #c9d1d9 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}

[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #4ECDC4, #44B8B0) !important;
}
[data-testid="stProgressBar"] > div {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 99px !important;
}

[data-testid="stDownloadButton"] > button {
    background: rgba(78,205,196,0.1) !important;
    border: 1px solid rgba(78,205,196,0.3) !important;
    color: #4ECDC4 !important;
    font-weight: 600 !important;
}

[data-testid="stSelectbox"] > div > div {
    background: #141c2e !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #c9d1d9 !important;
}

.sf-warn {
    background: rgba(255,193,7,0.07);
    border: 1px solid rgba(255,193,7,0.25);
    border-radius: 10px;
    padding: 11px 16px;
    font-size: 0.82rem;
    color: #ffd54f;
    margin-bottom: 14px;
}
.sf-info {
    background: rgba(78,205,196,0.07);
    border: 1px solid rgba(78,205,196,0.2);
    border-radius: 10px;
    padding: 11px 16px;
    font-size: 0.82rem;
    color: #4ECDC4;
    margin-bottom: 14px;
}

.sf-sec { font-size: 0.95rem; font-weight: 700; color: #e6edf3; margin-bottom: 3px; }
.sf-sec-sub { font-size: 0.73rem; color: #4a5568; margin-bottom: 12px; }

.sf-skill-row {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 9px; font-size: 0.8rem;
}
.sf-skill-name { min-width: 120px; color: #c9d1d9; }
.sf-skill-track { flex: 1; height: 6px; background: rgba(255,255,255,0.06); border-radius: 99px; overflow: hidden; }
.sf-skill-fill  { height: 100%; border-radius: 99px; transition: width 1s ease; }
.sf-skill-val   { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #4a5568; min-width: 28px; text-align: right; }

.badge { font-size: 0.62rem; border-radius: 4px; padding: 2px 7px; font-weight: 600; letter-spacing: 0.03em; margin-left: 4px; }
.bk { background: rgba(78,205,196,0.12); color: #4ECDC4; border: 1px solid rgba(78,205,196,0.3); }
.bp { background: rgba(255,230,109,0.1); color: #FFE66D; border: 1px solid rgba(255,230,109,0.3); }
.bm { background: rgba(255,107,107,0.1); color: #FF6B6B; border: 1px solid rgba(255,107,107,0.3); }
.bh { background: rgba(255,107,107,0.1); color: #FF6B6B; border: 1px solid rgba(255,107,107,0.25); border-radius: 99px; font-size: 0.6rem; padding: 1px 7px; }
.bg { background: rgba(255,230,109,0.08); color: #FFE66D; border: 1px solid rgba(255,230,109,0.25); border-radius: 99px; font-size: 0.6rem; padding: 1px 7px; }

.sf-mod {
    background: #1a2438;
    border: 1px solid rgba(255,255,255,0.06);
    border-left: 3px solid #4ECDC4;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.sf-mod.crit { border-left-color: #FF6B6B; box-shadow: 0 0 12px rgba(255,107,107,0.1); }
.sf-mod.adv  { border-left-color: #FF9A9A; }
.sf-mod.int  { border-left-color: #FFE66D; }
.sf-mod-title { font-size: 0.84rem; font-weight: 600; color: #e6edf3; display: flex; justify-content: space-between; gap: 8px; }
.sf-mod-meta  { font-size: 0.71rem; color: #4a5568; margin-top: 3px; }
.sf-mod-reason { font-size: 0.75rem; color: #6b7a99; margin-top: 7px; padding-top: 7px; border-top: 1px solid rgba(255,255,255,0.05); font-style: italic; line-height: 1.5; }

.sf-prow { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.82rem; }
.sf-prow:last-child { border-bottom: none; }
.sf-pk { color: #4a5568; }
.sf-pv { font-weight: 600; color: #c9d1d9; text-align: right; }

.tf-item { background: rgba(167,139,250,0.05); border-left: 2px solid #a78bfa; border-radius: 6px; padding: 7px 11px; margin-bottom: 6px; font-size: 0.79rem; color: #8892a4; }
.ob-item { background: rgba(255,107,107,0.04); border-left: 2px solid #ff6b6b; border-radius: 6px; padding: 7px 11px; margin-bottom: 6px; font-size: 0.79rem; color: #8892a4; }

.sf-ar { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); border-radius: 6px; padding: 6px 10px; margin-bottom: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #4a5568; display: flex; gap: 10px; flex-wrap: wrap; }

.sf-statusbar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #0a0e1a;
    border-top: 1px solid rgba(255,255,255,0.07);
    padding: 6px 24px;
    font-size: 0.69rem; color: #4a5568;
    display: flex; align-items: center; gap: 20px;
    z-index: 999;
}
.sf-statusbar span { display: flex; align-items: center; gap: 5px; }
.sf-statusbar .dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.sf-statusbar .green { background: #4ECDC4; }
.sf-statusbar .yellow { background: #FFE66D; }
.sf-statusbar .version { font-family: 'JetBrains Mono', monospace; margin-left: auto; }

@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.fade-in { animation: fadeUp 0.4s ease; }

.css-1d391kg, [data-testid="stAppViewContainer"] > section { padding-bottom: 48px !important; }
</style>
"""

# =============================================================================
#  STREAMLIT UI
# =============================================================================
def render_nav():
    st.markdown("""
    <div class="sf-nav">
      <div class="sf-logo">
        <div class="sf-logo-main">SkillForge</div>
        <div class="sf-logo-sub">Skill Gap · Learning Pathways</div>
      </div>
      <div class="sf-nav-right">
        <span class="sf-pill active">Groq LLaMA 4-Scout</span>
        <span class="sf-pill active">NetworkX Pathing</span>
        <span class="sf-pill active">Semantic Match</span>
        <span class="sf-pill active">Skill Decay</span>
        <span class="sf-pill light-btn">☀ Light</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_hero():
    st.markdown("""
    <div class="sf-hero">
      <h1>Map Your Path to <span>Role Mastery</span></h1>
      <p>Upload your resume and the target job description — the AI identifies<br>
         your exact skill gaps and builds a dependency-aware learning roadmap.</p>
    </div>
    """, unsafe_allow_html=True)

def render_status_bar():
    total_cost = sum(e.get("cost",0) for e in _audit_log)
    calls = len(_audit_log)
    st.markdown(f"""
    <div class="sf-statusbar">
      <span><span class="dot green"></span> Groq llama-4-scout</span>
      <span><span class="dot green"></span> NetworkX</span>
      <span><span class="dot {'green' if SEMANTIC else 'yellow'}"></span>
        Semantic Match {'✓' if SEMANTIC else '(loading)'}</span>
      <span><span class="dot green"></span> Skill Decay</span>
      <span class="version">v5.0.0  ·  {calls} calls  ·  ${total_cost:.5f}</span>
    </div>
    """, unsafe_allow_html=True)

def main():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    render_nav()
    render_hero()

    # ── Sample buttons ─────────────────────────────────────────────────────────
    # FIX: Write directly into session_state keys used by the text areas,
    # then call st.rerun() so Streamlit picks them up before rendering.
    st.markdown('<div class="sf-samples"><div class="sf-samples-label">Try a sample:</div></div>',
                unsafe_allow_html=True)
    s1, s2, s3, _ = st.columns([1,1,1,3])

    if s1.button("👨‍💻 Junior SWE", key="sp_jswe", use_container_width=True):
        st.session_state["jd_paste"]  = SAMPLES["junior_swe"]["jd"]
        st.session_state["res_paste"] = SAMPLES["junior_swe"]["resume"]
        st.session_state.pop("result", None)
        st.rerun()

    if s2.button("🧪 Senior Data Scientist", key="sp_ds", use_container_width=True):
        st.session_state["jd_paste"]  = SAMPLES["senior_ds"]["jd"]
        st.session_state["res_paste"] = SAMPLES["senior_ds"]["resume"]
        st.session_state.pop("result", None)
        st.rerun()

    if s3.button("💼 HR Manager", key="sp_hr", use_container_width=True):
        st.session_state["jd_paste"]  = SAMPLES["hr_manager"]["jd"]
        st.session_state["res_paste"] = SAMPLES["hr_manager"]["resume"]
        st.session_state.pop("result", None)
        st.rerun()

    # ── Three-column input layout ──────────────────────────────────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col_res, col_jd, col_btn = st.columns([5, 5, 3], gap="medium")

    # Resume card
    with col_res:
        st.markdown("""
        <div style="background:#141c2e;border:1px solid rgba(255,255,255,0.07);
                    border-radius:14px;padding:20px 20px 0;margin-bottom:-12px">
          <div style="text-align:center;font-size:1.5rem;margin-bottom:6px">📄</div>
          <div style="text-align:center;font-size:1rem;font-weight:700;color:#e6edf3;margin-bottom:14px">Resume</div>
        </div>
        """, unsafe_allow_html=True)
        resume_file = st.file_uploader(
            "Drop or browse",
            type=["pdf","docx","jpg","jpeg","png","webp"],
            key="res_file",
            label_visibility="collapsed",
        )
        st.markdown("""
        <div style="background:#141c2e;border:1px solid rgba(255,255,255,0.07);
                    border-radius:0 0 14px 14px;padding:0 20px 18px">
          <p style="font-size:0.7rem;color:#3d4f6b;text-align:center;margin:4px 0 0">PDF or DOCX</p>
        </div>
        """, unsafe_allow_html=True)

    # JD card
    with col_jd:
        st.markdown("""
        <div style="background:#141c2e;border:1px solid rgba(255,255,255,0.07);
                    border-radius:14px;padding:20px 20px 0;margin-bottom:-12px">
          <div style="text-align:center;font-size:1.5rem;margin-bottom:6px">💼</div>
          <div style="text-align:center;font-size:1rem;font-weight:700;color:#e6edf3;margin-bottom:14px">Job Description</div>
        </div>
        """, unsafe_allow_html=True)
        jd_file = st.file_uploader(
            "Drop or browse",
            type=["pdf","docx"],
            key="jd_file",
            label_visibility="collapsed",
        )
        st.markdown("""
        <div style="background:#141c2e;border:1px solid rgba(255,255,255,0.07);
                    padding:0 20px 4px">
          <p style="font-size:0.7rem;color:#3d4f6b;text-align:center;margin:4px 0 2px">PDF, DOCX or paste below</p>
        </div>
        """, unsafe_allow_html=True)
        # FIX: No value= param — session_state["jd_paste"] drives the content
        jd_paste = st.text_area(
            "JD paste",
            height=90,
            placeholder="…or paste the JD text here",
            key="jd_paste",
            label_visibility="collapsed",
        )
        st.markdown("""
        <div style="background:#141c2e;border:1px solid rgba(255,255,255,0.07);
                    border-radius:0 0 14px 14px;padding:6px 20px 14px">
        </div>
        """, unsafe_allow_html=True)

    # Analyze card
    with col_btn:
        st.markdown("""
        <div style="background:#141c2e;border:1px solid rgba(255,255,255,0.07);
                    border-radius:14px;padding:24px 20px;text-align:center">
          <div style="font-size:1.8rem;margin-bottom:8px">⚡</div>
          <div style="font-size:1rem;font-weight:700;color:#e6edf3;margin-bottom:4px">Analyze</div>
          <div style="font-size:0.73rem;color:#4a5568;margin-bottom:20px">AI-powered gap analysis</div>
        </div>
        """, unsafe_allow_html=True)
        analyze_btn = st.button("Analyze →", key="analyze_main", use_container_width=True)

        st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
        hpd = st.select_slider("Pace (hrs/day)", options=[1,2,4,8], value=2, key="hpd")
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption(f"`{MODEL_FAST.split('/')[-1]}`")

    # Resume paste expander
    with st.expander("✏ Or paste resume text directly"):
        # FIX: No value= param — session_state["res_paste"] drives the content
        res_paste = st.text_area(
            "Resume text",
            height=120,
            placeholder="Paste resume text here…",
            key="res_paste",
            label_visibility="collapsed",
        )

    with st.expander("📊 Compare multiple JDs (optional)"):
        jd2 = st.text_area("JD #2", height=80, placeholder="Paste second JD for comparison…", key="jd2")
        jd3 = st.text_area("JD #3", height=80, placeholder="Paste third JD for comparison…", key="jd3")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Run analysis ───────────────────────────────────────────────────────────
    if analyze_btn:
        res_text, res_img = "", None
        if resume_file:
            res_text, res_img = parse_uploaded_file(resume_file)
        elif st.session_state.get("res_paste", "").strip():
            res_text = st.session_state["res_paste"].strip()

        jd_text = ""
        if jd_file:
            jd_text, _ = parse_uploaded_file(jd_file)
        elif st.session_state.get("jd_paste", "").strip():
            jd_text = st.session_state["jd_paste"].strip()

        if not res_text and not res_img:
            st.error("Please upload or paste a resume."); return
        if not jd_text:
            st.error("Please upload or paste a job description."); return

        with st.spinner("⚡ Calling Groq llama-4-scout…"):
            result = run_analysis(res_text, jd_text, res_img)

        if "error" in result:
            if result.get("error") == "rate_limited":
                st.error(f"⚠ Rate limited: {result.get('message','')}"); return
            st.error(f"Analysis error: {result.get('error','unknown')}"); return

        st.session_state["result"]     = result
        st.session_state["resume_txt"] = res_text

    # ── Render results ─────────────────────────────────────────────────────────
    res = st.session_state.get("result")
    if not res:
        render_status_bar()
        return

    c   = res["candidate"];   jd  = res["jd"]
    gp  = res["gap_profile"]; pt  = res["path"]
    im  = res["impact"];      sm  = res.get("seniority",{})
    ql  = res.get("quality",{}); iv = res.get("interview",{})
    wp  = res.get("weekly_plan",[]); tf = res.get("transfers",[])
    roi = res.get("roi",[]); obs = res.get("obsolescence",[])
    cgm = res.get("career_months",0)
    hpd_val = hpd

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)

    if res.get("_cache_hit"):
        st.markdown('<div class="sf-info">⚡ <b>Cached result</b> — 0 API calls used</div>', unsafe_allow_html=True)
    if sm.get("has_mismatch"):
        st.markdown(
            f'<div class="sf-warn">⚠ <b>Seniority Gap:</b> Candidate is {sm["candidate"]}, '
            f'role requires {sm["required"]}. Leadership modules auto-added.</div>',
            unsafe_allow_html=True,
        )

    # KPI strip — 6 metrics
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Current Fit",   f"{im['current_fit']}%")
    k2.metric("Projected Fit", f"{im['projected_fit']}%", f"+{im['fit_delta']}%")
    k3.metric("Training Hrs",  f"{im['roadmap_hours']}h", f"saves ~{im['hours_saved']}h")
    k4.metric("Modules",       im["modules_count"], f"{im['critical_count']} critical")
    k5.metric("Interview",     f"{iv.get('score',0)}%", iv.get("label","--"))
    k6.metric("Ready In",      weeks_ready(im["roadmap_hours"], hpd_val))

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    tabs = st.tabs(["🗺 Skill Gap","📚 Roadmap + ROI","🔬 ATS Audit","💰 Salary + Rewrite","📋 API Log"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — SKILL GAP
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[0]:
        l, r = st.columns([1.1, 1], gap="large")

        with l:
            st.markdown('<div class="sf-sec">Skill Gap Radar</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sf-sec-sub">{c.get("name","Candidate")} vs {jd.get("role_title","Target Role")}</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(radar_chart(gp), use_container_width=True, config={"displayModeBar":False})

        with r:
            k_cnt = sum(1 for g in gp if g["status"]=="Known")
            p_cnt = sum(1 for g in gp if g["status"]=="Partial")
            m_cnt = sum(1 for g in gp if g["status"]=="Missing")
            st.markdown('<div class="sf-sec">All Skills</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sf-sec-sub">{k_cnt} Known &nbsp;·&nbsp; {p_cnt} Partial &nbsp;·&nbsp; {m_cnt} Missing</div>',
                        unsafe_allow_html=True)
            bars_html = ""
            for g in gp:
                col  = {"Known":"#4ECDC4","Partial":"#FFE66D","Missing":"#FF6B6B"}[g["status"]]
                bc   = {"Known":"bk","Partial":"bp","Missing":"bm"}[g["status"]]
                dmnd = {3:"🔥",2:"📈",1:"✓"}.get(g.get("demand",1),"✓")
                dk   = " ⏱" if g.get("decayed") else ""
                ob   = " ⚠" if g.get("obsolescence_risk") else ""
                bars_html += f"""
                <div class="sf-skill-row">
                  <div class="sf-skill-name">{g['skill'][:16]}{dk}{ob}</div>
                  <div class="sf-skill-track">
                    <div class="sf-skill-fill" style="width:{g['proficiency']/10*100}%;background:{col}"></div>
                  </div>
                  <div class="sf-skill-val">{g['proficiency']}/10 {dmnd}</div>
                  <span class="badge {bc}">{g['status']}</span>
                </div>"""
            st.markdown(f'<div style="max-height:340px;overflow-y:auto">{bars_html}</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        tc, oc, pc = st.columns(3, gap="medium")

        with tc:
            st.markdown('<div class="sf-sec">↗ Transfer Map</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec-sub">Your skills give a head start</div>', unsafe_allow_html=True)
            if tf:
                for t_item in tf[:5]:
                    st.markdown(f'<div class="tf-item">↗ {t_item["label"]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No strong transfer paths detected.")

        with oc:
            st.markdown('<div class="sf-sec">⚠ Obsolescence Risks</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec-sub">Skills losing value by 2027</div>', unsafe_allow_html=True)
            if obs:
                for o in obs:
                    st.markdown(f'<div class="ob-item">⚠ <b>{o["skill"]}</b>: {o["reason"]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No risks detected.")

        with pc:
            st.markdown('<div class="sf-sec">👤 Candidate Profile</div>', unsafe_allow_html=True)
            rows_html = ""
            for k_lbl, v_val in [
                ("Name",       c.get("name","--")),
                ("Role",       c.get("current_role","--")),
                ("Seniority",  c.get("seniority","--")),
                ("Experience", f"{c.get('years_experience','--')} yrs"),
                ("Education",  (c.get("education","--") or "")[:30]),
                ("Domain",     c.get("domain","--")),
            ]:
                rows_html += f'<div class="sf-prow"><span class="sf-pk">{k_lbl}</span><span class="sf-pv">{v_val}</span></div>'
            st.markdown(rows_html, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — ROADMAP + ROI
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        rl, rr = st.columns([1.1, 1], gap="large")
        lc = {"Beginner":"#4ECDC4","Intermediate":"#FFE66D","Advanced":"#FF6B6B"}

        with rl:
            st.markdown('<div class="sf-sec">Learning Roadmap</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec-sub">Dependency-ordered · critical path highlighted · AI reasoning per module</div>',
                        unsafe_allow_html=True)
            for i, m in enumerate(pt):
                crit  = m.get("is_critical",False)
                level = m["level"]
                cls   = "crit" if crit else ("adv" if level=="Advanced" else "int" if level=="Intermediate" else "")
                flag  = " ★ CRITICAL" if crit else ""
                prereqs_str = ", ".join(m.get("prereqs",[]) or []) or "None"
                with st.expander(f"#{i+1}  {m['title']}  ·  {m['duration_hrs']}h{flag}"):
                    st.markdown(f"""
                    <div class="sf-mod {cls}">
                      <div class="sf-mod-title">
                        <span>{m['title']}</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-size:.68rem;color:{lc.get(level,'#888')}">{level} · {m['duration_hrs']}h</span>
                      </div>
                      <div class="sf-mod-meta">Skill: {m['skill']} &nbsp;·&nbsp; Domain: {m['domain']} &nbsp;·&nbsp; Gap: {m.get('gap_status','--')} &nbsp;·&nbsp; Prereqs: {prereqs_str}</div>
                      {f'<div class="sf-mod-reason">{m["reasoning"]}</div>' if m.get("reasoning") else ""}
                    </div>
                    """, unsafe_allow_html=True)

        with rr:
            st.markdown('<div class="sf-sec">ROI Ranking</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec-sub">Highest return-on-time — tackle these first</div>', unsafe_allow_html=True)
            st.plotly_chart(roi_chart(roi), use_container_width=True, config={"displayModeBar":False})

        st.markdown("---")
        st.markdown('<div class="sf-sec">Priority Matrix — Ease vs Impact</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-sec-sub">Bubble size = course duration. Top-right = Quick Wins.</div>', unsafe_allow_html=True)
        st.plotly_chart(priority_matrix(gp), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="sf-sec">Training Timeline</div>', unsafe_allow_html=True)
        st.plotly_chart(timeline_chart(pt), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="sf-sec">🗓 Weekly Study Plan</div>', unsafe_allow_html=True)
        wp_curr = weekly_plan(pt, hpd_val)
        for w in wp_curr[:8]:
            with st.expander(f"Week {w['week']} — {w['total_hrs']:.1f}h"):
                for mx in w["modules"]:
                    crit_t = "★ " if mx.get("is_critical") else ""
                    st.markdown(f"- {crit_t}**{mx['title']}** ({mx['hrs_this_week']:.1f}h / {mx['total_hrs']}h total)")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — ATS AUDIT
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[2]:
        ats   = ql.get("ats_score", 0)
        cs_sc = ql.get("completeness_score", 0)
        cl_sc = ql.get("clarity_score", 0)
        grade = ql.get("overall_grade","--")
        gc    = {"A":"#4ECDC4","B":"#FFE66D","C":"#FFA726","D":"#FF6B6B"}.get(grade,"#888")

        a1,a2,a3,a4 = st.columns(4)
        a1.metric("ATS Score",    f"{ats}%")
        a2.metric("Grade",        grade)
        a3.metric("Completeness", f"{cs_sc}%")
        a4.metric("Clarity",      f"{cl_sc}%")
        st.progress(ats/100)

        dl, dr = st.columns(2, gap="large")
        with dl:
            st.markdown('<div class="sf-sec" style="margin-top:16px">✏ Improvement Tips</div>', unsafe_allow_html=True)
            for i, tip in enumerate((ql.get("improvement_tips") or [])[:6]):
                st.markdown(
                    f'<div style="display:flex;gap:10px;margin-bottom:8px;font-size:.82rem;color:#8892a4;line-height:1.5">'
                    f'<span style="font-family:JetBrains Mono,monospace;font-size:.68rem;color:#4ECDC4;background:rgba(78,205,196,.08);'
                    f'border:1px solid rgba(78,205,196,.2);border-radius:4px;padding:2px 6px;min-width:28px;text-align:center;flex-shrink:0">0{i+1}</span>'
                    f'<span>{tip}</span></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div class="sf-sec" style="margin-top:16px">🗣 Interview Talking Points</div>', unsafe_allow_html=True)
            for p in (ql.get("interview_talking_points") or [])[:4]:
                st.markdown(
                    f'<div style="font-size:.82rem;color:#8892a4;margin-bottom:8px;padding-left:12px;'
                    f'border-left:2px solid #4ECDC4;line-height:1.5">→ {p}</div>',
                    unsafe_allow_html=True,
                )
        with dr:
            st.markdown('<div class="sf-sec" style="margin-top:16px">🔴 ATS Issues</div>', unsafe_allow_html=True)
            for iss in (ql.get("ats_issues") or ["No critical issues detected"])[:5]:
                st.warning(iss)

            st.markdown('<div class="sf-sec" style="margin-top:12px">Missing JD Keywords</div>', unsafe_allow_html=True)
            kws = ql.get("missing_keywords") or ["None identified"]
            tags_html = "".join(
                f'<span style="font-size:.72rem;padding:3px 10px;border-radius:4px;background:rgba(255,107,107,.08);'
                f'color:#FF6B6B;border:1px solid rgba(255,107,107,.2);margin:3px;display:inline-block;font-weight:600">{k}</span>'
                for k in kws
            )
            st.markdown(f'<div style="margin-top:8px;line-height:2">{tags_html}</div>', unsafe_allow_html=True)

        st.markdown("---")
        ir1, ir2, ir3 = st.columns(3)
        ir1.metric("Interview Ready", f"{iv.get('score',0)}%", iv.get("label","--"))
        ir2.metric("Seniority Gap",   f"{sm.get('gap_levels',0)} level(s)")
        ir3.metric("Est. Career Time",f"~{cgm} months")
        st.markdown(
            f'<div style="font-size:.82rem;color:#8892a4;margin-top:8px">'
            f'✅ Required Known: <b>{iv.get("req_known",0)}</b> &nbsp;·&nbsp; '
            f'🟡 Partial: <b>{iv.get("req_partial",0)}</b> &nbsp;·&nbsp; '
            f'❌ Missing: <b>{iv.get("req_missing",0)}</b> &nbsp;·&nbsp; '
            f'💡 {iv.get("advice","")}</div>',
            unsafe_allow_html=True,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — SALARY + REWRITE
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        sc, rw = st.columns(2, gap="large")

        with sc:
            st.markdown('<div class="sf-sec">💰 Live Salary Lookup</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sf-sec-sub">Role: {jd.get("role_title","--")} · Groq web search tool</div>',
                        unsafe_allow_html=True)
            loc = st.selectbox("Location", ["India","USA","UK","Germany","Canada","Singapore"], index=0)
            if st.button("🔍 Fetch Live Salary", key="sal_btn"):
                with st.spinner("Searching market data via Groq…"):
                    sal = fetch_live_salary(jd.get("role_title","the role"), loc)
                if sal.get("median_lpa",0):
                    st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar":False})
                    st.caption(f"Source: {sal.get('source','market data')} · {sal.get('note','')}")
                else:
                    st.warning(f"Could not fetch: {sal.get('note','unavailable')}")

        with rw:
            st.markdown('<div class="sf-sec">✍ AI Resume Rewrite</div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec-sub">ATS-optimized rewrite targeting this JD + missing keywords</div>',
                        unsafe_allow_html=True)
            rtxt = st.session_state.get("resume_txt","")
            if not rtxt:
                st.info("No resume text available (image-only uploads can't be rewritten).")
            else:
                if st.button("🔄 Rewrite Resume", key="rw_btn"):
                    with st.spinner("Rewriting with llama-4-scout…"):
                        rewritten = rewrite_resume(rtxt, jd, ql.get("missing_keywords",[]))
                    st.text_area("Rewritten Resume (ATS-optimized)", value=rewritten,
                                 height=300, key="rw_result", label_visibility="visible")

        # PDF Export
        st.markdown("---")
        st.markdown('<div class="sf-sec">📄 Download Report</div>', unsafe_allow_html=True)
        ec1, ec2 = st.columns([1,2])
        with ec1:
            for k,v in [("Candidate",c.get("name","--")),("Role",jd.get("role_title","--")),
                         ("ATS Score",f"{ql.get('ats_score','--')}%"),("Grade",ql.get("overall_grade","--")),
                         ("Current Fit",f"{im['current_fit']}%"),("Projected",f"{im['projected_fit']}% (+{im['fit_delta']}%)"),
                         ("Modules",im["modules_count"]),("Training",f"{im['roadmap_hours']}h")]:
                c1x, c2x = st.columns([1,2]); c1x.caption(k); c2x.markdown(f"**{v}**")
        with ec2:
            if REPORTLAB:
                pdf_buf = build_pdf(c, jd, gp, pt, im, ql, iv)
                nm = (c.get("name","candidate") or "candidate").replace(" ","_")
                fn = f"skillforge_v5_{nm}_{datetime.now().strftime('%Y%m%d')}.pdf"
                st.download_button("⬇ Download PDF Report", data=pdf_buf, file_name=fn,
                                    mime="application/pdf", use_container_width=True)
            else:
                st.warning("`pip install reportlab` to enable PDF export")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — API LOG
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[4]:
        total_cost = sum(e.get("cost",0) for e in _audit_log)
        st.markdown('<div class="sf-sec">🔍 Groq API Audit Log</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sf-sec-sub">{len(_audit_log)} calls · ${total_cost:.5f} total · key: .env only</div>',
                    unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            used  = sum(e.get("in",0)+e.get("out",0) for e in _audit_log)
            limit = 500_000
            pct   = min(100, round(used/limit*100))
            st.caption(f"**llama-4-scout:** {used:,} / {limit:,} tokens ({pct}%)")
            st.progress(pct/100)
        with b2:
            st.caption(f"**Session cost:** ${total_cost:.5f}")
            st.caption(f"**Model:** {MODEL_FAST.split('/')[-1]}")

        st.markdown("---")
        for e in reversed(_audit_log[-25:]):
            ok = e.get("status") == "ok"
            st.markdown(
                f'<div class="sf-ar">'
                f'<span style="color:{"#4ECDC4" if ok else "#FF6B6B"}">{"●" if ok else "✕"}</span>'
                f'<span style="color:#a78bfa">{e.get("ts","--")}</span>'
                f'<span style="color:#4ECDC4">{e.get("model","--")}</span>'
                f'<span>in:{e.get("in",0)} out:{e.get("out",0)} cached:{e.get("cached",0)}</span>'
                f'<span>{e.get("ms",0)}ms</span>'
                f'<span>${e.get("cost",0):.6f}</span>'
                f'<span style="color:{"#4ECDC4" if ok else "#FF6B6B"}">{e.get("status","--")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)
    render_status_bar()

# =============================================================================
#  CLI MODE  (python main.py --analyze junior_swe)
# =============================================================================
def cli_analyze(scenario_key: str):
    if scenario_key not in SAMPLES:
        print(f"Unknown scenario '{scenario_key}'. Choose: {list(SAMPLES.keys())}"); sys.exit(1)
    s = SAMPLES[scenario_key]
    print(f"\n  SkillForge v5 CLI  ·  {s['label']}")
    print("  " + "="*52)
    t0 = time.time()
    result = run_analysis(s["resume"], s["jd"])
    print(f"  Done in {round(time.time()-t0,2)}s")
    if "error" in result: print(f"  ❌ {result}"); return
    c=result["candidate"]; im=result["impact"]; iv=result["interview"]; pt=result["path"]
    print(f"\n  Candidate : {c.get('name','--')} ({c.get('seniority','--')})")
    print(f"  Role      : {result['jd'].get('role_title','--')}")
    print(f"  Fit       : {im['current_fit']}% → {im['projected_fit']}% (+{im['fit_delta']}%)")
    print(f"  Interview : {iv['score']}% ({iv['label']})")
    print(f"  Roadmap   : {im['modules_count']} modules / {im['roadmap_hours']}h / {im['critical_count']} critical")
    for i,m in enumerate(pt):
        crit = "★ " if m.get("is_critical") else "  "
        print(f"    {crit}#{i+1:02d} [{m['level'][:3]}] {m['title']}  ({m['duration_hrs']}h)")
    print(f"\n  Hours saved vs generic 60h onboarding: ~{im['hours_saved']}h\n")

# =============================================================================
#  ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkillForge v5")
    parser.add_argument("--analyze", metavar="SCENARIO",
                        help="CLI mode: junior_swe | senior_ds | hr_manager")
    args, _ = parser.parse_known_args()

    if args.analyze:
        cli_analyze(args.analyze)
    else:
        threading.Thread(target=_load_semantic_bg, daemon=True).start()
        main()