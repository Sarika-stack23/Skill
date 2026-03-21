# =============================================================================
#  backend.py — SkillForge v11  |  All bugs fixed
#  Import this from app.py — do NOT run directly.
# =============================================================================

import os, json, io, re, time, hashlib, shelve, base64
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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
#  CONSTANTS
# =============================================================================
MODEL_FAST   = "llama-3.3-70b-versatile"
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
CURRENT_YEAR = datetime.now().year
_CACHE_PATH  = "/tmp/skillforge_v11"

# =============================================================================
#  GROQ CLIENT  (None if key missing — app.py checks before use)
# =============================================================================
_GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_CLIENT = Groq(api_key=_GROQ_KEY) if _GROQ_KEY else None

# =============================================================================
#  WEB SEARCH
# =============================================================================
_DDG_ERROR: str = ""


def get_ddg_error() -> str:
    """Live getter — avoids stale snapshot when imported into app.py."""
    return _DDG_ERROR


def ddg_search(query: str, max_results: int = 5) -> List[dict]:
    global _DDG_ERROR
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results*2, region="wt-wt"))
            blocked = ["zhihu.com", "baidu.com", "weibo.com", "163.com", "csdn.net"]
            results = [r for r in results if not any(b in r.get("href","") for b in blocked)][:max_results]
            return results
    except ImportError:
        _DDG_ERROR = "duckduckgo-search not installed — run `pip install duckduckgo-search`"
        return []
    except Exception as e:
        _DDG_ERROR = f"Web search unavailable: {e}"
        return []


def _is_english(text: str) -> bool:
    if not text:
        return True
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.75


# =============================================================================
#  SEMANTIC MATCHING  (loaded in background thread)
# =============================================================================
SEMANTIC: bool = False
_ST             = None
_CEMBS          = None


def _load_semantic_bg() -> None:
    global SEMANTIC, _ST, _CEMBS
    try:
        from sentence_transformers import SentenceTransformer
        _ST    = SentenceTransformer("all-MiniLM-L6-v2")
        _CEMBS = _ST.encode([c["skill"].lower() for c in CATALOG])
        SEMANTIC = True
    except Exception:
        pass


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
    "jquery":         "Replaced by vanilla JS and React",
    "php":            "Declining; Python/Node dominant",
    "hadoop":         "Replaced by Spark + cloud-native",
    "excel vba":      "Power Query and Python replacing VBA",
    "manual testing": "AI-assisted automation replacing manual QA",
    "waterfall":      "Industry fully shifted to Agile/DevOps",
}
TRANSFER_MAP: Dict[str, Dict[str, int]] = {
    "python":           {"machine learning":40,"mlops":35,"fastapi":60,"data analysis":50,"deep learning":30,"rest apis":45},
    "machine learning": {"deep learning":50,"mlops":45,"nlp":40,"statistics":30},
    "javascript":       {"react":55,"rest apis":40},
    "sql":              {"data analysis":35,"databases":60},
    "docker":           {"kubernetes":45,"ci/cd":35,"mlops":30},
    "linux":            {"docker":40,"ci/cd":30,"aws":20},
    "aws":              {"gcp":30,"cloud computing":70,"mlops":25},
    "human resources":  {"recruitment":45,"performance management":40,"employee relations":35},
    "communication":    {"leadership":35,"project management":25},
    "leadership":       {"strategic planning":40},
    "financial analysis":{"budgeting":55,"accounting":40},
}
SENIORITY_MAP: Dict[str, int] = {"Junior":0,"Mid":1,"Senior":2,"Lead":3}

SAMPLES: Dict[str, Dict] = {
    "junior_swe": {
        "label":  "Junior SWE → Full Stack",
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
        "label":  "Senior DS → Lead AI",
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
        "label":  "HR Coordinator → Manager",
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
#  FILE PARSER  (bytes-safe)
# =============================================================================
def _parse_bytes(raw_bytes: bytes, filename: str) -> Tuple[str, Optional[str]]:
    """Parse resume from raw bytes. Returns (text, image_b64_or_None)."""
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages), None
        except Exception as e:
            return f"[PDF error: {e}]", None
    if name.endswith(".docx"):
        try:
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs), None
        except Exception as e:
            return f"[DOCX error: {e}]", None
    if any(name.endswith(x) for x in [".jpg", ".jpeg", ".png", ".webp"]):
        media = (
            "image/jpeg" if name.endswith((".jpg", ".jpeg"))
            else "image/png" if name.endswith(".png") else "image/webp"
        )
        return "", f"data:{media};base64,{base64.b64encode(raw_bytes).decode()}"
    return raw_bytes.decode("utf-8", errors="ignore"), None


# =============================================================================
#  GROQ CALLS
# =============================================================================
_audit_log: List[dict] = []


def _extract_json(text: str) -> str:
    """Strip markdown fences and extract the first complete JSON object."""
    text  = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    start = text.find("{")
    if start == -1:
        return "{}"
    depth, end = 0, -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return text[start:end] if end > start else text[start:]


def _groq_call_vision(prompt: str, system: str,
                      image_b64: str, max_tokens: int = 3200) -> dict:
    """Vision model call. response_format JSON not supported — parse manually."""
    if not GROQ_CLIENT:
        return {"error": "GROQ_API_KEY not set"}
    content  = [
        {"type": "image_url", "image_url": {"url": image_b64}},
        {"type": "text", "text": prompt},
    ]
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": content},
    ]
    t0 = time.time()
    try:
        r        = GROQ_CLIENT.chat.completions.create(
            model=MODEL_VISION, messages=messages, temperature=0.1, max_tokens=max_tokens,
        )
        raw_text = r.choices[0].message.content or "{}"
        usage    = r.usage
        in_tok   = usage.prompt_tokens     if usage else 0
        out_tok  = usage.completion_tokens if usage else 0
        cost     = round((in_tok * 0.00000011) + (out_tok * 0.00000034), 6)
        _audit_log.append({
            "ts": datetime.now().strftime("%H:%M:%S"),
            "model": MODEL_VISION.split("/")[-1][:22],
            "in": in_tok, "out": out_tok,
            "ms": round((time.time() - t0) * 1000), "cost": cost, "status": "ok",
        })
        return json.loads(_extract_json(raw_text))
    except json.JSONDecodeError as e:
        _audit_log.append({
            "ts": datetime.now().strftime("%H:%M:%S"),
            "model": MODEL_VISION.split("/")[-1][:22],
            "status": f"json_err:{str(e)[:40]}", "in": 0, "out": 0, "ms": 0, "cost": 0,
        })
        return {"error": f"vision_json_parse_failed: {e}"}
    except Exception as e:
        err = str(e)
        if "429" in err or "rate_limit" in err:
            m      = re.search(r"try again in (\d+)m([\d.]+)s", err)
            wait_s = (int(m.group(1)) * 60 + float(m.group(2))) if m else 60
            return {
                "error": "rate_limited", "wait_seconds": int(wait_s),
                "message": f"Rate limited. Retry in {int(wait_s // 60)}m{int(wait_s % 60)}s.",
            }
        _audit_log.append({
            "ts": datetime.now().strftime("%H:%M:%S"),
            "model": MODEL_VISION.split("/")[-1][:22],
            "status": f"err:{err[:40]}", "in": 0, "out": 0, "ms": 0, "cost": 0,
        })
        return {"error": err}


def _groq_call(prompt: str, system: str,
               model: str = MODEL_FAST, max_tokens: int = 2800) -> dict:
    """Standard text-only Groq call with JSON response_format."""
    if not GROQ_CLIENT:
        return {"error": "GROQ_API_KEY not set"}
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ]
    t0 = time.time()
    try:
        r       = GROQ_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1,
            max_tokens=max_tokens, response_format={"type": "json_object"},
        )
        usage   = r.usage
        in_tok  = usage.prompt_tokens     if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        cost    = round((in_tok * 0.00000011) + (out_tok * 0.00000034), 6)
        _audit_log.append({
            "ts": datetime.now().strftime("%H:%M:%S"),
            "model": model.split("/")[-1][:22],
            "in": in_tok, "out": out_tok,
            "ms": round((time.time() - t0) * 1000), "cost": cost, "status": "ok",
        })
        return json.loads(r.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"error": "json_parse_failed"}
    except Exception as e:
        err = str(e)
        if "429" in err or "rate_limit" in err:
            m      = re.search(r"try again in (\d+)m([\d.]+)s", err)
            wait_s = (int(m.group(1)) * 60 + float(m.group(2))) if m else 60
            return {
                "error": "rate_limited", "wait_seconds": int(wait_s),
                "message": f"Rate limited. Retry in {int(wait_s // 60)}m{int(wait_s % 60)}s.",
            }
        _audit_log.append({
            "ts": datetime.now().strftime("%H:%M:%S"),
            "model": model.split("/")[-1][:22],
            "status": f"err:{err[:40]}", "in": 0, "out": 0, "ms": 0, "cost": 0,
        })
        return {"error": err}


_MEGA_SYS = (
    "You are a world-class senior tech recruiter, ATS specialist, and L&D expert. "
    "Extract ALL sections in ONE response as valid JSON. Be precise and evidence-based. "
    "Return ONLY the JSON object — no preamble, no markdown fences, no explanation text."
)
_VISION_SYS = (
    "You are an expert resume parser and tech recruiter. The user has uploaded an IMAGE of their resume. "
    "OCR every piece of visible text carefully (name, experience, skills, education, projects). "
    "Then analyze the gap against the job description. "
    "Return ONLY a valid JSON object — no markdown, no prose before/after the JSON."
)


def mega_call(resume_text: str, jd_text: str,
              modules_hint: Optional[List[dict]] = None,
              resume_image_b64: Optional[str] = None) -> dict:
    reasoning_block = (
        '\n  "reasoning": {"<module_id>": "<2-sentence why this candidate needs this module>"},'
        if modules_hint else ""
    )
    json_schema = (
        '{\n'
        '  "candidate": {\n'
        '    "name": "<full name or Unknown>",\n'
        '    "current_role": "<latest title>",\n'
        '    "years_experience": <int>,\n'
        '    "seniority": "<Junior|Mid|Senior|Lead>",\n'
        '    "domain": "<Tech|Non-Tech|Hybrid>",\n'
        '    "education": "<degree + field>",\n'
        '    "skills": [{"skill":"<n>","proficiency":<0-10>,"year_last_used":<year or 0>,"context":"<1-line evidence>"}],\n'
        '    "strengths": ["<s1>","<s2>","<s3>"],\n'
        '    "red_flags": ["<f1>","<f2>"]\n'
        '  },\n'
        '  "jd": {\n'
        '    "role_title": "<title>",\n'
        '    "seniority_required": "<Junior|Mid|Senior|Lead>",\n'
        '    "domain": "<Tech|Non-Tech|Hybrid>",\n'
        '    "required_skills": ["<skill>"],\n'
        '    "preferred_skills": ["<skill>"],\n'
        '    "key_responsibilities": ["<resp>"]\n'
        '  },\n'
        '  "audit": {\n'
        '    "ats_score": <0-100>,\n'
        '    "completeness_score": <0-100>,\n'
        '    "clarity_score": <0-100>,\n'
        '    "overall_grade": "<A|B|C|D>",\n'
        '    "ats_issues": ["<issue>"],\n'
        '    "improvement_tips": ["<tip1>","<tip2>","<tip3>","<tip4>","<tip5>"],\n'
        '    "missing_keywords": ["<kw>"],\n'
        '    "interview_talking_points": ["<pt1>","<pt2>","<pt3>"]\n'
        '  }' + reasoning_block + '\n}'
    )
    if resume_image_b64:
        prompt = (
            "I have uploaded an IMAGE of my resume. Please:\n"
            "1. Carefully OCR and read ALL text from the resume image\n"
            "2. Extract every skill, job title, company, date, project, and education detail visible\n"
            "3. Analyze the gap against this job description:\n\n"
            f"JOB DESCRIPTION:\n{jd_text[:2000]}\n\n"
            f"Return EXACTLY this JSON schema:\n{json_schema}\n\n"
            "Extract skills with realistic proficiency scores (expert=9, proficient=7, familiar=4, basic=3). "
            "For year_last_used, use the most recent job/project year where that skill appeared."
        )
        return _groq_call_vision(
            prompt=prompt, system=_VISION_SYS,
            image_b64=resume_image_b64, max_tokens=3200,
        )
    else:
        prompt = (
            f"Analyze this resume and job description.\n\n"
            f"RESUME:\n{resume_text[:4000]}\n\n"
            f"JOB DESCRIPTION:\n{jd_text[:2000]}\n\n"
            f"Return EXACTLY this JSON:\n{json_schema}"
        )
        return _groq_call(prompt=prompt, system=_MEGA_SYS, model=MODEL_FAST, max_tokens=2800)


def rewrite_resume(resume_text: str, jd: dict, missing_kw: List[str]) -> str:
    r = _groq_call(
        f'Rewrite this resume for the target role. Naturally add missing keywords: {missing_kw[:8]}. '
        f'Keep all facts true. Return JSON: {{"rewritten_resume":"<text>"}}\n\n'
        f'Resume:\n{resume_text[:1500]}\n\nTarget: {jd.get("role_title","--")}  '
        f'Required: {jd.get("required_skills",[])}',
        system="Expert resume writer. Return JSON only.",
        model=MODEL_FAST, max_tokens=1500,
    )
    return r.get("rewritten_resume", "Could not rewrite resume.")


# =============================================================================
#  WEB SEARCH FEATURES
# =============================================================================
def search_real_salary(role: str, location: str) -> dict:
    results = ddg_search(f"{role} salary {location} 2025 average annual", max_results=6)
    if not results:
        return {}
    snippets = "\n".join(
        f"- {r.get('title','')}: {r.get('body','')[:200]}" for r in results[:5]
    )
    r = _groq_call(
        f'Extract salary data for "{role}" in {location} from these search snippets.\n\n'
        f'{snippets}\n\n'
        f'Return JSON: {{"min_lpa":<number>,"max_lpa":<number>,"median_lpa":<number>,'
        f'"currency":"INR or USD","source":"<website name>","note":"<key caveat>"}}',
        system="Extract structured salary info from web snippets. Return JSON only.",
        model=MODEL_FAST, max_tokens=400,
    )
    if "error" in r:
        return {}
    try:
        median = float(r.get("median_lpa") or 0)
    except (TypeError, ValueError):
        median = 0.0
    return r if median > 0 else {}


def search_course_links(skill: str) -> List[dict]:
    results = ddg_search(
        f"{skill} online course english 2024 2025 "
        "site:coursera.org OR site:udemy.com OR site:youtube.com OR site:edx.org",
        max_results=8,
    )
    courses = []
    for r in results:
        url   = r.get("href", "")
        title = r.get("title", "")
        body  = r.get("body", "")
        if not url or not title or not _is_english(title):
            continue
        if   "coursera.org" in url: plat, icon = "Coursera", "🎓"
        elif "udemy.com"    in url: plat, icon = "Udemy",    "🎯"
        elif "youtube.com"  in url: plat, icon = "YouTube",  "▶"
        elif "edx.org"      in url: plat, icon = "edX",      "📘"
        elif "linkedin.com" in url: plat, icon = "LinkedIn", "💼"
        else:
            continue
        courses.append({
            "title": title[:65], "url": url,
            "platform": plat, "icon": icon, "snippet": body[:120],
        })
    return courses[:4]


def search_skill_trends(skills: List[str]) -> Dict[str, str]:
    if not skills:
        return {}
    query   = " ".join(skills[:6])
    results = ddg_search(
        f"most in-demand tech skills 2025 hiring india {query}", max_results=5
    )
    text = " ".join(
        r.get("body", "") for r in results if _is_english(r.get("body", ""))
    ).lower()
    out = {}
    for skill in skills:
        count      = text.count(skill.lower())
        out[skill] = "🔥 Hot" if count >= 3 else "📈 Growing" if count >= 1 else "✓ Stable"
    return out


def search_job_market(role: str) -> List[str]:
    results = ddg_search(f"{role} job market hiring demand 2025 india", max_results=5)
    if not results:
        return []
    eng_snippets = [
        r.get("body", "")[:300] for r in results[:5]
        if _is_english(r.get("body", ""))
    ]
    if not eng_snippets:
        return []
    snippets = "\n".join(eng_snippets[:4])
    r = _groq_call(
        f'Based on these search results about "{role}" job market, give 3 short specific insights in English.\n\n'
        f'{snippets}\n\nReturn JSON: {{"insights":["<insight1>","<insight2>","<insight3>"]}}',
        system="Job market analyst. Give insights in English only. Return JSON only.",
        model=MODEL_FAST, max_tokens=300,
    )
    return r.get("insights", []) if "error" not in r else []


# =============================================================================
#  CACHE
# =============================================================================
def _ckey(r: str, j: str) -> str:
    return hashlib.md5((r + "||" + j).encode()).hexdigest()


def cache_get(r: str, j: str) -> Any:
    try:
        with shelve.open(_CACHE_PATH) as db:
            return db.get(_ckey(r, j))
    except Exception:
        return None


def cache_set(r: str, j: str, v: Any) -> None:
    try:
        with shelve.open(_CACHE_PATH) as db:
            db[_ckey(r, j)] = v
    except Exception:
        pass


def cache_bust(resume_text: str, resume_img: Optional[str], jd_text: str) -> None:
    """Delete a cache entry (force-fresh or new file upload)."""
    try:
        ck = (
            "txt:" + hashlib.md5(resume_text.encode()).hexdigest()
            if resume_text.strip()
            else "img:" + hashlib.md5((resume_img or "").encode()).hexdigest()
        )
        with shelve.open(_CACHE_PATH) as db:
            kk = _ckey(ck, jd_text)
            if kk in db:
                del db[kk]
    except Exception:
        pass


# =============================================================================
#  ANALYSIS ENGINE
# =============================================================================
def _match_skill(skill: str) -> int:
    sl = (
        skill.lower()
        .replace(".js", "").replace(".ts", "")
        .replace("(", "").replace(")", "").strip()
    )
    for i, cs in enumerate(CATALOG_SKILLS):
        if sl == cs or sl in cs or cs in sl:
            return i
    if SEMANTIC and _ST is not None and _CEMBS is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            sims = cosine_similarity(_ST.encode([sl]), _CEMBS)[0]
            best = int(np.argmax(sims))
            if sims[best] >= 0.52:
                return best
        except Exception:
            pass
    tokens         = set(sl.split())
    best_s, best_i = 0.0, -1
    for i, cs in enumerate(CATALOG_SKILLS):
        ov = len(tokens & set(cs.split())) / max(len(tokens), 1)
        if ov > best_s:
            best_s, best_i = ov, i
    return best_i if best_s >= 0.4 else -1


def skill_decay(p: Any, yr: Any) -> Tuple[int, bool]:
    """Apply time-decay to a proficiency score. Returns (adjusted, did_decay)."""
    try:
        p = int(p or 0)
    except (TypeError, ValueError):
        p = 0
    try:
        yr = int(yr or 0)
    except (TypeError, ValueError):
        yr = 0
    if yr <= 0 or yr >= CURRENT_YEAR - 1:
        return p, False
    yrs = CURRENT_YEAR - yr
    if yrs <= 2:
        return p, False
    adjusted = round(p * max(0.5, 1 - yrs / 5))
    return adjusted, adjusted < p


def analyze_gap(candidate: dict, jd: dict) -> List[dict]:
    rs    = {s["skill"].lower(): s for s in candidate.get("skills", [])}
    all_s = (
        [(s, True)  for s in jd.get("required_skills",  [])] +
        [(s, False) for s in jd.get("preferred_skills", [])]
    )
    out = []
    for skill, req in all_s:
        sl                         = skill.lower().replace(".js", "").replace(".ts", "").strip()
        status, prof, ctx, dec, orig = "Missing", 0, "", False, 0
        src = rs.get(sl) or next(
            (v for k, v in rs.items() if sl in k or k in sl), None
        )
        if src:
            try:
                raw_p = int(src.get("proficiency") or 0)
            except (TypeError, ValueError):
                raw_p = 0
            prof, dec = skill_decay(raw_p, src.get("year_last_used") or 0)
            orig      = raw_p
            ctx       = src.get("context", "")
            status    = "Known" if prof >= 7 else "Partial"
        idx    = _match_skill(skill)
        demand = MARKET_DEMAND.get(sl, MARKET_DEMAND.get(skill.lower(), 1))
        obs    = OBSOLESCENCE_RISK.get(sl)
        out.append({
            "skill": skill, "status": status, "proficiency": prof,
            "original_prof": orig, "decayed": dec, "is_required": req,
            "context": ctx,
            "catalog_course": CATALOG[idx] if idx >= 0 else None,
            "demand": demand, "obsolescence_risk": obs,
        })
    return out


def seniority_check(c: dict, jd: dict) -> dict:
    cs  = c.get("seniority", "Mid")
    rs  = jd.get("seniority_required", "Mid")
    gap = SENIORITY_MAP.get(rs, 1) - SENIORITY_MAP.get(cs, 1)
    return {
        "has_mismatch":   gap > 0,
        "gap_levels":     gap,
        "candidate":      cs,
        "required":       rs,
        "add_leadership": gap >= 1,
        "add_strategic":  gap >= 2,
    }


def build_path(gp: List[dict], c: dict, jd: Optional[dict] = None) -> List[dict]:
    needed:  set  = set()
    id2gap:  dict = {}
    for g in gp:
        if g["status"] == "Known":
            continue
        co = g.get("catalog_course")
        if not co:
            continue
        needed.add(co["id"])
        id2gap[co["id"]] = g
        try:
            for anc in nx.ancestors(SKILL_GRAPH, co["id"]):
                ad = CATALOG_BY_ID.get(anc)
                if ad and not any(
                    x["status"] == "Known" and x["skill"].lower() in ad["skill"].lower()
                    for x in gp
                ):
                    needed.add(anc)
        except Exception:
            pass
    if jd:
        sm = seniority_check(c, jd)
        if sm["add_leadership"]:
            needed.update(["LD01", "LD02"])
        if sm["add_strategic"]:
            needed.add("LD03")
    sub = SKILL_GRAPH.subgraph(needed)
    try:
        ordered = list(nx.topological_sort(sub))
    except Exception:
        ordered = list(needed)
    crit: set = set()
    try:
        if sub.nodes:
            crit = set(nx.dag_longest_path(sub))
    except Exception:
        pass
    path, seen = [], set()
    for cid in ordered:
        if cid in seen:
            continue
        seen.add(cid)
        co = CATALOG_BY_ID.get(cid)
        if not co:
            continue
        g = id2gap.get(cid, {})
        try:
            prio_prof = int(g.get("proficiency") or 0)
        except (TypeError, ValueError):
            prio_prof = 0
        path.append({
            **co,
            "gap_skill":   g.get("skill", co["skill"]),
            "gap_status":  g.get("status", "Prereq"),
            "priority":    (0 if g.get("is_required") else 1, prio_prof),
            "reasoning":   "",
            "is_critical": cid in crit,
            "demand":      g.get("demand", 1),
            "is_required": g.get("is_required", False),
        })
    path.sort(key=lambda x: x["priority"])
    return path


def calc_impact(gp: List[dict], path: List[dict]) -> dict:
    tot     = len(gp)
    known   = sum(1 for g in gp if g["status"] == "Known")
    covered = len({m["gap_skill"] for m in path})
    rhrs    = sum(int(m.get("duration_hrs") or 0) for m in path)
    cur     = min(100, round(known / max(tot, 1) * 100))
    proj    = min(100, round((known + covered) / max(tot, 1) * 100))
    return {
        "total_skills":   tot,
        "known_skills":   known,
        "gaps_addressed": covered,
        "roadmap_hours":  rhrs,
        "hours_saved":    max(0, 60 - rhrs),
        "current_fit":    cur,
        "projected_fit":  proj,
        "fit_delta":      proj - cur,
        "modules_count":  len(path),
        "critical_count": sum(1 for m in path if m.get("is_critical")),
        "decayed_skills": sum(1 for g in gp if g.get("decayed")),
    }


def interview_readiness(gp: List[dict], c: dict) -> dict:
    rk  = [g for g in gp if g["status"] == "Known"   and g["is_required"]]
    rp  = [g for g in gp if g["status"] == "Partial"  and g["is_required"]]
    rm  = [g for g in gp if g["status"] == "Missing"  and g["is_required"]]
    tot = max(len(rk) + len(rp) + len(rm), 1)
    adj = {"Junior": 5, "Mid": 0, "Senior": -5, "Lead": -10}.get(
        c.get("seniority", "Mid"), 0
    )
    sc = max(0, min(100, round((len(rk) + len(rp) * 0.4) / tot * 100) + adj))
    if   sc >= 75: v = ("Strong",    "#4ade80", "Ready for most rounds")
    elif sc >= 50: v = ("Moderate",  "#fbbf24", "Pass screening; prep gaps")
    elif sc >= 30: v = ("Weak",      "#fb923c", "Gap work before applying")
    else:          v = ("Not Ready", "#f87171", "Significant prep needed")
    return {
        "score": sc, "label": v[0], "color": v[1], "advice": v[2],
        "req_known": len(rk), "req_partial": len(rp), "req_missing": len(rm),
    }


def weekly_plan(path: List[dict], hpd: float = 2.0) -> List[dict]:
    try:
        hpd = max(float(hpd), 0.5)   # guard: hpd must never be 0 or negative
    except (TypeError, ValueError):
        hpd = 2.0
    cap               = hpd * 5
    weeks, cur, hrs, wn = [], [], 0.0, 1
    for m in path:
        try:
            rem = float(int(m.get("duration_hrs") or 0))
        except (TypeError, ValueError):
            rem = 0.0
        while rem > 0:
            avail = cap - hrs
            if avail <= 0:
                weeks.append({"week": wn, "modules": cur, "total_hrs": hrs})
                cur, hrs, wn = [], 0.0, wn + 1
                avail = cap
            chunk = min(rem, avail)
            ex    = next((x for x in cur if x["id"] == m["id"]), None)
            if ex:
                ex["hrs_this_week"] += chunk
            else:
                cur.append({
                    "id": m["id"], "title": m["title"], "level": m["level"],
                    "domain": m["domain"], "is_critical": m.get("is_critical", False),
                    "hrs_this_week": chunk,
                    "total_hrs": int(m.get("duration_hrs") or 0),
                })
            hrs += chunk
            rem -= chunk
    if cur:
        weeks.append({"week": wn, "modules": cur, "total_hrs": hrs})
    return weeks


def transfer_map_calc(c: dict, gp: List[dict]) -> List[dict]:
    known = {
        g["skill"].lower() for g in c.get("skills", [])
        if int(g.get("proficiency") or 0) >= 6
    }
    out = []
    for g in gp:
        if g["status"] == "Known":
            continue
        sl = g["skill"].lower()
        for k in known:
            pct = TRANSFER_MAP.get(k, {}).get(sl, 0)
            if pct:
                out.append({
                    "gap_skill":    g["skill"],
                    "known_skill":  k.title(),
                    "transfer_pct": pct,
                    "label": f"Your {k.title()} → {pct}% head start on {g['skill']}",
                })
    return sorted(out, key=lambda x: x["transfer_pct"], reverse=True)


def roi_rank(gp: List[dict], path: List[dict]) -> List[dict]:
    out = []
    for m in path:
        g   = next((x for x in gp if x["skill"] == m.get("gap_skill")), {})
        hrs = max(int(m.get("duration_hrs") or 1), 1)
        roi = round(
            (g.get("demand", 1) * (1.5 if g.get("is_required") else 1) * 10) / hrs, 2
        )
        out.append({
            "id": m["id"], "title": m["title"], "skill": m["skill"],
            "roi": roi, "hrs": int(m.get("duration_hrs") or 0),
            "is_required": g.get("is_required", False),
        })
    return sorted(out, key=lambda x: x["roi"], reverse=True)


def weeks_ready(hrs: float, hpd: float) -> str:
    try:
        hpd = max(float(hpd), 0.5)
        hrs = float(hrs)
    except (TypeError, ValueError):
        return "–"
    if hrs <= 0:
        return "0d"
    w = (hrs / hpd) / 5
    if w < 1:  return f"{int(hrs / hpd)}d"
    if w < 4:  return f"{w:.1f}w"
    return f"{(w / 4):.1f}mo"


# =============================================================================
#  FULL PIPELINE
# =============================================================================
def run_analysis(resume_text: str, jd_text: str,
                 resume_image_b64: Optional[str] = None) -> dict:
    if resume_text and resume_text.strip():
        cache_k = "txt:" + hashlib.md5(resume_text.encode()).hexdigest()
    elif resume_image_b64:
        cache_k = "img:" + hashlib.md5(resume_image_b64.encode()).hexdigest()
    else:
        cache_k = "empty"

    cached = cache_get(cache_k, jd_text)
    if cached:
        cached["_cache_hit"] = True
        return cached

    kws            = [w.strip() for w in jd_text.split() if len(w) > 3][:20]
    potential_mods = [
        c for c in CATALOG
        if any(
            kw.lower() in c["skill"].lower() or c["skill"].lower() in kw.lower()
            for kw in kws
        )
    ][:10]

    raw = mega_call(
        resume_text=resume_text, jd_text=jd_text,
        modules_hint=potential_mods, resume_image_b64=resume_image_b64,
    )
    if "error" in raw:
        return raw

    candidate = raw.get("candidate", {})
    jd_data   = raw.get("jd",        {})
    quality   = raw.get("audit",     {})
    rsn_map   = raw.get("reasoning", {}) or {}

    if not candidate or not jd_data:
        return {"error": "parse_failed — empty candidate or JD"}

    gp   = analyze_gap(candidate, jd_data)
    path = build_path(gp, candidate, jd_data)
    for m in path:
        m["reasoning"] = rsn_map.get(m["id"], f"Addresses gap in {m['gap_skill']}.")

    im  = calc_impact(gp, path)
    sm  = seniority_check(candidate, jd_data)
    iv  = interview_readiness(gp, candidate)
    wp  = weekly_plan(path)
    tf  = transfer_map_calc(candidate, gp)
    roi = roi_rank(gp, path)
    obs = [
        {"skill": g["skill"], "status": g["status"],
         "reason": OBSOLESCENCE_RISK[g["skill"].lower()]}
        for g in gp if OBSOLESCENCE_RISK.get(g["skill"].lower())
    ]
    cgm = max(
        0,
        (SENIORITY_MAP.get(jd_data.get("seniority_required", "Mid"), 1) -
         SENIORITY_MAP.get(candidate.get("seniority", "Mid"), 1)) * 18,
    )
    result = {
        "candidate": candidate, "jd": jd_data, "gap_profile": gp, "path": path,
        "impact": im, "seniority": sm, "quality": quality, "interview": iv,
        "weekly_plan": wp, "transfers": tf, "roi": roi, "obsolescence": obs,
        "career_months": cgm, "_cache_hit": False,
        "_is_image": bool(resume_image_b64),   # FIX: track image resumes for badge
    }
    cache_set(cache_k, jd_text, result)
    return result


def run_analysis_with_web(resume_text: str, jd_text: str,
                          resume_image_b64: Optional[str] = None,
                          location: str = "India") -> dict:
    result = run_analysis(resume_text, jd_text, resume_image_b64)
    if "error" in result:
        return result
    role       = result["jd"].get("role_title", "")
    gap_skills = [g["skill"] for g in result["gap_profile"] if g["status"] != "Known"][:6]
    with ThreadPoolExecutor(max_workers=3) as ex:
        sal_f   = ex.submit(search_real_salary,  role, location)
        trend_f = ex.submit(search_skill_trends, gap_skills)
        mkt_f   = ex.submit(search_job_market,   role)
    result["salary"]          = sal_f.result()
    result["skill_trends"]    = trend_f.result()
    result["market_insights"] = mkt_f.result()
    return result


# =============================================================================
#  PDF EXPORT
# =============================================================================
def build_pdf(c: dict, jd: dict, gp: List[dict], path: List[dict],
              im: dict, ql: Optional[dict] = None, iv: Optional[dict] = None) -> io.BytesIO:
    buf = io.BytesIO()
    if not REPORTLAB:
        return buf
    doc    = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=48, bottomMargin=48, leftMargin=48, rightMargin=48,
    )
    styles = getSampleStyleSheet()
    TEAL   = rl_colors.HexColor("#2dd4bf")
    BD = ParagraphStyle("BD", parent=styles["Normal"],   fontSize=10, spaceAfter=5)
    H1 = ParagraphStyle("H1", parent=styles["Title"],    fontSize=20, spaceAfter=4, textColor=TEAL)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, spaceBefore=14)
    IT = ParagraphStyle("IT", parent=styles["Normal"],   fontSize=9,  spaceAfter=4, leftIndent=18,
                        textColor=rl_colors.HexColor("#555"))
    story = [
        Paragraph("SkillForge — AI Adaptive Onboarding Report", H1),
        Paragraph(
            f"Candidate: <b>{c.get('name','--')}</b>  |  "
            f"Role: <b>{jd.get('role_title','--')}</b>  |  "
            f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}",
            BD,
        ),
        Spacer(1, 14),
    ]
    if ql or iv:
        story.append(Paragraph("Scores", H2))
        rows: List[List[str]] = []
        if ql:
            rows += [
                ["ATS Score",    f"{ql.get('ats_score','--')}%"],
                ["Grade",        str(ql.get("overall_grade", "--"))],
                ["Completeness", f"{ql.get('completeness_score','--')}%"],
                ["Clarity",      f"{ql.get('clarity_score','--')}%"],
            ]
        if iv:
            rows += [
                ["Interview Ready", f"{iv['score']}% — {iv['label']}"],
                ["Known",           str(iv["req_known"])],
                ["Missing",         str(iv["req_missing"])],
            ]
        t = Table([["Metric", "Value"]] + rows, colWidths=[200, 260])
        t.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), TEAL),
            ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.white),
            ("FONTSIZE",       (0, 0), (-1, -1), 10),
            ("GRID",           (0, 0), (-1, -1), 0.4, rl_colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.whitesmoke, rl_colors.white]),
            ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ]))
        story += [t, Spacer(1, 14)]
    story.append(Paragraph("Learning Roadmap", H2))
    for i, m in enumerate(path):
        crit_label = "[CRITICAL] " if m.get("is_critical") else ""
        story.append(Paragraph(
            f"<b>{i+1}. {crit_label}{m['title']}</b> — {m['level']} / {m['duration_hrs']}h", BD,
        ))
        if m.get("reasoning"):
            story.append(Paragraph(f"→ {m['reasoning']}", IT))
    doc.build(story)
    buf.seek(0)
    return buf


# =============================================================================
#  CHARTS
# =============================================================================
_BG    = "rgba(0,0,0,0)"
_GRID  = "rgba(255,255,255,0.06)"
_TEAL  = "#2dd4bf"
_AMBER = "#f59e0b"
_RED   = "#ef4444"
_GREEN = "#4ade80"
_FONT  = dict(color="#94a3b8", family="'DM Mono', 'IBM Plex Mono', monospace")


def _bl(**kw) -> dict:
    return dict(
        paper_bgcolor=_BG, plot_bgcolor=_BG, font=_FONT,
        margin=dict(l=8, r=8, t=8, b=36), **kw,
    )


def radar_chart(gp: List[dict]) -> go.Figure:
    items = [g for g in gp if g["is_required"]][:10] or gp[:10]
    if not items:
        return go.Figure()
    theta = [g["skill"][:14] for g in items]
    fig   = go.Figure(data=[
        go.Scatterpolar(
            r=[10] * len(items), theta=theta, fill="toself",
            name="Required", line=dict(color=_RED, width=1), opacity=0.08,
        ),
        go.Scatterpolar(
            r=[int(g.get("proficiency") or 0) for g in items],
            theta=theta, fill="toself", name="Current",
            line=dict(color=_TEAL, width=2.5), opacity=0.7,
        ),
    ])
    fig.update_layout(
        **_bl(height=320),
        polar=dict(
            bgcolor=_BG,
            radialaxis=dict(visible=True, range=[0, 10], gridcolor=_GRID,
                            tickfont=dict(size=9, color="#475569")),
            angularaxis=dict(gridcolor=_GRID, tickfont=dict(size=11)),
        ),
        showlegend=True,
        legend=dict(bgcolor=_BG, x=0.72, y=1.22, font=dict(size=10)),
    )
    return fig


def timeline_chart(path: List[dict]) -> go.Figure:
    if not path:
        return go.Figure()
    lc    = {"Critical": _RED, "Beginner": _TEAL, "Intermediate": _AMBER, "Advanced": "#f97316"}
    shown: set = set()
    fig   = go.Figure()
    for m in path:
        k    = "Critical" if m.get("is_critical") else m["level"]
        show = k not in shown
        shown.add(k)
        fig.add_trace(go.Bar(
            x=[int(m.get("duration_hrs") or 0)],
            y=[m["title"][:30]],
            orientation="h",
            marker=dict(color=lc.get(k, "#64748b"), opacity=0.85, line=dict(width=0)),
            name=k, legendgroup=k, showlegend=show,
            hovertemplate=f"<b>{m['title']}</b><br>{m['level']} · {m['duration_hrs']}h<extra></extra>",
        ))
    fig.update_layout(
        **_bl(height=max(260, len(path) * 38)),
        xaxis=dict(title="Hours", gridcolor=_GRID, zeroline=False, tickfont=dict(size=11)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11), autorange="reversed"),
        legend=dict(bgcolor=_BG, orientation="h", y=1.05, font=dict(size=11)),
        barmode="overlay",
    )
    return fig


def salary_chart(s: dict) -> go.Figure:
    if not s:
        return go.Figure()
    try:
        med = float(s.get("median_lpa") or 0)
    except (TypeError, ValueError):
        med = 0.0
    if med <= 0:
        return go.Figure()

    def _n(v: Any) -> float:
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    vals = [_n(s.get("min_lpa")), _n(s.get("median_lpa")), _n(s.get("max_lpa"))]
    curr = s.get("currency", "INR")
    sym  = "₹" if curr == "INR" else "$"
    unit = "L/yr" if curr == "INR" else "k/yr"
    lbls = [f"{sym}{v}{unit}" for v in vals]
    fig  = go.Figure(go.Bar(
        x=["Min", "Median", "Max"], y=vals,
        marker_color=[_TEAL, _AMBER, _RED], opacity=0.82,
        text=lbls, textposition="outside",
        textfont=dict(size=13, family="'DM Mono','IBM Plex Mono',monospace"),
    ))
    fig.update_layout(
        **_bl(height=230),
        yaxis=dict(title=unit, gridcolor=_GRID, zeroline=False, tickfont=dict(size=11)),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=12)),
    )
    return fig


def roi_bar(roi_list: List[dict]) -> go.Figure:
    if not roi_list:
        return go.Figure()
    top = roi_list[:10]
    fig = go.Figure(go.Bar(
        x=[m["roi"] for m in top],
        y=[m["title"][:28] for m in top],
        orientation="h",
        marker=dict(
            color=[_RED if m["is_required"] else _TEAL for m in top],
            opacity=0.85, line=dict(width=0),
        ),
        hovertemplate="<b>%{y}</b><br>ROI Index: %{x}<extra></extra>",
    ))
    fig.update_layout(
        **_bl(height=max(200, len(top) * 36)),
        xaxis=dict(title="ROI Index", gridcolor=_GRID, zeroline=False, tickfont=dict(size=11)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", autorange="reversed", tickfont=dict(size=11)),
    )
    return fig