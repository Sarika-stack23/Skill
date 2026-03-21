# =============================================================================
#  backend.py — SkillForge v12  |  All bugs fixed + UI data fixes
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

MODEL_FAST   = "llama-3.3-70b-versatile"
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
CURRENT_YEAR = datetime.now().year
_CACHE_PATH  = "/tmp/skillforge_v12"

_GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_CLIENT = Groq(api_key=_GROQ_KEY) if _GROQ_KEY else None

_DDG_ERROR: str = ""


def get_ddg_error() -> str:
    return _DDG_ERROR


def ddg_search(query: str, max_results: int = 5) -> List[dict]:
    global _DDG_ERROR
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results*2, region="wt-wt"))
            blocked = ["zhihu.com", "baidu.com", "weibo.com", "163.com", "csdn.net"]
            results = [r for r in results if not any(b in r.get("href","") for b in blocked)][:max_results]
            _DDG_ERROR = ""  # clear on success
            return results
    except ImportError:
        _DDG_ERROR = "web_search_unavailable"
        return []
    except Exception as e:
        _DDG_ERROR = f"web_search_unavailable: {str(e)[:60]}"
        return []


def _is_english(text: str) -> bool:
    if not text:
        return True
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / max(len(text), 1) > 0.75


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
#  SKILL ALIASES — FIX: explicit mapping for common variations
# =============================================================================
SKILL_ALIASES: Dict[str, str] = {
    # REST API variations
    "rest api design":       "rest apis",
    "rest api":              "rest apis",
    "restful api":           "rest apis",
    "restful apis":          "rest apis",
    "api design":            "rest apis",
    # React variations
    "react.js":              "react",
    "reactjs":               "react",
    # MERN — maps to constituent skills
    # handled separately in analyze_gap
    # JavaScript
    "js":                    "javascript",
    "es6":                   "javascript",
    "typescript":            "javascript",  # partial overlap
    # Python
    "python3":               "python",
    # Node
    "node.js":               "rest apis",   # node implies api capability
    "nodejs":                "rest apis",
    # CSS/HTML
    "html5":                 "html/css",
    "css3":                  "html/css",
    "html":                  "html/css",
    "css":                   "html/css",
    # Docker/K8s
    "containerization":      "docker",
    "containers":            "docker",
    # SQL
    "mysql":                 "sql",
    "postgresql":            "sql",
    "postgres":              "sql",
    "sqlite":                "sql",
    "nosql":                 "sql",  # partial
    # ML
    "deep learning":         "deep learning",
    "pytorch":               "deep learning",
    "tensorflow":            "deep learning",
    "scikit-learn":          "machine learning",
    "supervised learning":   "machine learning",
    # Cloud
    "aws sagemaker":         "aws",
    "ec2":                   "aws",
    "s3":                    "aws",
    "gcp":                   "gcp",
    "google cloud":          "gcp",
    # DevOps
    "github actions":        "ci/cd",
    "jenkins":               "ci/cd",
    "gitlab ci":             "ci/cd",
    # Data
    "pandas":                "data analysis",
    "numpy":                 "data analysis",
    "matplotlib":            "data visualization",
    "seaborn":               "data visualization",
}

# MERN stack implies these skills
MERN_IMPLIES: List[str] = ["react", "javascript", "rest apis"]


# =============================================================================
#  CATALOG — 47 courses (unchanged)
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

# FIX: demand labels derived from MARKET_DEMAND, not just web search counts
def demand_label(skill: str) -> str:
    d = MARKET_DEMAND.get(skill.lower(), 1)
    if d >= 3: return "🔥 Hot"
    if d >= 2: return "📈 Growing"
    return "✓ Stable"

OBSOLESCENCE_RISK: Dict[str, str] = {
    "jquery":         "Replaced by vanilla JS and React",
    "php":            "Declining; Python/Node dominant",
    "hadoop":         "Replaced by Spark + cloud-native",
    "excel vba":      "Power Query and Python replacing VBA",
    "manual testing": "AI-assisted automation replacing manual QA",
    "waterfall":      "Industry fully shifted to Agile/DevOps",
}
TRANSFER_MAP: Dict[str, Dict[str, int]] = {
    "python":            {"machine learning":40,"mlops":35,"fastapi":60,"data analysis":50,
                          "deep learning":30,"rest apis":45,"docker":25,"aws":20},
    "machine learning":  {"deep learning":50,"mlops":45,"nlp":40,"statistics":30},
    "javascript":        {"react":55,"rest apis":40,"html/css":35,"ci/cd":20},
    "react":             {"javascript":50,"html/css":60,"rest apis":30},
    "rest apis":         {"fastapi":45,"rest apis":0},
    "sql":               {"data analysis":35,"databases":60,"aws":15},
    "docker":            {"kubernetes":45,"ci/cd":35,"mlops":30,"aws":30,"linux":40},
    "linux":             {"docker":40,"ci/cd":30,"aws":20},
    "aws":               {"gcp":30,"cloud computing":70,"mlops":25,"docker":20,"kubernetes":25},
    "mern stack":        {"react":65,"javascript":60,"rest apis":55,"html/css":50},
    "html/css":          {"react":30,"javascript":20},
    "rest api design":   {"fastapi":50,"rest apis":55},
    "human resources":   {"recruitment":45,"performance management":40,"employee relations":35},
    "communication":     {"leadership":35,"project management":25},
    "leadership":        {"strategic planning":40},
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


def _build_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    for c in CATALOG:
        G.add_node(c["id"], **c)
        for p in c["prereqs"]:
            G.add_edge(p, c["id"])
    return G


SKILL_GRAPH = _build_graph()


def _parse_bytes(raw_bytes: bytes, filename: str) -> Tuple[str, Optional[str]]:
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


_audit_log: List[dict] = []


def _extract_json(text: str) -> str:
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


def _groq_call_vision(prompt: str, system: str, image_b64: str, max_tokens: int = 3200) -> dict:
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
        _audit_log.append({"ts": datetime.now().strftime("%H:%M:%S"), "model": MODEL_VISION.split("/")[-1][:22], "status": f"json_err:{str(e)[:40]}", "in": 0, "out": 0, "ms": 0, "cost": 0})
        return {"error": f"vision_json_parse_failed: {e}"}
    except Exception as e:
        err = str(e)
        if "429" in err or "rate_limit" in err:
            m = re.search(r"try again in (\d+)m([\d.]+)s", err)
            wait_s = (int(m.group(1)) * 60 + float(m.group(2))) if m else 60
            return {"error": "rate_limited", "wait_seconds": int(wait_s), "message": f"Rate limited. Retry in {int(wait_s // 60)}m{int(wait_s % 60)}s."}
        _audit_log.append({"ts": datetime.now().strftime("%H:%M:%S"), "model": MODEL_VISION.split("/")[-1][:22], "status": f"err:{err[:40]}", "in": 0, "out": 0, "ms": 0, "cost": 0})
        return {"error": err}


def _groq_call(prompt: str, system: str, model: str = MODEL_FAST, max_tokens: int = 2800) -> dict:
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
            m = re.search(r"try again in (\d+)m([\d.]+)s", err)
            wait_s = (int(m.group(1)) * 60 + float(m.group(2))) if m else 60
            return {"error": "rate_limited", "wait_seconds": int(wait_s), "message": f"Rate limited. Retry in {int(wait_s // 60)}m{int(wait_s % 60)}s."}
        _audit_log.append({"ts": datetime.now().strftime("%H:%M:%S"), "model": model.split("/")[-1][:22], "status": f"err:{err[:40]}", "in": 0, "out": 0, "ms": 0, "cost": 0})
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


def mega_call(resume_text: str, jd_text: str, modules_hint: Optional[List[dict]] = None, resume_image_b64: Optional[str] = None) -> dict:
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
        return _groq_call_vision(prompt=prompt, system=_VISION_SYS, image_b64=resume_image_b64, max_tokens=3200)
    else:
        prompt = (
            f"Analyze this resume and job description.\n\n"
            f"RESUME:\n{resume_text[:4000]}\n\n"
            f"JOB DESCRIPTION:\n{jd_text[:2000]}\n\n"
            f"Return EXACTLY this JSON:\n{json_schema}"
        )
        return _groq_call(prompt=prompt, system=_MEGA_SYS, model=MODEL_FAST, max_tokens=2800)


def rewrite_resume(resume_text: str, jd: dict, missing_kw: List[str]) -> str:
    # FIX: strict anti-hallucination prompt + no truncation of resume
    system = (
        "You are an expert ATS resume writer. "
        "CRITICAL RULE: You MUST NOT add any technology, tool, framework, skill, certification, "
        "company, project, or experience that is NOT explicitly present in the original resume. "
        "Do NOT invent experience. Do NOT add skills the candidate hasn't listed. "
        "Only restructure, rephrase, and reorganize EXISTING facts for ATS clarity. "
        "If a missing keyword cannot be honestly inserted based on existing experience, skip it. "
        "Return JSON only: {\"rewritten_resume\": \"<text>\"}"
    )
    prompt = (
        f"Rewrite this resume to improve ATS score for the target role.\n"
        f"Only use EXISTING facts from the resume — never fabricate experience.\n"
        f"Add missing keywords ONLY where honestly supported by existing experience: {missing_kw[:8]}\n\n"
        f"ORIGINAL RESUME:\n{resume_text[:3000]}\n\n"
        f"TARGET ROLE: {jd.get('role_title','--')}\n"
        f"REQUIRED SKILLS: {jd.get('required_skills', [])}\n\n"
        f"Return JSON: {{\"rewritten_resume\": \"<full rewritten resume>\"}}"
    )
    r = _groq_call(prompt=prompt, system=system, model=MODEL_FAST, max_tokens=2000)
    return r.get("rewritten_resume", "Could not rewrite resume.")


# =============================================================================
#  WEB SEARCH FEATURES
# =============================================================================
def generate_reasoning(path: List[dict], candidate: dict, jd: dict) -> Dict[str, str]:
    """
    FIX: Dedicated reasoning generation — called after path is built.
    Generates 2-sentence personalized reasoning per module using candidate context.
    Returns dict of module_id → reasoning string.
    """
    if not GROQ_CLIENT or not path:
        return {}

    # Build context summary for the prompt
    cname    = candidate.get("name", "the candidate")
    crole    = candidate.get("current_role", "")
    known    = [s["skill"] for s in candidate.get("skills", []) if int(s.get("proficiency") or 0) >= 7]
    gaps     = [m["gap_skill"] for m in path if m.get("is_required")][:6]
    role     = jd.get("role_title", "")

    modules_list = "\n".join(
        f'- {m["id"]}: {m["title"]} (skill: {m["skill"]}, level: {m["level"]}, '
        f'gap_skill: {m["gap_skill"]}, required: {m.get("is_required", False)})'
        for m in path[:14]
    )

    prompt = (
        f"Candidate: {cname}, {crole}. Target role: {role}.\n"
        f"Known skills: {known}. Gap skills to address: {gaps}.\n\n"
        f"For each module below, write EXACTLY 2 sentences of personalized reasoning:\n"
        f"Sentence 1: Why this specific candidate needs this module given their background.\n"
        f"Sentence 2: How it connects to the target role requirements.\n\n"
        f"Modules:\n{modules_list}\n\n"
        f"Return JSON: {{\"reasoning\": {{\"<module_id>\": \"<2 sentences>\", ...}}}}"
    )
    r = _groq_call(
        prompt=prompt,
        system="Expert L&D advisor. Write concise, personalized module reasoning. Return JSON only.",
        model=MODEL_FAST, max_tokens=1200,
    )
    return r.get("reasoning", {}) if "error" not in r else {}

def search_real_salary(role: str, location: str) -> dict:
    results = ddg_search(f"{role} salary {location} 2025 average annual", max_results=6)
    if not results:
        return {}
    snippets = "\n".join(f"- {r.get('title','')}: {r.get('body','')[:200]}" for r in results[:5])
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
        courses.append({"title": title[:65], "url": url, "platform": plat, "icon": icon, "snippet": body[:120]})
    return courses[:4]


def search_skill_trends(skills: List[str]) -> Dict[str, str]:
    """FIX: use MARKET_DEMAND as primary source, web search to upgrade/downgrade."""
    out = {}
    for skill in skills:
        out[skill] = demand_label(skill)
    # Attempt web search to refine, but don't fail silently on error
    if not skills:
        return out
    try:
        query   = " ".join(skills[:6])
        results = ddg_search(f"most in-demand tech skills 2025 hiring india {query}", max_results=5)
        if results:
            text = " ".join(r.get("body", "") for r in results if _is_english(r.get("body", ""))).lower()
            for skill in skills:
                count = text.count(skill.lower())
                # Only upgrade from MARKET_DEMAND base, never downgrade below it
                base = out[skill]
                if count >= 3 and base != "🔥 Hot":
                    out[skill] = "🔥 Hot"
    except Exception:
        pass
    return out


def search_job_market(role: str) -> List[str]:
    results = ddg_search(f"{role} job market hiring demand 2025 india", max_results=5)
    if not results:
        return []
    eng_snippets = [r.get("body", "")[:300] for r in results[:5] if _is_english(r.get("body", ""))]
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
def _normalize_skill(skill: str) -> str:
    """Normalize a skill name through alias map."""
    sl = (
        skill.lower()
        .replace(".js", "").replace(".ts", "")
        .replace("(", "").replace(")", "").strip()
    )
    return SKILL_ALIASES.get(sl, sl)


def _match_skill(skill: str) -> int:
    sl = _normalize_skill(skill)
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


def _build_candidate_skill_lookup(candidate: dict) -> Dict[str, dict]:
    """
    FIX: Build a comprehensive skill lookup from candidate.skills that:
    - Uses SKILL_ALIASES to normalize keys
    - Expands MERN Stack to constituent skills
    - Handles all common variations
    """
    rs: Dict[str, dict] = {}
    for s in candidate.get("skills", []):
        raw = s["skill"]
        sl  = raw.lower().replace(".js","").replace(".ts","").replace("(","").replace(")","").strip()
        # direct entry
        rs[sl] = s
        # alias entry
        alias = SKILL_ALIASES.get(sl)
        if alias:
            rs[alias] = s
        # MERN expansion
        if "mern" in sl:
            for implied in MERN_IMPLIES:
                if implied not in rs:
                    # Create a derived entry — same proficiency, same year
                    rs[implied] = {**s, "skill": implied, "context": f"Derived from MERN Stack: {s.get('context','')}"}
        # dot notation cleanup
        rs[sl.replace(".", "")] = s
    return rs


def analyze_gap(candidate: dict, jd: dict) -> List[dict]:
    rs    = _build_candidate_skill_lookup(candidate)
    all_s = (
        [(s, True)  for s in jd.get("required_skills",  [])] +
        [(s, False) for s in jd.get("preferred_skills", [])]
    )

    # FIX: also extract SQL from resume text if missing from skills
    raw_text_skills = set(rs.keys())

    out = []
    for skill, req in all_s:
        sl_raw   = skill.lower().replace(".js","").replace(".ts","").replace("(","").replace(")","").strip()
        sl       = SKILL_ALIASES.get(sl_raw, sl_raw)
        status, prof, ctx, dec, orig = "Missing", 0, "", False, 0

        # FIX: multi-strategy lookup
        src = (
            rs.get(sl) or
            rs.get(sl_raw) or
            next((v for k, v in rs.items() if sl in k or k in sl or sl_raw in k or k in sl_raw), None)
        )

        if src:
            try:
                raw_p = int(src.get("proficiency") or 0)
            except (TypeError, ValueError):
                raw_p = 0
            prof, dec = skill_decay(raw_p, src.get("year_last_used") or 0)
            orig      = raw_p
            ctx       = src.get("context", "")
            if prof >= 7:
                status = "Known"
            elif prof > 0:
                status = "Partial"
            else:
                status = "Missing"  # FIX: 0/10 is not Partial, it's Missing

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

    # FIX: Build known proficiency map to skip beginner prereqs for expert skills
    known_prof: Dict[str, int] = {}
    for skill_entry in c.get("skills", []):
        sl  = skill_entry["skill"].lower()
        p, _ = skill_decay(skill_entry.get("proficiency", 0), skill_entry.get("year_last_used", 0))
        known_prof[sl] = p
        alias = SKILL_ALIASES.get(sl)
        if alias:
            known_prof[alias] = p

    for g in gp:
        if g["status"] == "Known":
            continue
        co = g.get("catalog_course")
        if not co:
            continue

        # FIX: skip Beginner courses if candidate already has solid foundation
        candidate_prof = g.get("proficiency", 0)
        if candidate_prof >= 5 and co["level"] == "Beginner":
            # Find intermediate version instead
            better = next(
                (cat for cat in CATALOG
                 if cat["skill"].lower() == co["skill"].lower()
                 and cat["level"] == "Intermediate"),
                None
            )
            if better:
                co = better

        needed.add(co["id"])
        id2gap[co["id"]] = g
        try:
            for anc in nx.ancestors(SKILL_GRAPH, co["id"]):
                ad = CATALOG_BY_ID.get(anc)
                if ad:
                    anc_skill_lower = ad["skill"].lower()
                    cand_p = known_prof.get(anc_skill_lower, 0)
                    # FIX: skip prereq if candidate proficiency >= 6 for that skill
                    # This handles WE01(HTML/CSS) and WE02(JS) being pulled in for React
                    # when candidate already has JavaScript/MERN experience
                    if cand_p >= 6:
                        continue
                    # Also skip if any alias of this skill is known
                    alias_known = any(
                        known_prof.get(alias_val, 0) >= 6
                        for alias_key, alias_val in SKILL_ALIASES.items()
                        if alias_val == anc_skill_lower or alias_key == anc_skill_lower
                    )
                    if alias_known:
                        continue
                    if not any(
                        x["status"] == "Known" and x["skill"].lower() in anc_skill_lower
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
            # Required JD skills and their direct course IDs
            required_gap_skills = {g["skill"].lower() for g in gp if g["is_required"]}

            # Assign node scores: required skill node = 10, prereq-only = 1
            node_score: Dict[str, int] = {}
            for node in sub.nodes:
                co = CATALOG_BY_ID.get(node, {})
                node_score[node] = 10 if co.get("skill","").lower() in required_gap_skills else 1

            # Find longest path by cumulative node score using topological sort + DP
            topo = list(nx.topological_sort(sub))
            dp: Dict[str, int]        = {n: node_score.get(n, 1) for n in topo}
            prev: Dict[str, Optional[str]] = {n: None for n in topo}
            for node in topo:
                for succ in sub.successors(node):
                    candidate_score = dp[node] + node_score.get(succ, 1)
                    if candidate_score > dp[succ]:
                        dp[succ] = candidate_score
                        prev[succ] = node

            # Trace back from highest-score node
            end = max(dp, key=lambda n: dp[n])
            path_nodes: set = set()
            cur: Optional[str] = end
            while cur is not None:
                path_nodes.add(cur)
                cur = prev[cur]
            crit = path_nodes
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
    # FIX: only count JD skills covered, not DAG prerequisites
    jd_skills_lower = {g["skill"].lower() for g in gp}
    covered = len({
        m["gap_skill"].lower() for m in path
        if m["gap_skill"].lower() in jd_skills_lower
    })
    rhrs    = sum(int(m.get("duration_hrs") or 0) for m in path)
    cur     = min(100, round(known / max(tot, 1) * 100))
    proj    = min(100, round((known + covered) / max(tot, 1) * 100))
    # FIX: hours saved comparison — only positive if roadmap < 60h
    hours_saved = max(0, 60 - rhrs)
    return {
        "total_skills":   tot,
        "known_skills":   known,
        "gaps_addressed": covered,
        "roadmap_hours":  rhrs,
        "hours_saved":    hours_saved,
        "roadmap_longer": rhrs > 60,  # FIX: flag when roadmap exceeds generic
        "current_fit":    cur,
        "projected_fit":  proj,
        "fit_delta":      proj - cur,
        "modules_count":  len(path),
        "critical_count": sum(1 for m in path if m.get("is_critical")),
        "decayed_skills": sum(1 for g in gp if g.get("decayed")),
    }


def interview_readiness(gp: List[dict], c: dict) -> dict:
    rk  = [g for g in gp if g["status"] == "Known"   and g["is_required"]]
    # FIX: only count Partial if proficiency > 0 (0-prof Partials are effectively Missing for interviews)
    rp  = [g for g in gp if g["status"] == "Partial"  and g["is_required"] and int(g.get("proficiency") or 0) > 0]
    rm  = [g for g in gp if (g["status"] == "Missing" or (g["status"] == "Partial" and int(g.get("proficiency") or 0) == 0)) and g["is_required"]]
    tot = max(len(rk) + len(rp) + len(rm), 1)
    adj = {"Junior": 5, "Mid": 0, "Senior": -5, "Lead": -10}.get(c.get("seniority", "Mid"), 0)
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
        hpd = max(float(hpd), 0.5)
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
    # FIX: normalize candidate skills through alias map before lookup
    known: set = set()
    for s in c.get("skills", []):
        if int(s.get("proficiency") or 0) >= 6:
            sl = s["skill"].lower().replace(".js","").replace("(","").replace(")","").strip()
            known.add(sl)
            # add alias
            alias = SKILL_ALIASES.get(sl)
            if alias:
                known.add(alias)
            # MERN expands to react + javascript
            if "mern" in sl:
                known.update(["react", "javascript", "rest apis"])

    out = []
    seen_destinations: set = set()
    for g in gp:
        if g["status"] == "Known":
            continue
        sl = g["skill"].lower()
        best_pct, best_k = 0, None
        for k in known:
            pct = TRANSFER_MAP.get(k, {}).get(sl, 0)
            if pct > best_pct:
                best_pct, best_k = pct, k
        if best_k and best_pct > 0 and sl not in seen_destinations:
            seen_destinations.add(sl)
            out.append({
                "gap_skill":    g["skill"],
                "known_skill":  best_k.title(),
                "transfer_pct": best_pct,
                "label": f"Your {best_k.title()} → {best_pct}% head start on {g['skill']}",
                "strength": "Strong" if best_pct >= 50 else "Moderate" if best_pct >= 30 else "Partial",
            })
    return sorted(out, key=lambda x: x["transfer_pct"], reverse=True)[:4]


def roi_rank(gp: List[dict], path: List[dict]) -> List[dict]:
    out = []
    for m in path:
        g   = next((x for x in gp if x["skill"] == m.get("gap_skill")), {})
        hrs = max(int(m.get("duration_hrs") or 1), 1)
        roi = round((g.get("demand", 1) * (1.5 if g.get("is_required") else 1) * 10) / hrs, 2)
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
def run_analysis(resume_text: str, jd_text: str, resume_image_b64: Optional[str] = None) -> dict:
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
        if any(kw.lower() in c["skill"].lower() or c["skill"].lower() in kw.lower() for kw in kws)
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

    # FIX: sanity check — if expert candidate has 0 known skills, flag
    yrs = int(candidate.get("years_experience") or 0)
    skills_count = len(candidate.get("skills", []))
    if skills_count == 0 and yrs > 2:
        return {"error": "analysis_quality_failure — no skills extracted for experienced candidate. Please try again."}

    gp   = analyze_gap(candidate, jd_data)
    path = build_path(gp, candidate, jd_data)

    # FIX: dedicated reasoning generation — personalized per candidate, not generic fallback
    rsn_map_llm = generate_reasoning(path, candidate, jd_data)
    # Merge: LLM reasoning wins, fallback to generic only if missing
    for m in path:
        llm_rsn = rsn_map_llm.get(m["id"]) or rsn_map.get(m["id"])
        m["reasoning"] = llm_rsn if llm_rsn else f"Addresses gap in {m['gap_skill']} — required for {jd_data.get('role_title', 'the target role')}."

    im  = calc_impact(gp, path)
    sm  = seniority_check(candidate, jd_data)
    iv  = interview_readiness(gp, candidate)
    wp  = weekly_plan(path)
    tf  = transfer_map_calc(candidate, gp)
    roi = roi_rank(gp, path)
    obs = [
        {"skill": g["skill"], "status": g["status"], "reason": OBSOLESCENCE_RISK[g["skill"].lower()]}
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
        "_is_image": bool(resume_image_b64),
    }
    cache_set(cache_k, jd_text, result)
    return result


def run_analysis_with_web(resume_text: str, jd_text: str, resume_image_b64: Optional[str] = None, location: str = "India") -> dict:
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
def build_pdf(c: dict, jd: dict, gp: List[dict], path: List[dict], im: dict, ql: Optional[dict] = None, iv: Optional[dict] = None) -> io.BytesIO:
    buf = io.BytesIO()
    if not REPORTLAB:
        return buf
    doc    = SimpleDocTemplate(buf, pagesize=letter, topMargin=48, bottomMargin=48, leftMargin=48, rightMargin=48)
    styles = getSampleStyleSheet()
    TEAL   = rl_colors.HexColor("#2dd4bf")
    BD = ParagraphStyle("BD", parent=styles["Normal"],   fontSize=10, spaceAfter=5)
    H1 = ParagraphStyle("H1", parent=styles["Title"],    fontSize=20, spaceAfter=4, textColor=TEAL)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, spaceBefore=14)
    IT = ParagraphStyle("IT", parent=styles["Normal"],   fontSize=9,  spaceAfter=4, leftIndent=18, textColor=rl_colors.HexColor("#555"))
    story = [
        Paragraph("SkillForge — AI Adaptive Onboarding Report", H1),
        Paragraph(f"Candidate: <b>{c.get('name','--')}</b>  |  Role: <b>{jd.get('role_title','--')}</b>  |  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}", BD),
        Spacer(1, 14),
    ]
    if ql or iv:
        story.append(Paragraph("Scores", H2))
        rows: List[List[str]] = []
        if ql:
            rows += [["ATS Score", f"{ql.get('ats_score','--')}%"], ["Grade", str(ql.get("overall_grade", "--"))], ["Completeness", f"{ql.get('completeness_score','--')}%"], ["Clarity", f"{ql.get('clarity_score','--')}%"]]
        if iv:
            rows += [
                ["Interview Ready", f"{iv['score']}% — {iv['label']}"],
                ["Known skills",    str(iv["req_known"])],
                ["Partial skills",  str(iv["req_partial"])],
                ["Missing skills",  str(iv["req_missing"])],  # FIX: was always showing 0
            ]
        t = Table([["Metric", "Value"]] + rows, colWidths=[200, 260])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 10), ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.whitesmoke, rl_colors.white]),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [t, Spacer(1, 14)]
    story.append(Paragraph("Learning Roadmap", H2))
    for i, m in enumerate(path):
        crit_label = "[CRITICAL] " if m.get("is_critical") else ""
        story.append(Paragraph(f"<b>{i+1}. {crit_label}{m['title']}</b> — {m['level']} / {m['duration_hrs']}h", BD))
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
    return dict(paper_bgcolor=_BG, plot_bgcolor=_BG, font=_FONT, margin=dict(l=8, r=8, t=8, b=36), **kw)


def radar_chart(gp: List[dict]) -> go.Figure:
    items = [g for g in gp if g["is_required"]][:10] or gp[:10]
    if not items:
        return go.Figure()
    # FIX: if all current scores are 0, switch to bar chart for readability
    all_zero = all(int(g.get("proficiency") or 0) == 0 for g in items)
    if all_zero or len([g for g in items if int(g.get("proficiency") or 0) > 0]) < 2:
        return _gap_bar_chart(gp)
    theta = [g["skill"][:14] for g in items]
    fig   = go.Figure(data=[
        go.Scatterpolar(r=[10] * len(items), theta=theta, fill="toself", name="Required", line=dict(color=_RED, width=1), opacity=0.08),
        go.Scatterpolar(r=[int(g.get("proficiency") or 0) for g in items], theta=theta, fill="toself", name="Current", line=dict(color=_TEAL, width=2.5), opacity=0.7),
    ])
    fig.update_layout(
        **_bl(height=320),
        polar=dict(bgcolor=_BG, radialaxis=dict(visible=True, range=[0, 10], gridcolor=_GRID, tickfont=dict(size=9, color="#475569")), angularaxis=dict(gridcolor=_GRID, tickfont=dict(size=11))),
        showlegend=True, legend=dict(bgcolor=_BG, x=0.72, y=1.22, font=dict(size=10)),
    )
    return fig


def _gap_bar_chart(gp: List[dict]) -> go.Figure:
    """FIX: fallback when radar would be near-empty — show horizontal bar gap chart."""
    items = [g for g in gp if g["is_required"]][:8] or gp[:8]
    skills = [g["skill"][:16] for g in items]
    current = [int(g.get("proficiency") or 0) for g in items]
    required = [10] * len(items)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Required", y=skills, x=required, orientation="h", marker_color=_RED, opacity=0.15))
    fig.add_trace(go.Bar(name="Current", y=skills, x=current, orientation="h", marker_color=_TEAL, opacity=0.85))
    fig.update_layout(
        **_bl(height=320), barmode="overlay",
        xaxis=dict(range=[0, 10], gridcolor=_GRID, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=10), autorange="reversed"),
        legend=dict(bgcolor=_BG, orientation="h", y=1.1, font=dict(size=10)),
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
            x=[int(m.get("duration_hrs") or 0)], y=[m["title"][:30]], orientation="h",
            marker=dict(color=lc.get(k, "#64748b"), opacity=0.85, line=dict(width=0)),
            name=k, legendgroup=k, showlegend=show,
            hovertemplate=f"<b>{m['title']}</b><br>{m['level']} · {m['duration_hrs']}h<extra></extra>",
        ))
    fig.update_layout(
        **_bl(height=max(260, len(path) * 38)),
        xaxis=dict(title="Hours", gridcolor=_GRID, zeroline=False, tickfont=dict(size=11)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11), autorange="reversed"),
        legend=dict(bgcolor=_BG, orientation="h", y=1.05, font=dict(size=11)), barmode="overlay",
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
        x=[m["roi"] for m in top], y=[m["title"][:28] for m in top], orientation="h",
        marker=dict(color=[_RED if m["is_required"] else _TEAL for m in top], opacity=0.85, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>ROI Index: %{x}<extra></extra>",
    ))
    fig.update_layout(
        **_bl(height=max(200, len(top) * 36)),
        xaxis=dict(title="ROI Index", gridcolor=_GRID, zeroline=False, tickfont=dict(size=11)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", autorange="reversed", tickfont=dict(size=11)),
    )
    return fig


# =============================================================================
#  3D DAG — build JavaScript-ready graph data from path
# =============================================================================
def build_dag_data(path: List[dict], gp: List[dict]) -> dict:
    """Convert path + catalog graph into nodes/edges for the 3D DAG visualization."""
    path_ids   = {m["id"] for m in path}
    req_skills = {g["skill"].lower() for g in gp if g["is_required"]}
    crit_ids   = {m["id"] for m in path if m.get("is_critical")}

    nodes = []
    for m in path:
        nodes.append({
            "id":       m["id"],
            "label":    m["title"][:22],
            "skill":    m["skill"],
            "level":    m["level"],
            "required": m.get("is_required", False) or m["skill"].lower() in req_skills,
            "critical": m["id"] in crit_ids,
            "hrs":      int(m.get("duration_hrs") or 0),
        })

    # Only include edges where both src and dst are in the path
    edges = []
    for m in path:
        for prereq_id in (m.get("prereqs") or []):
            if prereq_id in path_ids:
                edges.append({"src": prereq_id, "dst": m["id"]})

    return {"nodes": nodes, "edges": edges}


def animated_radar_chart(gp: List[dict]) -> go.Figure:
    """Radar chart that animates from 0 to current proficiency on load."""
    items = [g for g in gp if g["is_required"]][:10] or gp[:10]
    if not items:
        return go.Figure()

    all_zero = all(int(g.get("proficiency") or 0) == 0 for g in items)
    if all_zero or len([g for g in items if int(g.get("proficiency") or 0) > 0]) < 2:
        return _gap_bar_chart(gp)

    theta  = [g["skill"][:14] for g in items]
    target = [int(g.get("proficiency") or 0) for g in items]

    # Build animation frames: 0 → target in 12 steps
    frames = []
    steps  = 12
    for step in range(steps + 1):
        frac = step / steps
        # ease-out cubic
        t_ease = 1 - (1 - frac) ** 3
        r_vals = [round(v * t_ease, 1) for v in target]
        frames.append(go.Frame(
            data=[
                go.Scatterpolar(r=[10]*len(items), theta=theta, fill="toself",
                                name="Required", line=dict(color=_RED, width=1), opacity=0.08),
                go.Scatterpolar(r=r_vals, theta=theta, fill="toself",
                                name="Current", line=dict(color=_TEAL, width=2.5), opacity=0.8),
            ],
            name=str(step)
        ))

    fig = go.Figure(
        data=[
            go.Scatterpolar(r=[10]*len(items), theta=theta, fill="toself",
                            name="Required", line=dict(color=_RED, width=1), opacity=0.08),
            go.Scatterpolar(r=[0]*len(items), theta=theta, fill="toself",
                            name="Current", line=dict(color=_TEAL, width=2.5), opacity=0.8),
        ],
        frames=frames,
        layout=go.Layout(
            **_bl(height=320),
            polar=dict(
                bgcolor=_BG,
                radialaxis=dict(visible=True, range=[0,10], gridcolor=_GRID,
                                tickfont=dict(size=9, color="#475569")),
                angularaxis=dict(gridcolor=_GRID, tickfont=dict(size=11)),
            ),
            showlegend=True,
            legend=dict(bgcolor=_BG, x=0.72, y=1.22, font=dict(size=10)),
            updatemenus=[dict(
                type="buttons", showactive=False, y=1.28, x=0.58,
                xanchor="left",
                buttons=[dict(
                    label="▶ Animate",
                    method="animate",
                    args=[None, {"frame": {"duration": 60, "redraw": True},
                                 "fromcurrent": True, "transition": {"duration": 0}}]
                )]
            )],
        )
    )
    return fig


def generate_interview_questions(gp: List[dict], candidate: dict, jd: dict) -> Dict[str, List[str]]:
    """
    Generate 3 targeted interview questions per Known/Partial skill.
    Returns dict of skill → [q1, q2, q3]
    """
    if not GROQ_CLIENT:
        return {}

    relevant = [g for g in gp if g["status"] in ("Known","Partial") and g["is_required"]][:5]
    if not relevant:
        return {}

    role    = jd.get("role_title","the role")
    cname   = candidate.get("name","the candidate")
    skills_list = "\n".join(
        f"- {g['skill']} (proficiency {g['proficiency']}/10, status: {g['status']}): {g.get('context','')}"
        for g in relevant
    )

    prompt = (
        f"You are a senior technical interviewer at a top tech company.\n"
        f"Candidate: {cname}. Target role: {role}.\n\n"
        f"For each skill below, write exactly 3 interview questions that:\n"
        f"1. Test real depth, not just definitions\n"
        f"2. Are realistic for the stated proficiency level\n"
        f"3. Are specific to the candidate's context where possible\n\n"
        f"Skills:\n{skills_list}\n\n"
        f"Return JSON: {{\"questions\": {{\"<skill>\": [\"<q1>\",\"<q2>\",\"<q3>\"], ...}}}}"
    )
    r = _groq_call(
        prompt=prompt,
        system="Expert technical interviewer. Write realistic, depth-testing interview questions. Return JSON only.",
        model=MODEL_FAST, max_tokens=1000,
    )
    return r.get("questions", {}) if "error" not in r else {}


def build_ics_calendar(path: List[dict], hpd: float = 2.0, start_date: Optional[Any] = None) -> str:
    """
    Generate an .ics calendar file from the weekly study plan.
    Each module becomes a calendar event scheduled at 2h/day blocks.
    """
    from datetime import datetime as dt, timedelta
    if start_date is None:
        start_date = dt.now().replace(hour=19, minute=0, second=0, microsecond=0)
        # Start next Monday
        days_ahead = 7 - start_date.weekday()
        start_date = start_date + timedelta(days=days_ahead)

    try:
        hpd = max(float(hpd), 0.5)
    except (TypeError, ValueError):
        hpd = 2.0

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SkillForge//AI Adaptive Onboarding//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:SkillForge Learning Roadmap",
        "X-WR-TIMEZONE:Asia/Kolkata",
    ]

    current_dt = start_date
    session_hrs = min(hpd, 2.0)  # max 2h sessions
    uid_counter = 0

    for m in path:
        total_hrs = int(m.get("duration_hrs") or 0)
        sessions  = max(1, round(total_hrs / session_hrs))
        title     = m["title"]
        skill     = m["skill"]
        crit_tag  = " ★" if m.get("is_critical") else ""

        for sess in range(sessions):
            # Skip weekends
            while current_dt.weekday() >= 5:
                current_dt += timedelta(days=1)

            dtstart = current_dt.strftime("%Y%m%dT%H%M%S")
            dtend   = (current_dt + timedelta(hours=session_hrs)).strftime("%Y%m%dT%H%M%S")
            uid_counter += 1
            dtstamp = dt.now().strftime("%Y%m%dT%H%M%SZ")

            lines += [
                "BEGIN:VEVENT",
                f"UID:skillforge-{uid_counter}@skillforge.ai",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART;TZID=Asia/Kolkata:{dtstart}",
                f"DTEND;TZID=Asia/Kolkata:{dtend}",
                f"SUMMARY:📚 {title}{crit_tag}",
                f"DESCRIPTION:Skill: {skill}\\nLevel: {m['level']}\\nSession {sess+1}/{sessions}\\n{m.get('reasoning','')[:100]}",
                f"CATEGORIES:SkillForge,{skill}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
            # Next session: same day if time permits, else next day
            next_dt = current_dt + timedelta(hours=session_hrs + 0.5)
            if next_dt.hour >= 22:
                current_dt = (current_dt + timedelta(days=1)).replace(
                    hour=int(start_date.hour), minute=0)
            else:
                current_dt = next_dt

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)