# SkillForge ⚡ — AI Adaptive Onboarding Engine

> Intelligent skill-gap analysis and personalized learning pathway generation — powered by Groq LLaMA 3.3, NetworkX DAG, sentence-transformers, and a custom adaptive algorithm.

## 🚀 Live Demo

**Try it now → [skill-forge-345.streamlit.app](https://skill-forge-345.streamlit.app/)**

No setup needed. Click any demo scenario on the landing page for instant results.

📹 **Video walkthrough → [Watch Demo](https://drive.google.com/file/d/1dzOV292Z8zhcYhXy_l8U_rs0G9uezaP6/view?usp=sharing)**

---

## The Problem

Corporate onboarding is broken. Everyone gets the same 60-hour curriculum regardless of what they already know. Experienced hires waste time on concepts they mastered years ago. Beginners get overwhelmed by advanced modules out of sequence. Nobody wins.

## The Solution

Upload a **resume PDF** + **job description**. SkillForge:

1. Validates the uploaded file is genuinely a resume — not a JD, invoice, or report
2. Extracts every skill with proficiency score (0–10) and year last used
3. Applies a **skill decay model** — skills unused 2+ years have proficiency reduced
4. Computes the exact **Known / Partial / Missing** gap against the JD
5. Generates a **dependency-aware learning roadmap** using a NetworkX DAG with topological sort
6. Detects the **critical path** using node-weighted dynamic programming
7. Scores **interview readiness** based on actual required skill coverage
8. Audits the resume for **ATS compliance** and rewrites it — without fabricating experience

---

## Resume Validation Layer

SkillForge enforces a strict resume-only upload policy to prevent garbage-in garbage-out analysis. Any PDF that is not a genuine resume is blocked before any LLM call is made.

### How it works

```
Upload PDF
    │
    ▼
[1] PDF-ONLY GATE
    Streamlit uploader: type=["pdf"]
    OS file picker physically blocks .docx, .jpg, .png, etc.
    │
    ▼
[2] TEXT EXTRACTION
    pdfplumber → raw text
    If text < 30 meaningful words → PyMuPDF rasterise → Vision OCR fallback
    │
    ▼
[3] SIGNAL SCORING  (needs ≥ 3 hits from 35 resume keywords)
    education, skills, experience, projects, internship, cgpa, gpa,
    university, linkedin, github, email, phone, python, java, react,
    developer, engineer, analyst, certification, frameworks, tools …
    │
    ▼
[4] NON-RESUME REJECTION  (any single match = instant block)
    "job description", "job posting", "we are looking for",
    "invoice", "purchase order", "terms and conditions",
    "quarterly report", "bibliography", "chapter ", "abstract",
    "dear sir", "to whom it may concern", "privacy policy" …
    │
    ▼
[5] LENGTH GUARD
    < 80 words  → too short to be a resume
    > 6,000 words → report, thesis, or multi-page document
    │
    ▼
PASS → session state updated, analysis proceeds
FAIL → inline error shown, session state untouched (prior valid resume preserved)
```

### Key properties

| Property | Detail |
|---|---|
| **Resume signals** | 35+ keywords covering education, skills, experience, tools |
| **Reject signals** | 20 non-resume document patterns |
| **Word range** | 80 – 6,000 words |
| **State corruption on reject** | 0 — a failed upload never overwrites a previously loaded valid resume |
| **File types accepted** | PDF only |
| **Error display** | Inline red card with specific reason; no page reload |

### Implementation

```python
# main.py — _is_resume() function
RESUME_SIGNALS = [
    "experience", "education", "skills", "projects", "internship",
    "b.tech", "bachelor", "master", "cgpa", "gpa", "university",
    "linkedin", "github", "email", "phone", "developer", "engineer",
    "python", "java", "javascript", "react", "sql", "aws", "docker",
    ...  # 35+ signals total
]

NON_RESUME_SIGNALS = [
    "job description", "job posting", "we are looking for",
    "invoice", "purchase order", "terms and conditions",
    "quarterly report", "bibliography", "chapter ", "abstract",
    ...  # 20 signals total
]

def _is_resume(text: str) -> tuple[bool, str]:
    """Returns (is_resume: bool, reason: str)."""
    text_lower = text.lower()
    word_count = len(text.split())

    # Hard reject on non-resume signals
    for sig in NON_RESUME_SIGNALS:
        if sig in text_lower:
            return False, f'This looks like a "{sig.strip()}" document, not a resume.'

    # Require minimum resume keyword density
    hits = sum(1 for sig in RESUME_SIGNALS if sig in text_lower)
    if hits < 3:
        return False, f"Could not confirm this is a resume ({hits}/3 keywords found)."

    # Length bounds
    if word_count < 80:
        return False, f"File is too short ({word_count} words) to be a resume."
    if word_count > 6000:
        return False, f"File is too long ({word_count} words). Upload just your resume."

    return True, "OK"
```

---

## Demo Scenarios

| Scenario | What it tests |
|---|---|
| 💻 Junior SWE → Mid Full Stack | Long roadmap, many missing skills, seniority gap injection |
| 🧠 Senior DS → Lead AI | Skill decay on NLP/MLOps, strategic modules, high starting fit |
| 👔 HR Coordinator → Manager | Non-tech domain, people management, leadership injection |

---

## Architecture

```
Resume PDF (validated) + Job Description
              │
              ▼
     ┌──────────────────────┐
     │  Resume Validation   │  PDF-only gate → signal scoring → length check
     │  _is_resume()        │  Blocks JDs, invoices, reports, theses
     └────────┬─────────────┘
              │
              ▼
     ┌─────────────────┐
     │   File Parser   │  pdfplumber · python-docx · base64 image
     │                 │  scanned-PDF → PyMuPDF rasterise → vision OCR
     └────────┬────────┘
              │
              ▼
     ┌─────────────────────────────────────┐
     │   Groq LLM Mega Call                │
     │   LLaMA 3.3-70b (text)              │
     │   Llama 4 Scout Vision (images)     │
     └────────┬────────────────────────────┘
              │
              ▼
     ┌─────────────────────────┐
     │  Semantic Skill Matcher  │  sentence-transformers + 60+ regex rules
     │  + Skill Decay Model     │  max(0.5, 1 - years_since/5)
     └────────────┬────────────┘
                  │
                  ▼
     ┌──────────────────────────────────────┐
     │      Adaptive Path Generator         │
     │   NetworkX DAG topological sort      │
     │   Node-weighted DP critical path     │
     └──────────────┬───────────────────────┘
                    │
                    ▼
     ┌──────────────────────────────────────┐
     │   Streamlit UI (5 tabs)              │
     │   Gap · Roadmap · Interview          │
     │   Research · ATS & Export            │
     └──────────────────────────────────────┘
```

---

## Dependency Graph — NetworkX DAG

The 47-course catalog is modelled as a **directed acyclic graph**. Arrows show prerequisite relationships. Topological sort guarantees foundational modules always appear before advanced ones.

![SkillForge 47-Course Dependency DAG](dag.png)

**Color key:** Teal = Python/Data · Purple = ML/AI · Amber = SQL · Orange = DevOps · Blue = Cloud · Green = Web/API · Pink = HR · Mint = Leadership

The adaptive path generator walks this graph using `nx.ancestors()` to pull all required prerequisites, then runs `nx.topological_sort()` on the induced subgraph to determine the correct learning order.

---

## Adaptive Algorithm — Logic Detail

```
1. Collect catalog modules for all Missing + Partial gap skills
2. Walk NetworkX ancestors() to pull prerequisite modules
   → Skip if candidate already has proficiency >= 6 for that prereq
   → MERN Stack → expands to React + JavaScript + REST APIs
3. Build induced subgraph of all needed modules
4. topological_sort() → guarantees foundational-first ordering
5. Node-weighted DP for critical path:
   required_skill_node weight = 10
   prereq_only_node weight    = 1
6. Seniority mismatch → inject LD01/LD02/LD03 leadership modules
7. Separate Groq call for personalized 2-sentence reasoning per module
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **UI Framework** | Streamlit >=1.35.0 |
| **Input Validation** | `_is_resume()` — 35 resume signals, 20 reject signals, word count guard |
| **LLM — Text** | Groq API — LLaMA 3.3-70b-versatile |
| **LLM — Vision** | Groq API — Llama 4 Scout 17B |
| **Skill Matching** | sentence-transformers all-MiniLM-L6-v2 + cosine similarity |
| **Regex Fallback** | 60+ compiled patterns covering SQL, Docker, K8s, NLP, CI/CD |
| **Dependency Graph** | networkx — DiGraph, topological sort, ancestor traversal |
| **PDF Parsing** | pdfplumber + PyMuPDF (scanned PDF rasterisation) |
| **Charts** | Plotly >=5.20 (animated radar, ROI bar, timeline, salary) |
| **PDF Export** | reportlab |
| **Calendar Export** | ICS/iCal — one session/day, 7 PM, weekdays only |

---

## Datasets & Model Citations

| Resource | Source | Usage |
|---|---|---|
| Resume Dataset | [Kaggle — snehaanbhawal](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset/data) | Resume parsing validation |
| O*NET Skills DB | [onetcenter.org](https://www.onetcenter.org/db_releases.html) | Skill taxonomy reference |
| Job Descriptions | [Kaggle — kshitizregmi](https://www.kaggle.com/datasets/kshitizregmi/jobs-and-job-description) | JD parsing testing |
| LLaMA 3.3-70b | Meta via Groq | Skill extraction, ATS audit, reasoning |
| Llama 4 Scout 17B | Meta via Groq | Vision OCR — image & scanned PDF |
| all-MiniLM-L6-v2 | Hugging Face (SBERT) | Semantic skill matching |

---

## Project Structure

```
SkillForge/
├── main.py          <- Streamlit UI — all tabs, rendering, state management
│                      Includes: _is_resume(), RESUME_SIGNALS, NON_RESUME_SIGNALS
├── backend.py       <- Core logic: AI pipeline, DAG, analysis, charts
├── dag.png          <- NetworkX DAG visualization (47-course graph)
├── .env             <- GROQ_API_KEY=gsk_... (never committed)
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.9+
- Free Groq API key → [console.groq.com](https://console.groq.com)

```bash
git clone https://github.com/Sarika-stack23/Skill.git
cd Skill
pip install -r requirements.txt
echo "GROQ_API_KEY=gsk_your_key_here" > .env
streamlit run main.py
```

Opens at **http://localhost:8501**

### Docker

```bash
docker build -t skillforge .
docker run -p 8501:8501 -e GROQ_API_KEY=gsk_your_key_here skillforge
```

---

## Requirements

```
streamlit>=1.35.0
groq>=0.9.0
pdfplumber>=0.10.0
python-docx>=1.1.0
python-dotenv>=1.0.0
plotly>=5.20.0
networkx>=3.3
reportlab>=4.0.0
sentence-transformers>=2.7.0
scikit-learn>=1.4.0
numpy>=1.26.0
ddgs>=9.0.0
```

Optional (for scanned PDF support):
```
PyMuPDF>=1.23.0
Pillow>=10.0.0
```

---