# =============================================================================
#  main.py — SkillForge v8  |  Clean redesign · Real data only · Feature-effective
#  Run: streamlit run main.py
# =============================================================================

import os, sys, json, io, re, time, hashlib, shelve, threading, argparse, base64
from typing import Tuple, Optional, List, Dict, Any
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

# =============================================================================
#  WEB SEARCH
# =============================================================================
def ddg_search(query: str, max_results: int = 5) -> List[dict]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

# =============================================================================
#  SEMANTIC MATCHING
# =============================================================================
SEMANTIC, _ST, _CEMBS = False, None, None

def _load_semantic_bg():
    global SEMANTIC, _ST, _CEMBS
    try:
        from sentence_transformers import SentenceTransformer
        _ST    = SentenceTransformer("all-MiniLM-L6-v2")
        _CEMBS = _ST.encode([c["skill"].lower() for c in CATALOG])
        SEMANTIC = True
    except Exception:
        pass

# =============================================================================
#  GROQ CLIENT
# =============================================================================
_GROQ_KEY = os.getenv("GROQ_API_KEY", "")
if not _GROQ_KEY:
    st.error("**GROQ_API_KEY missing** — add it to `.env`  →  [console.groq.com](https://console.groq.com)")
    st.stop()

GROQ_CLIENT  = Groq(api_key=_GROQ_KEY)
MODEL_FAST   = "meta-llama/llama-4-scout-17b-16e-instruct"
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

# Scenarios — no fake computed stats; those are calculated after analysis
SAMPLES = {
    "junior_swe": {
        "label": "Junior SWE → Full Stack",
        "description": "1 yr experience · Python basics · HTML/CSS · no cloud",
        "resume": """John Smith
Junior Software Developer | 1 year experience
Skills: Python (basic, 4/10), HTML/CSS, some JavaScript
Education: B.Tech Computer Science 2023
Projects: Built a todo app using Flask. Familiar with Git basics.
No professional cloud or DevOps experience.""",
        "jd": """Software Engineer Full Stack - Mid Level
Required: Python, React, FastAPI, Docker, SQL, REST APIs, AWS
Preferred: Kubernetes, CI/CD
Seniority: Mid | Domain: Tech""",
    },
    "senior_ds": {
        "label": "Senior DS → Lead AI",
        "description": "7 yr experience · Python expert · NLP & MLOps unused 2+ yrs",
        "resume": """Priya Patel
Senior Data Scientist | 7 years experience
Skills: Python (expert, 9/10), Machine Learning (expert), Deep Learning (PyTorch, 8/10), SQL (advanced, 8/10), AWS SageMaker (7/10)
Last used NLP: 2022. Last used MLOps: 2021.
Led team of 5. Published 3 ML papers.""",
        "jd": """Lead Data Scientist - AI Products
Required: Python, Machine Learning, Deep Learning, NLP, MLOps, SQL, AWS
Preferred: GCP, Kubernetes, Leadership
Seniority: Lead | Domain: Tech""",
    },
    "hr_manager": {
        "label": "HR Coordinator → Manager",
        "description": "3 yr experience · Recruitment strength · no L&D or leadership",
        "resume": """Amara Johnson
HR Coordinator | 3 years experience
Skills: Human Resources (intermediate, 6/10), Recruitment (good, 7/10), Microsoft Office
Some performance review experience. No formal L&D training.""",
        "jd": """HR Manager - People and Culture
Required: Human Resources, Recruitment, Performance Management, Employee Relations
Preferred: L&D Strategy, Communication, Leadership
Seniority: Senior | Domain: Non-Tech""",
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
#  FILE PARSER
# =============================================================================
def parse_uploaded_file(f) -> Tuple[str, Optional[str]]:
    if f is None: return "", None
    name = f.name.lower(); raw = f.read()
    if name.endswith(".pdf"):
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages), None
        except Exception as e: return f"[PDF error: {e}]", None
    if name.endswith(".docx"):
        try:
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs), None
        except Exception as e: return f"[DOCX error: {e}]", None
    if any(name.endswith(x) for x in [".jpg",".jpeg",".png",".webp"]):
        media = ("image/jpeg" if name.endswith((".jpg",".jpeg"))
                 else "image/png" if name.endswith(".png") else "image/webp")
        return "", f"data:{media};base64,{base64.b64encode(raw).decode()}"
    return raw.decode("utf-8", errors="ignore"), None

# =============================================================================
#  GROQ CALLS
# =============================================================================
_audit_log: List[dict] = []

def _groq_call(prompt: str, system: str, model: str = MODEL_FAST,
               max_tokens: int = 2800, image_b64: Optional[str] = None) -> dict:
    content: Any = prompt
    if image_b64:
        content = [{"type":"image_url","image_url":{"url":image_b64}},
                   {"type":"text","text":prompt}]
    messages = [{"role":"system","content":system},{"role":"user","content":content}]
    t0 = time.time()
    try:
        r = GROQ_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1,
            max_tokens=max_tokens, response_format={"type":"json_object"},
        )
        usage = r.usage
        in_tok  = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        cost = round((in_tok*0.00000011)+(out_tok*0.00000034),6)
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),
                           "model":model.split("/")[-1][:22],
                           "in":in_tok,"out":out_tok,
                           "ms":round((time.time()-t0)*1000),"cost":cost,"status":"ok"})
        return json.loads(r.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"error":"json_parse_failed"}
    except Exception as e:
        err = str(e); wait_s = 0
        if "429" in err or "rate_limit" in err:
            m = re.search(r"try again in (\d+)m([\d.]+)s", err)
            if m: wait_s = int(m.group(1))*60+float(m.group(2))
            return {"error":"rate_limited","wait_seconds":int(wait_s),
                    "message":f"Rate limited. Retry in {int(wait_s//60)}m{int(wait_s%60)}s."}
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),
                           "model":model.split("/")[-1][:22],
                           "status":f"err:{err[:40]}","in":0,"out":0,"ms":0,"cost":0})
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

def rewrite_resume(resume_text: str, jd: dict, missing_kw: List[str]) -> str:
    r = _groq_call(
        f'Rewrite this resume for the target role. Naturally add missing keywords: {missing_kw[:8]}. '
        f'Keep all facts true. Return JSON: {{"rewritten_resume":"<text>"}}\n\n'
        f'Resume:\n{resume_text[:1500]}\n\nTarget: {jd.get("role_title","--")}  '
        f'Required: {jd.get("required_skills",[])}',
        system="Expert resume writer. Return JSON only.", model=MODEL_FAST, max_tokens=1500,
    )
    return r.get("rewritten_resume","Could not rewrite resume.")

# =============================================================================
#  WEB SEARCH FEATURES
# =============================================================================
def search_real_salary(role: str, location: str) -> dict:
    results = ddg_search(f"{role} salary {location} 2025 average annual", max_results=6)
    if not results:
        return {}
    snippets = "\n".join([f"- {r.get('title','')}: {r.get('body','')[:200]}" for r in results[:5]])
    r = _groq_call(
        f'Extract salary data for "{role}" in {location} from these search snippets.\n\n{snippets}\n\n'
        f'Return JSON: {{"min_lpa":<number>,"max_lpa":<number>,"median_lpa":<number>,'
        f'"currency":"INR or USD","source":"<website name>","note":"<key caveat>"}}',
        system="Extract structured salary info from web snippets. Return JSON only.",
        model=MODEL_FAST, max_tokens=400,
    )
    return r if ("error" not in r and r.get("median_lpa",0) > 0) else {}

def search_course_links(skill: str) -> List[dict]:
    results = ddg_search(f'"{skill}" online course 2025 coursera OR udemy OR youtube', max_results=6)
    courses = []
    for r in results:
        url  = r.get("href","")
        body = r.get("body","")
        if not url: continue
        if   "coursera.org" in url: plat, icon = "Coursera", "🎓"
        elif "udemy.com"    in url: plat, icon = "Udemy",    "🎯"
        elif "youtube.com"  in url: plat, icon = "YouTube",  "▶"
        elif "edx.org"      in url: plat, icon = "edX",      "📘"
        elif "linkedin.com" in url: plat, icon = "LinkedIn", "💼"
        else: continue
        courses.append({"title":r.get("title","")[:65],"url":url,
                        "platform":plat,"icon":icon,"snippet":body[:100]})
    return courses[:3]

def search_skill_trends(skills: List[str]) -> Dict[str, str]:
    if not skills: return {}
    query = " ".join(skills[:6])
    results = ddg_search(f"most in-demand skills 2025 2026 hiring {query}", max_results=4)
    text = " ".join([r.get("body","") for r in results]).lower()
    out = {}
    for skill in skills:
        sl = skill.lower()
        count = text.count(sl)
        out[skill] = ("🔥 Hot" if count >= 3 else "📈 Growing" if count >= 1 else "✓ Stable")
    return out

def search_job_market(role: str) -> List[str]:
    results = ddg_search(f'"{role}" job market hiring trends 2025 2026', max_results=4)
    if not results: return []
    snippets = "\n".join([r.get("body","")[:300] for r in results[:4]])
    r = _groq_call(
        f'Based on these search results about "{role}" job market, give 3 short specific insights.\n\n'
        f'{snippets}\n\nReturn JSON: {{"insights":["<insight1>","<insight2>","<insight3>"]}}',
        system="Job market analyst. Return JSON only.", model=MODEL_FAST, max_tokens=300,
    )
    return r.get("insights",[]) if "error" not in r else []

# =============================================================================
#  CACHE
# =============================================================================
_CACHE_PATH = "/tmp/skillforge_v8"
def _ckey(r: str, j: str) -> str: return hashlib.md5((r+"||"+j).encode()).hexdigest()
def cache_get(r, j):
    try:
        with shelve.open(_CACHE_PATH) as db: return db.get(_ckey(r,j))
    except: return None
def cache_set(r, j, v):
    try:
        with shelve.open(_CACHE_PATH) as db: db[_ckey(r,j)] = v
    except: pass

# =============================================================================
#  ANALYSIS ENGINE
# =============================================================================
def _match_skill(skill: str) -> int:
    sl = (skill.lower().replace(".js","").replace(".ts","")
                       .replace("(","").replace(")","").strip())
    for i, cs in enumerate(CATALOG_SKILLS):
        if sl == cs or sl in cs or cs in sl: return i
    if SEMANTIC and _ST and _CEMBS is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            sims = cosine_similarity(_ST.encode([sl]), _CEMBS)[0]
            best = int(np.argmax(sims))
            if sims[best] >= 0.52: return best
        except: pass
    tokens = set(sl.split()); best_s, best_i = 0.0, -1
    for i, cs in enumerate(CATALOG_SKILLS):
        ov = len(tokens & set(cs.split())) / max(len(tokens), 1)
        if ov > best_s: best_s, best_i = ov, i
    return best_i if best_s >= 0.4 else -1

def skill_decay(p, yr):
    if yr <= 0 or yr >= CURRENT_YEAR - 1: return p, False
    yrs = CURRENT_YEAR - yr
    if yrs <= 2: return p, False
    a = round(p * max(0.5, 1 - yrs / 5)); return a, a < p

def analyze_gap(candidate, jd):
    rs = {s["skill"].lower(): s for s in candidate.get("skills", [])}
    all_s = [(s, True) for s in jd.get("required_skills", [])] + \
            [(s, False) for s in jd.get("preferred_skills", [])]
    out = []
    for skill, req in all_s:
        sl = skill.lower().replace(".js","").replace(".ts","").strip()
        status, prof, ctx, dec, orig = "Missing", 0, "", False, 0
        src = rs.get(sl) or next((v for k,v in rs.items() if sl in k or k in sl), None)
        if src:
            raw_p = src.get("proficiency", 0); prof, dec = skill_decay(raw_p, src.get("year_last_used", 0))
            orig, ctx = raw_p, src.get("context",""); status = "Known" if prof >= 7 else "Partial"
        idx = _match_skill(skill)
        demand = MARKET_DEMAND.get(sl, MARKET_DEMAND.get(skill.lower(), 1))
        obs = OBSOLESCENCE_RISK.get(sl)
        out.append({"skill":skill,"status":status,"proficiency":prof,"original_prof":orig,
                    "decayed":dec,"is_required":req,"context":ctx,
                    "catalog_course":CATALOG[idx] if idx >= 0 else None,
                    "demand":demand,"obsolescence_risk":obs})
    return out

def seniority_check(c, jd):
    cs, rs = c.get("seniority","Mid"), jd.get("seniority_required","Mid")
    gap = SENIORITY_MAP.get(rs,1) - SENIORITY_MAP.get(cs,1)
    return {"has_mismatch":gap>0,"gap_levels":gap,"candidate":cs,"required":rs,
            "add_leadership":gap>=1,"add_strategic":gap>=2}

def build_path(gp, c, jd=None):
    needed = set(); id2gap = {}
    for g in gp:
        if g["status"] == "Known": continue
        co = g.get("catalog_course")
        if not co: continue
        needed.add(co["id"]); id2gap[co["id"]] = g
        try:
            for anc in nx.ancestors(SKILL_GRAPH, co["id"]):
                ad = CATALOG_BY_ID.get(anc)
                if ad and not any(x["status"]=="Known" and x["skill"].lower() in ad["skill"].lower()
                                  for x in gp):
                    needed.add(anc)
        except: pass
    if jd:
        sm = seniority_check(c, jd)
        if sm["add_leadership"]: needed.update(["LD01","LD02"])
        if sm["add_strategic"]:  needed.add("LD03")
    sub = SKILL_GRAPH.subgraph(needed)
    try: ordered = list(nx.topological_sort(sub))
    except: ordered = list(needed)
    crit = set()
    try:
        if sub.nodes: crit = set(nx.dag_longest_path(sub))
    except: pass
    path, seen = [], set()
    for cid in ordered:
        if cid in seen: continue
        seen.add(cid); co = CATALOG_BY_ID.get(cid)
        if not co: continue
        g = id2gap.get(cid, {})
        path.append({**co,
                     "gap_skill":  g.get("skill", co["skill"]),
                     "gap_status": g.get("status","Prereq"),
                     "priority":   (0 if g.get("is_required") else 1, g.get("proficiency",0)),
                     "reasoning":  "",
                     "is_critical":cid in crit,
                     "demand":     g.get("demand", 1),
                     "is_required":g.get("is_required", False)})
    path.sort(key=lambda x: x["priority"]); return path

def calc_impact(gp, path):
    tot = len(gp); known = sum(1 for g in gp if g["status"]=="Known")
    covered = len({m["gap_skill"] for m in path}); rhrs = sum(m["duration_hrs"] for m in path)
    cur  = min(100, round(known/max(tot,1)*100))
    proj = min(100, round((known+covered)/max(tot,1)*100))
    return {"total_skills":tot,"known_skills":known,"gaps_addressed":covered,
            "roadmap_hours":rhrs,"hours_saved":max(0,60-rhrs),
            "current_fit":cur,"projected_fit":proj,"fit_delta":proj-cur,
            "modules_count":len(path),"critical_count":sum(1 for m in path if m.get("is_critical")),
            "decayed_skills":sum(1 for g in gp if g.get("decayed"))}

def interview_readiness(gp, c):
    rk = [g for g in gp if g["status"]=="Known"   and g["is_required"]]
    rp = [g for g in gp if g["status"]=="Partial"  and g["is_required"]]
    rm = [g for g in gp if g["status"]=="Missing"  and g["is_required"]]
    tot = max(len(rk)+len(rp)+len(rm), 1)
    sc = max(0, min(100, round((len(rk)+len(rp)*0.4)/tot*100)
                    + {"Junior":5,"Mid":0,"Senior":-5,"Lead":-10}.get(c.get("seniority","Mid"),0)))
    if   sc >= 75: v = ("Strong",    "#4ade80", "Ready for most rounds")
    elif sc >= 50: v = ("Moderate",  "#fbbf24", "Pass screening; prep gaps")
    elif sc >= 30: v = ("Weak",      "#fb923c", "Gap work before applying")
    else:          v = ("Not Ready", "#f87171", "Significant prep needed")
    return {"score":sc,"label":v[0],"color":v[1],"advice":v[2],
            "req_known":len(rk),"req_partial":len(rp),"req_missing":len(rm)}

def weekly_plan(path, hpd=2.0):
    cap, weeks, cur, hrs, wn = hpd*5, [], [], 0.0, 1
    for m in path:
        rem = float(m["duration_hrs"])
        while rem > 0:
            avail = cap - hrs
            if avail <= 0:
                weeks.append({"week":wn,"modules":cur,"total_hrs":hrs})
                cur, hrs, wn = [], 0.0, wn+1; avail = cap
            chunk = min(rem, avail)
            ex = next((x for x in cur if x["id"]==m["id"]), None)
            if ex: ex["hrs_this_week"] += chunk
            else:  cur.append({"id":m["id"],"title":m["title"],"level":m["level"],
                                "domain":m["domain"],"is_critical":m.get("is_critical",False),
                                "hrs_this_week":chunk,"total_hrs":m["duration_hrs"]})
            hrs += chunk; rem -= chunk
    if cur: weeks.append({"week":wn,"modules":cur,"total_hrs":hrs})
    return weeks

def transfer_map_calc(c, gp):
    known = {g["skill"].lower() for g in c.get("skills",[]) if g.get("proficiency",0) >= 6}
    out = []
    for g in gp:
        if g["status"] == "Known": continue
        sl = g["skill"].lower()
        for k in known:
            pct = TRANSFER_MAP.get(k,{}).get(sl, 0)
            if pct: out.append({"gap_skill":g["skill"],"known_skill":k.title(),
                                  "transfer_pct":pct,
                                  "label":f"Your {k.title()} → {pct}% head start on {g['skill']}"})
    return sorted(out, key=lambda x: x["transfer_pct"], reverse=True)

def roi_rank(gp, path):
    out = []
    for m in path:
        g = next((x for x in gp if x["skill"]==m.get("gap_skill")), {})
        roi = round((g.get("demand",1)*(1.5 if g.get("is_required") else 1)*10)/max(m["duration_hrs"],1), 2)
        out.append({"id":m["id"],"title":m["title"],"skill":m["skill"],"roi":roi,
                    "hrs":m["duration_hrs"],"is_required":g.get("is_required",False)})
    return sorted(out, key=lambda x: x["roi"], reverse=True)

def weeks_ready(hrs, hpd):
    if hpd <= 0: return "-"
    w = (hrs/hpd)/5
    if w < 1:   return f"{int(hrs/hpd)}d"
    elif w < 4: return f"{w:.1f}w"
    return f"{(w/4):.1f}mo"

# =============================================================================
#  FULL PIPELINE
# =============================================================================
def run_analysis(resume_text, jd_text, resume_image_b64=None):
    cache_k = resume_text or "img"
    cached = cache_get(cache_k, jd_text)
    if cached: cached["_cache_hit"] = True; return cached
    kws = [w.strip() for w in jd_text.split() if len(w)>3][:20]
    potential_mods = [c for c in CATALOG
                      if any(kw.lower() in c["skill"].lower() or c["skill"].lower() in kw.lower()
                             for kw in kws)][:10]
    raw = mega_call(resume_text=resume_text, jd_text=jd_text,
                    modules_hint=potential_mods, resume_image_b64=resume_image_b64)
    if "error" in raw: return raw
    candidate = raw.get("candidate",{}); jd_data = raw.get("jd",{})
    quality = raw.get("audit",{}); rsn_map = raw.get("reasoning",{})
    if not candidate or not jd_data:
        return {"error":"parse_failed — empty candidate or JD"}
    gp   = analyze_gap(candidate, jd_data)
    path = build_path(gp, candidate, jd_data)
    for m in path: m["reasoning"] = rsn_map.get(m["id"], f"Addresses gap in {m['gap_skill']}.")
    im  = calc_impact(gp, path);      sm  = seniority_check(candidate, jd_data)
    iv  = interview_readiness(gp, candidate); wp = weekly_plan(path)
    tf  = transfer_map_calc(candidate, gp);   roi = roi_rank(gp, path)
    obs = [{"skill":g["skill"],"status":g["status"],"reason":OBSOLESCENCE_RISK[g["skill"].lower()]}
           for g in gp if OBSOLESCENCE_RISK.get(g["skill"].lower())]
    cgm = max(0, SENIORITY_MAP.get(jd_data.get("seniority_required","Mid"),1)
                 - SENIORITY_MAP.get(candidate.get("seniority","Mid"),1)) * 18
    result = {"candidate":candidate,"jd":jd_data,"gap_profile":gp,"path":path,
              "impact":im,"seniority":sm,"quality":quality,"interview":iv,
              "weekly_plan":wp,"transfers":tf,"roi":roi,"obsolescence":obs,
              "career_months":cgm,"_cache_hit":False}
    cache_set(cache_k, jd_text, result); return result

def run_analysis_with_web(resume_text, jd_text, resume_image_b64=None, location="India"):
    result = run_analysis(resume_text, jd_text, resume_image_b64)
    if "error" in result: return result
    role = result["jd"].get("role_title","")
    gap_skills = [g["skill"] for g in result["gap_profile"] if g["status"] != "Known"][:6]
    with ThreadPoolExecutor(max_workers=3) as ex:
        sal_f   = ex.submit(search_real_salary, role, location)
        trend_f = ex.submit(search_skill_trends, gap_skills)
        mkt_f   = ex.submit(search_job_market, role)
    result["salary"]          = sal_f.result()
    result["skill_trends"]    = trend_f.result()
    result["market_insights"] = mkt_f.result()
    return result

# =============================================================================
#  PDF EXPORT
# =============================================================================
def build_pdf(c, jd, gp, path, im, ql=None, iv=None):
    buf = io.BytesIO()
    if not REPORTLAB: return buf
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=48, bottomMargin=48, leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    TEAL = rl_colors.HexColor("#2dd4bf")
    BD = ParagraphStyle("BD", parent=styles["Normal"], fontSize=10, spaceAfter=5)
    H1 = ParagraphStyle("H1", parent=styles["Title"],   fontSize=20, spaceAfter=4, textColor=TEAL)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"],fontSize=13, spaceAfter=6, spaceBefore=14)
    IT = ParagraphStyle("IT", parent=styles["Normal"],  fontSize=9,  spaceAfter=4, leftIndent=18,
                        textColor=rl_colors.HexColor("#555"))
    story = [
        Paragraph("SkillForge — AI Adaptive Onboarding Report", H1),
        Paragraph(f"Candidate: <b>{c.get('name','--')}</b>  |  Role: <b>{jd.get('role_title','--')}</b>  "
                  f"|  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}", BD),
        Spacer(1, 14),
    ]
    if ql or iv:
        story.append(Paragraph("Scores", H2))
        rows = []
        if ql: rows += [["ATS Score", f"{ql.get('ats_score','--')}%"],
                        ["Grade", ql.get("overall_grade","--")],
                        ["Completeness", f"{ql.get('completeness_score','--')}%"],
                        ["Clarity", f"{ql.get('clarity_score','--')}%"]]
        if iv: rows += [["Interview Ready", f"{iv['score']}% — {iv['label']}"],
                        ["Known", str(iv["req_known"])],
                        ["Missing", str(iv["req_missing"])]]
        t = Table([["Metric","Value"]]+rows, colWidths=[200,260])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),TEAL),
            ("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
            ("FONTSIZE",(0,0),(-1,-1),10),
            ("GRID",(0,0),(-1,-1),0.4,rl_colors.grey),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.whitesmoke,rl_colors.white]),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story += [t, Spacer(1,14)]
    story.append(Paragraph("Learning Roadmap", H2))
    for i, m in enumerate(path):
        story.append(Paragraph(
            f"<b>{i+1}. {'[CRITICAL] ' if m.get('is_critical') else ''}{m['title']}</b>"
            f" — {m['level']} / {m['duration_hrs']}h", BD))
        if m.get("reasoning"): story.append(Paragraph(f"→ {m['reasoning']}", IT))
    doc.build(story); buf.seek(0); return buf

# =============================================================================
#  CHARTS
# =============================================================================
_BG     = "rgba(0,0,0,0)"
_GRID   = "rgba(255,255,255,0.05)"
_TEAL   = "#2dd4bf"
_AMBER  = "#f59e0b"
_RED    = "#ef4444"
_GREEN  = "#4ade80"
_PURPLE = "#a78bfa"
_FONT   = dict(color="#94a3b8", family="'IBM Plex Mono', monospace")

def _base_layout(**kw):
    return dict(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=_FONT, margin=dict(l=10,r=10,t=10,b=30),
        **kw
    )

def radar_chart(gp):
    items = gp[:10]
    if not items: return go.Figure()
    theta = [g["skill"][:16] for g in items]
    fig = go.Figure(data=[
        go.Scatterpolar(r=[10]*len(items), theta=theta, fill="toself",
                        name="Required", line=dict(color=_RED, width=1), opacity=0.1),
        go.Scatterpolar(r=[g.get("original_prof", g["proficiency"]) for g in items],
                        theta=theta, fill="toself", name="Before decay",
                        line=dict(color=_AMBER, width=1, dash="dot"), opacity=0.25),
        go.Scatterpolar(r=[g["proficiency"] for g in items], theta=theta, fill="toself",
                        name="Current", line=dict(color=_TEAL, width=2), opacity=0.7),
    ])
    fig.update_layout(
        **_base_layout(height=300),
        polar=dict(bgcolor=_BG,
                   radialaxis=dict(visible=True, range=[0,10], gridcolor=_GRID,
                                   tickfont=dict(size=8, color="#475569")),
                   angularaxis=dict(gridcolor=_GRID, tickfont=dict(size=9))),
        showlegend=True,
        legend=dict(bgcolor=_BG, x=0.75, y=1.18, font=dict(size=9)),
    )
    return fig

def timeline_chart(path):
    if not path: return go.Figure()
    lc = {"Critical":_RED,"Beginner":_TEAL,"Intermediate":_AMBER,"Advanced":"#f97316"}
    shown, fig = set(), go.Figure()
    for i, m in enumerate(path):
        k = "Critical" if m.get("is_critical") else m["level"]
        show = k not in shown; shown.add(k)
        fig.add_trace(go.Bar(
            x=[m["duration_hrs"]], y=[f"{m['title'][:26]}"],
            orientation="h",
            marker=dict(color=lc.get(k,"#64748b"), opacity=0.82,
                        line=dict(width=0),
                        pattern=dict(shape="/" if m.get("is_critical") else "")),
            name=k, legendgroup=k, showlegend=show,
            hovertemplate=f"<b>{m['title']}</b><br>{m['level']} · {m['duration_hrs']}h<extra></extra>",
        ))
    fig.update_layout(
        **_base_layout(height=max(240, len(path)*34)),
        xaxis=dict(title="Hours", gridcolor=_GRID, zeroline=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9.5), autorange="reversed"),
        legend=dict(bgcolor=_BG, orientation="h", y=1.04, font=dict(size=9)),
        barmode="overlay",
    )
    return fig

def roi_chart(roi_list):
    if not roi_list: return go.Figure()
    top = roi_list[:10]
    colors = [_RED if m["is_required"] else _TEAL for m in top]
    fig = go.Figure(go.Bar(
        x=[m["roi"] for m in top],
        y=[m["title"][:26] for m in top],
        orientation="h",
        marker=dict(color=colors, opacity=0.82, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>ROI: %{x}<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=max(200, len(top)*30)),
        xaxis=dict(title="ROI Index", gridcolor=_GRID, zeroline=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", autorange="reversed", tickfont=dict(size=9.5)),
    )
    return fig

def priority_matrix(gp):
    ease_map = {"Beginner":9,"Intermediate":5,"Advanced":2}
    pts = [{"skill":g["skill"],
             "ease":ease_map.get((g.get("catalog_course") or {}).get("level","Intermediate"),5),
             "impact":min(10, g.get("demand",1)*3+(3 if g["is_required"] else 0)),
             "hrs":(g.get("catalog_course") or {}).get("duration_hrs",6),
             "status":g["status"]}
            for g in gp if g["status"]!="Known" and g.get("catalog_course")]
    if not pts: return go.Figure()
    fig = go.Figure()
    for sl, col in [("Missing",_RED),("Partial",_AMBER)]:
        sub = [p for p in pts if p["status"]==sl]
        if not sub: continue
        fig.add_trace(go.Scatter(
            x=[p["ease"] for p in sub], y=[p["impact"] for p in sub],
            mode="markers+text",
            marker=dict(size=[max(12, p["hrs"]*2.5) for p in sub], color=col, opacity=0.65),
            text=[p["skill"][:13] for p in sub], textposition="top center",
            textfont=dict(size=8.5, color="#94a3b8"), name=sl,
            hovertemplate="<b>%{text}</b><br>Ease:%{x:.1f} Impact:%{y:.1f}<extra></extra>",
        ))
    for x, y, t in [(2.5,8.5,"PRIORITY"),(7.5,8.5,"QUICK WIN"),
                    (2.5,2.5,"LONG HAUL"),(7.5,2.5,"OPTIONAL")]:
        fig.add_annotation(x=x, y=y, text=t, showarrow=False,
                           font=dict(size=8, color="#334155"))
    fig.add_hline(y=5.5, line_dash="dot", line_color=_GRID)
    fig.add_vline(x=5.5, line_dash="dot", line_color=_GRID)
    fig.update_layout(
        **_base_layout(height=320),
        xaxis=dict(title="Ease of learning", range=[0,11], gridcolor=_GRID, zeroline=False),
        yaxis=dict(title="Career impact", range=[0,11], gridcolor=_GRID, zeroline=False),
        showlegend=True,
        legend=dict(bgcolor=_BG, x=0, y=1.08, orientation="h", font=dict(size=9)),
    )
    return fig

def salary_chart(s):
    if not s or not s.get("median_lpa"): return go.Figure()
    vals = [s.get("min_lpa",0), s.get("median_lpa",0), s.get("max_lpa",0)]
    curr = s.get("currency","INR")
    sym  = "₹" if curr=="INR" else "$"
    unit = "L/yr" if curr=="INR" else "k/yr"
    labels = [f"{sym}{v}{unit}" for v in vals]
    fig = go.Figure(go.Bar(
        x=["Min","Median","Max"], y=vals,
        marker_color=[_TEAL, _AMBER, _RED], opacity=0.8,
        text=labels, textposition="outside",
        textfont=dict(size=10, family="'IBM Plex Mono', monospace"),
        hovertemplate="<b>%{x}</b><br>%{y}<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=220),
        yaxis=dict(title=unit, gridcolor=_GRID, zeroline=False),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    return fig

# =============================================================================
#  CSS — Syne + IBM Plex Mono · Dark precision aesthetic
# =============================================================================
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
:root {
  --bg:        #080b12;
  --surface:   #0f1420;
  --raised:    #161c2d;
  --border:    rgba(255,255,255,0.07);
  --border-hi: rgba(45,212,191,0.22);
  --teal:      #2dd4bf;
  --teal-dim:  rgba(45,212,191,0.10);
  --amber:     #f59e0b;
  --red:       #ef4444;
  --green:     #4ade80;
  --text-1:    #f1f5f9;
  --text-2:    #94a3b8;
  --text-3:    #3d4d66;
  --mono:      'IBM Plex Mono', monospace;
  --display:   'Syne', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
  font-family: var(--display) !important;
  background: var(--bg) !important;
  color: var(--text-2) !important;
}

.stApp { background: var(--bg) !important; }

.main .block-container {
  padding: 0 !important;
  max-width: 100% !important;
}

/* Hide Streamlit chrome */
footer, #MainMenu,
header[data-testid="stHeader"],
[data-testid="stToolbar"] { display: none !important; }

/* Sidebar */
section[data-testid="stSidebar"] > div:first-child {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 99px; }

/* ── TOPBAR ── */
.sf-topbar {
  height: 50px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 28px;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 200;
  background: rgba(8,11,18,0.96);
  backdrop-filter: blur(16px);
}
.sf-brand {
  font-family: var(--display);
  font-size: 1.05rem; font-weight: 800;
  color: var(--text-1); letter-spacing: -0.03em;
}
.sf-brand em { color: var(--teal); font-style: normal; }
.sf-topbar-right {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 0.62rem; color: var(--text-3);
}
.sf-pill {
  padding: 3px 9px; border-radius: 4px;
  border: 1px solid var(--border);
  color: var(--text-3); font-size: 0.6rem;
}
.sf-pill.active { border-color: var(--border-hi); color: var(--teal); }

/* ── LAYOUT ── */
.sf-page { padding: 0 28px 80px; max-width: 1160px; margin: 0 auto; }

/* ── WELCOME ── */
.sf-welcome {
  padding: 52px 0 36px;
  max-width: 600px;
}
.sf-welcome-eyebrow {
  font-family: var(--mono); font-size: 0.65rem; font-weight: 500;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--teal); margin-bottom: 14px;
  display: flex; align-items: center; gap: 8px;
}
.sf-welcome-eyebrow::before {
  content: ''; display: inline-block;
  width: 24px; height: 1px; background: var(--teal);
}
.sf-welcome-title {
  font-family: var(--display); font-size: clamp(1.8rem,4vw,3rem);
  font-weight: 800; color: var(--text-1);
  line-height: 1.1; letter-spacing: -0.04em;
  margin-bottom: 16px;
}
.sf-welcome-title span { color: var(--teal); }
.sf-welcome-body {
  font-size: 0.9rem; color: var(--text-2); line-height: 1.65;
  max-width: 460px;
}

/* ── SCENARIO GRID ── */
.sf-scenario-label {
  font-family: var(--mono); font-size: 0.6rem; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-3); margin-bottom: 10px;
}
.sf-scenario-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 16px;
  cursor: pointer; transition: all 0.14s;
}
.sf-scenario-card:hover {
  border-color: var(--border-hi);
  background: var(--raised);
}
.sf-scenario-title {
  font-family: var(--display); font-size: 0.82rem; font-weight: 700;
  color: var(--text-1); margin-bottom: 4px;
}
.sf-scenario-desc {
  font-family: var(--mono); font-size: 0.65rem; color: var(--text-3);
  line-height: 1.4;
}

/* ── INPUT BLOCK ── */
.sf-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px; padding: 20px 22px;
  margin-bottom: 14px;
}
.sf-block-hd {
  font-family: var(--display); font-size: 0.8rem; font-weight: 700;
  color: var(--text-1); margin-bottom: 14px;
  display: flex; align-items: center; justify-content: space-between;
}
.sf-block-step {
  font-family: var(--mono); font-size: 0.58rem; padding: 2px 8px;
  border-radius: 4px; background: var(--teal-dim);
  color: var(--teal); border: 1px solid var(--border-hi);
}
.sf-preview-strip {
  display: flex; align-items: center; gap: 10px;
  background: rgba(45,212,191,0.04);
  border: 1px solid var(--border-hi);
  border-radius: 7px; padding: 9px 14px;
  margin-bottom: 16px;
  font-family: var(--mono); font-size: 0.7rem; color: var(--text-2);
}
.sf-preview-icon { color: var(--teal); font-size: 0.85rem; flex-shrink: 0; }

/* ── FILE UPLOADER ── */
[data-testid="stFileUploadDropzone"] {
  background: rgba(45,212,191,0.02) !important;
  border: 1.5px dashed rgba(45,212,191,0.16) !important;
  border-radius: 7px !important;
}
[data-testid="stFileUploadDropzone"]:hover {
  border-color: rgba(45,212,191,0.35) !important;
  background: rgba(45,212,191,0.04) !important;
}
[data-testid="stFileUploadDropzone"] button {
  background: transparent !important;
  border: 1px solid var(--border-hi) !important;
  color: var(--teal) !important;
  font-family: var(--mono) !important;
  font-size: 0.7rem !important;
  border-radius: 5px !important;
}

/* Textarea */
textarea {
  background: #0a0e1a !important;
  border: 1px solid var(--border) !important;
  border-radius: 7px !important; color: #b0c0d8 !important;
  font-family: var(--mono) !important;
  font-size: 0.76rem !important;
  resize: vertical !important;
}
textarea:focus { border-color: var(--border-hi) !important; outline: none !important; }
textarea::placeholder { color: var(--text-3) !important; }

/* Primary button */
.stButton > button {
  background: var(--teal) !important; border: none !important;
  border-radius: 7px !important; color: #071013 !important;
  font-family: var(--display) !important;
  font-weight: 700 !important; font-size: 0.82rem !important;
  padding: 10px 0 !important; width: 100% !important;
  letter-spacing: 0.01em !important;
  transition: opacity 0.15s !important;
}
.stButton > button:hover { opacity: 0.82 !important; }
.stButton > button:disabled { opacity: 0.3 !important; }

/* Ghost variant */
.sf-ghost .stButton > button {
  background: var(--raised) !important;
  border: 1px solid var(--border) !important;
  color: var(--text-2) !important;
}
.sf-ghost .stButton > button:hover {
  border-color: rgba(255,255,255,0.15) !important;
  color: var(--text-1) !important;
}

/* ── RESULTS ── */
.sf-section-title {
  font-family: var(--display); font-size: 1.1rem; font-weight: 700;
  color: var(--text-1); letter-spacing: -0.02em;
  margin-bottom: 3px;
}
.sf-section-sub {
  font-family: var(--mono); font-size: 0.65rem; color: var(--text-3);
  margin-bottom: 18px;
}
.sf-divider { height: 1px; background: var(--border); margin: 28px 0; }

/* Score banner */
.sf-score-banner {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px; padding: 24px 28px;
  margin-bottom: 22px;
  display: grid; grid-template-columns: auto 1fr auto;
  gap: 32px; align-items: center;
}
@media(max-width:700px){ .sf-score-banner{ grid-template-columns:1fr; } }

.sf-score-main { text-align: center; }
.sf-score-num {
  font-family: var(--mono); font-size: 3.5rem; font-weight: 600;
  color: var(--teal); line-height: 1; letter-spacing: -0.04em;
}
.sf-score-label {
  font-family: var(--mono); font-size: 0.6rem; font-weight: 500;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-3); margin-top: 4px;
}
.sf-score-delta {
  font-family: var(--mono); font-size: 0.75rem;
  color: var(--text-2); margin-top: 6px;
}
.sf-score-delta strong { color: var(--green); font-weight: 600; }

.sf-kpi-strip { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; }
@media(max-width:600px){ .sf-kpi-strip{ grid-template-columns: repeat(2,1fr); } }
.sf-kpi {
  background: var(--raised); border: 1px solid var(--border);
  border-radius: 7px; padding: 12px 14px;
}
.sf-kpi-val {
  font-family: var(--mono); font-size: 1.35rem; font-weight: 600;
  color: var(--text-1); line-height: 1.1;
}
.sf-kpi-label {
  font-family: var(--mono); font-size: 0.58rem; font-weight: 500;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-3); margin-top: 3px;
}
.sf-kpi-note { font-family: var(--mono); font-size: 0.65rem; color: var(--teal); margin-top: 2px; }

.sf-interview-box {
  text-align: center;
  background: var(--raised); border: 1px solid var(--border);
  border-radius: 9px; padding: 16px 20px;
}
.sf-interview-num {
  font-family: var(--mono); font-size: 2rem; font-weight: 600; line-height: 1;
}
.sf-interview-label {
  font-family: var(--mono); font-size: 0.6rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--text-3); margin-top: 4px;
}
.sf-interview-advice {
  font-family: var(--mono); font-size: 0.67rem;
  color: var(--text-2); margin-top: 5px;
}

/* ── SKILL ROWS ── */
.sf-skill-row {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 7px; padding: 10px 13px;
  margin-bottom: 5px; transition: border-color 0.12s;
}
.sf-skill-row:hover { border-color: rgba(255,255,255,0.12); }
.sf-skill-inner {
  display: grid;
  grid-template-columns: 140px 1fr 48px 72px;
  align-items: center; gap: 10px;
}
.sf-skill-name {
  font-family: var(--display); font-size: 0.78rem; font-weight: 600;
  color: var(--text-1);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sf-bar { height: 3px; background: rgba(255,255,255,0.05); border-radius: 99px; }
.sf-bar-fill { height: 100%; border-radius: 99px; }
.sf-skill-score {
  font-family: var(--mono); font-size: 0.7rem; color: var(--text-2);
  text-align: right;
}
.sf-badge {
  font-family: var(--mono); font-size: 0.57rem; font-weight: 600;
  padding: 2px 7px; border-radius: 3px; text-align: center;
}
.sf-badge-known   { background:rgba(45,212,191,0.1); color:var(--teal);  border:1px solid rgba(45,212,191,0.2); }
.sf-badge-partial { background:rgba(245,158,11,0.1); color:var(--amber); border:1px solid rgba(245,158,11,0.2); }
.sf-badge-missing { background:rgba(239,68,68,0.1);  color:var(--red);   border:1px solid rgba(239,68,68,0.2); }

.sf-skill-detail {
  margin-top: 9px; padding-top: 9px;
  border-top: 1px solid var(--border);
  font-family: var(--mono); font-size: 0.68rem; color: var(--text-2);
  display: grid; grid-template-columns: 1fr 1fr; gap: 5px;
}
.sf-detail-full { grid-column: 1 / -1; }

/* ── MODULE CARDS ── */
.sf-mod {
  display: grid; grid-template-columns: 36px 1fr 48px;
  gap: 10px; align-items: start;
  background: var(--surface); border: 1px solid var(--border);
  border-left: 3px solid transparent;
  border-radius: 0 7px 7px 0;
  padding: 11px 14px; margin-bottom: 6px;
  transition: border-color 0.12s;
}
.sf-mod:hover { border-color: rgba(255,255,255,0.1); }
.sf-mod.is-critical { border-left-color: var(--red) !important; }
.sf-mod.is-advanced { border-left-color: #f97316; }
.sf-mod.is-intermediate { border-left-color: var(--amber); }
.sf-mod.is-beginner { border-left-color: var(--teal); }
.sf-mod.is-done { opacity: 0.4; }
.sf-mod-num {
  font-family: var(--mono); font-size: 0.62rem; color: var(--text-3);
  padding-top: 2px; text-align: center;
}
.sf-mod-title {
  font-family: var(--display); font-size: 0.82rem; font-weight: 700;
  color: var(--text-1); margin-bottom: 3px;
}
.sf-mod-meta {
  font-family: var(--mono); font-size: 0.63rem; color: var(--text-3);
}
.sf-mod-tags { display: flex; gap: 4px; margin-top: 5px; flex-wrap: wrap; }
.sf-mod-tag {
  font-family: var(--mono); font-size: 0.57rem;
  padding: 2px 6px; border-radius: 3px;
  background: var(--raised); color: var(--text-2);
  border: 1px solid var(--border);
}
.sf-mod-reason {
  font-family: var(--mono); font-size: 0.66rem;
  color: var(--text-3); font-style: italic;
  margin-top: 5px; line-height: 1.5; border-top: 1px solid var(--border); padding-top: 5px;
}
.sf-mod-hrs {
  font-family: var(--mono); font-size: 0.72rem;
  color: var(--text-2); text-align: right; white-space: nowrap;
}

/* Course link */
.sf-course {
  background: rgba(45,212,191,0.03);
  border: 1px solid var(--border-hi);
  border-radius: 5px; padding: 6px 10px;
  margin-top: 6px; font-family: var(--mono); font-size: 0.67rem;
}
.sf-course a { color: var(--teal); text-decoration: none; font-weight: 500; }
.sf-course a:hover { text-decoration: underline; }
.sf-course-plat { font-size: 0.6rem; color: var(--text-3); margin-top: 1px; }

/* ── ATS ── */
.sf-ats-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin-bottom: 16px; }
@media(max-width:600px){ .sf-ats-grid{ grid-template-columns: repeat(2,1fr); } }
.sf-ats-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 7px; padding: 14px; text-align: center;
}
.sf-ats-val {
  font-family: var(--mono); font-size: 1.55rem; font-weight: 600;
  color: var(--text-1); line-height: 1;
}
.sf-ats-lbl {
  font-family: var(--mono); font-size: 0.58rem; font-weight: 500;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-3); margin-top: 4px;
}
.sf-progress-bar {
  height: 3px; background: rgba(255,255,255,0.05);
  border-radius: 99px; overflow: hidden; margin-bottom: 18px;
}
.sf-progress-fill { height: 100%; background: var(--teal); }

.sf-tip-row {
  display: flex; gap: 10px; margin-bottom: 8px;
  font-family: var(--mono); font-size: 0.72rem;
  color: var(--text-2); line-height: 1.55;
}
.sf-tip-num {
  font-size: 0.6rem; color: var(--teal);
  background: var(--teal-dim); border: 1px solid var(--border-hi);
  border-radius: 3px; padding: 2px 6px; font-weight: 600;
  min-width: 22px; text-align: center; flex-shrink: 0; height: fit-content;
}
.sf-talking-pt {
  font-family: var(--mono); font-size: 0.72rem; color: var(--text-2);
  padding: 7px 0 7px 12px; border-left: 2px solid var(--teal);
  margin-bottom: 6px; line-height: 1.55;
}
.sf-kw { display: inline-block; font-family: var(--mono); font-size: 0.62rem;
  padding: 2px 8px; border-radius: 3px; margin: 3px;
  background: rgba(239,68,68,0.07); color: var(--red);
  border: 1px solid rgba(239,68,68,0.15); font-weight: 500; }

/* ── WEB INTEL ── */
.sf-intel-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 9px; padding: 16px 18px;
}
.sf-intel-hd {
  font-family: var(--display); font-size: 0.78rem; font-weight: 700;
  color: var(--text-1); margin-bottom: 12px;
}
.sf-insight {
  background: rgba(45,212,191,0.03);
  border-left: 2px solid var(--teal);
  border-radius: 0 4px 4px 0;
  padding: 7px 10px; margin-bottom: 5px;
  font-family: var(--mono); font-size: 0.7rem;
  color: var(--text-2); line-height: 1.5;
}
.sf-trend-pill {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--raised); border: 1px solid var(--border);
  border-radius: 5px; padding: 5px 10px; margin: 3px;
  font-family: var(--mono); font-size: 0.67rem;
}
.sf-trend-skill { color: var(--text-1); font-weight: 500; }

/* ── EXPORT ── */
.sf-export-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 9px; padding: 18px 20px;
}
.sf-export-hd {
  font-family: var(--display); font-size: 0.82rem; font-weight: 700;
  color: var(--text-1); margin-bottom: 4px;
}
.sf-export-sub {
  font-family: var(--mono); font-size: 0.65rem; color: var(--text-3);
  margin-bottom: 14px; line-height: 1.5;
}
.sf-export-row {
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 0.68rem;
  padding: 5px 0; border-bottom: 1px solid var(--border);
}
.sf-export-key { color: var(--text-3); }
.sf-export-val { color: var(--text-1); font-weight: 500; }

/* Download button */
[data-testid="stDownloadButton"] > button {
  background: var(--raised) !important;
  border: 1px solid var(--border) !important;
  color: var(--text-2) !important;
  font-family: var(--mono) !important; font-weight: 500 !important;
  font-size: 0.75rem !important;
}
[data-testid="stDownloadButton"] > button:hover {
  border-color: var(--border-hi) !important; color: var(--teal) !important;
}

/* Metrics override */
[data-testid="stMetric"] {
  background: var(--raised) !important;
  border: 1px solid var(--border) !important;
  border-radius: 7px !important; padding: 11px 13px !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important;
  font-size: 1.35rem !important; color: var(--text-1) !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important;
  color: var(--text-3) !important; font-size: 0.57rem !important;
  text-transform: uppercase !important; letter-spacing: 0.08em !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important; color: var(--text-1) !important;
  font-family: var(--mono) !important; font-size: 0.76rem !important;
}

/* Select slider */
[data-testid="stSlider"] .st-ae { background: var(--teal) !important; }

/* Expander */
[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 7px !important; margin-bottom: 4px !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--mono) !important;
  color: var(--text-2) !important; font-size: 0.76rem !important;
}

/* Tabs */
[data-testid="stTabs"] button {
  font-family: var(--mono) !important; font-size: 0.72rem !important;
}

/* Checkbox */
[data-testid="stCheckbox"] label {
  font-family: var(--mono) !important; font-size: 0.74rem !important;
  color: var(--text-2) !important;
}

/* Sidebar nav */
.sf-nav-item {
  display: flex; align-items: center; gap: 9px;
  padding: 7px 10px; border-radius: 5px; cursor: pointer;
  font-family: var(--mono); font-size: 0.72rem; color: var(--text-2);
  transition: all 0.12s; margin-bottom: 1px; text-decoration: none;
}
.sf-nav-item:hover { background: var(--raised); color: var(--text-1); }
.sf-nav-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.sf-nav-section {
  font-family: var(--mono); font-size: 0.57rem; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-3); padding: 4px 10px; margin-top: 6px;
}
.sf-nav-divider { height: 1px; background: var(--border); margin: 8px 0; }

/* Diff pane */
.sf-diff {
  background: #0a0e1a; border: 1px solid var(--border);
  border-radius: 7px; padding: 13px; font-family: var(--mono);
  font-size: 0.7rem; color: var(--text-2); white-space: pre-wrap;
  line-height: 1.6; max-height: 300px; overflow-y: auto;
}

/* API log */
.sf-log-line {
  font-family: var(--mono); font-size: 0.63rem; color: var(--text-3);
  padding: 4px 8px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 4px;
  margin-bottom: 3px; display: flex; gap: 10px;
}

/* Sticky footer */
.sf-footer {
  position: fixed; bottom: 0; left: 0; right: 0;
  background: rgba(8,11,18,0.97); border-top: 1px solid var(--border);
  padding: 5px 28px; font-family: var(--mono); font-size: 0.6rem;
  color: var(--text-3); display: flex; align-items: center; gap: 14px; z-index: 99;
}
.sf-footer-dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.sf-footer-right { margin-left: auto; }

/* Transfer badge */
.sf-transfer {
  display: flex; align-items: center; gap: 8px;
  background: var(--raised); border: 1px solid var(--border);
  border-radius: 5px; padding: 7px 11px; margin-bottom: 5px;
  font-family: var(--mono); font-size: 0.68rem; color: var(--text-2);
}
.sf-transfer-pct { color: var(--purple, #a78bfa); font-weight: 600; }

/* Seniority warning */
.sf-seniority-warn {
  background: rgba(245,158,11,0.06);
  border: 1px solid rgba(245,158,11,0.2);
  border-radius: 7px; padding: 9px 13px;
  font-family: var(--mono); font-size: 0.7rem; color: var(--amber);
  margin-bottom: 10px;
}

/* Obsolescence */
.sf-obs-card {
  background: rgba(239,68,68,0.04); border: 1px solid rgba(239,68,68,0.15);
  border-radius: 6px; padding: 9px 12px;
}
.sf-obs-skill { font-family: var(--display); font-size: 0.76rem; font-weight: 700; color: var(--red); }
.sf-obs-reason { font-family: var(--mono); font-size: 0.64rem; color: var(--text-3); margin-top: 2px; }

/* Mobile */
@media(max-width:640px){
  .sf-page { padding: 0 14px 80px; }
  .sf-topbar { padding: 0 14px; }
  .sf-topbar-right { display: none; }
  .sf-kpi-strip { grid-template-columns: repeat(2,1fr); }
  .sf-skill-inner { grid-template-columns: 100px 1fr 36px 60px; }
}
</style>
"""

# =============================================================================
#  SESSION STATE INIT
# =============================================================================
def _init_state():
    defaults = {
        "step":              1,
        "resume_text":       "",
        "resume_image":      None,
        "jd_text":           "",
        "result":            None,
        "completed":         set(),
        "hpd":               2,
        "rw_result":         None,
        "course_cache":      {},
        "sal_location":      "India",
        "force_fresh":       False,
        "search_query":      "",
        "search_results":    [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# Keys that must be wiped on full reset (includes Streamlit widget keys)
_RESET_KEYS = [
    "step","resume_text","resume_image","jd_text","result",
    "completed","rw_result","course_cache","force_fresh",
    "search_query","search_results",
    # widget keys — must delete so text areas re-initialize empty
    "res_paste","jd_paste",
]

def _full_reset():
    for k in _RESET_KEYS:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

# =============================================================================
#  TOPBAR
# =============================================================================
def render_topbar():
    cost  = sum(e.get("cost",0) for e in _audit_log)
    calls = len(_audit_log)
    sem   = "semantic ✓" if SEMANTIC else "semantic ⟳"
    st.markdown(f"""
    <div class="sf-topbar">
      <div class="sf-brand">Skill<em>Forge</em></div>
      <div class="sf-topbar-right">
        <span class="sf-pill active">Groq LLaMA 4-Scout</span>
        <span class="sf-pill">NetworkX DAG</span>
        <span class="sf-pill">{sem}</span>
        <span class="sf-pill">{calls} calls · ${cost:.4f}</span>
      </div>
    </div>""", unsafe_allow_html=True)

# =============================================================================
#  STEP 1 — RESUME
# =============================================================================
def render_step1():
    st.markdown('<div class="sf-page">', unsafe_allow_html=True)

    st.markdown("""
    <div class="sf-welcome">
      <div class="sf-welcome-eyebrow">AI-powered onboarding engine</div>
      <div class="sf-welcome-title">Close your<br><span>skill gap</span><br>precisely.</div>
      <div class="sf-welcome-body">Upload your resume and a job description. SkillForge identifies exactly what you're missing and builds a dependency-ordered learning roadmap — skipping what you already know.</div>
    </div>""", unsafe_allow_html=True)

    # Scenario presets
    st.markdown('<div class="sf-scenario-label">Try a sample scenario</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, key in zip(cols, SAMPLES):
        s = SAMPLES[key]
        with col:
            st.markdown(f"""
            <div class="sf-scenario-card">
              <div class="sf-scenario-title">{s['label']}</div>
              <div class="sf-scenario-desc">{s['description']}</div>
            </div>""", unsafe_allow_html=True)
            if st.button("Load", key=f"preset_{key}", use_container_width=True):
                # Clear widget keys so the text areas re-initialize with preset content
                for wk in ["res_paste","jd_paste"]:
                    if wk in st.session_state: del st.session_state[wk]
                st.session_state["resume_text"] = s["resume"]
                st.session_state["jd_text"]     = s["jd"]
                st.session_state["step"]        = "analyzing"
                st.rerun()

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── Resume input ──────────────────────────────────────────────────────────
    st.markdown('<p style="font-family:var(--mono);font-size:0.72rem;font-weight:600;color:var(--text-1);margin-bottom:10px">Your resume <span style="font-size:0.6rem;color:var(--text-3)">— Step 1 of 2</span></p>', unsafe_allow_html=True)

    tab_upload, tab_paste = st.tabs(["📎 Upload file", "✏️ Paste text"])

    with tab_upload:
        f = st.file_uploader("Resume", type=["pdf","docx","jpg","jpeg","png","webp"],
                             key="res_file", label_visibility="collapsed")
        if f:
            txt, img = parse_uploaded_file(f)
            st.session_state["resume_text"]  = txt
            st.session_state["resume_image"] = img
            # Sync widget key so paste tab shows the extracted text
            if "res_paste" in st.session_state: del st.session_state["res_paste"]
            wc = len(txt.split()) if txt else 0
            st.success(f"✓ {f.name} — {wc} words extracted" if wc else f"✓ {f.name} loaded as image")

    with tab_paste:
        # Only pre-initialize the widget key if it hasn't been set yet.
        # This lets the user type freely without the value being overwritten on rerun.
        if "res_paste" not in st.session_state:
            st.session_state["res_paste"] = st.session_state.get("resume_text", "")

        st.text_area("Resume text", height=200,
                     placeholder="Paste your resume here — name, experience, skills, education…",
                     key="res_paste", label_visibility="collapsed")
        # Always sync from widget → session state
        st.session_state["resume_text"] = st.session_state.get("res_paste", "")

        wc = len(st.session_state["resume_text"].split())
        if wc > 10:
            st.markdown(f'<p style="font-family:var(--mono);font-size:0.63rem;color:var(--text-3)">{wc} words detected</p>', unsafe_allow_html=True)

    # Clear button
    if st.session_state.get("resume_text") or st.session_state.get("resume_image"):
        clr_col, _ = st.columns([1,4])
        with clr_col:
            if st.button("✕ Clear resume", key="clear_resume"):
                st.session_state["resume_text"]  = ""
                st.session_state["resume_image"] = None
                if "res_paste" in st.session_state: del st.session_state["res_paste"]
                if "res_file"  in st.session_state: del st.session_state["res_file"]
                st.rerun()

    has_resume = bool(st.session_state.get("resume_text","").strip() or st.session_state.get("resume_image"))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    if has_resume:
        if st.button("Continue → Add job description", key="to_step2", use_container_width=True):
            st.session_state["step"] = 2
            st.rerun()
    else:
        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;color:var(--text-3);text-align:center;padding:6px 0">Upload or paste your resume to continue</p>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  STEP 2 — JOB DESCRIPTION
# =============================================================================
def render_step2():
    st.markdown('<div class="sf-page">', unsafe_allow_html=True)
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # Resume preview strip
    rtxt = st.session_state.get("resume_text","")
    preview = (rtxt[:110] or "Image resume uploaded").strip()
    wc = len(rtxt.split())
    st.markdown(f"""
    <div class="sf-preview-strip">
      <span class="sf-preview-icon">✓</span>
      <span>Resume loaded ({wc} words) — <em style="color:var(--text-1)">{preview}…</em></span>
    </div>""", unsafe_allow_html=True)

    # JD input — same pattern as resume: init key once, then sync
    st.markdown('<p style="font-family:var(--mono);font-size:0.72rem;font-weight:600;color:var(--text-1);margin-bottom:10px">Job description <span style="font-size:0.6rem;color:var(--text-3)">— Step 2 of 2</span></p>', unsafe_allow_html=True)

    tab_upload, tab_paste = st.tabs(["📎 Upload JD file", "✏️ Paste JD text"])
    with tab_upload:
        f = st.file_uploader("JD file", type=["pdf","docx"], key="jd_file",
                             label_visibility="collapsed")
        if f:
            txt, _ = parse_uploaded_file(f)
            st.session_state["jd_text"] = txt
            if "jd_paste" in st.session_state: del st.session_state["jd_paste"]
            st.success(f"✓ {f.name} — {len(txt.split())} words extracted")
    with tab_paste:
        if "jd_paste" not in st.session_state:
            st.session_state["jd_paste"] = st.session_state.get("jd_text", "")

        st.text_area("Job description", height=200,
                     placeholder="Paste the full job description — title, responsibilities, required skills…",
                     key="jd_paste", label_visibility="collapsed")
        st.session_state["jd_text"] = st.session_state.get("jd_paste","")

        wc_jd = len(st.session_state["jd_text"].split())
        if wc_jd > 10:
            st.markdown(f'<p style="font-family:var(--mono);font-size:0.63rem;color:var(--text-3)">{wc_jd} words detected</p>', unsafe_allow_html=True)

    has_jd = bool(st.session_state.get("jd_text","").strip())

    # Options row
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    opt_l, opt_r = st.columns([1,1])
    with opt_l:
        loc = st.selectbox("Salary benchmark location",
                           ["India","USA","UK","Germany","Canada","Singapore"],
                           key="loc_pick", label_visibility="visible",
                           index=["India","USA","UK","Germany","Canada","Singapore"].index(
                               st.session_state.get("sal_location","India")))
        st.session_state["sal_location"] = loc
    with opt_r:
        force = st.checkbox("Force fresh analysis (skip cache)", key="force_fresh",
                            value=st.session_state.get("force_fresh", False))
        st.session_state["force_fresh"] = force
        st.markdown('<p style="font-family:var(--mono);font-size:0.62rem;color:var(--text-3)">Tick this if you changed your resume and want to re-run</p>', unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    back_col, go_col = st.columns([1,3])
    with back_col:
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("← Back", key="back_btn", use_container_width=True):
            st.session_state["step"] = 1; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with go_col:
        if has_jd:
            if st.button("Analyze skill gap ⚡", key="analyze_btn", use_container_width=True):
                st.session_state["step"] = "analyzing"; st.rerun()
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;color:var(--text-3);padding:10px 0">Paste or upload the job description to continue</p>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  LOADING
# =============================================================================
def render_loading():
    st.markdown('<div class="sf-page">', unsafe_allow_html=True)
    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)

    # Bust cache if user requested fresh run
    if st.session_state.get("force_fresh"):
        rtxt = st.session_state.get("resume_text","") or "img"
        jtxt = st.session_state.get("jd_text","")
        try:
            with shelve.open(_CACHE_PATH) as db:
                k = _ckey(rtxt, jtxt)
                if k in db: del db[k]
        except: pass
        st.session_state["force_fresh"] = False

    with st.status("Analyzing your profile…", expanded=True) as status:
        st.write("📄 Parsing resume and job description…")
        result = run_analysis_with_web(
            st.session_state.get("resume_text",""),
            st.session_state.get("jd_text",""),
            resume_image_b64=st.session_state.get("resume_image"),
            location=st.session_state.get("sal_location","India"),
        )
        if "error" not in result:
            st.write("🧩 Gap analysis complete")
            st.write("🗺️ Roadmap built via NetworkX DAG")
            st.write("🌐 Web intelligence fetched")
            status.update(label="Analysis complete ✓", state="complete")
        else:
            status.update(label="Analysis failed", state="error")

    if "error" in result:
        if result.get("error") == "rate_limited":
            st.error(f"⏳ Rate limited — {result.get('message','')}")
            st.info("Groq free tier has per-minute limits. Wait the indicated time then retry.")
        else:
            st.error(f"Analysis failed: `{result.get('error','unknown')}`")
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("← Try again", key="retry_btn"):
            st.session_state["step"] = 2; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.session_state["result"] = result
    st.session_state["step"]   = "results"
    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  SIDEBAR
# =============================================================================
def render_sidebar(im, iv, sm):
    with st.sidebar:
        st.markdown("""
        <div style="padding:12px 8px 4px">
          <div style="font-family:'Syne',sans-serif;font-size:0.95rem;font-weight:800;
                      color:#f1f5f9;letter-spacing:-0.02em;margin-bottom:14px">
            Skill<span style="color:#2dd4bf">Forge</span>
          </div>
        </div>""", unsafe_allow_html=True)

        sections = [
            ("score",   "#2dd4bf", "Overview"),
            ("skills",  "#f59e0b", "Skill gap"),
            ("roadmap", "#ef4444", "Roadmap"),
            ("ats",     "#a78bfa", "ATS audit"),
            ("intel",   "#4ade80", "Web intel"),
            ("export",  "#64748b", "Export"),
        ]
        st.markdown('<div style="padding:0 8px">', unsafe_allow_html=True)
        for anchor, color, label in sections:
            st.markdown(f"""
            <a href="#{anchor}" class="sf-nav-item">
              <div class="sf-nav-dot" style="background:{color}"></div>{label}
            </a>""", unsafe_allow_html=True)

        st.markdown('<div class="sf-nav-divider"></div>', unsafe_allow_html=True)

        # Real computed stats only
        st.markdown(f"""
        <div style="padding:4px 10px;font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#3d4d66">
          <div style="margin-bottom:4px">fit delta &nbsp;<span style="color:#94a3b8">+{im.get('fit_delta',0)}%</span></div>
          <div style="margin-bottom:4px">modules &nbsp;<span style="color:#94a3b8">{im.get('modules_count',0)}</span></div>
          <div style="margin-bottom:4px">training &nbsp;<span style="color:#94a3b8">{im.get('roadmap_hours',0)}h</span></div>
          <div style="margin-bottom:4px">interview &nbsp;<span style="color:{iv.get('color','#4ade80')}">{iv.get('score',0)}% {iv.get('label','')}</span></div>
        </div>""", unsafe_allow_html=True)

        if sm.get("has_mismatch"):
            st.markdown(f"""
            <div class="sf-seniority-warn" style="margin:8px">
              ⚠ Seniority gap: {sm['candidate']} → {sm['required']}<br>
              <span style="color:#3d4d66">Leadership modules injected</span>
            </div>""", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-nav-divider"></div>', unsafe_allow_html=True)

        st.markdown('<div style="padding:0 8px">', unsafe_allow_html=True)
        st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
        if st.button("↩ Start over", key="sidebar_reset", use_container_width=True):
            _full_reset()
        st.markdown('</div></div>', unsafe_allow_html=True)


# =============================================================================
#  SECTION: SCORE OVERVIEW
# =============================================================================
def render_score_overview(res):
    c  = res["candidate"];  jd = res["jd"]
    im = res["impact"];     iv = res["interview"]

    st.markdown('<div id="score"></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # Name / role banner
    name = c.get("name","Unknown"); role = jd.get("role_title","--")
    seniority = c.get("seniority",""); domain = c.get("domain","")
    yrs = c.get("years_experience",0)

    col_fit, col_kpis, col_iv = st.columns([1,1.6,1])

    with col_fit:
        cur   = im["current_fit"]
        proj  = im["projected_fit"]
        delta = im["fit_delta"]
        st.markdown(f"""
        <div style="background:var(--surface);border:1px solid var(--border);
                    border-radius:10px;padding:22px 18px;text-align:center;height:100%;">
          <div class="sf-score-label">Current fit</div>
          <div class="sf-score-num">{cur}%</div>
          <div class="sf-score-delta">→ <strong>+{delta}%</strong> after roadmap</div>
          <div style="height:1px;background:var(--border);margin:14px 0"></div>
          <div style="font-family:var(--mono);font-size:0.68rem;color:var(--text-3)">
            {name} · {yrs}yr · {seniority}
          </div>
          <div style="font-family:var(--mono);font-size:0.64rem;color:var(--text-3);margin-top:2px">
            → {role}
          </div>
        </div>""", unsafe_allow_html=True)

    with col_kpis:
        k1,k2 = st.columns(2)
        k1.metric("Training hours",  f"{im['roadmap_hours']}h",     f"saves ~{im['hours_saved']}h vs generic")
        k2.metric("Projected fit",   f"{proj}%",                    f"+{delta}% gain")
        k3,k4 = st.columns(2)
        k3.metric("Modules",         im["modules_count"],            f"{im['critical_count']} on critical path")
        k4.metric("Ready in",        weeks_ready(im["roadmap_hours"], st.session_state.get("hpd",2)),
                  f"at {st.session_state.get('hpd',2)}h/day")

        if im.get("decayed_skills",0):
            st.markdown(f'<div style="font-family:var(--mono);font-size:0.67rem;color:var(--amber);margin-top:6px;">⏱ {im["decayed_skills"]} skill(s) have decayed from inactivity</div>', unsafe_allow_html=True)

    with col_iv:
        iv_color = iv.get("color","#4ade80")
        st.markdown(f"""
        <div class="sf-interview-box" style="border-color:rgba{tuple(int(iv_color.lstrip('#')[i:i+2],16) for i in (0,2,4))}44">
          <div class="sf-interview-label">Interview readiness</div>
          <div class="sf-interview-num" style="color:{iv_color}">{iv['score']}%</div>
          <div style="font-family:var(--mono);font-size:0.72rem;color:{iv_color};font-weight:600;margin-top:4px">{iv['label']}</div>
          <div class="sf-interview-advice">{iv.get('advice','')}</div>
          <div style="height:1px;background:var(--border);margin:10px 0"></div>
          <div style="font-family:var(--mono);font-size:0.63rem;color:var(--text-3)">
            ✓ {iv['req_known']} known &nbsp; ~ {iv['req_partial']} partial &nbsp; ✗ {iv['req_missing']} missing
          </div>
        </div>""", unsafe_allow_html=True)

    # Salary — only shown if real data was returned
    sal = res.get("salary",{})
    if sal and sal.get("median_lpa",0):
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        curr = sal.get("currency","INR")
        sym  = "₹" if curr=="INR" else "$"
        unit = "L/yr" if curr=="INR" else "k/yr"
        sal_left, sal_right = st.columns([1,2])
        with sal_left:
            st.markdown(f"""
            <div style="background:var(--surface);border:1px solid var(--border);
                        border-radius:9px;padding:16px 18px;">
              <div style="font-family:var(--mono);font-size:0.6rem;letter-spacing:0.1em;
                          text-transform:uppercase;color:var(--text-3);margin-bottom:6px">
                Live salary · {role[:22]}
              </div>
              <div style="font-family:'IBM Plex Mono',monospace;font-size:1.9rem;
                          font-weight:600;color:var(--teal);line-height:1">
                {sym}{sal.get('median_lpa',0)}<span style="font-size:0.8rem;color:var(--text-2);font-weight:400"> {unit}</span>
              </div>
              <div style="font-family:var(--mono);font-size:0.67rem;color:var(--text-3);margin-top:4px">
                range: {sym}{sal.get('min_lpa',0)} – {sym}{sal.get('max_lpa',0)} {unit}
              </div>
              <div style="font-family:var(--mono);font-size:0.6rem;color:var(--text-3);margin-top:4px">
                Source: {sal.get('source','web search')} · {sal.get('note','')}
              </div>
            </div>""", unsafe_allow_html=True)
        with sal_right:
            st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar":False})

    if res.get("_cache_hit"):
        st.markdown('<p style="font-family:var(--mono);font-size:0.63rem;color:var(--text-3);text-align:right;margin-top:4px">⚡ Cached — 0 API calls used this run</p>', unsafe_allow_html=True)


# =============================================================================
#  SECTION: SKILL GAP
# =============================================================================
def render_skill_gap(res):
    gp     = res["gap_profile"]
    trends = res.get("skill_trends",{})

    st.markdown('<div id="skills"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

    k_c = sum(1 for g in gp if g["status"]=="Known")
    p_c = sum(1 for g in gp if g["status"]=="Partial")
    m_c = sum(1 for g in gp if g["status"]=="Missing")

    st.markdown('<div class="sf-section-title">Skill gap analysis</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sf-section-sub">{k_c} known · {p_c} partial · {m_c} missing — click to expand detail</div>', unsafe_allow_html=True)

    chart_col, list_col = st.columns([1, 1.1], gap="large")

    with chart_col:
        st.plotly_chart(radar_chart(gp), use_container_width=True, config={"displayModeBar":False})

        # Transfer advantages — computed, real
        tf = res.get("transfers",[])
        if tf:
            st.markdown('<p style="font-family:var(--mono);font-size:0.68rem;font-weight:600;color:var(--text-1);margin:10px 0 6px">Transfer advantages</p>', unsafe_allow_html=True)
            for t in tf[:4]:
                st.markdown(f'<div class="sf-transfer"><span style="color:#a78bfa">↗ {t["transfer_pct"]}%</span><span>{t["label"]}</span></div>', unsafe_allow_html=True)

        # Obsolescence risks — only if any exist
        obs = res.get("obsolescence",[])
        if obs:
            st.markdown('<p style="font-family:var(--mono);font-size:0.68rem;font-weight:600;color:var(--text-1);margin:14px 0 6px">Obsolescence risks</p>', unsafe_allow_html=True)
            for o in obs:
                st.markdown(f'<div class="sf-obs-card"><div class="sf-obs-skill">{o["skill"]}</div><div class="sf-obs-reason">{o["reason"]}</div></div>', unsafe_allow_html=True)

    with list_col:
        filt = st.selectbox("Filter skills", ["All","Missing","Partial","Known","Required only"],
                            key="sf_filter", label_visibility="collapsed")
        if "expanded_skills" not in st.session_state:
            st.session_state["expanded_skills"] = set()

        for g in gp:
            show = (filt == "All" or
                    (filt == "Missing"       and g["status"]=="Missing") or
                    (filt == "Partial"       and g["status"]=="Partial") or
                    (filt == "Known"         and g["status"]=="Known") or
                    (filt == "Required only" and g["is_required"]))
            if not show: continue

            status   = g["status"]
            color_map = {"Known":_TEAL,"Partial":_AMBER,"Missing":_RED}
            badge_cls = {"Known":"sf-badge-known","Partial":"sf-badge-partial","Missing":"sf-badge-missing"}
            bar_col   = color_map[status]
            pct       = g["proficiency"] / 10 * 100
            trend     = trends.get(g["skill"],"")
            trend_col = (_RED if "Hot" in trend else _AMBER if "Growing" in trend else "#3d4d66")
            decay_ic  = " ⏱" if g.get("decayed") else ""

            exp_key = f"exp_{g['skill'].replace(' ','_').replace('/','_')}"
            is_exp  = g["skill"] in st.session_state["expanded_skills"]
            toggled = st.toggle(
                f"{g['skill']}{decay_ic} — {g['proficiency']}/10 [{status}]",
                value=is_exp, key=exp_key, label_visibility="collapsed"
            )
            if toggled: st.session_state["expanded_skills"].add(g["skill"])
            else:        st.session_state["expanded_skills"].discard(g["skill"])

            detail = ""
            if is_exp:
                co = g.get("catalog_course")
                ctx_html  = f'<div class="sf-detail-full" style="font-style:italic;color:#3d4d66">{g["context"]}</div>' if g.get("context") else ""
                decay_html = f'<div class="sf-detail-full" style="color:var(--amber)">⏱ Decayed from {g["original_prof"]}/10 (unused for {CURRENT_YEAR - g.get("year_last_used",CURRENT_YEAR-3) if g.get("year_last_used",0) > 0 else "2+"}yr)</div>' if g.get("decayed") else ""
                obs_html   = f'<div class="sf-detail-full" style="color:var(--red)">⚠ {g["obsolescence_risk"]}</div>' if g.get("obsolescence_risk") else ""
                course_html = f'<div><span style="color:var(--text-3)">Course:</span> {co["title"]} ({co["duration_hrs"]}h · {co["level"]})</div>' if co else '<div style="color:var(--text-3)">No catalog match</div>'
                demand_html = f'<div><span style="color:var(--text-3)">Market:</span> <span style="color:{trend_col}">{trend or "—"}</span></div>'
                detail = f'<div class="sf-skill-detail">{ctx_html}{decay_html}{obs_html}{course_html}{demand_html}</div>'

            st.markdown(f"""
            <div class="sf-skill-row">
              <div class="sf-skill-inner">
                <div class="sf-skill-name">{g['skill']}{decay_ic}</div>
                <div class="sf-bar"><div class="sf-bar-fill" style="width:{pct}%;background:{bar_col}"></div></div>
                <div class="sf-skill-score">{g['proficiency']}/10</div>
                <span class="sf-badge {badge_cls[status]}">{status}</span>
              </div>
              {detail}
            </div>""", unsafe_allow_html=True)


# =============================================================================
#  SECTION: ROADMAP
# =============================================================================
def render_roadmap(res):
    path      = res["path"]
    gp        = res["gap_profile"]
    completed = st.session_state.get("completed", set())

    st.markdown('<div id="roadmap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

    hd_l, hd_r = st.columns([2,1])
    with hd_l:
        st.markdown('<div class="sf-section-title">Learning roadmap</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-section-sub">Dependency-ordered · critical path highlighted · AI reasoning per module</div>', unsafe_allow_html=True)
    with hd_r:
        hpd = st.select_slider("Pace (h/day)", options=[1,2,4,8],
                               value=st.session_state.get("hpd",2),
                               key="hpd_slider", label_visibility="visible")
        st.session_state["hpd"] = hpd
        rem_hrs = sum(m["duration_hrs"] for m in path if m["id"] not in completed)
        st.markdown(f'<p style="font-family:var(--mono);font-size:0.67rem;color:var(--text-2);text-align:right">Done in <strong style="color:var(--teal)">{weeks_ready(rem_hrs,hpd)}</strong> · {rem_hrs}h remaining</p>', unsafe_allow_html=True)

    mod_col, chart_col = st.columns([1.1,1], gap="large")

    with mod_col:
        for i, m in enumerate(path):
            is_done = m["id"] in completed
            is_crit = m.get("is_critical",False)
            level   = m["level"]
            level_cls = ("is-critical" if is_crit else
                         "is-advanced" if level=="Advanced" else
                         "is-intermediate" if level=="Intermediate" else "is-beginner")
            done_cls = " is-done" if is_done else ""

            checked = st.checkbox(
                f"#{i+1:02d} {m['title']} — {m['duration_hrs']}h",
                value=is_done, key=f"chk_{m['id']}"
            )
            if checked: completed.add(m["id"])
            else:        completed.discard(m["id"])
            st.session_state["completed"] = completed

            prereqs_str = ", ".join(m.get("prereqs",[]) or []) or "none"
            tags = []
            if is_crit: tags.append(f'<span class="sf-mod-tag" style="color:var(--red);border-color:rgba(239,68,68,0.3)">★ critical</span>')
            if m.get("is_required"): tags.append(f'<span class="sf-mod-tag" style="color:var(--teal)">required</span>')
            tags.append(f'<span class="sf-mod-tag">{m["domain"]}</span>')
            tags.append(f'<span class="sf-mod-tag">{level}</span>')
            tags_html = "".join(tags)

            # Cached course links
            courses  = st.session_state.get("course_cache",{}).get(m["skill"],[])
            crs_html = ""
            for crs in courses[:2]:
                crs_html += f'<div class="sf-course">{crs["icon"]} <a href="{crs["url"]}" target="_blank">{crs["title"][:52]}</a><div class="sf-course-plat">{crs["platform"]}</div></div>'

            st.markdown(f"""
            <div class="sf-mod {level_cls}{done_cls}">
              <div class="sf-mod-num">{'✓' if is_done else f'#{i+1:02d}'}</div>
              <div>
                <div class="sf-mod-title">{m['title']}</div>
                <div class="sf-mod-meta">Skill: {m['skill']} · prereqs: {prereqs_str}</div>
                <div class="sf-mod-tags">{tags_html}</div>
                {'<div class="sf-mod-reason">'+m["reasoning"]+'</div>' if m.get("reasoning") else ""}
                {crs_html}
              </div>
              <div class="sf-mod-hrs">{m['duration_hrs']}h</div>
            </div>""", unsafe_allow_html=True)

    with chart_col:
        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-bottom:6px">ROI ranking</p>', unsafe_allow_html=True)
        st.plotly_chart(roi_chart(res.get("roi",[])), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin:14px 0 6px">Priority matrix</p>', unsafe_allow_html=True)
        st.plotly_chart(priority_matrix(gp), use_container_width=True, config={"displayModeBar":False})

    # Timeline
    st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-top:18px;margin-bottom:8px">Training timeline</p>', unsafe_allow_html=True)
    st.plotly_chart(timeline_chart(path), use_container_width=True, config={"displayModeBar":False})

    # Weekly plan
    st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-top:16px;margin-bottom:8px">Weekly study plan</p>', unsafe_allow_html=True)
    remaining_path = [m for m in path if m["id"] not in completed]
    wp = weekly_plan(remaining_path, hpd)
    for w in wp[:8]:
        with st.expander(f"Week {w['week']} — {w['total_hrs']:.1f}h / {hpd*5}h capacity"):
            for mx in w["modules"]:
                crit = "★ " if mx.get("is_critical") else ""
                st.markdown(f"- {crit}**{mx['title']}** &nbsp;·&nbsp; `{mx['hrs_this_week']:.1f}h` of `{mx['total_hrs']}h total`")

    # Course link loader
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    cache = st.session_state.get("course_cache",{})
    loaded = len(cache)
    gap_skills_unique = list({m["skill"] for m in path})
    if loaded < len(gap_skills_unique):
        if st.button(f"Load course links for all {len(gap_skills_unique)} skills →", key="load_courses"):
            new_cache = {}
            with st.spinner("Searching Coursera · Udemy · YouTube…"):
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {ex.submit(search_course_links, s): s for s in gap_skills_unique[:10]}
                    for fut in futs:
                        new_cache[futs[fut]] = fut.result()
            st.session_state["course_cache"] = new_cache
            st.rerun()
    elif loaded > 0:
        st.markdown(f'<p style="font-family:var(--mono);font-size:0.67rem;color:var(--teal)">✓ Course links loaded for {loaded} skills</p>', unsafe_allow_html=True)


# =============================================================================
#  SECTION: ATS AUDIT
# =============================================================================
def render_ats(res):
    ql  = res.get("quality",{})
    iv  = res.get("interview",{})
    sm  = res.get("seniority",{})
    cgm = res.get("career_months",0)

    st.markdown('<div id="ats"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-title">ATS audit & interview readiness</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Resume quality scores · improvement tips · ATS keyword gaps · interview talking points</div>', unsafe_allow_html=True)

    ats_score = ql.get("ats_score", 0)

    st.markdown(f"""
    <div class="sf-ats-grid">
      <div class="sf-ats-card">
        <div class="sf-ats-val">{ql.get('ats_score','--')}%</div>
        <div class="sf-ats-lbl">ATS Score</div>
      </div>
      <div class="sf-ats-card">
        <div class="sf-ats-val" style="color:var(--teal)">{ql.get('overall_grade','--')}</div>
        <div class="sf-ats-lbl">Grade</div>
      </div>
      <div class="sf-ats-card">
        <div class="sf-ats-val">{ql.get('completeness_score','--')}%</div>
        <div class="sf-ats-lbl">Completeness</div>
      </div>
      <div class="sf-ats-card">
        <div class="sf-ats-val">{ql.get('clarity_score','--')}%</div>
        <div class="sf-ats-lbl">Clarity</div>
      </div>
    </div>
    <div class="sf-progress-bar"><div class="sf-progress-fill" style="width:{ats_score}%"></div></div>
    """, unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-bottom:10px">Improvement tips</p>', unsafe_allow_html=True)
        for i, tip in enumerate((ql.get("improvement_tips") or [])[:6]):
            st.markdown(f'<div class="sf-tip-row"><span class="sf-tip-num">0{i+1}</span><span>{tip}</span></div>', unsafe_allow_html=True)

        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin:14px 0 8px">Interview talking points</p>', unsafe_allow_html=True)
        for pt in (ql.get("interview_talking_points") or [])[:4]:
            st.markdown(f'<div class="sf-talking-pt">→ {pt}</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-bottom:8px">ATS issues</p>', unsafe_allow_html=True)
        issues = ql.get("ats_issues") or []
        if issues:
            for iss in issues[:5]:
                st.warning(iss)
        else:
            st.success("No critical ATS issues detected")

        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin:12px 0 6px">Missing keywords</p>', unsafe_allow_html=True)
        kws = ql.get("missing_keywords") or []
        if kws:
            pills_html = "".join(f'<span class="sf-kw">{k}</span>' for k in kws)
            st.markdown(f'<div style="line-height:2.3">{pills_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.67rem;color:var(--text-3)">No missing keywords identified</p>', unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        c1.metric("Interview ready",  f"{iv.get('score',0)}%",     iv.get("label","--"))
        c2.metric("Seniority gap",    f"{sm.get('gap_levels',0)} lvl")
        c3.metric("Career time est",  f"~{cgm}mo" if cgm else "On track")

    # Resume rewrite
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-bottom:4px">AI resume rewrite</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-family:var(--mono);font-size:0.65rem;color:var(--text-3);margin-bottom:10px">ATS-optimized version with missing keywords injected naturally</p>', unsafe_allow_html=True)

    rtxt = st.session_state.get("resume_text","")
    if not rtxt:
        st.info("Resume image uploaded — text rewrite requires a text or PDF resume.")
    else:
        if st.button("Generate ATS-optimized rewrite →", key="rw_btn", use_container_width=False):
            with st.spinner("Rewriting with LLaMA 4-Scout…"):
                rw = rewrite_resume(rtxt, res["jd"], kws)
            st.session_state["rw_result"] = rw

        rw = st.session_state.get("rw_result")
        if rw:
            d1, d2 = st.columns(2)
            with d1:
                st.markdown('<p style="font-family:var(--mono);font-size:0.6rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-3)">Original</p>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff">{rtxt[:1400]}</div>', unsafe_allow_html=True)
            with d2:
                st.markdown('<p style="font-family:var(--mono);font-size:0.6rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--teal)">Rewritten</p>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff">{rw[:1400]}</div>', unsafe_allow_html=True)
            st.download_button(
                "⬇ Download rewritten resume",
                data=rw, file_name="skillforge_rewritten_resume.txt", mime="text/plain"
            )


# =============================================================================
#  SECTION: WEB INTELLIGENCE
# =============================================================================
def render_web_intel(res):
    sal    = res.get("salary",{})
    trends = res.get("skill_trends",{})
    mkt    = res.get("market_insights",[])
    jd     = res["jd"]
    gp     = res["gap_profile"]

    st.markdown('<div id="intel"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-title">Live web intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Real-time salary data · market insights · skill demand — fetched via DuckDuckGo + Groq during analysis</div>', unsafe_allow_html=True)

    # Salary + market insights side by side
    sal_col, mkt_col = st.columns(2, gap="large")

    with sal_col:
        st.markdown('<div class="sf-intel-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-intel-hd">Salary benchmark</div>', unsafe_allow_html=True)
        if sal and sal.get("median_lpa",0):
            st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar":False})
            st.caption(f"Source: {sal.get('source','web')} · {sal.get('note','')}")
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;color:var(--text-3)">Salary data unavailable for this role/location. Try refreshing:</p>', unsafe_allow_html=True)
            loc = st.selectbox("Location", ["India","USA","UK","Germany","Canada","Singapore"], key="sal_loc_sel")
            if st.button("Fetch salary data", key="sal_refresh"):
                with st.spinner("Searching…"):
                    new_sal = search_real_salary(jd.get("role_title",""), loc)
                st.session_state["result"]["salary"] = new_sal
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with mkt_col:
        st.markdown('<div class="sf-intel-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-intel-hd">Job market insights</div>', unsafe_allow_html=True)
        if mkt:
            for ins in mkt:
                st.markdown(f'<div class="sf-insight">📌 {ins}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;color:var(--text-3)">No market data retrieved. Try fetching:</p>', unsafe_allow_html=True)
            if st.button("Fetch market insights", key="mkt_refresh"):
                with st.spinner("Searching…"):
                    new_mkt = search_job_market(jd.get("role_title",""))
                st.session_state["result"]["market_insights"] = new_mkt
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Skill demand signals — only shown if data exists
    if trends:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-bottom:8px">Skill market signals</p>', unsafe_allow_html=True)
        pills_html = ""
        for skill, sig in trends.items():
            sig_col = (_RED if "Hot" in sig else _AMBER if "Growing" in sig else "#3d4d66")
            pills_html += f'<span class="sf-trend-pill"><span class="sf-trend-skill">{skill[:14]}</span><span style="color:{sig_col}">{sig}</span></span>'
        st.markdown(f'<div style="line-height:2.5">{pills_html}</div>', unsafe_allow_html=True)

    # Find courses for specific skill
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;font-weight:600;color:var(--text-1);margin-bottom:8px">Search real courses</p>', unsafe_allow_html=True)
    gap_skills = [g["skill"] for g in gp if g["status"] != "Known"]
    if gap_skills:
        sel_skill = st.selectbox("Pick a skill to find courses:", gap_skills, key="course_sel")
        if st.button(f"Search courses for {sel_skill}", key="course_search"):
            with st.spinner(f"Searching Coursera · Udemy · YouTube for {sel_skill}…"):
                found = search_course_links(sel_skill)
            cc = st.session_state.get("course_cache",{})
            cc[sel_skill] = found
            st.session_state["course_cache"] = cc

        cached_courses = st.session_state.get("course_cache",{}).get(sel_skill,[])
        for crs in cached_courses:
            st.markdown(f'<div class="sf-course">{crs["icon"]} <a href="{crs["url"]}" target="_blank">{crs["title"]}</a><div class="sf-course-plat">{crs["platform"]} · {crs["snippet"]}</div></div>', unsafe_allow_html=True)
        if not cached_courses and sel_skill in st.session_state.get("course_cache",{}):
            st.warning(f"No course links found for {sel_skill} — try a different skill or search manually.")


# =============================================================================
#  SECTION: EXPORT
# =============================================================================
def render_export(res):
    c  = res["candidate"]; jd = res["jd"]
    gp = res["gap_profile"]; pt = res["path"]
    im = res["impact"];     ql = res.get("quality",{})
    iv = res.get("interview",{})

    st.markdown('<div id="export"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-title">Export</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Download your personalized roadmap as PDF · JSON · CSV</div>', unsafe_allow_html=True)

    e1, e2, e3 = st.columns(3, gap="medium")

    with e1:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">PDF report</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-sub">Full roadmap with AI reasoning traces, ATS audit, and scores</div>', unsafe_allow_html=True)
        for k, v in [("Candidate", c.get("name","--")),
                     ("Role", jd.get("role_title","--")),
                     ("ATS score", f"{ql.get('ats_score','--')}%"),
                     ("Modules", im["modules_count"]),
                     ("Training", f"{im['roadmap_hours']}h")]:
            st.markdown(f'<div class="sf-export-row"><span class="sf-export-key">{k}</span><span class="sf-export-val">{v}</span></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if REPORTLAB:
            pdf_buf = build_pdf(c, jd, gp, pt, im, ql, iv)
            nm = (c.get("name","candidate") or "candidate").replace(" ","_")
            st.download_button("⬇ Download PDF", data=pdf_buf,
                               file_name=f"skillforge_{nm}_{datetime.now().strftime('%Y%m%d')}.pdf",
                               mime="application/pdf", use_container_width=True)
        else:
            st.caption("`pip install reportlab` to enable PDF export")
        st.markdown('</div>', unsafe_allow_html=True)

    with e2:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">JSON export</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-sub">Complete structured result for integrations and downstream tools</div>', unsafe_allow_html=True)
        export_data = {
            "candidate":    c, "jd": jd, "impact": im, "interview": iv,
            "gap_profile":  [{k:v for k,v in g.items() if k!="catalog_course"} for g in gp],
            "roadmap":      [{"id":m["id"],"title":m["title"],"skill":m["skill"],
                              "level":m["level"],"duration_hrs":m["duration_hrs"],
                              "is_critical":m.get("is_critical",False),
                              "reasoning":m.get("reasoning","")} for m in pt],
            "generated_at": datetime.now().isoformat(),
        }
        json_str = json.dumps(export_data, indent=2, default=str)
        st.markdown("<div style='height:58px'></div>", unsafe_allow_html=True)
        st.download_button("⬇ Download JSON", data=json_str,
                           file_name=f"skillforge_{datetime.now().strftime('%Y%m%d')}.json",
                           mime="application/json", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with e3:
        st.markdown('<div class="sf-export-card">', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-hd">Skill gap CSV</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-export-sub">Tabular gap data for spreadsheet analysis and HR reporting</div>', unsafe_allow_html=True)
        csv_rows = ["Skill,Status,Proficiency,Required,Demand,Decayed"]
        for g in gp:
            csv_rows.append(f'"{g["skill"]}",{g["status"]},{g["proficiency"]},{g["is_required"]},{g.get("demand",1)},{g.get("decayed",False)}')
        st.markdown("<div style='height:58px'></div>", unsafe_allow_html=True)
        st.download_button("⬇ Download CSV", data="\n".join(csv_rows),
                           file_name=f"skillforge_gap_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime="text/csv", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
#  API LOG
# =============================================================================
def render_api_log():
    total_cost = sum(e.get("cost",0) for e in _audit_log)
    with st.expander(f"API log — {len(_audit_log)} calls · ${total_cost:.5f}"):
        for e in reversed(_audit_log[-20:]):
            ok = e.get("status") == "ok"
            status_color = "#4ade80" if ok else "#ef4444"
            st.markdown(f"""
            <div class="sf-log-line">
              <span style="color:{status_color}">{"●" if ok else "✕"}</span>
              <span>{e.get('ts','')}</span>
              <span style="color:#2dd4bf">{e.get('model','')}</span>
              <span>in:{e.get('in',0)} out:{e.get('out',0)}</span>
              <span>{e.get('ms',0)}ms</span>
              <span>${e.get('cost',0):.6f}</span>
            </div>""", unsafe_allow_html=True)


# =============================================================================
#  FOOTER
# =============================================================================
def render_footer():
    cost  = sum(e.get("cost",0) for e in _audit_log)
    calls = len(_audit_log)
    sem_c = "#4ade80" if SEMANTIC else "#f59e0b"
    sem_t = "semantic ✓" if SEMANTIC else "semantic ⟳"
    st.markdown(f"""
    <div class="sf-footer">
      <span><span class="sf-footer-dot" style="background:#2dd4bf"></span>Groq LLaMA 4-Scout</span>
      <span><span class="sf-footer-dot" style="background:#2dd4bf"></span>NetworkX DAG</span>
      <span><span class="sf-footer-dot" style="background:{sem_c}"></span>{sem_t}</span>
      <span><span class="sf-footer-dot" style="background:#2dd4bf"></span>DDG search</span>
      <span class="sf-footer-right">v8 · {calls} calls · ${cost:.5f}</span>
    </div>""", unsafe_allow_html=True)


# =============================================================================
#  TAB 2: LIVE RESEARCH (salary + job market + free-form search + courses)
# =============================================================================
def render_research_tab(res):
    sal    = res.get("salary",{})
    trends = res.get("skill_trends",{})
    mkt    = res.get("market_insights",[])
    jd     = res["jd"]
    gp     = res["gap_profile"]

    # ── Free-form web search ─────────────────────────────────────────────────
    st.markdown('<div class="sf-section-title">Web search</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Search anything — courses, companies, job market data, skills, salaries</div>', unsafe_allow_html=True)

    srch_col, btn_col = st.columns([4,1])
    with srch_col:
        query = st.text_input("Search the web", placeholder='e.g. "FastAPI vs Flask 2025" or "React developer salary Bangalore"',
                              key="search_input", label_visibility="collapsed",
                              value=st.session_state.get("search_query",""))
        st.session_state["search_query"] = query
    with btn_col:
        do_search = st.button("Search →", key="search_go", use_container_width=True)

    if do_search and query.strip():
        with st.spinner(f"Searching: {query}…"):
            raw = ddg_search(query, max_results=8)
        st.session_state["search_results"] = raw

    results = st.session_state.get("search_results",[])
    if results:
        st.markdown(f'<p style="font-family:var(--mono);font-size:0.65rem;color:var(--text-3);margin-bottom:10px">{len(results)} results for <em style="color:var(--text-1)">{st.session_state.get("search_query","")}</em></p>', unsafe_allow_html=True)
        for r in results:
            title = r.get("title","No title")
            href  = r.get("href","")
            body  = r.get("body","")[:180]
            st.markdown(f"""
            <div style="background:var(--surface);border:1px solid var(--border);
                        border-radius:7px;padding:11px 14px;margin-bottom:6px;">
              <div style="font-family:var(--display);font-size:0.8rem;font-weight:600;
                          color:var(--text-1);margin-bottom:3px">
                <a href="{href}" target="_blank" style="color:var(--teal);text-decoration:none">{title}</a>
              </div>
              <div style="font-family:var(--mono);font-size:0.65rem;color:var(--text-3);margin-bottom:4px">{href[:60]}…</div>
              <div style="font-family:var(--mono);font-size:0.7rem;color:var(--text-2);line-height:1.5">{body}</div>
            </div>""", unsafe_allow_html=True)
    elif do_search:
        st.warning("No results found. Try a different query.")

    # Quick search shortcuts
    role = jd.get("role_title","")
    gap_skills_list = [g["skill"] for g in gp if g["status"]!="Known"][:5]
    st.markdown('<p style="font-family:var(--mono);font-size:0.65rem;color:var(--text-3);margin-top:8px;margin-bottom:6px">Quick searches:</p>', unsafe_allow_html=True)
    shortcut_cols = st.columns(len(gap_skills_list) + 1)
    for i, skill in enumerate(gap_skills_list):
        with shortcut_cols[i]:
            if st.button(f"{skill} courses", key=f"qs_{i}", use_container_width=True):
                st.session_state["search_query"] = f"{skill} online course tutorial 2025"
                st.session_state["search_results"] = ddg_search(f"{skill} online course tutorial 2025", max_results=8)
                st.rerun()
    with shortcut_cols[-1]:
        if st.button(f"{role[:18]} salary", key="qs_sal", use_container_width=True):
            loc = st.session_state.get("sal_location","India")
            st.session_state["search_query"] = f"{role} salary {loc} 2025"
            st.session_state["search_results"] = ddg_search(f"{role} salary {loc} 2025", max_results=8)
            st.rerun()

    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

    # ── Salary + Market ──────────────────────────────────────────────────────
    sal_col, mkt_col = st.columns(2, gap="large")

    with sal_col:
        st.markdown('<div class="sf-section-title" style="font-size:0.9rem">Salary benchmark</div>', unsafe_allow_html=True)
        if sal and sal.get("median_lpa",0):
            curr = sal.get("currency","INR")
            sym  = "₹" if curr=="INR" else "$"
            unit = "L/yr" if curr=="INR" else "k/yr"
            st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar":False})
            st.caption(f"Source: {sal.get('source','web')} · {sal.get('note','')}")
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;color:var(--text-3);margin-bottom:8px">Salary data not yet fetched or unavailable.</p>', unsafe_allow_html=True)
            loc_sel = st.selectbox("Location", ["India","USA","UK","Germany","Canada","Singapore"], key="sal_loc_sel2")
            if st.button("Fetch salary data", key="sal_refresh2"):
                with st.spinner("Searching…"):
                    new_sal = search_real_salary(role, loc_sel)
                st.session_state["result"]["salary"] = new_sal
                st.rerun()

    with mkt_col:
        st.markdown('<div class="sf-section-title" style="font-size:0.9rem">Job market insights</div>', unsafe_allow_html=True)
        if mkt:
            for ins in mkt:
                st.markdown(f'<div class="sf-insight">📌 {ins}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="font-family:var(--mono);font-size:0.7rem;color:var(--text-3);margin-bottom:8px">Market insights not yet fetched.</p>', unsafe_allow_html=True)
            if st.button("Fetch market insights", key="mkt_refresh2"):
                with st.spinner("Searching…"):
                    new_mkt = search_job_market(role)
                st.session_state["result"]["market_insights"] = new_mkt
                st.rerun()

    # ── Skill demand signals ─────────────────────────────────────────────────
    if trends:
        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-section-title" style="font-size:0.9rem">Skill demand signals</div>', unsafe_allow_html=True)
        pills_html = ""
        for skill, sig in trends.items():
            sig_col = (_RED if "Hot" in sig else _AMBER if "Growing" in sig else "#3d4d66")
            pills_html += f'<span class="sf-trend-pill"><span class="sf-trend-skill">{skill[:14]}</span><span style="color:{sig_col}">&nbsp;{sig}</span></span>'
        st.markdown(f'<div style="line-height:2.8">{pills_html}</div>', unsafe_allow_html=True)

        # Refresh trends
        if st.button("Re-fetch skill trends", key="trends_refresh"):
            gap_skills_r = [g["skill"] for g in gp if g["status"]!="Known"][:6]
            with st.spinner("Checking latest demand data…"):
                new_trends = search_skill_trends(gap_skills_r)
            st.session_state["result"]["skill_trends"] = new_trends
            st.rerun()

    # ── Course finder ────────────────────────────────────────────────────────
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-title" style="font-size:0.9rem">Course finder</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Find real courses on Coursera, Udemy, YouTube for any gap skill</div>', unsafe_allow_html=True)

    gap_skills = [g["skill"] for g in gp if g["status"]!="Known"]
    if gap_skills:
        crs_col, crs_btn = st.columns([3,1])
        with crs_col:
            sel_skill = st.selectbox("Pick a skill:", gap_skills, key="course_sel",
                                     label_visibility="collapsed")
        with crs_btn:
            find_courses = st.button(f"Find courses", key="course_search", use_container_width=True)

        if find_courses:
            with st.spinner(f"Searching Coursera · Udemy · YouTube for {sel_skill}…"):
                found = search_course_links(sel_skill)
            cc = st.session_state.get("course_cache",{})
            cc[sel_skill] = found
            st.session_state["course_cache"] = cc

        cached_courses = st.session_state.get("course_cache",{}).get(sel_skill,[])
        if cached_courses:
            for crs in cached_courses:
                st.markdown(f'<div class="sf-course">{crs["icon"]} <a href="{crs["url"]}" target="_blank">{crs["title"]}</a><div class="sf-course-plat">{crs["platform"]} · {crs["snippet"]}</div></div>', unsafe_allow_html=True)
        elif sel_skill in st.session_state.get("course_cache",{}):
            st.warning(f"No links found for {sel_skill}. Try searching manually above.")

        # Load all at once
        if st.button("Load courses for all gap skills at once", key="load_all_courses"):
            all_cache = {}
            with st.spinner(f"Fetching courses for {len(gap_skills[:10])} skills…"):
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {ex.submit(search_course_links, s): s for s in gap_skills[:10]}
                    for fut in futs:
                        all_cache[futs[fut]] = fut.result()
            st.session_state["course_cache"] = all_cache
            st.success(f"✓ Loaded courses for {len(all_cache)} skills")
            st.rerun()


# =============================================================================
#  RESULTS PAGE — 3 TABS
# =============================================================================
def render_results_page():
    res = st.session_state.get("result")
    if not res: return

    im = res["impact"]; iv = res["interview"]; sm = res.get("seniority",{})
    render_sidebar(im, iv, sm)

    st.markdown('<div class="sf-page">', unsafe_allow_html=True)

    # Score overview always visible above tabs
    render_score_overview(res)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📊 Gap & Roadmap",
        "🌐 Live Research",
        "✅ ATS & Export",
    ])

    with tab1:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        render_skill_gap(res)
        render_roadmap(res)

    with tab2:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        render_research_tab(res)

    with tab3:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        render_ats(res)
        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        render_export(res)
        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        render_api_log()

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  MAIN
# =============================================================================
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    _init_state()

    step = st.session_state.get("step", 1)
    render_topbar()

    if step == "results":
        # Reset button in topbar area
        _, rc = st.columns([11,1])
        with rc:
            st.markdown('<div class="sf-ghost">', unsafe_allow_html=True)
            if st.button("Reset", key="top_reset"):
                _full_reset()
            st.markdown("</div>", unsafe_allow_html=True)
        render_results_page()
    else:
        if step == 1:
            render_step1()
        elif step == 2:
            render_step2()
        elif step == "analyzing":
            render_loading()

    render_footer()


# =============================================================================
#  CLI MODE
# =============================================================================
def cli_analyze(scenario_key):
    if scenario_key not in SAMPLES:
        print(f"Unknown scenario. Choose from: {list(SAMPLES.keys())}"); sys.exit(1)
    s = SAMPLES[scenario_key]
    print(f"\n  SkillForge v8 CLI  ·  {s['label']}\n  {'='*52}")
    t0 = time.time()
    result = run_analysis(s["resume"], s["jd"])
    print(f"  Done in {round(time.time()-t0, 2)}s")
    if "error" in result:
        print(f"  Error: {result}"); return
    c  = result["candidate"]; im = result["impact"]
    iv = result["interview"]; pt = result["path"]
    print(f"\n  Candidate : {c.get('name','--')} ({c.get('seniority','--')})")
    print(f"  Role      : {result['jd'].get('role_title','--')}")
    print(f"  Fit       : {im['current_fit']}% → {im['projected_fit']}% (+{im['fit_delta']}%)")
    print(f"  Interview : {iv['score']}% ({iv['label']})")
    print(f"  Roadmap   : {im['modules_count']} modules / {im['roadmap_hours']}h / {im['critical_count']} critical")
    for i, m in enumerate(pt):
        crit = "★ " if m.get("is_critical") else "  "
        print(f"    {crit}#{i+1:02d} [{m['level'][:3]}] {m['title']} ({m['duration_hrs']}h)")
    print(f"\n  Hours saved vs generic 60h: ~{im['hours_saved']}h\n")


# =============================================================================
#  ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkillForge v8")
    parser.add_argument("--analyze", metavar="SCENARIO",
                        help="junior_swe | senior_ds | hr_manager")
    args, _ = parser.parse_known_args()
    if args.analyze:
        cli_analyze(args.analyze)
    else:
        threading.Thread(target=_load_semantic_bg, daemon=True).start()
        main()