# =============================================================================
#  main.py — SkillForge v6  |  Streamlit Edition
#  REDESIGN: 1-click samples · always-visible inputs · web search · course links
#  Run: streamlit run main.py
# =============================================================================

import os, sys, json, io, re, time, hashlib, shelve, threading, argparse, base64
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="SkillForge — AI Onboarding Engine",
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

# ── Web search (DuckDuckGo — free, no API key) ────────────────────────────────
def ddg_search(query: str, max_results: int = 5) -> List[dict]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

# ── Semantic matching ─────────────────────────────────────────────────────────
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

# ── Groq ──────────────────────────────────────────────────────────────────────
_GROQ_KEY = os.getenv("GROQ_API_KEY", "")
if not _GROQ_KEY:
    st.error("**GROQ_API_KEY missing** — add it to `.env`\n\nGet a free key at [console.groq.com](https://console.groq.com)")
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
        "label":"👨‍💻 Junior SWE",
        "resume":"John Smith\nJunior Software Developer | 1 year experience\nSkills: Python (basic, 4/10), HTML/CSS, some JavaScript\nEducation: B.Tech Computer Science 2023\nProjects: Built a todo app using Flask. Familiar with Git basics.\nNo professional cloud or DevOps experience.",
        "jd":"Software Engineer Full Stack - Mid Level\nRequired: Python, React, FastAPI, Docker, SQL, REST APIs, AWS\nPreferred: Kubernetes, CI/CD\nSeniority: Mid | Domain: Tech",
    },
    "senior_ds": {
        "label":"🧪 Senior DS",
        "resume":"Priya Patel\nSenior Data Scientist | 7 years experience\nSkills: Python (expert, 9/10), Machine Learning (expert), Deep Learning (PyTorch, 8/10), SQL (advanced, 8/10), AWS SageMaker (7/10)\nLast used NLP: 2022. Last used MLOps: 2021.\nLed team of 5. Published 3 ML papers.",
        "jd":"Lead Data Scientist - AI Products\nRequired: Python, Machine Learning, Deep Learning, NLP, MLOps, SQL, AWS\nPreferred: GCP, Kubernetes, Leadership\nSeniority: Lead | Domain: Tech",
    },
    "hr_manager": {
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
        media = ("image/jpeg" if name.endswith((".jpg",".jpeg")) else "image/png" if name.endswith(".png") else "image/webp")
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
        content = [{"type":"image_url","image_url":{"url":image_b64}},{"type":"text","text":prompt}]
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
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),"model":model.split("/")[-1][:22],
                            "in":in_tok,"out":out_tok,"cached":cached_c,
                            "ms":round((time.time()-t0)*1000),"cost":cost,"status":"ok"})
        return json.loads(r.choices[0].message.content or "{}")
    except json.JSONDecodeError as e:
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),"model":model.split("/")[-1][:22],
                            "status":f"json_err","in":0,"out":0,"cached":0,"ms":0,"cost":0})
        return {"error":"json_parse_failed"}
    except Exception as e:
        err = str(e); wait_s = 0
        if "429" in err or "rate_limit" in err:
            m = re.search(r"try again in (\d+)m([\d.]+)s", err)
            if m: wait_s = int(m.group(1))*60+float(m.group(2))
            return {"error":"rate_limited","wait_seconds":int(wait_s),
                    "message":f"Rate limited. Retry in {int(wait_s//60)}m{int(wait_s%60)}s."}
        _audit_log.append({"ts":datetime.now().strftime("%H:%M:%S"),"model":model.split("/")[-1][:22],
                            "status":f"err:{err[:40]}","in":0,"out":0,"cached":0,"ms":0,"cost":0})
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
        f'Resume:\n{resume_text[:1500]}\n\nTarget: {jd.get("role_title","--")}  Required: {jd.get("required_skills",[])}',
        system="Expert resume writer. Return JSON only.", model=MODEL_FAST, max_tokens=1500,
    )
    return r.get("rewritten_resume","Could not rewrite resume.")

# =============================================================================
#  WEB SEARCH FEATURES (DuckDuckGo + Groq)
# =============================================================================
def search_real_salary(role: str, location: str) -> dict:
    """Live salary lookup: DDG search → Groq parse."""
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
    """Find real course URLs for a skill via DDG."""
    results = ddg_search(
        f'"{skill}" online course 2025 coursera OR udemy OR youtube', max_results=6
    )
    courses = []
    for r in results:
        url  = r.get('href','')
        body = r.get('body','')
        if not url: continue
        if 'coursera.org' in url:   plat, icon = 'Coursera', '🎓'
        elif 'udemy.com' in url:    plat, icon = 'Udemy',    '🎯'
        elif 'youtube.com' in url:  plat, icon = 'YouTube',  '▶️'
        elif 'edx.org' in url:      plat, icon = 'edX',      '📘'
        elif 'linkedin.com' in url: plat, icon = 'LinkedIn',  '💼'
        else:                        continue
        courses.append({"title":r.get('title','')[:65],"url":url,
                         "platform":plat,"icon":icon,"snippet":body[:100]})
    return courses[:4]

def search_skill_trends(skills: List[str]) -> Dict[str, str]:
    """Quick web-based demand signal per skill."""
    if not skills: return {}
    query = " ".join(skills[:6])
    results = ddg_search(f"most in-demand skills 2025 2026 hiring {query}", max_results=4)
    text = " ".join([r.get('body','') for r in results]).lower()
    out = {}
    for skill in skills:
        sl = skill.lower()
        count = text.count(sl)
        out[skill] = ("🔥 Hot" if count >= 3 else "📈 Growing" if count >= 1 else "✓ Stable")
    return out

def search_job_market(role: str) -> List[str]:
    """Get 3 quick job market insights for the target role."""
    results = ddg_search(f'"{role}" job market hiring trends 2025 2026', max_results=4)
    if not results: return []
    snippets = "\n".join([r.get('body','')[:300] for r in results[:4]])
    r = _groq_call(
        f'Based on these search results about "{role}" job market, give 3 short, specific insights.\n\n'
        f'{snippets}\n\nReturn JSON: {{"insights":["<insight1>","<insight2>","<insight3>"]}}',
        system="Job market analyst. Return JSON only.", model=MODEL_FAST, max_tokens=300,
    )
    return r.get("insights",[]) if "error" not in r else []

# =============================================================================
#  CACHE
# =============================================================================
_CACHE_PATH = "/tmp/skillforge_v6_st"
def _ckey(r: str, j: str) -> str: return hashlib.md5((r+"||"+j).encode()).hexdigest()
def cache_get(r,j):
    try:
        with shelve.open(_CACHE_PATH) as db: return db.get(_ckey(r,j))
    except: return None
def cache_set(r,j,v):
    try:
        with shelve.open(_CACHE_PATH) as db: db[_ckey(r,j)] = v
    except: pass

# =============================================================================
#  ANALYSIS ENGINE
# =============================================================================
def _match_skill(skill: str) -> int:
    sl = skill.lower().replace(".js","").replace(".ts","").replace("(","").replace(")","").strip()
    for i,cs in enumerate(CATALOG_SKILLS):
        if sl==cs or sl in cs or cs in sl: return i
    if SEMANTIC and _ST and _CEMBS is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            sims = cosine_similarity(_ST.encode([sl]),_CEMBS)[0]
            best = int(np.argmax(sims))
            if sims[best]>=0.52: return best
        except: pass
    tokens=set(sl.split()); best_s,best_i=0.0,-1
    for i,cs in enumerate(CATALOG_SKILLS):
        ov=len(tokens&set(cs.split()))/max(len(tokens),1)
        if ov>best_s: best_s,best_i=ov,i
    return best_i if best_s>=0.4 else -1

def skill_decay(p,yr):
    if yr<=0 or yr>=CURRENT_YEAR-1: return p,False
    yrs=CURRENT_YEAR-yr
    if yrs<=2: return p,False
    a=round(p*max(0.5,1-yrs/5)); return a,a<p

def analyze_gap(candidate,jd):
    rs={s["skill"].lower():s for s in candidate.get("skills",[])}
    all_s=[(s,True) for s in jd.get("required_skills",[])]+[(s,False) for s in jd.get("preferred_skills",[])]
    out=[]
    for skill,req in all_s:
        sl=skill.lower().replace(".js","").replace(".ts","").strip()
        status,prof,ctx,dec,orig="Missing",0,"",False,0
        src=rs.get(sl) or next((v for k,v in rs.items() if sl in k or k in sl),None)
        if src:
            raw_p=src.get("proficiency",0); prof,dec=skill_decay(raw_p,src.get("year_last_used",0))
            orig,ctx=raw_p,src.get("context",""); status="Known" if prof>=7 else "Partial"
        idx=_match_skill(skill)
        demand=MARKET_DEMAND.get(sl,MARKET_DEMAND.get(skill.lower(),1))
        obs=OBSOLESCENCE_RISK.get(sl)
        out.append({"skill":skill,"status":status,"proficiency":prof,"original_prof":orig,
                    "decayed":dec,"is_required":req,"context":ctx,
                    "catalog_course":CATALOG[idx] if idx>=0 else None,
                    "demand":demand,"obsolescence_risk":obs})
    return out

def seniority_check(c,jd):
    cs,rs=c.get("seniority","Mid"),jd.get("seniority_required","Mid")
    gap=SENIORITY_MAP.get(rs,1)-SENIORITY_MAP.get(cs,1)
    return {"has_mismatch":gap>0,"gap_levels":gap,"candidate":cs,"required":rs,
            "add_leadership":gap>=1,"add_strategic":gap>=2}

def build_path(gp,c,jd=None):
    needed=set(); id2gap={}
    for g in gp:
        if g["status"]=="Known": continue
        co=g.get("catalog_course")
        if not co: continue
        needed.add(co["id"]); id2gap[co["id"]]=g
        try:
            for anc in nx.ancestors(SKILL_GRAPH,co["id"]):
                ad=CATALOG_BY_ID.get(anc)
                if ad and not any(x["status"]=="Known" and x["skill"].lower() in ad["skill"].lower() for x in gp):
                    needed.add(anc)
        except: pass
    if jd:
        sm=seniority_check(c,jd)
        if sm["add_leadership"]: needed.update(["LD01","LD02"])
        if sm["add_strategic"]:  needed.add("LD03")
    sub=SKILL_GRAPH.subgraph(needed)
    try: ordered=list(nx.topological_sort(sub))
    except: ordered=list(needed)
    crit=set()
    try:
        if sub.nodes: crit=set(nx.dag_longest_path(sub))
    except: pass
    path,seen=[],set()
    for cid in ordered:
        if cid in seen: continue
        seen.add(cid); co=CATALOG_BY_ID.get(cid)
        if not co: continue
        g=id2gap.get(cid,{})
        path.append({**co,"gap_skill":g.get("skill",co["skill"]),"gap_status":g.get("status","Prereq"),
                     "priority":(0 if g.get("is_required") else 1,g.get("proficiency",0)),
                     "reasoning":"","is_critical":cid in crit,"demand":g.get("demand",1),
                     "is_required":g.get("is_required",False)})
    path.sort(key=lambda x:x["priority"]); return path

def calc_impact(gp,path):
    tot=len(gp); known=sum(1 for g in gp if g["status"]=="Known")
    covered=len({m["gap_skill"] for m in path}); rhrs=sum(m["duration_hrs"] for m in path)
    cur=min(100,round(known/max(tot,1)*100)); proj=min(100,round((known+covered)/max(tot,1)*100))
    return {"total_skills":tot,"known_skills":known,"gaps_addressed":covered,
            "roadmap_hours":rhrs,"hours_saved":max(0,60-rhrs),
            "current_fit":cur,"projected_fit":proj,"fit_delta":proj-cur,
            "modules_count":len(path),"critical_count":sum(1 for m in path if m.get("is_critical")),
            "decayed_skills":sum(1 for g in gp if g.get("decayed"))}

def interview_readiness(gp,c):
    rk=[g for g in gp if g["status"]=="Known"   and g["is_required"]]
    rp=[g for g in gp if g["status"]=="Partial" and g["is_required"]]
    rm=[g for g in gp if g["status"]=="Missing" and g["is_required"]]
    tot=max(len(rk)+len(rp)+len(rm),1)
    sc=max(0,min(100,round((len(rk)+len(rp)*0.4)/tot*100)
                    +{"Junior":5,"Mid":0,"Senior":-5,"Lead":-10}.get(c.get("seniority","Mid"),0)))
    if sc>=75:   v=("Strong","#00d4c8","Ready for most rounds")
    elif sc>=50: v=("Moderate","#f5c842","Pass screening; prep gaps")
    elif sc>=30: v=("Weak","#f5a623","Gap work before applying")
    else:        v=("Not Ready","#f55142","Significant prep needed")
    return {"score":sc,"label":v[0],"color":v[1],"advice":v[2],
            "req_known":len(rk),"req_partial":len(rp),"req_missing":len(rm)}

def weekly_plan(path,hpd=2.0):
    cap,weeks,cur,hrs,wn=hpd*5,[],[],0.0,1
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

def transfer_map(c,gp):
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

def roi_rank(gp,path):
    out=[]
    for m in path:
        g=next((x for x in gp if x["skill"]==m.get("gap_skill")),{})
        roi=round((g.get("demand",1)*(1.5 if g.get("is_required") else 1)*10)/max(m["duration_hrs"],1),2)
        out.append({"id":m["id"],"title":m["title"],"skill":m["skill"],"roi":roi,
                    "hrs":m["duration_hrs"],"is_required":g.get("is_required",False)})
    return sorted(out,key=lambda x:x["roi"],reverse=True)

def weeks_ready(hrs,hpd):
    if hpd<=0: return "-"
    w=(hrs/hpd)/5
    if w<1:   return f"{int(hrs/hpd)}d"
    elif w<4: return f"{w:.1f}w"
    return f"{(w/4):.1f}mo"

# =============================================================================
#  PIPELINE
# =============================================================================
def run_analysis(resume_text,jd_text,resume_image_b64=None):
    cache_k=resume_text or "img"
    cached=cache_get(cache_k,jd_text)
    if cached: cached["_cache_hit"]=True; return cached
    kws=[w.strip() for w in jd_text.split() if len(w)>3][:20]
    potential_mods=[c for c in CATALOG if any(kw.lower() in c["skill"].lower() or c["skill"].lower() in kw.lower() for kw in kws)][:10]
    raw=mega_call(resume_text=resume_text,jd_text=jd_text,modules_hint=potential_mods,resume_image_b64=resume_image_b64)
    if "error" in raw: return raw
    candidate=raw.get("candidate",{}); jd_data=raw.get("jd",{})
    quality=raw.get("audit",{}); rsn_map=raw.get("reasoning",{})
    if not candidate or not jd_data: return {"error":"parse_failed — empty candidate or JD"}
    gp=analyze_gap(candidate,jd_data)
    path=build_path(gp,candidate,jd_data)
    for m in path: m["reasoning"]=rsn_map.get(m["id"],f"Addresses gap in {m['gap_skill']}.")
    im=calc_impact(gp,path); sm=seniority_check(candidate,jd_data)
    iv=interview_readiness(gp,candidate); wp=weekly_plan(path)
    tf=transfer_map(candidate,gp); roi=roi_rank(gp,path)
    obs=[{"skill":g["skill"],"status":g["status"],"reason":OBSOLESCENCE_RISK[g["skill"].lower()]}
         for g in gp if OBSOLESCENCE_RISK.get(g["skill"].lower())]
    cgm=max(0,SENIORITY_MAP.get(jd_data.get("seniority_required","Mid"),1)
              -SENIORITY_MAP.get(candidate.get("seniority","Mid"),1))*18
    result={"candidate":candidate,"jd":jd_data,"gap_profile":gp,"path":path,
            "impact":im,"seniority":sm,"quality":quality,"interview":iv,
            "weekly_plan":wp,"transfers":tf,"roi":roi,"obsolescence":obs,
            "career_months":cgm,"_cache_hit":False}
    cache_set(cache_k,jd_text,result); return result

# =============================================================================
#  PDF EXPORT
# =============================================================================
def build_pdf(c,jd,gp,path,im,ql=None,iv=None):
    buf=io.BytesIO()
    if not REPORTLAB: return buf
    doc=SimpleDocTemplate(buf,pagesize=letter,topMargin=48,bottomMargin=48,leftMargin=48,rightMargin=48)
    styles=getSampleStyleSheet()
    TEAL=rl_colors.HexColor("#00d4c8")
    BD=ParagraphStyle("BD",parent=styles["Normal"],fontSize=10,spaceAfter=5)
    H1=ParagraphStyle("H1",parent=styles["Title"],fontSize=20,spaceAfter=4,textColor=TEAL)
    H2=ParagraphStyle("H2",parent=styles["Heading2"],fontSize=13,spaceAfter=6,spaceBefore=14)
    IT=ParagraphStyle("IT",parent=styles["Normal"],fontSize=9,spaceAfter=4,leftIndent=18,
                       textColor=rl_colors.HexColor("#555"),italics=True)
    story=[Paragraph("SkillForge v6 — AI Adaptive Onboarding Report",H1),
           Paragraph(f"Candidate: <b>{c.get('name','--')}</b>  |  Role: <b>{jd.get('role_title','--')}</b>  "
                     f"|  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}",BD),Spacer(1,14)]
    if ql or iv:
        story.append(Paragraph("Scores",H2))
        rows=[]
        if ql: rows+=[["ATS Score",f"{ql.get('ats_score','--')}%"],["Grade",ql.get("overall_grade","--")],
                       ["Completeness",f"{ql.get('completeness_score','--')}%"],["Clarity",f"{ql.get('clarity_score','--')}%"]]
        if iv: rows+=[["Interview Ready",f"{iv['score']}% — {iv['label']}"],["Known",str(iv["req_known"])],["Missing",str(iv["req_missing"])]]
        t=Table([["Metric","Value"]]+rows,colWidths=[200,260])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),TEAL),("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
                                ("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.4,rl_colors.grey),
                                ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.whitesmoke,rl_colors.white]),
                                ("LEFTPADDING",(0,0),(-1,-1),8)]))
        story+=[t,Spacer(1,14)]
    story.append(Paragraph("Learning Roadmap",H2))
    for i,m in enumerate(path):
        story.append(Paragraph(f"<b>{i+1}. {'[CRITICAL] ' if m.get('is_critical') else ''}{m['title']}</b> — {m['level']} / {m['duration_hrs']}h",BD))
        if m.get("reasoning"): story.append(Paragraph(f"→ {m['reasoning']}",IT))
    doc.build(story); buf.seek(0); return buf

# =============================================================================
#  CHARTS
# =============================================================================
_BG="#0a0f1e"; _PLOTBG="rgba(0,0,0,0)"; _GRID="#1a2540"

def radar_chart(gp):
    items=gp[:10]
    if not items: return go.Figure()
    theta=[g["skill"][:14] for g in items]
    fig=go.Figure(data=[
        go.Scatterpolar(r=[10]*len(items),theta=theta,fill="toself",name="JD Required",line=dict(color="#f55142",width=2),opacity=0.18),
        go.Scatterpolar(r=[g.get("original_prof",g["proficiency"]) for g in items],theta=theta,fill="toself",name="Before Decay",line=dict(color="#f5c842",width=1,dash="dot"),opacity=0.18),
        go.Scatterpolar(r=[g["proficiency"] for g in items],theta=theta,fill="toself",name="Current",line=dict(color="#00d4c8",width=2.5),opacity=0.80),
    ])
    fig.update_layout(polar=dict(bgcolor=_PLOTBG,
                                  radialaxis=dict(visible=True,range=[0,10],gridcolor=_GRID,tickfont=dict(size=9,color="#445")),
                                  angularaxis=dict(gridcolor=_GRID)),
                      paper_bgcolor=_PLOTBG,plot_bgcolor=_PLOTBG,
                      font=dict(color="#b0bcd4",family="sans-serif"),
                      showlegend=True,legend=dict(bgcolor=_PLOTBG,x=0.78,y=1.15,font=dict(size=10)),
                      margin=dict(l=30,r=30,t=40,b=30),height=340)
    return fig

def timeline_chart(path):
    if not path: return go.Figure()
    lc={"Critical":"#f55142","Beginner":"#00d4c8","Intermediate":"#f5c842","Advanced":"#f5a623"}
    shown,fig=set(),go.Figure()
    for i,m in enumerate(path):
        k="Critical" if m.get("is_critical") else m["level"]
        show=k not in shown; shown.add(k)
        fig.add_trace(go.Bar(x=[m["duration_hrs"]],y=[f"#{i+1} {m['title'][:28]}"],orientation="h",
                             marker=dict(color=lc.get(k,"#888"),opacity=0.88,line=dict(width=0)),
                             name=k,legendgroup=k,showlegend=show,
                             hovertemplate=f"<b>{m['title']}</b><br>{m['level']} · {m['duration_hrs']}h<extra></extra>"))
    fig.update_layout(paper_bgcolor=_PLOTBG,plot_bgcolor="rgba(10,15,30,0.6)",font=dict(color="#b0bcd4"),
                      xaxis=dict(title="Hours",gridcolor=_GRID,zeroline=False),
                      yaxis=dict(gridcolor=_GRID,tickfont=dict(size=10)),
                      margin=dict(l=10,r=20,t=10,b=40),height=max(280,len(path)*38),
                      legend=dict(bgcolor=_PLOTBG,orientation="h",y=1.03),barmode="overlay")
    return fig

def roi_chart(roi_list):
    if not roi_list: return go.Figure()
    top=roi_list[:10]
    fig=go.Figure(go.Bar(x=[m["roi"] for m in top],y=[m["title"][:28] for m in top],orientation="h",
                         marker=dict(color=["#f55142" if m["is_required"] else "#00d4c8" for m in top],opacity=0.88),
                         hovertemplate="<b>%{y}</b><br>ROI: %{x}<extra></extra>"))
    fig.update_layout(paper_bgcolor=_PLOTBG,plot_bgcolor="rgba(10,15,30,0.4)",font=dict(color="#b0bcd4"),
                      xaxis=dict(title="ROI Index",gridcolor=_GRID,zeroline=False),
                      yaxis=dict(gridcolor=_GRID,autorange="reversed"),
                      margin=dict(l=10,r=20,t=10,b=40),height=max(240,len(top)*34))
    return fig

def priority_matrix(gp):
    ease_map={"Beginner":9,"Intermediate":5,"Advanced":2}
    pts=[{"skill":g["skill"],"ease":ease_map.get((g.get("catalog_course") or {}).get("level","Intermediate"),5),
           "impact":min(10,g.get("demand",1)*3+(3 if g["is_required"] else 0)),
           "hrs":(g.get("catalog_course") or {}).get("duration_hrs",6),"status":g["status"]}
          for g in gp if g["status"]!="Known" and g.get("catalog_course")]
    if not pts: return go.Figure()
    fig=go.Figure()
    for sl,col in [("Missing","#f55142"),("Partial","#f5c842")]:
        sub=[p for p in pts if p["status"]==sl]
        if not sub: continue
        fig.add_trace(go.Scatter(x=[p["ease"] for p in sub],y=[p["impact"] for p in sub],mode="markers+text",
                                 marker=dict(size=[max(14,p["hrs"]*2.8) for p in sub],color=col,opacity=0.75),
                                 text=[p["skill"][:13] for p in sub],textposition="top center",
                                 textfont=dict(size=9,color="#b0bcd4"),name=sl,
                                 hovertemplate="<b>%{text}</b><br>Ease:%{x:.1f} Impact:%{y:.1f}<extra></extra>"))
    for x,y,t in [(2.5,8.5,"HIGH PRIORITY"),(7.5,8.5,"QUICK WIN"),(2.5,2.5,"LONG HAUL"),(7.5,2.5,"NICE TO HAVE")]:
        fig.add_annotation(x=x,y=y,text=t,showarrow=False,font=dict(size=9,color="#2d3f60"))
    fig.add_hline(y=5.5,line_dash="dot",line_color=_GRID)
    fig.add_vline(x=5.5,line_dash="dot",line_color=_GRID)
    fig.update_layout(paper_bgcolor=_PLOTBG,plot_bgcolor="rgba(10,15,30,0.4)",font=dict(color="#b0bcd4"),
                      xaxis=dict(title="Ease",range=[0,11],gridcolor=_GRID,zeroline=False),
                      yaxis=dict(title="Impact",range=[0,11],gridcolor=_GRID,zeroline=False),
                      margin=dict(l=20,r=20,t=20,b=40),showlegend=True,height=380,
                      legend=dict(bgcolor=_PLOTBG,x=0,y=1.1,orientation="h"))
    return fig

def salary_chart(s):
    if not s or not s.get("median_lpa"): return go.Figure()
    vals=[s.get("min_lpa",0),s.get("median_lpa",0),s.get("max_lpa",0)]
    fig=go.Figure(go.Bar(x=["Min","Median","Max"],y=vals,
                         marker_color=["#00d4c8","#f5c842","#f55142"],opacity=0.9,
                         text=[f"₹{v}L" if s.get("currency","INR")=="INR" else f"${v}k" for v in vals],
                         textposition="outside",hovertemplate="<b>%{x}</b><br>%{y}<extra></extra>"))
    fig.update_layout(paper_bgcolor=_PLOTBG,plot_bgcolor="rgba(10,15,30,0.4)",font=dict(color="#b0bcd4"),
                      yaxis=dict(title=f"{s.get('currency','INR')} / yr",gridcolor=_GRID),
                      xaxis=dict(gridcolor=_GRID),margin=dict(l=20,r=20,t=20,b=40),height=260)
    return fig

# =============================================================================
#  CSS — v6 redesign: refined dark, glass cards, tighter layout
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background: #080d1a !important;
    color: #c0ccdf !important;
}
.stApp { background: #080d1a !important; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"],footer,#MainMenu,header[data-testid="stHeader"]{ display:none!important; }

::-webkit-scrollbar { width: 3px; } ::-webkit-scrollbar-thumb { background:#1e2d4a; border-radius:99px; }

/* ── NAV ── */
.sf-nav {
    background: rgba(5,9,20,0.95);
    border-bottom: 1px solid rgba(0,212,200,0.12);
    padding: 0 28px;
    height: 54px;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 1000;
    backdrop-filter: blur(20px);
}
.sf-brand {
    font-family: 'Syne', sans-serif;
    font-size: 1.25rem; font-weight: 800;
    background: linear-gradient(135deg, #00d4c8 0%, #00a8e8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
}
.sf-brand-sub { font-size: 0.52rem; letter-spacing: 0.2em; color: #2d4060; text-transform: uppercase; margin-top: -2px; font-family: 'DM Mono', monospace; }
.sf-tags { display: flex; gap: 6px; align-items: center; }
.sf-tag {
    font-size: 0.62rem; padding: 3px 9px; border-radius: 99px;
    border: 1px solid rgba(0,212,200,0.2); color: #00d4c8;
    background: rgba(0,212,200,0.05); font-family: 'DM Mono', monospace;
    white-space: nowrap;
}
.sf-tag.web { border-color: rgba(0,168,232,0.3); color: #00a8e8; background: rgba(0,168,232,0.05); }

/* ── HERO (compact) ── */
.sf-hero {
    padding: 36px 28px 20px;
    display: flex; align-items: center; justify-content: space-between; gap: 24px;
}
.sf-hero-text h1 {
    font-family: 'Syne', sans-serif; font-size: clamp(1.6rem, 3vw, 2.6rem);
    font-weight: 800; letter-spacing: -0.03em; color: #e8f0ff; line-height: 1.1;
}
.sf-hero-text h1 em { color: #00d4c8; font-style: normal; }
.sf-hero-text p { font-size: 0.82rem; color: #5a7090; margin-top: 6px; max-width: 480px; line-height: 1.5; }
.sf-hero-stats { display: flex; gap: 20px; }
.sf-stat { text-align: center; }
.sf-stat-val { font-family: 'DM Mono', monospace; font-size: 1.4rem; font-weight: 700; color: #00d4c8; }
.sf-stat-lbl { font-size: 0.6rem; color: #2d4060; text-transform: uppercase; letter-spacing: 0.08em; }

/* ── SAMPLE CHIPS ── */
.sf-chips { display: flex; gap: 8px; padding: 0 28px 20px; flex-wrap: wrap; align-items: center; }
.sf-chips-lbl { font-size: 0.65rem; color: #2d4060; text-transform: uppercase; letter-spacing: 0.1em; margin-right: 4px; white-space: nowrap; }

/* ── INPUT PANEL ── */
.sf-input-wrap {
    padding: 0 28px 24px;
    display: grid;
    grid-template-columns: 1fr 1fr 220px;
    gap: 14px;
    align-items: start;
}
@media(max-width:900px){ .sf-input-wrap{grid-template-columns:1fr;} }

.sf-card {
    background: rgba(12,18,35,0.8);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 18px;
    backdrop-filter: blur(8px);
}
.sf-card:hover { border-color: rgba(0,212,200,0.18); }
.sf-card-hd {
    font-family: 'Syne', sans-serif; font-size: 0.78rem; font-weight: 700;
    color: #e8f0ff; margin-bottom: 12px; letter-spacing: 0.02em;
    display: flex; align-items: center; gap: 7px;
}
.sf-card-hd span { font-size: 1rem; }

/* Streamlit widget overrides */
[data-testid="stFileUploadDropzone"] {
    background: rgba(0,212,200,0.03) !important;
    border: 1.5px dashed rgba(0,212,200,0.2) !important;
    border-radius: 8px !important; padding: 14px !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: rgba(0,212,200,0.45) !important;
    background: rgba(0,212,200,0.05) !important;
}
[data-testid="stFileUploadDropzone"] button {
    background: transparent !important; border: 1px solid rgba(0,212,200,0.35) !important;
    color: #00d4c8 !important; border-radius: 6px !important; font-size: 0.75rem !important;
}
textarea {
    background: rgba(6,10,22,0.9) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 8px !important; color: #b0bcd4 !important;
    font-size: 0.78rem !important; font-family: 'DM Mono', monospace !important;
    resize: vertical !important;
}
textarea:focus { border-color: rgba(0,212,200,0.4) !important; }
textarea::placeholder { color: #2d4060 !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00d4c8, #00a8e8) !important;
    border: none !important; border-radius: 10px !important;
    color: #04080f !important; font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important; font-size: 0.88rem !important;
    padding: 13px 0 !important; width: 100% !important;
    transition: all 0.2s !important; letter-spacing: 0.02em !important;
}
.stButton > button:hover {
    opacity: 0.88 !important; transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(0,212,200,0.3) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* Sample chip buttons — override with class */
.sample-chip > button {
    background: rgba(12,20,40,0.9) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #8090b0 !important; font-size: 0.75rem !important;
    font-weight: 600 !important; padding: 7px 14px !important;
    border-radius: 99px !important; font-family: 'DM Sans', sans-serif !important;
}
.sample-chip > button:hover {
    border-color: rgba(0,212,200,0.45) !important; color: #00d4c8 !important;
    background: rgba(0,212,200,0.06) !important;
    transform: translateY(-1px) !important; box-shadow: none !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important; gap: 2px !important;
    padding: 0 28px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; border: none !important;
    color: #3a5070 !important; font-size: 0.82rem !important;
    font-family: 'DM Sans', sans-serif !important;
    padding: 10px 18px !important; border-radius: 0 !important;
}
.stTabs [aria-selected="true"] {
    color: #00d4c8 !important;
    border-bottom: 2px solid #00d4c8 !important; background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 24px 28px !important; }

/* Metrics */
[data-testid="stMetric"] {
    background: rgba(12,18,35,0.8) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important; padding: 14px 16px !important;
}
[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace !important; font-size: 1.7rem !important;
    color: #00d4c8 !important; font-weight: 500 !important;
}
[data-testid="stMetricLabel"] {
    color: #3a5070 !important; font-size: 0.62rem !important;
    text-transform: uppercase !important; letter-spacing: 0.08em !important;
}

/* Expanders */
[data-testid="stExpander"] {
    background: rgba(12,18,35,0.7) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 8px !important; margin-bottom: 5px !important;
}
[data-testid="stExpander"] summary {
    color: #b0bcd4 !important; font-size: 0.82rem !important; font-weight: 500 !important;
}

/* Progress bar */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg,#00d4c8,#00a8e8) !important;
}
[data-testid="stProgressBar"] > div {
    background: rgba(255,255,255,0.05) !important; border-radius: 99px !important;
}

/* Download button */
[data-testid="stDownloadButton"] > button {
    background: rgba(0,212,200,0.08) !important;
    border: 1px solid rgba(0,212,200,0.3) !important;
    color: #00d4c8 !important; font-weight: 600 !important;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div {
    background: rgba(12,18,35,0.9) !important;
    border: 1px solid rgba(255,255,255,0.08) !important; color: #b0bcd4 !important;
}

/* Select slider */
[data-testid="stSlider"] { padding: 0 !important; }

/* ── RESULT ELEMENTS ── */
.kpi-bar { padding: 20px 28px; display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
@media(max-width:900px){ .kpi-bar{grid-template-columns:repeat(3,1fr);} }

.sf-sec { font-family:'Syne',sans-serif; font-size:0.88rem; font-weight:700; color:#e8f0ff; margin-bottom:2px; }
.sf-sec-sub { font-size:0.7rem; color:#3a5070; margin-bottom:12px; }

.sf-skill-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; font-size:0.78rem; }
.sf-skill-name { min-width:110px; color:#b0bcd4; font-size:0.76rem; }
.sf-skill-track { flex:1; height:5px; background:rgba(255,255,255,0.05); border-radius:99px; overflow:hidden; }
.sf-skill-fill  { height:100%; border-radius:99px; }
.sf-skill-val   { font-family:'DM Mono',monospace; font-size:0.68rem; color:#3a5070; min-width:30px; text-align:right; }

.badge { font-size:0.58rem; border-radius:4px; padding:2px 6px; font-weight:700; letter-spacing:0.04em; margin-left:3px; }
.bk { background:rgba(0,212,200,0.1); color:#00d4c8; border:1px solid rgba(0,212,200,0.25); }
.bp { background:rgba(245,200,66,0.1); color:#f5c842; border:1px solid rgba(245,200,66,0.25); }
.bm { background:rgba(245,81,66,0.1); color:#f55142; border:1px solid rgba(245,81,66,0.25); }

.sf-mod { background:rgba(12,20,38,0.8); border:1px solid rgba(255,255,255,0.05); border-left:3px solid #00d4c8; border-radius:8px; padding:11px 13px; margin-bottom:7px; }
.sf-mod.crit { border-left-color:#f55142; box-shadow:0 0 10px rgba(245,81,66,0.08); }
.sf-mod.int  { border-left-color:#f5c842; }
.sf-mod.adv  { border-left-color:#f5a623; }
.sf-mod-title { font-size:0.82rem; font-weight:600; color:#e8f0ff; display:flex; justify-content:space-between; gap:8px; }
.sf-mod-meta  { font-size:0.68rem; color:#3a5070; margin-top:3px; }
.sf-mod-reason { font-size:0.72rem; color:#5a7090; margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.04); font-style:italic; line-height:1.5; }

.sf-course-link { background:rgba(0,168,232,0.05); border:1px solid rgba(0,168,232,0.15); border-radius:7px; padding:8px 12px; margin-bottom:6px; font-size:0.75rem; }
.sf-course-link a { color:#00a8e8; text-decoration:none; font-weight:600; }
.sf-course-link a:hover { text-decoration:underline; }
.sf-course-plat { font-size:0.62rem; color:#3a5070; margin-top:2px; }

.sf-insight { background:rgba(0,212,200,0.04); border-left:2px solid #00d4c8; border-radius:0 6px 6px 0; padding:7px 12px; margin-bottom:5px; font-size:0.76rem; color:#8090b0; line-height:1.5; }
.tf-item { background:rgba(130,100,240,0.05); border-left:2px solid #8264f0; border-radius:6px; padding:7px 11px; margin-bottom:5px; font-size:0.76rem; color:#8090b0; }
.ob-item { background:rgba(245,81,66,0.04); border-left:2px solid #f55142; border-radius:6px; padding:7px 11px; margin-bottom:5px; font-size:0.76rem; color:#8090b0; }

.sf-prow { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.04); font-size:0.78rem; }
.sf-prow:last-child{ border-bottom:none; }
.sf-pk { color:#3a5070; } .sf-pv { font-weight:600; color:#b0bcd4; text-align:right; }

.sf-warn { background:rgba(245,166,35,0.06); border:1px solid rgba(245,166,35,0.2); border-radius:8px; padding:10px 15px; font-size:0.78rem; color:#f5a623; margin-bottom:12px; }
.sf-info { background:rgba(0,212,200,0.06); border:1px solid rgba(0,212,200,0.15); border-radius:8px; padding:10px 15px; font-size:0.78rem; color:#00d4c8; margin-bottom:12px; }

.sf-ar { background:rgba(255,255,255,0.015); border:1px solid rgba(255,255,255,0.04); border-radius:5px; padding:5px 9px; margin-bottom:3px; font-family:'DM Mono',monospace; font-size:0.65rem; color:#3a5070; display:flex; gap:10px; flex-wrap:wrap; }

.sf-statusbar {
    position:fixed; bottom:0; left:0; right:0;
    background:rgba(4,7,16,0.97); border-top:1px solid rgba(255,255,255,0.05);
    padding:5px 28px; font-size:0.64rem; color:#2d4060;
    display:flex; align-items:center; gap:18px; z-index:999;
    backdrop-filter:blur(12px);
}
.sf-statusbar .dot { width:5px; height:5px; border-radius:50%; display:inline-block; margin-right:4px; }
.sf-statusbar .g { background:#00d4c8; } .sf-statusbar .y { background:#f5c842; }
.sf-statusbar .ver { font-family:'DM Mono',monospace; margin-left:auto; }

.sf-divider { height:1px; background:linear-gradient(90deg,transparent,rgba(0,212,200,0.15),transparent); margin:20px 0; }

@keyframes fadeUp { from{opacity:0;transform:translateY(6px);} to{opacity:1;transform:translateY(0);} }
.fade-in { animation:fadeUp 0.35s ease; }

/* tab content padding fix */
.css-1d391kg,[data-testid="stAppViewContainer"]>section{ padding-bottom:36px!important; }
</style>
"""

# =============================================================================
#  UI HELPERS
# =============================================================================
def render_nav():
    st.markdown("""
    <div class="sf-nav">
      <div>
        <div class="sf-brand">SkillForge</div>
        <div class="sf-brand-sub">AI Adaptive Onboarding Engine · v6</div>
      </div>
      <div class="sf-tags">
        <span class="sf-tag">⚡ Groq LLaMA 4-Scout</span>
        <span class="sf-tag">◈ NetworkX DAG</span>
        <span class="sf-tag">◉ Semantic Match</span>
        <span class="sf-tag web">🌐 Web Search</span>
      </div>
    </div>""", unsafe_allow_html=True)

def render_statusbar():
    cost = sum(e.get("cost",0) for e in _audit_log)
    calls = len(_audit_log)
    st.markdown(f"""
    <div class="sf-statusbar">
      <span><span class="dot g"></span>Groq</span>
      <span><span class="dot g"></span>NetworkX</span>
      <span><span class="dot {'g' if SEMANTIC else 'y'}"></span>Semantic{'✓' if SEMANTIC else ' …'}</span>
      <span><span class="dot g"></span>DDG Search</span>
      <span class="ver">v6 · {calls} calls · ${cost:.5f}</span>
    </div>""", unsafe_allow_html=True)

# =============================================================================
#  MAIN UI
# =============================================================================
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    render_nav()

    # ── Compact hero ──────────────────────────────────────────────────────────
    st.markdown("""
    <div class="sf-hero">
      <div class="sf-hero-text">
        <h1>Personalized Path to <em>Role Mastery</em></h1>
        <p>Upload resume + JD → instant skill gap analysis, dependency-aware roadmap, live web intelligence.</p>
      </div>
      <div class="sf-hero-stats">
        <div class="sf-stat"><div class="sf-stat-val">47</div><div class="sf-stat-lbl">Courses</div></div>
        <div class="sf-stat"><div class="sf-stat-val">3</div><div class="sf-stat-lbl">Domains</div></div>
        <div class="sf-stat"><div class="sf-stat-val">0</div><div class="sf-stat-lbl">Hallucinations</div></div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Sample chips — ONE CLICK = auto-analyze ───────────────────────────────
    st.markdown('<div class="sf-chips"><span class="sf-chips-lbl">Try a demo:</span></div>',
                unsafe_allow_html=True)
    c1, c2, c3, _ = st.columns([1,1,1,5])

    with c1:
        st.markdown('<div class="sample-chip">', unsafe_allow_html=True)
        if st.button("👨‍💻 Junior SWE", key="sp_jswe", use_container_width=True):
            st.session_state["jd_paste"]     = SAMPLES["junior_swe"]["jd"]
            st.session_state["res_paste"]    = SAMPLES["junior_swe"]["resume"]
            st.session_state["auto_analyze"] = True
            st.session_state.pop("result", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="sample-chip">', unsafe_allow_html=True)
        if st.button("🧪 Senior DS", key="sp_ds", use_container_width=True):
            st.session_state["jd_paste"]     = SAMPLES["senior_ds"]["jd"]
            st.session_state["res_paste"]    = SAMPLES["senior_ds"]["resume"]
            st.session_state["auto_analyze"] = True
            st.session_state.pop("result", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="sample-chip">', unsafe_allow_html=True)
        if st.button("💼 HR Manager", key="sp_hr", use_container_width=True):
            st.session_state["jd_paste"]     = SAMPLES["hr_manager"]["jd"]
            st.session_state["res_paste"]    = SAMPLES["hr_manager"]["resume"]
            st.session_state["auto_analyze"] = True
            st.session_state.pop("result", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Always-visible input panel (3 columns, no expanders) ─────────────────
    col_res, col_jd, col_act = st.columns([5, 5, 3], gap="small")

    with col_res:
        st.markdown('<div class="sf-card"><div class="sf-card-hd"><span>📄</span> Resume</div>',
                    unsafe_allow_html=True)
        resume_file = st.file_uploader("resume_up", type=["pdf","docx","jpg","jpeg","png","webp"],
                                       key="res_file", label_visibility="collapsed")
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        res_paste = st.text_area("", height=110, placeholder="…or paste resume text here",
                                 key="res_paste", label_visibility="collapsed")
        st.markdown('<div style="font-size:0.62rem;color:#2d4060;text-align:center;padding-top:4px">PDF · DOCX · Image</div></div>',
                    unsafe_allow_html=True)

    with col_jd:
        st.markdown('<div class="sf-card"><div class="sf-card-hd"><span>💼</span> Job Description</div>',
                    unsafe_allow_html=True)
        jd_file = st.file_uploader("jd_up", type=["pdf","docx"],
                                   key="jd_file", label_visibility="collapsed")
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        jd_paste = st.text_area("", height=110, placeholder="…or paste JD text here",
                                key="jd_paste", label_visibility="collapsed")
        st.markdown('<div style="font-size:0.62rem;color:#2d4060;text-align:center;padding-top:4px">PDF · DOCX · Paste</div></div>',
                    unsafe_allow_html=True)

    with col_act:
        st.markdown('<div class="sf-card"><div class="sf-card-hd"><span>⚡</span> Analyze</div>',
                    unsafe_allow_html=True)
        hpd = st.select_slider("Pace (hrs/day)", options=[1,2,4,8], value=2, key="hpd")
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        analyze_btn = st.button("Analyze Skill Gap →", key="analyze_main", use_container_width=True)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        st.caption(f"🤖 `{MODEL_FAST.split('/')[-1][:20]}`")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

    # ── Fire analysis ─────────────────────────────────────────────────────────
    # Triggers: manual button click OR auto_analyze flag from sample chips
    should_run = analyze_btn or st.session_state.pop("auto_analyze", False)

    if should_run:
        res_text, res_img = "", None
        if resume_file:
            res_text, res_img = parse_uploaded_file(resume_file)
        elif st.session_state.get("res_paste","").strip():
            res_text = st.session_state["res_paste"].strip()

        jd_text = ""
        if jd_file:
            jd_text, _ = parse_uploaded_file(jd_file)
        elif st.session_state.get("jd_paste","").strip():
            jd_text = st.session_state["jd_paste"].strip()

        if not res_text and not res_img:
            st.error("⚠ Please upload or paste a resume first.")
        elif not jd_text:
            st.error("⚠ Please upload or paste a job description.")
        else:
            with st.spinner("⚡ Analyzing with Groq LLaMA 4-Scout…"):
                result = run_analysis(res_text, jd_text, res_img)

            if "error" in result:
                if result.get("error") == "rate_limited":
                    st.error(f"⚠ Rate limited: {result.get('message','')}")
                else:
                    st.error(f"Analysis error: {result.get('error','unknown')}")
            else:
                st.session_state["result"]     = result
                st.session_state["resume_txt"] = res_text

    # ── Render results ────────────────────────────────────────────────────────
    res = st.session_state.get("result")
    if not res:
        render_statusbar(); return

    c   = res["candidate"];   jd  = res["jd"]
    gp  = res["gap_profile"]; pt  = res["path"]
    im  = res["impact"];      sm  = res.get("seniority",{})
    ql  = res.get("quality",{}); iv = res.get("interview",{})
    tf  = res.get("transfers",[]); roi = res.get("roi",[])
    obs = res.get("obsolescence",[]); cgm = res.get("career_months",0)
    hpd_val = hpd

    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

    if res.get("_cache_hit"):
        st.markdown('<div class="sf-info" style="margin:0 28px 12px">⚡ <b>Cached result</b> — 0 API calls used</div>', unsafe_allow_html=True)
    if sm.get("has_mismatch"):
        st.markdown(
            f'<div class="sf-warn" style="margin:0 28px 12px">⚠ <b>Seniority Gap:</b> Candidate is {sm["candidate"]}, '
            f'role requires {sm["required"]} — leadership modules auto-added.</div>',
            unsafe_allow_html=True)

    # KPI row
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Current Fit",   f"{im['current_fit']}%")
    k2.metric("Projected Fit", f"{im['projected_fit']}%", f"+{im['fit_delta']}%")
    k3.metric("Training Hrs",  f"{im['roadmap_hours']}h", f"saves ~{im['hours_saved']}h")
    k4.metric("Modules",       im["modules_count"],        f"{im['critical_count']} critical")
    k5.metric("Interview",     f"{iv.get('score',0)}%",    iv.get("label","--"))
    k6.metric("Ready In",      weeks_ready(im["roadmap_hours"], hpd_val))

    # Tabs
    tabs = st.tabs(["🗺 Skill Gap", "📚 Roadmap + ROI", "🌐 Web Intel", "🔬 ATS Audit", "📄 Export", "📋 API Log"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — SKILL GAP
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[0]:
        l, r = st.columns([1.1, 1], gap="large")
        with l:
            st.markdown('<div class="sf-sec">Skill Gap Radar</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sf-sec-sub">{c.get("name","Candidate")} vs {jd.get("role_title","Target Role")}</div>', unsafe_allow_html=True)
            st.plotly_chart(radar_chart(gp), use_container_width=True, config={"displayModeBar":False})
        with r:
            k_cnt=sum(1 for g in gp if g["status"]=="Known")
            p_cnt=sum(1 for g in gp if g["status"]=="Partial")
            m_cnt=sum(1 for g in gp if g["status"]=="Missing")
            st.markdown(f'<div class="sf-sec">All Skills <span style="font-weight:400;font-size:0.72rem;color:#3a5070">— {k_cnt} Known · {p_cnt} Partial · {m_cnt} Missing</span></div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec-sub">⏱ = decayed proficiency &nbsp; ⚠ = obsolescence risk</div>', unsafe_allow_html=True)
            html=""
            for g in gp:
                col={"Known":"#00d4c8","Partial":"#f5c842","Missing":"#f55142"}[g["status"]]
                bc ={"Known":"bk","Partial":"bp","Missing":"bm"}[g["status"]]
                dmnd={3:"🔥",2:"📈",1:"✓"}.get(g.get("demand",1),"✓")
                html+=f"""<div class="sf-skill-row">
                  <div class="sf-skill-name">{g['skill'][:16]}{"⏱" if g.get("decayed") else ""}{"⚠" if g.get("obsolescence_risk") else ""}</div>
                  <div class="sf-skill-track"><div class="sf-skill-fill" style="width:{g['proficiency']/10*100}%;background:{col}"></div></div>
                  <div class="sf-skill-val">{g['proficiency']}/10 {dmnd}</div>
                  <span class="badge {bc}">{g['status']}</span>
                </div>"""
            st.markdown(f'<div style="max-height:320px;overflow-y:auto">{html}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        tc, oc, pc = st.columns(3, gap="medium")
        with tc:
            st.markdown('<div class="sf-sec">↗ Transfer Map</div><div class="sf-sec-sub">Your existing skills give a head start</div>', unsafe_allow_html=True)
            for t_item in (tf[:5] or []):
                st.markdown(f'<div class="tf-item">↗ {t_item["label"]}</div>', unsafe_allow_html=True)
            if not tf: st.caption("No strong transfer paths detected.")
        with oc:
            st.markdown('<div class="sf-sec">⚠ Obsolescence Risks</div><div class="sf-sec-sub">Skills fading by 2027</div>', unsafe_allow_html=True)
            for o in obs:
                st.markdown(f'<div class="ob-item"><b>{o["skill"]}</b>: {o["reason"]}</div>', unsafe_allow_html=True)
            if not obs: st.caption("No risks detected.")
        with pc:
            st.markdown('<div class="sf-sec">👤 Candidate Profile</div><div class="sf-sec-sub"> </div>', unsafe_allow_html=True)
            prows=""
            for k_l,v_v in [("Name",c.get("name","--")),("Role",c.get("current_role","--")),
                              ("Seniority",c.get("seniority","--")),("Experience",f"{c.get('years_experience','--')} yrs"),
                              ("Education",(c.get("education","--") or "")[:28]),("Domain",c.get("domain","--"))]:
                prows+=f'<div class="sf-prow"><span class="sf-pk">{k_l}</span><span class="sf-pv">{v_v}</span></div>'
            st.markdown(prows, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — ROADMAP + ROI
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        rl, rr = st.columns([1.1, 1], gap="large")
        lc={"Beginner":"#00d4c8","Intermediate":"#f5c842","Advanced":"#f5a623"}
        with rl:
            st.markdown('<div class="sf-sec">Learning Roadmap</div><div class="sf-sec-sub">Dependency-ordered · critical path in red · AI reasoning per module</div>', unsafe_allow_html=True)
            for i,m in enumerate(pt):
                crit=m.get("is_critical",False); level=m["level"]
                cls="crit" if crit else ("adv" if level=="Advanced" else "int" if level=="Intermediate" else "")
                with st.expander(f"{'★ ' if crit else ''}#{i+1}  {m['title']}  ·  {m['duration_hrs']}h"):
                    prereqs_str=", ".join(m.get("prereqs",[]) or []) or "None"
                    st.markdown(f"""<div class="sf-mod {cls}">
                      <div class="sf-mod-title">
                        <span>{m['title']}</span>
                        <span style="font-family:'DM Mono',monospace;font-size:.66rem;color:{lc.get(level,'#888')}">{level} · {m['duration_hrs']}h</span>
                      </div>
                      <div class="sf-mod-meta">Skill: {m['skill']} · Domain: {m['domain']} · Gap: {m.get('gap_status','--')} · Prereqs: {prereqs_str}</div>
                      {f'<div class="sf-mod-reason">{m["reasoning"]}</div>' if m.get("reasoning") else ""}
                    </div>""", unsafe_allow_html=True)
        with rr:
            st.markdown('<div class="sf-sec">ROI Ranking</div><div class="sf-sec-sub">Red = required gap · teal = preferred</div>', unsafe_allow_html=True)
            st.plotly_chart(roi_chart(roi), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-sec">Priority Matrix</div><div class="sf-sec-sub">Bubble size = course duration · Top-right = Quick Wins</div>', unsafe_allow_html=True)
        st.plotly_chart(priority_matrix(gp), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="sf-sec">Training Timeline</div>', unsafe_allow_html=True)
        st.plotly_chart(timeline_chart(pt), use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="sf-sec">🗓 Weekly Study Plan</div>', unsafe_allow_html=True)
        wp_curr = weekly_plan(pt, hpd_val)
        for w in wp_curr[:8]:
            with st.expander(f"Week {w['week']} — {w['total_hrs']:.1f}h"):
                for mx in w["modules"]:
                    st.markdown(f"- {'★ ' if mx.get('is_critical') else ''}**{mx['title']}** ({mx['hrs_this_week']:.1f}h / {mx['total_hrs']}h)")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — WEB INTEL (NEW)
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[2]:
        st.markdown('<div class="sf-sec">🌐 Live Web Intelligence</div><div class="sf-sec-sub">Real-time data from the web via DuckDuckGo + Groq — not hallucinated estimates</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

        wi1, wi2 = st.columns(2, gap="large")

        # ── Salary lookup ──────────────────────────────────────────────────
        with wi1:
            st.markdown('<div class="sf-sec">💰 Live Salary Lookup</div>', unsafe_allow_html=True)
            loc = st.selectbox("Location", ["India","USA","UK","Germany","Canada","Singapore","UAE"], index=0, key="sal_loc")
            if st.button("🌐 Search Live Salary", key="sal_btn", use_container_width=True):
                with st.spinner(f"Searching salary data for {jd.get('role_title','--')} in {loc}…"):
                    sal = search_real_salary(jd.get("role_title","the role"), loc)
                st.session_state["sal_result"] = sal

            sal = st.session_state.get("sal_result")
            if sal and sal.get("median_lpa",0):
                st.plotly_chart(salary_chart(sal), use_container_width=True, config={"displayModeBar":False})
                st.caption(f"Source: {sal.get('source','web')} · {sal.get('note','')}")
            elif sal:
                st.warning(f"Could not extract salary: {sal.get('note','—')}")

        # ── Job market intel ───────────────────────────────────────────────
        with wi2:
            st.markdown('<div class="sf-sec">📈 Job Market Intelligence</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sf-sec-sub">Role: {jd.get("role_title","--")}</div>', unsafe_allow_html=True)
            if st.button("🔍 Fetch Market Insights", key="mkt_btn", use_container_width=True):
                with st.spinner("Searching job market trends…"):
                    insights = search_job_market(jd.get("role_title","the role"))
                st.session_state["mkt_insights"] = insights

            for ins in st.session_state.get("mkt_insights",[]):
                st.markdown(f'<div class="sf-insight">📌 {ins}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

        # ── Skill trend signals ────────────────────────────────────────────
        st.markdown('<div class="sf-sec">🔥 Skill Market Signals</div><div class="sf-sec-sub">Web-searched demand signal per skill gap</div>', unsafe_allow_html=True)
        if st.button("🌐 Check Skill Trends", key="trend_btn", use_container_width=True):
            gap_skills=[g["skill"] for g in gp if g["status"]!="Known"][:8]
            with st.spinner("Searching skill demand trends…"):
                trends = search_skill_trends(gap_skills)
            st.session_state["skill_trends"] = trends

        trends = st.session_state.get("skill_trends",{})
        if trends:
            tcols = st.columns(4)
            for i,(skill,signal) in enumerate(trends.items()):
                color = "#f55142" if "Hot" in signal else "#f5c842" if "Growing" in signal else "#3a5070"
                tcols[i%4].markdown(
                    f'<div style="background:rgba(12,20,38,0.8);border:1px solid rgba(255,255,255,0.06);'
                    f'border-radius:8px;padding:10px 12px;margin-bottom:8px;text-align:center">'
                    f'<div style="font-size:0.78rem;font-weight:600;color:#e8f0ff">{skill}</div>'
                    f'<div style="font-size:0.72rem;color:{color};margin-top:3px">{signal}</div>'
                    f'</div>', unsafe_allow_html=True)

        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)

        # ── Real course links ──────────────────────────────────────────────
        st.markdown('<div class="sf-sec">📚 Find Real Courses Online</div><div class="sf-sec-sub">Live Coursera · Udemy · YouTube links for your skill gaps</div>', unsafe_allow_html=True)
        gap_skills_all = [g["skill"] for g in gp if g["status"]!="Known"]
        if gap_skills_all:
            selected_skill = st.selectbox("Pick a skill gap to find courses for:",
                                          gap_skills_all, key="course_skill_sel")
            if st.button(f"🔍 Find courses for {selected_skill}", key="course_search_btn", use_container_width=True):
                with st.spinner(f"Searching online courses for {selected_skill}…"):
                    courses = search_course_links(selected_skill)
                st.session_state[f"courses_{selected_skill}"] = courses

            courses = st.session_state.get(f"courses_{selected_skill}", [])
            if courses:
                for crs in courses:
                    st.markdown(
                        f'<div class="sf-course-link">'
                        f'{crs["icon"]} <a href="{crs["url"]}" target="_blank">{crs["title"]}</a>'
                        f'<div class="sf-course-plat">{crs["platform"]} · {crs["snippet"]}</div>'
                        f'</div>', unsafe_allow_html=True)
            elif f"courses_{selected_skill}" in st.session_state:
                st.warning("No courses found — try a different skill or check your connection.")
        else:
            st.success("🎉 No skill gaps detected! All required skills are Known.")

        # ── Resume rewrite ─────────────────────────────────────────────────
        st.markdown('<div class="sf-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sf-sec">✍ AI Resume Rewrite</div><div class="sf-sec-sub">ATS-optimized for this JD — missing keywords injected naturally</div>', unsafe_allow_html=True)
        rtxt = st.session_state.get("resume_txt","")
        if not rtxt:
            st.info("No resume text available (image-only uploads can't be rewritten).")
        else:
            if st.button("🔄 Rewrite Resume", key="rw_btn", use_container_width=True):
                with st.spinner("Rewriting with llama-4-scout…"):
                    rewritten = rewrite_resume(rtxt, jd, ql.get("missing_keywords",[]))
                st.session_state["rw_result"] = rewritten
            if st.session_state.get("rw_result"):
                st.text_area("Rewritten Resume (ATS-optimized)", value=st.session_state["rw_result"],
                             height=280, key="rw_display")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — ATS AUDIT
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        ats=ql.get("ats_score",0); cs_sc=ql.get("completeness_score",0)
        cl_sc=ql.get("clarity_score",0); grade=ql.get("overall_grade","--")

        a1,a2,a3,a4=st.columns(4)
        a1.metric("ATS Score",    f"{ats}%")
        a2.metric("Grade",        grade)
        a3.metric("Completeness", f"{cs_sc}%")
        a4.metric("Clarity",      f"{cl_sc}%")
        st.progress(ats/100)

        dl,dr=st.columns(2,gap="large")
        with dl:
            st.markdown('<div class="sf-sec" style="margin-top:16px">✏ Improvement Tips</div>', unsafe_allow_html=True)
            for i,tip in enumerate((ql.get("improvement_tips") or [])[:6]):
                st.markdown(
                    f'<div style="display:flex;gap:9px;margin-bottom:7px;font-size:.78rem;color:#8090b0;line-height:1.5">'
                    f'<span style="font-family:DM Mono,monospace;font-size:.65rem;color:#00d4c8;background:rgba(0,212,200,.08);'
                    f'border:1px solid rgba(0,212,200,.18);border-radius:4px;padding:2px 6px;min-width:26px;text-align:center;flex-shrink:0">0{i+1}</span>'
                    f'<span>{tip}</span></div>', unsafe_allow_html=True)
            st.markdown('<div class="sf-sec" style="margin-top:16px">🗣 Interview Talking Points</div>', unsafe_allow_html=True)
            for p in (ql.get("interview_talking_points") or [])[:4]:
                st.markdown(f'<div style="font-size:.78rem;color:#8090b0;margin-bottom:7px;padding-left:11px;border-left:2px solid #00d4c8;line-height:1.5">→ {p}</div>', unsafe_allow_html=True)

        with dr:
            st.markdown('<div class="sf-sec" style="margin-top:16px">🔴 ATS Issues</div>', unsafe_allow_html=True)
            for iss in (ql.get("ats_issues") or ["No critical issues detected"])[:5]:
                st.warning(iss)
            st.markdown('<div class="sf-sec" style="margin-top:12px">Missing Keywords</div>', unsafe_allow_html=True)
            kws=ql.get("missing_keywords") or ["None identified"]
            tags="".join(f'<span style="font-size:.68rem;padding:3px 9px;border-radius:4px;background:rgba(245,81,66,.08);'
                         f'color:#f55142;border:1px solid rgba(245,81,66,.18);margin:3px;display:inline-block;font-weight:600">{k}</span>' for k in kws)
            st.markdown(f'<div style="margin-top:8px;line-height:2.2">{tags}</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        ir1,ir2,ir3=st.columns(3)
        ir1.metric("Interview Ready", f"{iv.get('score',0)}%", iv.get("label","--"))
        ir2.metric("Seniority Gap",   f"{sm.get('gap_levels',0)} level(s)")
        ir3.metric("Est. Career Time",f"~{cgm} months")
        st.markdown(
            f'<div style="font-size:.76rem;color:#8090b0;margin-top:7px">'
            f'✅ Required Known: <b>{iv.get("req_known",0)}</b> &nbsp;·&nbsp; '
            f'🟡 Partial: <b>{iv.get("req_partial",0)}</b> &nbsp;·&nbsp; '
            f'❌ Missing: <b>{iv.get("req_missing",0)}</b> &nbsp;·&nbsp; '
            f'💡 {iv.get("advice","")}</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5 — EXPORT
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[4]:
        ex1,ex2=st.columns(2,gap="large")
        with ex1:
            st.markdown('<div class="sf-sec">📄 PDF Report</div><div class="sf-sec-sub">Full roadmap with reasoning traces</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            for k,v in [("Candidate",c.get("name","--")),("Role",jd.get("role_title","--")),
                         ("ATS Score",f"{ql.get('ats_score','--')}%"),("Grade",ql.get("overall_grade","--")),
                         ("Current Fit",f"{im['current_fit']}%"),("Projected",f"{im['projected_fit']}% (+{im['fit_delta']}%)"),
                         ("Modules",im["modules_count"]),("Training Hrs",f"{im['roadmap_hours']}h")]:
                c1x,c2x=st.columns([1,2]); c1x.caption(k); c2x.markdown(f"**{v}**")
            if REPORTLAB:
                pdf_buf=build_pdf(c,jd,gp,pt,im,ql,iv)
                nm=(c.get("name","candidate") or "candidate").replace(" ","_")
                st.download_button("⬇ Download PDF Report",data=pdf_buf,
                                    file_name=f"skillforge_v6_{nm}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",use_container_width=True)
            else:
                st.warning("`pip install reportlab` to enable PDF export")

        with ex2:
            st.markdown('<div class="sf-sec">📊 JSON Export</div><div class="sf-sec-sub">Full structured result for downstream tools</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            export_data = {
                "candidate": c, "jd": jd,
                "impact": im, "interview": iv,
                "gap_profile": [{k:v for k,v in g.items() if k!="catalog_course"} for g in gp],
                "roadmap": [{"id":m["id"],"title":m["title"],"skill":m["skill"],"level":m["level"],
                             "duration_hrs":m["duration_hrs"],"is_critical":m.get("is_critical",False),
                             "reasoning":m.get("reasoning","")} for m in pt],
                "generated_at": datetime.now().isoformat(),
            }
            json_str = json.dumps(export_data, indent=2, default=str)
            st.download_button("⬇ Download JSON", data=json_str,
                                file_name=f"skillforge_v6_{datetime.now().strftime('%Y%m%d')}.json",
                                mime="application/json", use_container_width=True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            # CSV of gap profile
            csv_rows=["Skill,Status,Proficiency,Required,Demand"]
            for g in gp:
                csv_rows.append(f'"{g["skill"]}",{g["status"]},{g["proficiency"]},{g["is_required"]},{g.get("demand",1)}')
            st.download_button("⬇ Download Gap CSV", data="\n".join(csv_rows),
                                file_name=f"skillforge_gap_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv", use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6 — API LOG
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[5]:
        total_cost=sum(e.get("cost",0) for e in _audit_log)
        st.markdown(f'<div class="sf-sec">🔍 Groq API Audit Log</div>'
                    f'<div class="sf-sec-sub">{len(_audit_log)} calls · ${total_cost:.5f} total · key: .env only · never exposed</div>',
                    unsafe_allow_html=True)
        b1,b2=st.columns(2)
        with b1:
            used=sum(e.get("in",0)+e.get("out",0) for e in _audit_log)
            pct=min(100,round(used/500000*100))
            st.caption(f"**Tokens used:** {used:,} / 500,000 ({pct}%)")
            st.progress(pct/100)
        with b2:
            st.caption(f"**Session cost:** ${total_cost:.5f}")
            st.caption(f"**Model:** `{MODEL_FAST.split('/')[-1]}`")
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        for e in reversed(_audit_log[-30:]):
            ok=e.get("status")=="ok"
            st.markdown(
                f'<div class="sf-ar">'
                f'<span style="color:{"#00d4c8" if ok else "#f55142"}">{"●" if ok else "✕"}</span>'
                f'<span style="color:#7b9fd4">{e.get("ts","--")}</span>'
                f'<span style="color:#00d4c8">{e.get("model","--")}</span>'
                f'<span>in:{e.get("in",0)} out:{e.get("out",0)} cached:{e.get("cached",0)}</span>'
                f'<span>{e.get("ms",0)}ms</span>'
                f'<span>${e.get("cost",0):.6f}</span>'
                f'<span style="color:{"#00d4c8" if ok else "#f55142"}">{e.get("status","--")}</span>'
                f'</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    render_statusbar()

# =============================================================================
#  CLI MODE
# =============================================================================
def cli_analyze(scenario_key):
    if scenario_key not in SAMPLES: print(f"Unknown: {list(SAMPLES.keys())}"); sys.exit(1)
    s=SAMPLES[scenario_key]
    print(f"\n  SkillForge v6 CLI  ·  {s['label']}\n  {'='*52}")
    t0=time.time(); result=run_analysis(s["resume"],s["jd"])
    print(f"  Done in {round(time.time()-t0,2)}s")
    if "error" in result: print(f"  ❌ {result}"); return
    c=result["candidate"]; im=result["impact"]; iv=result["interview"]; pt=result["path"]
    print(f"\n  Candidate : {c.get('name','--')} ({c.get('seniority','--')})")
    print(f"  Role      : {result['jd'].get('role_title','--')}")
    print(f"  Fit       : {im['current_fit']}% → {im['projected_fit']}% (+{im['fit_delta']}%)")
    print(f"  Interview : {iv['score']}% ({iv['label']})")
    print(f"  Roadmap   : {im['modules_count']} modules / {im['roadmap_hours']}h / {im['critical_count']} critical")
    for i,m in enumerate(pt):
        print(f"    {'★ ' if m.get('is_critical') else '  '}#{i+1:02d} [{m['level'][:3]}] {m['title']} ({m['duration_hrs']}h)")
    print(f"\n  Hours saved vs generic 60h: ~{im['hours_saved']}h\n")

# =============================================================================
#  ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="SkillForge v6")
    parser.add_argument("--analyze",metavar="SCENARIO",help="junior_swe | senior_ds | hr_manager")
    args,_=parser.parse_known_args()
    if args.analyze: cli_analyze(args.analyze)
    else:
        threading.Thread(target=_load_semantic_bg,daemon=True).start()
        main()