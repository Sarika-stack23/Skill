# =============================================================================
#  main.py — SkillForge v7  |  Redesigned UX
#  Sequential flow · Sections not tabs · Auto web intel · Live roadmap
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
#  WEB SEARCH (DuckDuckGo — free, no key)
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

SAMPLES = {
    "junior_swe": {
        "label": "Junior SWE → Full Stack",
        "role":  "Full Stack Engineer",
        "fit":   "38%→72%",
        "hrs":   "47h",
        "resume": "John Smith\nJunior Software Developer | 1 year experience\nSkills: Python (basic, 4/10), HTML/CSS, some JavaScript\nEducation: B.Tech Computer Science 2023\nProjects: Built a todo app using Flask. Familiar with Git basics.\nNo professional cloud or DevOps experience.",
        "jd":    "Software Engineer Full Stack - Mid Level\nRequired: Python, React, FastAPI, Docker, SQL, REST APIs, AWS\nPreferred: Kubernetes, CI/CD\nSeniority: Mid | Domain: Tech",
    },
    "senior_ds": {
        "label": "Senior DS → Lead AI",
        "role":  "Lead Data Scientist",
        "fit":   "61%→89%",
        "hrs":   "28h",
        "resume": "Priya Patel\nSenior Data Scientist | 7 years experience\nSkills: Python (expert, 9/10), Machine Learning (expert), Deep Learning (PyTorch, 8/10), SQL (advanced, 8/10), AWS SageMaker (7/10)\nLast used NLP: 2022. Last used MLOps: 2021.\nLed team of 5. Published 3 ML papers.",
        "jd":    "Lead Data Scientist - AI Products\nRequired: Python, Machine Learning, Deep Learning, NLP, MLOps, SQL, AWS\nPreferred: GCP, Kubernetes, Leadership\nSeniority: Lead | Domain: Tech",
    },
    "hr_manager": {
        "label": "HR Coordinator → Manager",
        "role":  "HR Manager",
        "fit":   "44%→81%",
        "hrs":   "22h",
        "resume": "Amara Johnson\nHR Coordinator | 3 years experience\nSkills: Human Resources (intermediate, 6/10), Recruitment (good, 7/10), Microsoft Office\nSome performance review experience. No formal L&D training.",
        "jd":    "HR Manager - People and Culture\nRequired: Human Resources, Recruitment, Performance Management, Employee Relations\nPreferred: L&D Strategy, Communication, Leadership\nSeniority: Senior | Domain: Non-Tech",
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
        cached_d = getattr(usage,"prompt_tokens_details",None)
        cached_c = getattr(cached_d,"cached_tokens",0) if cached_d else 0
        cost = round((in_tok*0.00000011)+(out_tok*0.00000034),6)
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),
                            "model":model.split("/")[-1][:22],
                            "in":in_tok,"out":out_tok,"cached":cached_c,
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
                            "status":f"err:{err[:40]}","in":0,"out":0,
                            "cached":0,"ms":0,"cost":0})
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
        return {"min_lpa":0,"max_lpa":0,"median_lpa":0,"note":"No web results found","source":"—"}
    snippets = "\n".join([f"- {r.get('title','')}: {r.get('body','')[:200]}" for r in results[:5]])
    r = _groq_call(
        f'Extract salary data for "{role}" in {location} from these search snippets.\n\n{snippets}\n\n'
        f'Return JSON: {{"min_lpa":<number>,"max_lpa":<number>,"median_lpa":<number>,'
        f'"currency":"INR or USD","source":"<website name>","note":"<key caveat>"}}',
        system="Extract structured salary info from web snippets. Return JSON only.",
        model=MODEL_FAST, max_tokens=400,
    )
    return r if "error" not in r else {"min_lpa":0,"max_lpa":0,"median_lpa":0,"note":"Parse failed","source":"—"}

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
_CACHE_PATH = "/tmp/skillforge_v7"
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
#  FULL PIPELINE (analysis + web intel in parallel)
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
    """Main analysis + parallel web intel fetch."""
    result = run_analysis(resume_text, jd_text, resume_image_b64)
    if "error" in result: return result
    role = result["jd"].get("role_title","")
    gap_skills = [g["skill"] for g in result["gap_profile"] if g["status"] != "Known"][:6]
    with ThreadPoolExecutor(max_workers=3) as ex:
        sal_f   = ex.submit(search_real_salary, role, location)
        trend_f = ex.submit(search_skill_trends, gap_skills)
        mkt_f   = ex.submit(search_job_market, role)
    result["salary"]         = sal_f.result()
    result["skill_trends"]   = trend_f.result()
    result["market_insights"]= mkt_f.result()
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
        Paragraph("SkillForge v7 — AI Adaptive Onboarding Report", H1),
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
_TRANSPARENT = "rgba(0,0,0,0)"
_GRID        = "rgba(255,255,255,0.06)"
_ACCENT      = "#2dd4bf"
_AMBER       = "#fbbf24"
_RED         = "#f87171"

def radar_chart(gp):
    items = gp[:10]
    if not items: return go.Figure()
    theta = [g["skill"][:14] for g in items]
    fig = go.Figure(data=[
        go.Scatterpolar(r=[10]*len(items), theta=theta, fill="toself",
                        name="Required", line=dict(color=_RED, width=1.5), opacity=0.15),
        go.Scatterpolar(r=[g.get("original_prof", g["proficiency"]) for g in items],
                        theta=theta, fill="toself", name="Before decay",
                        line=dict(color=_AMBER, width=1, dash="dot"), opacity=0.2),
        go.Scatterpolar(r=[g["proficiency"] for g in items], theta=theta, fill="toself",
                        name="Current", line=dict(color=_ACCENT, width=2), opacity=0.75),
    ])
    fig.update_layout(
        polar=dict(bgcolor=_TRANSPARENT,
                   radialaxis=dict(visible=True, range=[0,10], gridcolor=_GRID,
                                   tickfont=dict(size=9, color="#4a5568")),
                   angularaxis=dict(gridcolor=_GRID)),
        paper_bgcolor=_TRANSPARENT, plot_bgcolor=_TRANSPARENT,
        font=dict(color="#8892a4", family="system-ui,sans-serif"),
        showlegend=True,
        legend=dict(bgcolor=_TRANSPARENT, x=0.78, y=1.15, font=dict(size=10)),
        margin=dict(l=30, r=30, t=40, b=30), height=320,
    )
    return fig

def timeline_chart(path):
    if not path: return go.Figure()
    lc = {"Critical":_RED, "Beginner":_ACCENT, "Intermediate":_AMBER, "Advanced":"#fb923c"}
    shown, fig = set(), go.Figure()
    for i, m in enumerate(path):
        k = "Critical" if m.get("is_critical") else m["level"]
        show = k not in shown; shown.add(k)
        fig.add_trace(go.Bar(
            x=[m["duration_hrs"]], y=[f"#{i+1} {m['title'][:28]}"],
            orientation="h",
            marker=dict(color=lc.get(k,"#888"), opacity=0.85, line=dict(width=0)),
            name=k, legendgroup=k, showlegend=show,
            hovertemplate=f"<b>{m['title']}</b><br>{m['level']} · {m['duration_hrs']}h<extra></extra>",
        ))
    fig.update_layout(
        paper_bgcolor=_TRANSPARENT, plot_bgcolor="rgba(10,15,30,0.4)",
        font=dict(color="#8892a4"),
        xaxis=dict(title="Hours", gridcolor=_GRID, zeroline=False),
        yaxis=dict(gridcolor=_GRID, tickfont=dict(size=10)),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(260, len(path)*36),
        legend=dict(bgcolor=_TRANSPARENT, orientation="h", y=1.03),
        barmode="overlay",
    )
    return fig

def roi_chart(roi_list):
    if not roi_list: return go.Figure()
    top = roi_list[:10]
    fig = go.Figure(go.Bar(
        x=[m["roi"] for m in top],
        y=[m["title"][:28] for m in top],
        orientation="h",
        marker=dict(color=[_RED if m["is_required"] else _ACCENT for m in top], opacity=0.85),
        hovertemplate="<b>%{y}</b><br>ROI: %{x}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_TRANSPARENT, plot_bgcolor="rgba(10,15,30,0.4)",
        font=dict(color="#8892a4"),
        xaxis=dict(title="ROI Index", gridcolor=_GRID, zeroline=False),
        yaxis=dict(gridcolor=_GRID, autorange="reversed"),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(220, len(top)*32),
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
            marker=dict(size=[max(14, p["hrs"]*2.8) for p in sub], color=col, opacity=0.72),
            text=[p["skill"][:13] for p in sub], textposition="top center",
            textfont=dict(size=9, color="#8892a4"), name=sl,
            hovertemplate="<b>%{text}</b><br>Ease:%{x:.1f} Impact:%{y:.1f}<extra></extra>",
        ))
    for x, y, t in [(2.5,8.5,"HIGH PRIORITY"),(7.5,8.5,"QUICK WIN"),
                    (2.5,2.5,"LONG HAUL"),    (7.5,2.5,"NICE TO HAVE")]:
        fig.add_annotation(x=x, y=y, text=t, showarrow=False,
                           font=dict(size=9, color="#2d3f60"))
    fig.add_hline(y=5.5, line_dash="dot", line_color=_GRID)
    fig.add_vline(x=5.5, line_dash="dot", line_color=_GRID)
    fig.update_layout(
        paper_bgcolor=_TRANSPARENT, plot_bgcolor="rgba(10,15,30,0.4)",
        font=dict(color="#8892a4"),
        xaxis=dict(title="Ease", range=[0,11], gridcolor=_GRID, zeroline=False),
        yaxis=dict(title="Impact", range=[0,11], gridcolor=_GRID, zeroline=False),
        margin=dict(l=20, r=20, t=20, b=40),
        showlegend=True, height=360,
        legend=dict(bgcolor=_TRANSPARENT, x=0, y=1.1, orientation="h"),
    )
    return fig

def salary_chart(s):
    if not s or not s.get("median_lpa"): return go.Figure()
    vals = [s.get("min_lpa",0), s.get("median_lpa",0), s.get("max_lpa",0)]
    curr = s.get("currency","INR")
    labels = [f"₹{v}L" if curr=="INR" else f"${v}k" for v in vals]
    fig = go.Figure(go.Bar(
        x=["Min","Median","Max"], y=vals,
        marker_color=[_ACCENT, _AMBER, _RED], opacity=0.88,
        text=labels, textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_TRANSPARENT, plot_bgcolor="rgba(10,15,30,0.4)",
        font=dict(color="#8892a4"),
        yaxis=dict(title=f"{curr}/yr", gridcolor=_GRID),
        xaxis=dict(gridcolor=_GRID),
        margin=dict(l=20, r=20, t=20, b=40), height=240,
    )
    return fig

# =============================================================================
#  CSS — v7: token-based, clean, one font, no neon
# =============================================================================
CSS = """
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif !important;
    background: #0c0e14 !important;
    color: #c5cdd8 !important;
}
.stApp { background: #0c0e14 !important; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] > div:first-child {
    background: #0f1118 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    padding: 0 !important;
}
footer, #MainMenu, header[data-testid="stHeader"] { display: none !important; }

::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 99px; }

/* ── VARIABLES ── */
:root {
    --accent:       #2dd4bf;
    --accent-dim:   rgba(45,212,191,0.12);
    --accent-border:rgba(45,212,191,0.25);
    --amber:        #fbbf24;
    --red:          #f87171;
    --green:        #4ade80;
    --surface:      #141720;
    --raised:       #1a1e2a;
    --border:       rgba(255,255,255,0.07);
    --border-med:   rgba(255,255,255,0.12);
    --text-1:       #f0f2f7;
    --text-2:       #8892a4;
    --text-3:       #3a4459;
}

/* ── LAYOUT ── */
.sf-page      { padding: 0 32px 80px; max-width: 1200px; margin: 0 auto; }
.sf-page-wide { padding: 0 24px 80px; }

/* ── TOPBAR ── */
.sf-topbar {
    height: 52px;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 32px;
    border-bottom: 1px solid var(--border);
    background: rgba(12,14,20,0.95);
    position: sticky; top: 0; z-index: 100;
    backdrop-filter: blur(12px);
}
.sf-brand { font-size: 1rem; font-weight: 700; color: var(--text-1); letter-spacing: -0.02em; }
.sf-brand em { color: var(--accent); font-style: normal; }
.sf-topbar-tags { display: flex; gap: 6px; }
.sf-chip {
    font-size: 0.65rem; padding: 3px 9px; border-radius: 99px;
    border: 1px solid var(--border-med); color: var(--text-2);
    letter-spacing: 0.03em;
}

/* ── STEP INDICATOR ── */
.sf-steps {
    display: flex; align-items: center; gap: 0;
    padding: 20px 0 28px;
}
.sf-step {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.78rem; color: var(--text-3);
}
.sf-step.active { color: var(--text-1); }
.sf-step.done   { color: var(--accent); }
.sf-step-dot {
    width: 22px; height: 22px; border-radius: 50%;
    border: 1.5px solid var(--text-3);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.65rem; font-weight: 700; color: var(--text-3);
    flex-shrink: 0;
}
.sf-step.active .sf-step-dot {
    border-color: var(--accent); color: var(--accent);
    background: var(--accent-dim);
}
.sf-step.done .sf-step-dot {
    border-color: var(--accent); background: var(--accent);
    color: #0c0e14;
}
.sf-step-line {
    width: 40px; height: 1px; background: var(--border);
    margin: 0 4px; flex-shrink: 0;
}
.sf-step-line.done { background: var(--accent); opacity: 0.4; }

/* ── ENTRY ZONE ── */
.sf-entry-wrap {
    min-height: 70vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 32px 24px;
}
.sf-entry-title {
    font-size: clamp(1.5rem, 3.5vw, 2.4rem);
    font-weight: 700; color: var(--text-1);
    letter-spacing: -0.03em; text-align: center;
    line-height: 1.15; margin-bottom: 10px;
}
.sf-entry-title em { color: var(--accent); font-style: normal; }
.sf-entry-sub {
    font-size: 0.85rem; color: var(--text-2);
    text-align: center; max-width: 480px; line-height: 1.6;
    margin-bottom: 36px;
}

/* ── PERSONA CARDS ── */
.sf-personas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; width: 100%; max-width: 640px; margin-bottom: 32px; }
@media(max-width:600px) { .sf-personas { grid-template-columns: 1fr; } }
.sf-persona {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 14px;
    cursor: pointer; transition: border-color 0.15s;
}
.sf-persona:hover { border-color: var(--accent-border); }
.sf-persona-label { font-size: 0.76rem; font-weight: 600; color: var(--text-1); margin-bottom: 3px; }
.sf-persona-role  { font-size: 0.68rem; color: var(--text-2); margin-bottom: 6px; }
.sf-persona-stats { display: flex; gap: 10px; }
.sf-persona-stat  { font-size: 0.65rem; }
.sf-persona-stat span { color: var(--accent); font-weight: 600; }

/* ── INPUT CARD ── */
.sf-input-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px; padding: 22px 24px;
    width: 100%; max-width: 620px;
}
.sf-input-card.highlight { border-color: var(--accent-border); }
.sf-input-hd {
    font-size: 0.78rem; font-weight: 600; color: var(--text-1);
    margin-bottom: 14px; display: flex; align-items: center;
    justify-content: space-between;
}
.sf-input-hd-badge {
    font-size: 0.62rem; padding: 2px 8px; border-radius: 99px;
    background: var(--accent-dim); color: var(--accent);
    border: 1px solid var(--accent-border);
}
.sf-input-tip {
    font-size: 0.68rem; color: var(--text-3); margin-top: 8px; text-align: center;
}

/* Streamlit file upload overrides */
[data-testid="stFileUploadDropzone"] {
    background: rgba(45,212,191,0.03) !important;
    border: 1.5px dashed rgba(45,212,191,0.18) !important;
    border-radius: 8px !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: rgba(45,212,191,0.4) !important;
    background: rgba(45,212,191,0.05) !important;
}
[data-testid="stFileUploadDropzone"] button {
    background: transparent !important;
    border: 1px solid rgba(45,212,191,0.3) !important;
    color: var(--accent) !important;
    border-radius: 6px !important; font-size: 0.72rem !important;
}

/* Textarea */
textarea {
    background: #0f1118 !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important; color: #b0bcd4 !important;
    font-size: 0.78rem !important; resize: vertical !important;
}
textarea:focus { border-color: var(--accent-border) !important; outline: none !important; }
textarea::placeholder { color: var(--text-3) !important; }

/* Primary button */
.stButton > button {
    background: var(--accent) !important; border: none !important;
    border-radius: 9px !important; color: #0c0e14 !important;
    font-weight: 700 !important; font-size: 0.85rem !important;
    padding: 11px 0 !important; width: 100% !important;
    transition: opacity 0.15s !important;
    letter-spacing: 0.01em !important;
}
.stButton > button:hover { opacity: 0.85 !important; }
.stButton > button:active { opacity: 0.95 !important; transform: scale(0.99) !important; }

/* Ghost button variant */
.sf-btn-ghost > button {
    background: var(--raised) !important;
    border: 1px solid var(--border-med) !important;
    color: var(--text-2) !important; font-weight: 500 !important;
}
.sf-btn-ghost > button:hover { color: var(--text-1) !important; border-color: var(--border-med) !important; }

/* Sidebar nav */
.sf-sidenav { padding: 16px 12px; }
.sf-sidenav-title {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--text-3);
    padding: 0 4px; margin-bottom: 8px;
}
.sf-nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 10px; border-radius: 7px;
    font-size: 0.78rem; color: var(--text-2);
    cursor: pointer; transition: all 0.12s;
    margin-bottom: 2px; text-decoration: none;
    border: 1px solid transparent;
}
.sf-nav-item:hover { background: var(--surface); color: var(--text-1); }
.sf-nav-item.active {
    background: var(--accent-dim); color: var(--accent);
    border-color: var(--accent-border);
}
.sf-nav-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.sf-nav-divider { height: 1px; background: var(--border); margin: 10px 0; }
.sf-nav-meta { padding: 8px 10px; }
.sf-nav-stat { font-size: 0.68rem; color: var(--text-3); margin-bottom: 4px; }
.sf-nav-stat span { color: var(--text-2); font-weight: 600; }

/* ── LOADING STATES ── */
.sf-loading-wrap { padding: 48px 0; }
.sf-loading-title {
    font-size: 1.1rem; font-weight: 600; color: var(--text-1);
    margin-bottom: 6px;
}
.sf-loading-sub { font-size: 0.8rem; color: var(--text-2); margin-bottom: 32px; }
.sf-load-steps { display: flex; flex-direction: column; gap: 10px; max-width: 400px; }
.sf-load-step {
    display: flex; align-items: center; gap: 12px;
    font-size: 0.78rem; color: var(--text-3); padding: 10px 14px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; transition: all 0.2s;
}
.sf-load-step.active {
    color: var(--accent); border-color: var(--accent-border);
    background: var(--accent-dim);
}
.sf-load-step.done { color: var(--green); border-color: rgba(74,222,128,0.2); }
.sf-load-icon { font-size: 0.85rem; width: 18px; text-align: center; flex-shrink: 0; }

/* ── SCORE HERO ── */
.sf-hero-section { padding: 32px 0 24px; }
.sf-hero-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px; padding: 28px 32px;
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 24px; align-items: center;
    margin-bottom: 20px;
}
@media(max-width:700px){ .sf-hero-card{ grid-template-columns:1fr; } }
.sf-fit-score { text-align: center; }
.sf-fit-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em;
                text-transform: uppercase; color: var(--text-3); margin-bottom: 8px; }
.sf-fit-num   { font-size: 3rem; font-weight: 800; color: var(--accent); line-height: 1; }
.sf-fit-arrow { font-size: 0.8rem; color: var(--text-2); margin-top: 4px; }
.sf-fit-arrow em { color: var(--green); font-style: normal; font-weight: 700; }
.sf-kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.sf-kpi {
    background: var(--raised); border-radius: 8px; padding: 12px 14px;
    border: 1px solid var(--border);
}
.sf-kpi-v { font-size: 1.3rem; font-weight: 700; color: var(--text-1); line-height: 1.1; }
.sf-kpi-l { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em;
             text-transform: uppercase; color: var(--text-3); margin-top: 2px; }
.sf-kpi-d { font-size: 0.7rem; color: var(--accent); margin-top: 2px; }

/* ── SECTION HEADER ── */
.sf-section-hd {
    font-size: 1rem; font-weight: 700; color: var(--text-1);
    margin-bottom: 4px; letter-spacing: -0.01em;
}
.sf-section-sub {
    font-size: 0.72rem; color: var(--text-3); margin-bottom: 18px;
}
.sf-divider { height: 1px; background: var(--border); margin: 28px 0; }

/* ── SKILL ROWS ── */
.sf-skill-item {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 11px 14px; margin-bottom: 6px;
    cursor: pointer; transition: border-color 0.12s;
}
.sf-skill-item:hover { border-color: var(--border-med); }
.sf-skill-item.expanded { border-color: var(--accent-border); }
.sf-skill-row { display: flex; align-items: center; gap: 10px; }
.sf-skill-name { min-width: 130px; font-size: 0.78rem; color: var(--text-1); font-weight: 500; }
.sf-skill-bar  { flex: 1; height: 4px; background: rgba(255,255,255,0.06); border-radius: 99px; overflow: hidden; }
.sf-skill-fill { height: 100%; border-radius: 99px; transition: width 0.3s; }
.sf-skill-val  { font-size: 0.68rem; color: var(--text-2); min-width: 36px; text-align: right; font-variant-numeric: tabular-nums; }
.sf-badge { font-size: 0.58rem; border-radius: 4px; padding: 2px 6px; font-weight: 700; flex-shrink: 0; }
.sf-badge-known   { background: rgba(45,212,191,0.1);  color: var(--accent); border: 1px solid rgba(45,212,191,0.2); }
.sf-badge-partial { background: rgba(251,191,36,0.1);  color: var(--amber);  border: 1px solid rgba(251,191,36,0.2); }
.sf-badge-missing { background: rgba(248,113,113,0.1); color: var(--red);    border: 1px solid rgba(248,113,113,0.2); }
.sf-badge-demand  { font-size: 0.6rem; margin-left: 2px; }
.sf-skill-detail {
    margin-top: 10px; padding-top: 10px;
    border-top: 1px solid var(--border);
    font-size: 0.72rem; color: var(--text-2);
    display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
}
.sf-skill-ctx { grid-column: 1 / -1; color: var(--text-3); font-style: italic; }
.sf-decay-note { color: var(--amber); }
.sf-obs-note   { color: var(--red); }

/* ── ROADMAP CARDS ── */
.sf-roadmap-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px; flex-wrap: wrap; gap: 10px;
}
.sf-pace-row { display: flex; align-items: center; gap: 10px; font-size: 0.78rem; color: var(--text-2); }
.sf-pace-val { font-weight: 700; color: var(--accent); min-width: 20px; }
.sf-mod-card {
    background: var(--surface); border: 1px solid var(--border);
    border-left: 3px solid transparent;
    border-radius: 0 8px 8px 0; padding: 12px 16px;
    margin-bottom: 7px; transition: border-color 0.12s;
    display: grid; grid-template-columns: 22px 1fr auto; gap: 12px; align-items: start;
}
.sf-mod-card:hover { border-color: var(--border-med) !important; }
.sf-mod-card.critical { border-left-color: var(--red) !important; }
.sf-mod-card.advanced { border-left-color: #fb923c; }
.sf-mod-card.intermediate { border-left-color: var(--amber); }
.sf-mod-card.beginner { border-left-color: var(--accent); }
.sf-mod-card.done { opacity: 0.5; }
.sf-mod-num { font-size: 0.65rem; color: var(--text-3); font-weight: 700;
              padding-top: 2px; font-variant-numeric: tabular-nums; }
.sf-mod-title { font-size: 0.82rem; font-weight: 600; color: var(--text-1); }
.sf-mod-meta  { font-size: 0.68rem; color: var(--text-3); margin-top: 3px; }
.sf-mod-tags  { display: flex; gap: 5px; margin-top: 5px; flex-wrap: wrap; }
.sf-mod-tag   { font-size: 0.58rem; padding: 2px 7px; border-radius: 4px;
                background: var(--raised); color: var(--text-2);
                border: 1px solid var(--border); }
.sf-mod-reason { font-size: 0.71rem; color: var(--text-3); font-style: italic;
                 margin-top: 5px; line-height: 1.5; }
.sf-mod-hrs {
    font-size: 0.72rem; color: var(--text-2); white-space: nowrap;
    font-variant-numeric: tabular-nums;
}
.sf-course-link {
    background: rgba(45,212,191,0.04); border: 1px solid var(--accent-border);
    border-radius: 6px; padding: 6px 10px; margin-top: 6px;
    font-size: 0.7rem;
}
.sf-course-link a { color: var(--accent); text-decoration: none; font-weight: 600; }
.sf-course-link a:hover { text-decoration: underline; }
.sf-course-plat { font-size: 0.62rem; color: var(--text-3); margin-top: 1px; }

/* Checkbox override */
[data-testid="stCheckbox"] label { font-size: 0.78rem !important; color: var(--text-2) !important; }

/* ── ATS / AUDIT ── */
.sf-ats-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin-bottom: 20px; }
@media(max-width:600px){ .sf-ats-grid{ grid-template-columns: repeat(2,1fr); } }
.sf-ats-card { background: var(--surface); border: 1px solid var(--border);
               border-radius: 8px; padding: 14px 16px; text-align: center; }
.sf-ats-val  { font-size: 1.6rem; font-weight: 700; color: var(--text-1); line-height: 1; }
.sf-ats-lbl  { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em;
               text-transform: uppercase; color: var(--text-3); margin-top: 4px; }
.sf-progress { height: 4px; background: rgba(255,255,255,0.06);
               border-radius: 99px; overflow: hidden; margin-bottom: 20px; }
.sf-progress-fill { height: 100%; background: var(--accent); border-radius: 99px; transition: width 0.4s; }

.sf-tip { display: flex; gap: 10px; margin-bottom: 8px; font-size: 0.76rem;
          color: var(--text-2); line-height: 1.5; }
.sf-tip-num { font-size: 0.62rem; color: var(--accent);
              background: var(--accent-dim); border: 1px solid var(--accent-border);
              border-radius: 4px; padding: 1px 6px; font-weight: 700;
              min-width: 24px; text-align: center; flex-shrink: 0; height: fit-content; }
.sf-kw-pill { display: inline-block; font-size: 0.64rem; padding: 2px 9px;
              border-radius: 4px; margin: 3px;
              background: rgba(248,113,113,0.08); color: var(--red);
              border: 1px solid rgba(248,113,113,0.18); font-weight: 600; }
.sf-talking-pt { font-size: 0.76rem; color: var(--text-2); padding: 7px 0 7px 11px;
                 border-left: 2px solid var(--accent); margin-bottom: 6px; line-height: 1.5; }

/* ── WEB INTEL ── */
.sf-intel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
@media(max-width:700px){ .sf-intel-grid{ grid-template-columns:1fr; } }
.sf-intel-card { background: var(--surface); border: 1px solid var(--border);
                 border-radius: 10px; padding: 16px 18px; }
.sf-intel-hd { font-size: 0.78rem; font-weight: 600; color: var(--text-1); margin-bottom: 12px; }
.sf-insight { background: rgba(45,212,191,0.04); border-left: 2px solid var(--accent);
              border-radius: 0 5px 5px 0; padding: 7px 11px; margin-bottom: 5px;
              font-size: 0.74rem; color: var(--text-2); line-height: 1.5; }
.sf-trend-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; }
.sf-trend-card { background: var(--raised); border: 1px solid var(--border);
                 border-radius: 7px; padding: 9px 11px; text-align: center; }
.sf-trend-skill { font-size: 0.72rem; font-weight: 600; color: var(--text-1); }
.sf-trend-sig   { font-size: 0.66rem; margin-top: 3px; }

/* ── DIFF VIEW ── */
.sf-diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media(max-width:700px){ .sf-diff-grid{ grid-template-columns:1fr; } }
.sf-diff-pane { background: var(--surface); border: 1px solid var(--border);
                border-radius: 8px; padding: 14px; font-size: 0.72rem;
                color: var(--text-2); white-space: pre-wrap; line-height: 1.6;
                max-height: 320px; overflow-y: auto; }
.sf-diff-label { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em;
                 text-transform: uppercase; color: var(--text-3); margin-bottom: 8px; }

/* ── EXPORT ── */
.sf-export-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
@media(max-width:700px){ .sf-export-grid{ grid-template-columns:1fr; } }
.sf-export-card { background: var(--surface); border: 1px solid var(--border);
                  border-radius: 10px; padding: 18px; }
.sf-export-hd { font-size: 0.8rem; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.sf-export-sub { font-size: 0.68rem; color: var(--text-3); margin-bottom: 14px; }

/* Download button */
[data-testid="stDownloadButton"] > button {
    background: var(--raised) !important;
    border: 1px solid var(--border-med) !important;
    color: var(--text-1) !important; font-weight: 600 !important;
    font-size: 0.78rem !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: var(--accent-border) !important; color: var(--accent) !important;
}

/* Metrics */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 9px !important; padding: 12px 14px !important;
}
[data-testid="stMetricValue"] { font-size: 1.5rem !important; color: var(--accent) !important; }
[data-testid="stMetricLabel"] { color: var(--text-3) !important; font-size: 0.58rem !important;
                                 text-transform: uppercase !important; letter-spacing: 0.08em !important; }

/* Slider */
[data-testid="stSlider"] .st-ae { background: var(--accent) !important; }

/* Select */
[data-testid="stSelectbox"] > div > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important; color: var(--text-1) !important;
}

/* Expander */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important; margin-bottom: 5px !important;
}
[data-testid="stExpander"] summary { color: var(--text-1) !important; font-size: 0.8rem !important; }

/* Progress */
[data-testid="stProgressBar"] > div > div { background: var(--accent) !important; }
[data-testid="stProgressBar"] > div { background: rgba(255,255,255,0.05) !important; border-radius: 99px !important; }

/* Tab content padding */
[data-testid="stAppViewContainer"] > section { padding-bottom: 48px !important; }

/* Mobile */
@media(max-width:640px) {
    .sf-page     { padding: 0 16px 80px; }
    .sf-topbar   { padding: 0 16px; }
    .sf-hero-card{ grid-template-columns: 1fr; text-align: center; }
    .sf-kpi-grid { grid-template-columns: 1fr 1fr; }
    .sf-topbar-tags { display: none; }
}

/* API log */
.sf-log-row { display: flex; gap: 10px; flex-wrap: wrap; font-size: 0.65rem;
              color: var(--text-3); padding: 5px 8px;
              background: var(--surface); border: 1px solid var(--border);
              border-radius: 5px; margin-bottom: 4px;
              font-family: "SF Mono","Fira Code",monospace; }
.sf-log-ok  { color: var(--green); }
.sf-log-err { color: var(--red); }

/* Status footer */
.sf-footer {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: rgba(12,14,20,0.97); border-top: 1px solid var(--border);
    padding: 5px 32px; font-size: 0.62rem; color: var(--text-3);
    display: flex; align-items: center; gap: 16px; z-index: 99;
}
.sf-footer-dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.sf-footer .ml { margin-left: auto; font-variant-numeric: tabular-nums; }
</style>
"""

# =============================================================================
#  SESSION STATE INIT
# =============================================================================
def _init_state():
    defaults = {
        "step":             1,       # 1, 2, "analyzing", "results"
        "resume_text":      "",
        "resume_image":     None,
        "jd_text":          "",
        "result":           None,
        "completed_modules":set(),
        "hpd":              2,
        "rw_result":        None,
        "course_cache":     {},
        "sal_location":     "India",
        "load_step":        0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# =============================================================================
#  TOPBAR
# =============================================================================
def render_topbar(show_reset=False):
    cost  = sum(e.get("cost",0) for e in _audit_log)
    calls = len(_audit_log)
    sem_status = "Semantic ✓" if SEMANTIC else "Semantic …"
    st.markdown(f"""
    <div class="sf-topbar">
      <div class="sf-brand">Skill<em>Forge</em></div>
      <div class="sf-topbar-tags">
        <span class="sf-chip">Groq LLaMA 4-Scout</span>
        <span class="sf-chip">NetworkX DAG</span>
        <span class="sf-chip">{sem_status}</span>
        <span class="sf-chip">{calls} calls · ${cost:.4f}</span>
      </div>
    </div>""", unsafe_allow_html=True)
    if show_reset:
        _, cr = st.columns([10,1])
        with cr:
            if st.button("↩ Reset", key="reset_btn"):
                for k in ["step","resume_text","resume_image","jd_text","result",
                          "completed_modules","rw_result","course_cache"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

# =============================================================================
#  STEP INDICATOR
# =============================================================================
def render_steps(current: int):
    steps = ["Resume", "Job description", "Results"]
    items = ""
    for i, label in enumerate(steps, 1):
        cls = "done" if i < current else ("active" if i == current else "")
        icon = "✓" if i < current else str(i)
        items += f'<div class="sf-step {cls}"><div class="sf-step-dot">{icon}</div>{label}</div>'
        if i < len(steps):
            line_cls = "done" if i < current else ""
            items += f'<div class="sf-step-line {line_cls}"></div>'
    st.markdown(f'<div class="sf-steps">{items}</div>', unsafe_allow_html=True)

# =============================================================================
#  ENTRY — STEP 1: RESUME
# =============================================================================
def render_step1():
    render_steps(1)

    st.markdown("""
    <div style="text-align:center; padding: 8px 0 28px;">
      <div class="sf-entry-title">How close are you to <em>this role?</em></div>
      <div class="sf-entry-sub">Upload your resume and a job description — get a dependency-aware, personalized learning roadmap in seconds.</div>
    </div>""", unsafe_allow_html=True)

    # Persona cards (one-click auto-run)
    st.markdown('<div style="max-width:640px;margin:0 auto 28px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.65rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-3);margin-bottom:10px;">Try a preset scenario</div>', unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    for col, key in zip([p1,p2,p3], SAMPLES):
        s = SAMPLES[key]
        with col:
            st.markdown(f"""
            <div class="sf-persona">
              <div class="sf-persona-label">{s['label']}</div>
              <div class="sf-persona-role">{s['role']}</div>
              <div class="sf-persona-stats">
                <div class="sf-persona-stat">Fit <span>{s['fit']}</span></div>
                <div class="sf-persona-stat">· <span>{s['hrs']}</span> training</div>
              </div>
            </div>""", unsafe_allow_html=True)
            if st.button(f"Load →", key=f"persona_{key}", use_container_width=True):
                st.session_state["resume_text"] = s["resume"]
                st.session_state["jd_text"]     = s["jd"]
                st.session_state["step"]        = "analyzing"
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Upload area
    st.markdown('<div style="max-width:620px;margin:0 auto;">', unsafe_allow_html=True)
    st.markdown('<div class="sf-input-card highlight">'
                '<div class="sf-input-hd">Your resume <span class="sf-input-hd-badge">Step 1 of 2</span></div>',
                unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Upload file", "Paste text"])
    with tab1:
        f = st.file_uploader("resume_file", type=["pdf","docx","jpg","jpeg","png","webp"],
                             key="res_file_up", label_visibility="collapsed")
        if f:
            txt, img = parse_uploaded_file(f)
            st.session_state["resume_text"]  = txt
            st.session_state["resume_image"] = img
            st.success(f"✓ {f.name} uploaded — {len(txt.split())} words extracted")
    with tab2:
        pasted = st.text_area("", height=130, placeholder="Paste your resume text here…",
                              key="res_paste_area", label_visibility="collapsed",
                              value=st.session_state.get("resume_text",""))
        if pasted: st.session_state["resume_text"] = pasted

    st.markdown('<div class="sf-input-tip">PDF · DOCX · Image · plain text</div></div>',
                unsafe_allow_html=True)

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    has_resume = bool(st.session_state.get("resume_text") or st.session_state.get("resume_image"))

    if has_resume:
        if st.button("Continue to Job Description →", key="to_step2", use_container_width=True):
            st.session_state["step"] = 2
            st.rerun()
    else:
        st.markdown('<div style="text-align:center;font-size:0.72rem;color:var(--text-3);padding:8px 0">Upload or paste your resume to continue</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  ENTRY — STEP 2: JOB DESCRIPTION
# =============================================================================
def render_step2():
    render_steps(2)

    # Resume preview strip
    preview = (st.session_state.get("resume_text","")[:120] or "Image resume uploaded").strip()
    st.markdown(f"""
    <div style="background:rgba(45,212,191,0.05);border:1px solid var(--accent-border);
                border-radius:8px;padding:10px 16px;margin-bottom:20px;
                font-size:0.74rem;color:var(--text-2);display:flex;align-items:center;gap:10px;
                max-width:620px;margin-left:auto;margin-right:auto;">
      <span style="color:var(--accent);font-size:0.9rem">✓</span>
      <span>Resume loaded — <em style="color:var(--text-1)">{preview}…</em></span>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div style="max-width:620px;margin:0 auto;">', unsafe_allow_html=True)
    st.markdown('<div class="sf-input-card highlight">'
                '<div class="sf-input-hd">Job description <span class="sf-input-hd-badge">Step 2 of 2</span></div>',
                unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Upload file", "Paste text"])
    with tab1:
        f = st.file_uploader("jd_file", type=["pdf","docx"],
                             key="jd_file_up", label_visibility="collapsed")
        if f:
            txt, _ = parse_uploaded_file(f)
            st.session_state["jd_text"] = txt
            st.success(f"✓ {f.name} uploaded")
    with tab2:
        pasted = st.text_area("", height=150, placeholder="Paste job description here…",
                              key="jd_paste_area", label_visibility="collapsed",
                              value=st.session_state.get("jd_text",""))
        if pasted: st.session_state["jd_text"] = pasted

    st.markdown('<div class="sf-input-tip">PDF · DOCX · plain text</div></div>',
                unsafe_allow_html=True)

    has_jd = bool(st.session_state.get("jd_text","").strip())

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1,3])
    with c1:
        st.markdown('<div class="sf-btn-ghost">', unsafe_allow_html=True)
        if st.button("← Back", key="back_btn", use_container_width=True):
            st.session_state["step"] = 1; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        if has_jd:
            if st.button("Analyze Skill Gap ⚡", key="analyze_btn", use_container_width=True):
                st.session_state["step"] = "analyzing"; st.rerun()
        else:
            st.markdown('<div style="text-align:center;font-size:0.72rem;color:var(--text-3);padding:10px 0">Paste or upload a JD to analyze</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  LOADING — STAGED STEPS
# =============================================================================
LOAD_STEPS = [
    ("Parsing resume & job description…",     "→ Extracting text and structure"),
    ("Identifying skills & proficiency…",      "→ LLM structured extraction"),
    ("Running gap analysis…",                  "→ Semantic skill matching"),
    ("Building dependency roadmap…",           "→ NetworkX topological sort"),
    ("Fetching live web intelligence…",        "→ Salary · trends · market data"),
]

def render_loading():
    render_steps(3)
    st.markdown('<div class="sf-loading-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="sf-loading-title">Analyzing your profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-loading-sub">This takes 10–20 seconds. Groq LLaMA 4-Scout + NetworkX DAG.</div>', unsafe_allow_html=True)

    placeholders = []
    st.markdown('<div class="sf-load-steps">', unsafe_allow_html=True)
    for i, (label, sub) in enumerate(LOAD_STEPS):
        ph = st.empty()
        placeholders.append((ph, i, label, sub))
        ph.markdown(f'<div class="sf-load-step"><span class="sf-load-icon">○</span>{label}</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    # Animate first step
    placeholders[0][0].markdown(
        f'<div class="sf-load-step active"><span class="sf-load-icon">⟳</span>{LOAD_STEPS[0][0]}</div>',
        unsafe_allow_html=True)

    # Run analysis
    with st.spinner(""):
        result = run_analysis_with_web(
            st.session_state.get("resume_text",""),
            st.session_state.get("jd_text",""),
            resume_image_b64=st.session_state.get("resume_image"),
            location=st.session_state.get("sal_location","India"),
        )

    if "error" in result:
        if result.get("error") == "rate_limited":
            st.error(f"⏳ Rate limited — {result.get('message','')}")
            st.info("Groq free tier has per-minute limits. Wait the indicated time and re-run.")
        else:
            st.error(f"Analysis failed: `{result.get('error','unknown')}`")
        st.session_state["step"] = 2
        if st.button("← Try again"): st.rerun()
        return

    # Mark all steps done
    for ph, i, label, sub in placeholders:
        ph.markdown(f'<div class="sf-load-step done"><span class="sf-load-icon">✓</span>{label}</div>', unsafe_allow_html=True)

    st.session_state["result"] = result
    st.session_state["step"]   = "results"
    time.sleep(0.4)
    st.rerun()

# =============================================================================
#  SIDEBAR NAVIGATION
# =============================================================================
def render_sidebar(im, iv, sm):
    with st.sidebar:
        st.markdown("""
        <div class="sf-sidenav">
          <div class="sf-sidenav-title">Sections</div>
        </div>""", unsafe_allow_html=True)

        sections = [
            ("score",    "#2dd4bf", "Score overview"),
            ("skills",   "#fbbf24", "Skill gap"),
            ("roadmap",  "#f87171", "Learning roadmap"),
            ("ats",      "#818cf8", "ATS audit"),
            ("intel",    "#34d399", "Web intelligence"),
            ("export",   "#8892a4", "Export"),
        ]
        for anchor, color, label in sections:
            st.markdown(f"""
            <a href="#{anchor}" class="sf-nav-item">
              <div class="sf-nav-dot" style="background:{color}"></div>
              {label}
            </a>""", unsafe_allow_html=True)

        st.markdown('<div class="sf-nav-divider"></div>', unsafe_allow_html=True)

        # Quick stats
        st.markdown(f"""
        <div class="sf-nav-meta">
          <div class="sf-nav-stat">Fit delta <span>+{im.get('fit_delta',0)}%</span></div>
          <div class="sf-nav-stat">Modules <span>{im.get('modules_count',0)}</span></div>
          <div class="sf-nav-stat">Training hrs <span>{im.get('roadmap_hours',0)}h</span></div>
          <div class="sf-nav-stat">Interview <span>{iv.get('score',0)}% {iv.get('label','')}</span></div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="sf-nav-divider"></div>', unsafe_allow_html=True)

        if sm.get("has_mismatch"):
            st.markdown(f"""
            <div style="padding:8px 10px;background:rgba(251,191,36,0.06);
                        border:1px solid rgba(251,191,36,0.2);border-radius:7px;
                        font-size:0.7rem;color:#fbbf24;margin:0 12px 10px;">
              ⚠ Seniority gap: {sm['candidate']} → {sm['required']}<br>
              <span style="color:#4a5568">Leadership modules added</span>
            </div>""", unsafe_allow_html=True)

        if st.button("↩ Start over", key="sidebar_reset", use_container_width=True):
            for k in ["step","resume_text","resume_image","jd_text","result",
                      "completed_modules","rw_result","course_cache"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()

# =============================================================================
#  SECTION: SCORE HERO
# =============================================================================
def render_score_hero(res):
    c = res["candidate"]; jd = res["jd"]
    im = res["impact"];   iv = res["interview"]
    sal = res.get("salary",{})

    st.markdown('<div id="score"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-hero-section">', unsafe_allow_html=True)

    col_score, col_kpis, col_sal = st.columns([1,1.4,1])

    with col_score:
        cur  = im["current_fit"]
        proj = im["projected_fit"]
        delta= im["fit_delta"]
        iv_color = iv.get("color","#4ade80")
        st.markdown(f"""
        <div style="background:var(--surface);border:1px solid var(--border);
                    border-radius:14px;padding:24px 20px;text-align:center;">
          <div class="sf-fit-label">Role fit</div>
          <div class="sf-fit-num">{cur}%</div>
          <div class="sf-fit-arrow">→ <em>+{delta}%</em> after roadmap</div>
          <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border);">
            <div style="font-size:1.4rem;font-weight:700;color:{iv_color}">{iv['score']}%</div>
            <div style="font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;
                        color:var(--text-3);margin-top:2px;">Interview ready</div>
            <div style="font-size:0.68rem;color:var(--text-2);margin-top:3px;">{iv.get('advice','')}</div>
          </div>
        </div>""", unsafe_allow_html=True)

    with col_kpis:
        km1, km2 = st.columns(2)
        km1.metric("Training hours",   f"{im['roadmap_hours']}h",      f"saves ~{im['hours_saved']}h")
        km2.metric("Projected fit",    f"{proj}%",                     f"+{delta}%")
        km3, km4 = st.columns(2)
        km3.metric("Modules",          im["modules_count"],             f"{im['critical_count']} critical")
        km4.metric("Ready in",         weeks_ready(im["roadmap_hours"], st.session_state.get("hpd",2)))
        if im.get("decayed_skills",0):
            st.markdown(f'<div style="font-size:0.7rem;color:#fbbf24;margin-top:6px;">⏱ {im["decayed_skills"]} skill(s) with proficiency decay detected</div>', unsafe_allow_html=True)

    with col_sal:
        if sal and sal.get("median_lpa",0):
            curr = sal.get("currency","INR")
            sym  = "₹" if curr=="INR" else "$"
            unit = "L/yr" if curr=="INR" else "k/yr"
            st.markdown(f"""
            <div style="background:var(--surface);border:1px solid var(--border);
                        border-radius:14px;padding:20px;height:100%;min-height:140px;">
              <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.08em;
                          text-transform:uppercase;color:var(--text-3);margin-bottom:8px;">Live salary — {jd.get('role_title','')[:18]}</div>
              <div style="font-size:2rem;font-weight:800;color:var(--accent);line-height:1;">
                {sym}{sal.get('median_lpa',0)}<span style="font-size:0.8rem;color:var(--text-2);font-weight:400"> {unit}</span>
              </div>
              <div style="font-size:0.7rem;color:var(--text-3);margin-top:4px;">
                {sym}{sal.get('min_lpa',0)} – {sym}{sal.get('max_lpa',0)} {unit}
              </div>
              <div style="font-size:0.62rem;color:var(--text-3);margin-top:6px;">
                Source: {sal.get('source','web')}
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:var(--surface);border:1px solid var(--border);
                        border-radius:14px;padding:20px;">
              <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.08em;
                          text-transform:uppercase;color:var(--text-3);margin-bottom:10px;">Candidate</div>
              <div style="font-size:0.88rem;font-weight:600;color:var(--text-1)">{c.get('name','Unknown')}</div>
              <div style="font-size:0.74rem;color:var(--text-2);margin-top:2px">{c.get('current_role','')}</div>
              <div style="font-size:0.7rem;color:var(--text-3);margin-top:8px">{c.get('seniority','')} · {c.get('years_experience',0)} yrs · {c.get('domain','')}</div>
              <div style="font-size:0.68rem;color:var(--text-3);margin-top:4px">{(c.get('education','') or '')[:42]}</div>
            </div>""", unsafe_allow_html=True)

    if res.get("_cache_hit"):
        st.markdown('<div style="font-size:0.7rem;color:var(--text-3);text-align:right;margin-top:6px;">⚡ Cached result — 0 API calls used</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  SECTION: SKILL GAP
# =============================================================================
def render_skill_gap(res):
    gp     = res["gap_profile"]
    trends = res.get("skill_trends", {})

    st.markdown('<div id="skills"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-hd">Skill gap analysis</div>', unsafe_allow_html=True)

    k_c = sum(1 for g in gp if g["status"]=="Known")
    p_c = sum(1 for g in gp if g["status"]=="Partial")
    m_c = sum(1 for g in gp if g["status"]=="Missing")
    st.markdown(f'<div class="sf-section-sub">{k_c} known · {p_c} partial · {m_c} missing — click any row to expand detail</div>', unsafe_allow_html=True)

    left, right = st.columns([1, 1.1], gap="large")

    with left:
        st.plotly_chart(radar_chart(gp), use_container_width=True, config={"displayModeBar":False})

        # Transfer map
        tf = res.get("transfers",[])
        if tf:
            st.markdown('<div style="font-size:0.74rem;font-weight:600;color:var(--text-1);margin:12px 0 6px;">Transfer advantages</div>', unsafe_allow_html=True)
            for t in tf[:4]:
                st.markdown(f'<div style="font-size:0.72rem;color:var(--text-2);padding:5px 0 5px 10px;border-left:2px solid #818cf8;margin-bottom:4px;">↗ {t["label"]}</div>', unsafe_allow_html=True)

    with right:
        # Filter bar
        filt = st.selectbox("Filter", ["All","Missing","Partial","Known","Required only"],
                            key="skill_filter", label_visibility="collapsed")

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
            col_map  = {"Known":_ACCENT,"Partial":_AMBER,"Missing":_RED}
            badge_cls= {"Known":"sf-badge-known","Partial":"sf-badge-partial","Missing":"sf-badge-missing"}
            bar_col  = col_map[status]
            pct      = g["proficiency"]/10*100
            dmnd     = {"🔥":"Hot","📈":"Growing","✓":"Stable"}.get(
                       {3:"🔥",2:"📈",1:"✓"}.get(g.get("demand",1),"✓"),"")
            trend    = trends.get(g["skill"],"")
            trend_col= (_RED if "Hot" in trend else _AMBER if "Growing" in trend else "var(--text-3)")
            decay_icon = " ⏱" if g.get("decayed") else ""
            obs_icon   = " ⚠" if g.get("obsolescence_risk") else ""

            exp_key = f"exp_{g['skill'].replace(' ','_')}"
            is_exp  = st.session_state["expanded_skills"].__contains__(g["skill"])
            cls     = "expanded" if is_exp else ""

            if st.toggle(f"**{g['skill']}{decay_icon}{obs_icon}** — {g['proficiency']}/10  [{status}]",
                         key=exp_key, value=is_exp, label_visibility="collapsed"):
                st.session_state["expanded_skills"].add(g["skill"])
            else:
                st.session_state["expanded_skills"].discard(g["skill"])

            detail_html = ""
            if is_exp:
                co = g.get("catalog_course")
                detail_html = f"""
                <div class="sf-skill-detail">
                  {'<div class="sf-skill-ctx">Context: '+g['context']+'</div>' if g.get('context') else ''}
                  {'<div class="sf-decay-note">⏱ Decayed from '+str(g['original_prof'])+'/10 (unused '+str(CURRENT_YEAR - g.get('proficiency',0))+' yr+)</div>' if g.get('decayed') else ''}
                  {'<div class="sf-obs-note">⚠ Obsolescence: '+g['obsolescence_risk']+'</div>' if g.get('obsolescence_risk') else ''}
                  {'<div>Catalog course: <strong>'+co['title']+'</strong> ('+str(co['duration_hrs'])+'h · '+co['level']+')</div>' if co else '<div>No catalog match</div>'}
                  <div>Demand: <span style="color:{trend_col}">{trend or '—'}</span></div>
                </div>"""

            st.markdown(f"""
            <div class="sf-skill-item {cls}">
              <div class="sf-skill-row">
                <div class="sf-skill-name">{g['skill']}{decay_icon}{obs_icon}</div>
                <div class="sf-skill-bar"><div class="sf-skill-fill" style="width:{pct}%;background:{bar_col}"></div></div>
                <div class="sf-skill-val">{g['proficiency']}/10</div>
                <span class="sf-badge {badge_cls[status]}">{status}</span>
                {'<span class="sf-badge-demand" style="color:'+trend_col+'">'+trend+'</span>' if trend else ''}
              </div>
              {detail_html}
            </div>""", unsafe_allow_html=True)

    # Obsolescence risks
    obs = res.get("obsolescence",[])
    if obs:
        st.markdown('<div style="margin-top:16px">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.76rem;font-weight:600;color:var(--text-1);margin-bottom:8px;">Obsolescence risks</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(obs),3))
        for i, o in enumerate(obs):
            cols[i%3].markdown(f'<div style="background:rgba(248,113,113,0.05);border:1px solid rgba(248,113,113,0.15);border-radius:7px;padding:9px 12px;font-size:0.72rem;"><div style="color:var(--red);font-weight:600">{o["skill"]}</div><div style="color:var(--text-3);margin-top:3px;">{o["reason"]}</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  SECTION: ROADMAP
# =============================================================================
def render_roadmap(res):
    path = res["path"]
    gp   = res["gap_profile"]
    completed = st.session_state.get("completed_modules", set())

    st.markdown('<div id="roadmap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

    # Header with inline pace slider
    hd_l, hd_r = st.columns([2,1])
    with hd_l:
        st.markdown('<div class="sf-section-hd">Learning roadmap</div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-section-sub">Dependency-ordered · critical path · AI reasoning per module · check off as you complete</div>', unsafe_allow_html=True)
    with hd_r:
        hpd = st.select_slider("Pace",options=[1,2,4,8],value=st.session_state.get("hpd",2),key="hpd_slider",label_visibility="collapsed")
        st.session_state["hpd"] = hpd
        rhrs = sum(m["duration_hrs"] for m in path if m["id"] not in completed)
        st.markdown(f'<div style="font-size:0.72rem;color:var(--text-2);text-align:right;">{hpd}h/day · done in <strong style="color:var(--accent)">{weeks_ready(rhrs,hpd)}</strong> · {rhrs}h remaining</div>', unsafe_allow_html=True)

    left, right = st.columns([1.1, 1], gap="large")

    with left:
        for i, m in enumerate(path):
            is_done = m["id"] in completed
            is_crit = m.get("is_critical",False)
            level   = m["level"]
            level_cls = ("critical" if is_crit else
                         "advanced" if level=="Advanced" else
                         "intermediate" if level=="Intermediate" else "beginner")
            done_cls  = " done" if is_done else ""

            # Checkbox
            checked = st.checkbox(
                f"#{i+1} {m['title']}",
                value=is_done,
                key=f"chk_{m['id']}",
            )
            if checked: completed.add(m["id"])
            else:        completed.discard(m["id"])
            st.session_state["completed_modules"] = completed

            prereqs_str = ", ".join(m.get("prereqs",[]) or []) or "None"
            tags_html = ""
            if is_crit: tags_html += '<span class="sf-mod-tag" style="color:var(--red);border-color:rgba(248,113,113,0.3)">★ critical path</span>'
            if m.get("is_required"): tags_html += '<span class="sf-mod-tag" style="color:var(--accent)">required</span>'
            tags_html += f'<span class="sf-mod-tag">{m["domain"]}</span>'
            tags_html += f'<span class="sf-mod-tag">{level}</span>'

            # Inline course links
            course_html = ""
            cache_key = f"courses_{m['skill'].replace(' ','_')}"
            courses = st.session_state.get("course_cache",{}).get(m["skill"],[])
            if courses:
                for crs in courses[:2]:
                    course_html += f'<div class="sf-course-link">{crs["icon"]} <a href="{crs["url"]}" target="_blank">{crs["title"][:55]}</a><div class="sf-course-plat">{crs["platform"]}</div></div>'

            st.markdown(f"""
            <div class="sf-mod-card {level_cls}{done_cls}">
              <div class="sf-mod-num">{'✓' if is_done else f'#{i+1:02d}'}</div>
              <div>
                <div class="sf-mod-title">{'~~' if is_done else ''}{m['title']}{'~~' if is_done else ''}</div>
                <div class="sf-mod-meta">Skill: {m['skill']} · Prereqs: {prereqs_str}</div>
                <div class="sf-mod-tags">{tags_html}</div>
                {'<div class="sf-mod-reason">'+m["reasoning"]+'</div>' if m.get("reasoning") else ""}
                {course_html}
              </div>
              <div class="sf-mod-hrs">{m['duration_hrs']}h</div>
            </div>""", unsafe_allow_html=True)

    with right:
        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">ROI ranking</div>', unsafe_allow_html=True)
        st.plotly_chart(roi_chart(res.get("roi",[])), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin:16px 0 10px;">Priority matrix</div>', unsafe_allow_html=True)
        st.plotly_chart(priority_matrix(gp), use_container_width=True, config={"displayModeBar":False})

    # Timeline
    st.markdown('<div style="margin-top:20px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">Training timeline</div>', unsafe_allow_html=True)
    st.plotly_chart(timeline_chart(path), use_container_width=True, config={"displayModeBar":False})

    # Weekly plan
    st.markdown('<div style="margin-top:16px;"><div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">Weekly study plan</div>', unsafe_allow_html=True)
    wp = weekly_plan([m for m in path if m["id"] not in completed], hpd)
    for w in wp[:6]:
        with st.expander(f"Week {w['week']} — {w['total_hrs']:.1f}h"):
            for mx in w["modules"]:
                crit = "★ " if mx.get("is_critical") else ""
                st.markdown(f"- {crit}**{mx['title']}** &nbsp; {mx['hrs_this_week']:.1f}h / {mx['total_hrs']}h")
    st.markdown("</div>", unsafe_allow_html=True)

    # Lazy-load course links for all modules
    if not st.session_state.get("course_cache"):
        if st.button("Load course links for all modules", key="load_courses_btn"):
            cache = {}
            gap_skills = list({m["skill"] for m in path})[:8]
            with st.spinner("Searching Coursera, Udemy, YouTube…"):
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futures = {ex.submit(search_course_links, s): s for s in gap_skills}
                    for fut in futures:
                        cache[futures[fut]] = fut.result()
            st.session_state["course_cache"] = cache
            st.rerun()

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
    st.markdown('<div class="sf-section-hd">ATS audit & interview readiness</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Resume quality scores · improvement tips · interview talking points · ATS keyword gaps</div>', unsafe_allow_html=True)

    # Score cards
    st.markdown(f"""
    <div class="sf-ats-grid">
      <div class="sf-ats-card"><div class="sf-ats-val">{ql.get('ats_score','--')}%</div><div class="sf-ats-lbl">ATS Score</div></div>
      <div class="sf-ats-card"><div class="sf-ats-val" style="color:var(--accent)">{ql.get('overall_grade','--')}</div><div class="sf-ats-lbl">Grade</div></div>
      <div class="sf-ats-card"><div class="sf-ats-val">{ql.get('completeness_score','--')}%</div><div class="sf-ats-lbl">Completeness</div></div>
      <div class="sf-ats-card"><div class="sf-ats-val">{ql.get('clarity_score','--')}%</div><div class="sf-ats-lbl">Clarity</div></div>
    </div>""", unsafe_allow_html=True)

    ats_pct = ql.get("ats_score",0)
    st.markdown(f'<div class="sf-progress"><div class="sf-progress-fill" style="width:{ats_pct}%"></div></div>', unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">Improvement tips</div>', unsafe_allow_html=True)
        for i, tip in enumerate((ql.get("improvement_tips") or [])[:6]):
            st.markdown(f'<div class="sf-tip"><span class="sf-tip-num">0{i+1}</span><span>{tip}</span></div>', unsafe_allow_html=True)

        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin:16px 0 10px;">Interview talking points</div>', unsafe_allow_html=True)
        for p in (ql.get("interview_talking_points") or [])[:4]:
            st.markdown(f'<div class="sf-talking-pt">→ {p}</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">ATS issues</div>', unsafe_allow_html=True)
        for iss in (ql.get("ats_issues") or ["No critical issues detected"])[:5]:
            st.warning(iss)

        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin:12px 0 8px;">Missing keywords</div>', unsafe_allow_html=True)
        kws = ql.get("missing_keywords") or []
        pills = "".join(f'<span class="sf-kw-pill">{k}</span>' for k in kws) or "None identified"
        st.markdown(f'<div style="line-height:2.2">{pills}</div>', unsafe_allow_html=True)

        st.markdown('<div style="margin-top:16px;">', unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        a1.metric("Interview ready", f"{iv.get('score',0)}%", iv.get("label","--"))
        a2.metric("Seniority gap",   f"{sm.get('gap_levels',0)} lvl")
        a3.metric("Career time est", f"~{cgm}mo")
        st.markdown(f'<div style="font-size:0.7rem;color:var(--text-2);margin-top:6px;">Known: <strong>{iv.get("req_known",0)}</strong> · Partial: <strong>{iv.get("req_partial",0)}</strong> · Missing: <strong>{iv.get("req_missing",0)}</strong></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Resume rewrite / diff
    st.markdown('<div style="margin-top:24px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.82rem;font-weight:600;color:var(--text-1);margin-bottom:6px;">AI resume rewrite — side-by-side diff</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.7rem;color:var(--text-3);margin-bottom:12px;">ATS-optimized rewrite with missing keywords injected naturally</div>', unsafe_allow_html=True)

    rtxt = st.session_state.get("resume_text","")
    if not rtxt:
        st.info("Resume text unavailable for image-only uploads.")
    else:
        if st.button("Generate rewrite →", key="rw_btn"):
            with st.spinner("Rewriting with LLaMA 4-Scout…"):
                rw = rewrite_resume(rtxt, res["jd"], kws)
            st.session_state["rw_result"] = rw

        rw = st.session_state.get("rw_result")
        if rw:
            d1, d2 = st.columns(2)
            with d1:
                st.markdown('<div class="sf-diff-label">Original</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff-pane">{rtxt[:1200]}</div>', unsafe_allow_html=True)
            with d2:
                st.markdown('<div class="sf-diff-label">Rewritten (ATS-optimized)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="sf-diff-pane">{rw[:1200]}</div>', unsafe_allow_html=True)
            st.download_button("⬇ Download rewritten resume", data=rw,
                               file_name="skillforge_rewritten_resume.txt",
                               mime="text/plain")
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  SECTION: WEB INTELLIGENCE
# =============================================================================
def render_web_intel(res):
    sal     = res.get("salary",{})
    trends  = res.get("skill_trends",{})
    mkt     = res.get("market_insights",[])
    jd      = res["jd"]

    st.markdown('<div id="intel"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-hd">Live web intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Real-time salary data · market signals · skill demand — auto-fetched via DuckDuckGo + Groq</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown('<div class="sf-intel-card"><div class="sf-intel-hd">Salary data</div>', unsafe_allow_html=True)
        if sal and sal.get("median_lpa",0):
            st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar":False})
            st.caption(f"Source: {sal.get('source','web')} · {sal.get('note','')}")
        else:
            # Allow manual refresh
            loc = st.selectbox("Location", ["India","USA","UK","Germany","Canada","Singapore"], key="sal_loc_sel")
            if st.button("Fetch salary data", key="sal_refresh"):
                with st.spinner("Searching…"):
                    new_sal = search_real_salary(jd.get("role_title",""), loc)
                res["salary"] = new_sal
                st.session_state["result"]["salary"] = new_sal
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="sf-intel-card"><div class="sf-intel-hd">Job market insights</div>', unsafe_allow_html=True)
        if mkt:
            for ins in mkt:
                st.markdown(f'<div class="sf-insight">📌 {ins}</div>', unsafe_allow_html=True)
        else:
            if st.button("Fetch market insights", key="mkt_refresh"):
                with st.spinner("Searching…"):
                    new_mkt = search_job_market(jd.get("role_title",""))
                st.session_state["result"]["market_insights"] = new_mkt
                st.rerun()
            st.markdown('<div style="font-size:0.72rem;color:var(--text-3)">Not fetched yet — click above</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Skill demand signals
    if trends:
        st.markdown('<div style="margin-top:16px;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">Skill market signals</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(trends), 6))
        for i, (skill, sig) in enumerate(trends.items()):
            col = cols[i % 6]
            sig_col = (_RED if "Hot" in sig else _AMBER if "Growing" in sig else "var(--text-3)")
            col.markdown(f"""
            <div class="sf-trend-card">
              <div class="sf-trend-skill">{skill[:14]}</div>
              <div class="sf-trend-sig" style="color:{sig_col}">{sig}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Find courses for specific skill
    st.markdown('<div style="margin-top:20px;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.78rem;font-weight:600;color:var(--text-1);margin-bottom:10px;">Find real courses online</div>', unsafe_allow_html=True)
    gap_skills = [g["skill"] for g in res["gap_profile"] if g["status"]!="Known"]
    if gap_skills:
        sel_skill = st.selectbox("Pick a skill to search courses for:", gap_skills, key="course_sel")
        if st.button(f"Search courses for {sel_skill}", key="course_search"):
            with st.spinner(f"Searching Coursera · Udemy · YouTube for {sel_skill}…"):
                courses = search_course_links(sel_skill)
            cc = st.session_state.get("course_cache",{})
            cc[sel_skill] = courses
            st.session_state["course_cache"] = cc
        courses = st.session_state.get("course_cache",{}).get(sel_skill,[])
        for crs in courses:
            st.markdown(f'<div class="sf-course-link">{crs["icon"]} <a href="{crs["url"]}" target="_blank">{crs["title"]}</a><div class="sf-course-plat">{crs["platform"]} · {crs["snippet"]}</div></div>', unsafe_allow_html=True)
        if not courses and sel_skill in st.session_state.get("course_cache",{}):
            st.warning("No courses found — try a different skill.")
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  SECTION: EXPORT
# =============================================================================
def render_export(res):
    c    = res["candidate"]; jd = res["jd"]
    gp   = res["gap_profile"]; pt = res["path"]
    im   = res["impact"];     ql = res.get("quality",{})
    iv   = res.get("interview",{})

    st.markdown('<div id="export"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-hd">Export</div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-sub">Download your roadmap as PDF · JSON · CSV</div>', unsafe_allow_html=True)

    e1, e2, e3 = st.columns(3, gap="medium")

    with e1:
        st.markdown('<div class="sf-export-card"><div class="sf-export-hd">PDF report</div><div class="sf-export-sub">Full roadmap with AI reasoning traces and ATS audit</div>', unsafe_allow_html=True)
        for k, v in [("Candidate",c.get("name","--")),("Role",jd.get("role_title","--")),
                     ("ATS score",f"{ql.get('ats_score','--')}%"),("Modules",im["modules_count"]),
                     ("Training",f"{im['roadmap_hours']}h")]:
            st.markdown(f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;padding:4px 0;border-bottom:1px solid var(--border);"><span style="color:var(--text-3)">{k}</span><span style="color:var(--text-1);font-weight:500">{v}</span></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        if REPORTLAB:
            pdf_buf = build_pdf(c, jd, gp, pt, im, ql, iv)
            nm = (c.get("name","candidate") or "candidate").replace(" ","_")
            st.download_button("⬇ Download PDF", data=pdf_buf,
                               file_name=f"skillforge_{nm}_{datetime.now().strftime('%Y%m%d')}.pdf",
                               mime="application/pdf", use_container_width=True)
        else:
            st.warning("`pip install reportlab` to enable PDF export")
        st.markdown("</div>", unsafe_allow_html=True)

    with e2:
        st.markdown('<div class="sf-export-card"><div class="sf-export-hd">JSON export</div><div class="sf-export-sub">Complete structured result for downstream tools and integrations</div>', unsafe_allow_html=True)
        export_data = {
            "candidate":   c, "jd": jd, "impact": im, "interview": iv,
            "gap_profile": [{k:v for k,v in g.items() if k!="catalog_course"} for g in gp],
            "roadmap":     [{"id":m["id"],"title":m["title"],"skill":m["skill"],
                             "level":m["level"],"duration_hrs":m["duration_hrs"],
                             "is_critical":m.get("is_critical",False),
                             "reasoning":m.get("reasoning","")} for m in pt],
            "generated_at":datetime.now().isoformat(),
        }
        json_str = json.dumps(export_data, indent=2, default=str)
        st.markdown('<div style="height:102px"></div>', unsafe_allow_html=True)
        st.download_button("⬇ Download JSON", data=json_str,
                           file_name=f"skillforge_{datetime.now().strftime('%Y%m%d')}.json",
                           mime="application/json", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with e3:
        st.markdown('<div class="sf-export-card"><div class="sf-export-hd">Gap CSV</div><div class="sf-export-sub">Skill gap table for spreadsheet analysis and HR reporting</div>', unsafe_allow_html=True)
        csv_rows = ["Skill,Status,Proficiency,Required,Demand,Decayed"]
        for g in gp:
            csv_rows.append(f'"{g["skill"]}",{g["status"]},{g["proficiency"]},{g["is_required"]},{g.get("demand",1)},{g.get("decayed",False)}')
        st.markdown('<div style="height:102px"></div>', unsafe_allow_html=True)
        st.download_button("⬇ Download CSV", data="\n".join(csv_rows),
                           file_name=f"skillforge_gap_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime="text/csv", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  API LOG
# =============================================================================
def render_api_log():
    st.markdown('<div style="margin-top:24px;">', unsafe_allow_html=True)
    with st.expander(f"API log — {len(_audit_log)} calls · ${sum(e.get('cost',0) for e in _audit_log):.5f}"):
        for e in reversed(_audit_log[-20:]):
            ok = e.get("status") == "ok"
            cls = "sf-log-ok" if ok else "sf-log-err"
            st.markdown(f'<div class="sf-log-row"><span class="{cls}">{"●" if ok else "✕"}</span><span style="color:#8892a4">{e.get("ts","")}</span><span style="color:{_ACCENT}">{e.get("model","")}</span><span>in:{e.get("in",0)} out:{e.get("out",0)}</span><span>{e.get("ms",0)}ms</span><span>${e.get("cost",0):.6f}</span><span class="{cls}">{e.get("status","")}</span></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  STATUS FOOTER
# =============================================================================
def render_footer():
    cost  = sum(e.get("cost",0) for e in _audit_log)
    calls = len(_audit_log)
    sem   = "✓ semantic" if SEMANTIC else "⟳ semantic loading"
    st.markdown(f"""
    <div class="sf-footer">
      <span><span class="sf-footer-dot" style="background:{_ACCENT}"></span>Groq</span>
      <span><span class="sf-footer-dot" style="background:{_ACCENT}"></span>NetworkX</span>
      <span><span class="sf-footer-dot" style="background:{'#4ade80' if SEMANTIC else '#fbbf24'}"></span>{sem}</span>
      <span><span class="sf-footer-dot" style="background:{_ACCENT}"></span>DDG search</span>
      <span class="ml">v7 · {calls} calls · ${cost:.5f}</span>
    </div>""", unsafe_allow_html=True)

# =============================================================================
#  RESULTS PAGE
# =============================================================================
def render_results_page():
    res = st.session_state.get("result")
    if not res: return

    im = res["impact"]; iv = res["interview"]; sm = res.get("seniority",{})

    render_sidebar(im, iv, sm)

    st.markdown('<div class="sf-page-wide">', unsafe_allow_html=True)

    render_score_hero(res)
    render_skill_gap(res)
    render_roadmap(res)
    render_ats(res)
    render_web_intel(res)
    render_export(res)
    render_api_log()

    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
#  MAIN
# =============================================================================
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    _init_state()

    step = st.session_state.get("step", 1)
    show_reset = (step == "results")

    render_topbar(show_reset=show_reset)

    if step == "results":
        render_results_page()
    else:
        st.markdown('<div class="sf-page">', unsafe_allow_html=True)
        if step == 1:
            render_step1()
        elif step == 2:
            render_step2()
        elif step == "analyzing":
            render_loading()
        st.markdown("</div>", unsafe_allow_html=True)

    render_footer()

# =============================================================================
#  CLI MODE
# =============================================================================
def cli_analyze(scenario_key):
    if scenario_key not in SAMPLES:
        print(f"Unknown scenario. Choose from: {list(SAMPLES.keys())}"); sys.exit(1)
    s = SAMPLES[scenario_key]
    print(f"\n  SkillForge v7 CLI  ·  {s['label']}\n  {'='*52}")
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
    parser = argparse.ArgumentParser(description="SkillForge v7")
    parser.add_argument("--analyze", metavar="SCENARIO",
                        help="junior_swe | senior_ds | hr_manager")
    args, _ = parser.parse_known_args()
    if args.analyze:
        cli_analyze(args.analyze)
    else:
        threading.Thread(target=_load_semantic_bg, daemon=True).start()
        main()