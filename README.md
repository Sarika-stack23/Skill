# SkillForge ⚡ — AI Adaptive Onboarding Engine

> **ARTPARK CodeForge Hackathon 2025**  
> Intelligent skill-gap analysis and personalized learning pathway generation — powered by Groq LLaMA 3.3, NetworkX DAG, and Plotly.

---

## What It Does

Most corporate onboarding is static — everyone gets the same 60-hour curriculum regardless of what they already know. SkillForge fixes this.

Upload a **resume** and a **job description**. SkillForge extracts skills from both, identifies the exact gap, and generates a **dependency-aware, personalized learning roadmap** — skipping what the candidate already knows and sequencing what they need in the right order.

| Before SkillForge | After SkillForge |
|---|---|
| 60-hour generic onboarding | 20–35 hour personalized roadmap |
| Same path for everyone | Role-fit score + adaptive path per candidate |
| No reasoning for training choices | AI reasoning trace on every module |
| One-size-fits-all | Works for Tech, Non-Tech, and Soft Skills roles |

---

## Live Demo

Try the three built-in demo scenarios:

| Scenario | What It Tests |
|---|---|
| 💻 Junior SWE → Mid Full Stack | Long roadmap, many missing skills, seniority gap |
| 🧠 Senior Data Scientist → Lead DS | Skill decay on NLP/MLOps, strategic modules added |
| 👔 HR Coordinator → HR Manager | Non-tech domain, people management, leadership injection |

---

## Architecture

```
Resume (PDF / DOCX / Image) + Job Description
              │
              ▼
     ┌─────────────────┐
     │   File Parser   │  pdfplumber · python-docx · base64 (images)
     └────────┬────────┘
              │ raw text / image_b64
              ▼
     ┌─────────────────┐
     │   Groq LLM      │  LLaMA 3.3-70b (text) · Llama 4 Scout Vision (images)
     │   Mega Call     │  → structured JSON: skills, proficiency, seniority, audit
     └────────┬────────┘
              │
              ▼
     ┌─────────────────────────┐
     │  Semantic Skill Matcher  │  sentence-transformers cosine similarity
     │  + Skill Decay Model     │  skills unused 2+ years → proficiency reduction
     └────────────┬────────────┘
                  │
                  ▼
     ┌─────────────────────────┐
     │     Gap Analyzer        │  Known / Partial / Missing
     │  + Seniority Check      │  auto-injects leadership modules on mismatch
     └────────────┬────────────┘
                  │ Gap Profile
                  ▼
     ┌──────────────────────────────────────┐
     │      Adaptive Path Generator         │
     │   NetworkX DAG topological sort      │
     │   Critical path detection            │
     │   Dependency chaining (prereq-aware) │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │         Web Research Layer           │  DuckDuckGo (ddgs)
     │  Salary · Skill Trends · Job Market  │  parallel via ThreadPoolExecutor
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │         Streamlit UI                 │
     │  Radar · ROI Bar · Timeline · Export │
     └──────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **UI Framework** | Streamlit |
| **Charts** | Plotly (Radar, Bar, Timeline) |
| **LLM — Text** | Groq API — LLaMA 3.3-70b-versatile |
| **LLM — Vision** | Groq API — Llama 4 Scout 17B (image resume OCR) |
| **Skill Matching** | `sentence-transformers` all-MiniLM-L6-v2 + cosine similarity |
| **Dependency Graph** | `networkx` — DiGraph, topological sort, critical path |
| **PDF Parsing** | `pdfplumber` |
| **DOCX Parsing** | `python-docx` |
| **PDF Export** | `reportlab` |
| **Web Search** | `ddgs` (DuckDuckGo Search) |
| **Env Management** | `python-dotenv` |

---

## Key Features

### Core Pipeline
- **Groq LLM Parsing** — Structured JSON extraction from raw resume and JD text
- **Vision OCR** — Image resumes (JPG/PNG) analyzed via Llama 4 Scout vision model
- **Semantic Skill Matching** — Cosine similarity maps "React.js" → "React", etc.
- **Skill Gap Analysis** — Proficiency score (0–10) per skill: Known / Partial / Missing
- **Adaptive Path Generator** — NetworkX topological sort + prerequisite chaining
- **Zero Hallucinations** — All recommendations sourced strictly from the 47-course catalog
- **AI Reasoning Traces** — 2-sentence explanation per module (parallelized)

### Advanced Features
- **Skill Decay Model** — Skills unused 2+ years: `max(0.5, 1 - years_since/5)`
- **Role Fit Score** — Current fit % → Projected fit % delta
- **Critical Path Highlighting** — `nx.dag_longest_path` identifies the key module chain
- **Seniority Mismatch Detection** — Auto-injects LD01/LD02/LD03 leadership modules
- **Weekly Study Plan** — Configurable pace (1–8h/day), tracks completion
- **Transfer Advantages** — Shows how existing skills accelerate learning new ones
- **ROI Ranking** — Modules ranked by demand × required × inverse hours
- **Live Salary Fetch** — DuckDuckGo search → Groq extraction → chart
- **Course Finder** — Real links from Coursera, Udemy, YouTube, edX
- **ATS Audit** — Score, grade, missing keywords, improvement tips
- **AI Resume Rewrite** — ATS-optimized version with keywords added naturally
- **PDF / JSON / CSV Export** — Full roadmap with reasoning

---

## Adaptive Algorithm — Logic Detail

The path generator is **not** an LLM deciding the order. It runs deterministic Python logic:

```
1. Collect catalog modules for all Missing + Partial skills
2. Walk the NetworkX dependency graph to pull in prerequisite modules
3. Build an induced subgraph of all needed modules
4. Run topological sort → guarantees foundational-first ordering
5. Detect critical path (longest dependency chain) → highlighted red
6. Score: required gaps first, then ascending proficiency
7. Seniority mismatch → inject LD01/LD02/LD03 leadership modules
```

---

## Course Catalog — 47 Courses

| Domain | Count | Examples |
|---|---|---|
| **Tech** | 28 | Python, ML, SQL, Docker, Kubernetes, AWS, React, FastAPI, NLP |
| **Non-Tech** | 13 | HR, Recruitment, Logistics, Finance, Operations |
| **Soft Skills** | 6 | Communication, Leadership, Strategic Thinking, Collaboration |

Each course has: `id`, `title`, `skill`, `domain`, `level`, `duration_hrs`, `prereqs[]`

---

## Project Structure

```
Skill/
├── main.py          ← Standalone single-file version (v10)
├── app.py           ← Streamlit UI (v11 split version)
├── backend.py       ← Core logic, AI, charts, analysis engine (v11)
├── .env             ← GROQ_API_KEY=... (never committed)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.9+
- Free Groq API key → [console.groq.com](https://console.groq.com)

### Installation

```bash
# 1. Clone
git clone https://github.com/Sarika-stack23/Skill.git
cd Skill

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 4. Run (single file version)
streamlit run main.py

# OR run the split version
streamlit run app.py
```

Opens at **http://localhost:8501**

### Optional: Better Semantic Matching

```bash
pip install sentence-transformers scikit-learn
```

Falls back to substring matching if not installed.

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

---

## How to Use

1. **Upload your resume** — PDF, DOCX, or image (JPG/PNG)
2. **Paste a job description** — copy from LinkedIn, Naukri, or any job board
3. **Select salary location** — India, USA, UK, etc.
4. **Tick "Force fresh"** — recommended for first-time uploads
5. **Click Analyze ⚡** — takes ~10–20 seconds
6. **Explore your results:**
   - **Gap Analysis** — see exactly which skills are Known / Partial / Missing
   - **Roadmap** — dependency-ordered modules with AI reasoning
   - **Research** — live salary data, course links, market trends
   - **ATS & Export** — resume rewrite + PDF/JSON/CSV download

---

## Datasets & Model Citations

| Resource | Source | Usage |
|---|---|---|
| Resume Dataset | [Kaggle — snehaanbhawal](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset/data) | Testing |
| Occupational Skills | [O*NET OnLine Database](https://www.onetcenter.org/db_releases.html) | Skill taxonomy reference |
| Job Descriptions | [Kaggle — kshitizregmi](https://www.kaggle.com/datasets/kshitizregmi/jobs-and-job-description) | JD testing |
| LLM | LLaMA 3.3-70b + Llama 4 Scout via [Groq](https://groq.com) | Parsing + reasoning + OCR |
| Embeddings | `all-MiniLM-L6-v2` via [sentence-transformers](https://www.sbert.net) | Semantic skill matching |

---

## Evaluation Criteria Coverage

| Criterion | Weight | How Covered |
|---|---|---|
| Technical Sophistication | 20% | Semantic matching · NetworkX DAG · skill decay · vision OCR |
| Communication & Docs | 20% | This README · inline code comments |
| User Experience | 15% | Dark UI · loading states · error messages · reset button |
| Grounding & Reliability | 15% | Catalog-only enforcement · zero hallucination guarantee |
| Reasoning Trace | 10% | Groq-generated per module · visible in UI |
| Product Impact | 10% | Hours saved · role fit delta · interview readiness % |
| Cross-Domain Scalability | 10% | Tech + Non-Tech + Soft all supported |

---

## CLI Mode (main.py only)

```bash
python main.py --analyze junior_swe
python main.py --analyze senior_ds
python main.py --analyze hr_manager
```

---

## Built By

**Sarika Jivrajika**  
B.Tech Computer Science Engineering — Jain University, Bengaluru (2027)  
GenAI Developer Intern @ HiDevs · GitHub: [@Sarika-stack23](https://github.com/Sarika-stack23)

---

*Built with Groq · NetworkX · Streamlit · sentence-transformers · DuckDuckGo*  
*ARTPARK CodeForge Hackathon 2025*