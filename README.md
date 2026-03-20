# SkillForge — AI-Adaptive Onboarding Engine

> **ARTPARK CodeForge Hackathon Submission**
> Intelligent skill-gap analysis and personalized learning pathway generation — powered by Groq LLaMA 3.3, NetworkX, and Plotly Dash.

---

## What It Does

Most corporate onboarding is static — everyone gets the same 60-hour curriculum regardless of what they already know. SkillForge fixes this.

Upload a **resume** and a **job description**. SkillForge extracts skills from both, identifies the exact gap, and generates a **dependency-aware, personalized learning roadmap** — skipping what the candidate already knows and sequencing what they need in the right order.

| Before SkillForge | After SkillForge |
|---|---|
| 60-hour generic onboarding | 20–35 hour personalized roadmap |
| Same path for junior and senior | Role-fit score + adaptive path per candidate |
| No reasoning for training choices | AI reasoning trace on every module |
| One-size-fits-all | Works for Tech, Non-Tech, and Hybrid roles |

---

## Architecture

```
Resume (PDF/DOCX) + Job Description
          │
          ▼
   ┌─────────────┐
   │  PDF/DOCX   │  pdfplumber · python-docx
   │   Parser    │
   └──────┬──────┘
          │ raw text
          ▼
   ┌─────────────┐
   │  Groq LLM   │  LLaMA 3.3-70b
   │   Parser    │  → structured JSON: skills, proficiency, seniority
   └──────┬──────┘
          │
          ▼
   ┌─────────────────────┐
   │   Semantic Matcher  │  sentence-transformers cosine similarity
   │   + Skill Decay     │  skills unused 2+ years → proficiency reduction
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │    Gap Analyzer     │  Known / Partial / Missing
   │  + Seniority Check  │  auto-injects leadership modules on mismatch
   └──────────┬──────────┘
              │ Gap Profile
              ▼
   ┌─────────────────────────────────────────┐
   │      Adaptive Path Generator            │
   │   NetworkX DAG topological sort         │  ← Original algorithm
   │   Critical path detection               │
   │   Dependency chaining (prereq-aware)    │
   └──────────────────┬──────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────┐
   │         Groq Reasoning Tracer           │  parallel via ThreadPoolExecutor
   │  "Why this module?" per recommendation  │
   └──────────────────┬──────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────┐
   │           Plotly Dash UI                │
   │  Radar Chart · Timeline · Role Fit Score│
   │  Impact Card · PDF Export               │
   └─────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **UI Framework** | Plotly Dash 4 + Dash Bootstrap Components 2 |
| **Charts** | Plotly (Radar chart, horizontal bar timeline) |
| **LLM** | Groq API — LLaMA 3.3-70b-versatile |
| **Skill Matching** | `sentence-transformers` (all-MiniLM-L6-v2) + cosine similarity |
| **Dependency Graph** | `networkx` — DiGraph, topological sort, critical path |
| **PDF Parsing** | `pdfplumber` |
| **DOCX Parsing** | `python-docx` |
| **PDF Export** | `reportlab` |
| **Env Management** | `python-dotenv` |

---

## Key Features

### Core Pipeline
- **Groq LLM Parsing** — Structured JSON extraction from raw resume and JD text
- **Semantic Skill Matching** — Cosine similarity maps "React.js" → "Frontend Development", etc.
- **Skill Gap Analysis** — Proficiency score (0–10) per skill; Known / Partial / Missing classification
- **Adaptive Path Generator** — Original algorithm using NetworkX topological sort + prerequisite chaining
- **Zero Hallucinations** — All recommendations come strictly from the pre-loaded course catalog; LLM never names courses
- **Groq Reasoning Traces** — AI-generated 2-sentence explanation per module (parallelized via ThreadPoolExecutor)

### Advanced Features (v2)
- **Skill Decay Model** — Skills unused for 2+ years have proficiency reduced via decay formula: `max(0.5, 1 - years_since/5)`
- **Role Fit Score** — Current fit % → Projected fit % delta, displayed as a before/after score card
- **Critical Path Highlighting** — NetworkX `dag_longest_path` identifies the most important module chain
- **Seniority Mismatch Detection** — Auto-injects leadership/strategy modules when candidate level < required level
- **Readiness Estimator** — "Ready in X weeks at Y hours/day" calculator
- **Domain Color Badges** — Tech (teal) / Non-Tech (yellow) / Soft (purple) on every module card
- **Dark / Light Mode** — Clientside toggle, instant switch
- **One-Click Sample Inputs** — 3 preset demo scenarios: Junior SWE, Senior Data Scientist, HR Manager
- **PDF Report Export** — Full roadmap with impact table, module reasoning, and skill gap overview

---

## Adaptive Algorithm — Logic Detail

The path generator is **not** an LLM deciding the order. It runs custom Python logic:

```
1. Collect catalog modules for all Missing + Partial skills
2. Walk the NetworkX dependency graph to pull in any prerequisite
   modules the candidate doesn't already have
3. Build an induced subgraph of all needed modules
4. Run topological sort → guarantees foundational-first ordering
5. Detect critical path (longest dependency chain) → highlighted in red
6. Score each module: required-gap first, then ascending proficiency
7. If seniority mismatch detected → inject LD01/LD02/LD03 leadership modules
```

This produces a guaranteed-valid, dependency-aware sequence every time — not a stochastic LLM guess.

---

## Course Catalog

The system contains **47 pre-loaded courses** across 5 domains:

| Domain | Courses | Examples |
|---|---|---|
| **Tech** | 28 | Python, ML, SQL, Docker, Kubernetes, AWS, React, FastAPI |
| **Non-Tech** | 13 | HR, Recruitment, Logistics, Finance, Operations |
| **Soft Skills** | 6 | Communication, Leadership, Strategic Thinking |

Each course has: `id`, `title`, `skill`, `domain`, `level`, `duration_hrs`, `prereqs[]`

All recommendations come **strictly from this catalog**. The LLM is never asked to name a course.

---

## Evaluation Criteria Coverage

| Criterion | Weight | Coverage |
|---|---|---|
| Technical Sophistication | 20% | Semantic matching · NetworkX graph · proficiency scoring · skill decay |
| Communication & Documentation | 20% | This README · demo video · 5-slide deck |
| User Experience | 15% | Dash + DBC · charts · dark/light mode · loading states · error messages |
| Grounding & Reliability | 15% | Catalog-only enforcement in code · confidence thresholds |
| Reasoning Trace | 10% | Groq-generated per module · visible in UI accordion |
| Product Impact | 10% | Hours saved · role readiness % · fit delta displayed |
| Cross-Domain Scalability | 10% | Tech + Non-Tech + Soft all in catalog · domain auto-detection |

---

## Setup

### Prerequisites
- Python 3.9+
- A Groq API key — get one free at [console.groq.com](https://console.groq.com)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/Sarika-stack23/Skill.git
cd Skill

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 4. Run
python main.py
```

Open your browser at **http://localhost:8050**

### Optional: Better Semantic Matching

For higher-quality skill matching (recommended):

```bash
pip install sentence-transformers scikit-learn
```

If not installed, the system automatically falls back to substring matching.

---

## Requirements

```
dash
dash-bootstrap-components
plotly
groq
pdfplumber
python-docx
python-dotenv
reportlab
networkx
sentence-transformers   # optional but recommended
scikit-learn            # required with sentence-transformers
```

---

## Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8050
CMD ["python", "main.py"]
```

```bash
docker build -t skillforge .
docker run -e GROQ_API_KEY=gsk_your_key -p 8050:8050 skillforge
```

---

## Project Structure

```
Skill/
├── main.py            ← Entire application (single file, 1482 lines)
├── .env               ← GROQ_API_KEY=... (never committed)
├── .gitignore         ← Excludes .env
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Demo Scenarios

Three one-click sample inputs are built into the UI:

| Scenario | What It Tests |
|---|---|
| 👨‍💻 Junior SWE → Mid Full Stack | Long roadmap, many missing skills, seniority gap detected |
| 🧠 Senior Data Scientist → Lead DS | Short roadmap, skill decay on NLP/MLOps, strategic modules added |
| 👔 HR Coordinator → HR Manager | Non-tech domain, people management, leadership injection |

---

## Datasets & Model Citations

| Resource | Source | Usage |
|---|---|---|
| Resume Dataset | [Kaggle — snehaanbhawal](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset/data) | Testing & validation |
| Occupational Skills | [O*NET OnLine Database](https://www.onetcenter.org/db_releases.html) | Skill taxonomy reference |
| Job Descriptions | [Kaggle — kshitizregmi](https://www.kaggle.com/datasets/kshitizregmi/jobs-and-job-description) | JD testing |
| LLM | LLaMA 3.3-70b-versatile via [Groq](https://groq.com) | Parsing + reasoning |
| Embedding Model | `all-MiniLM-L6-v2` via [sentence-transformers](https://www.sbert.net) | Semantic skill matching |

---

## License

MIT License — built for the ARTPARK CodeForge Hackathon 2025.

---

*Built with Groq · NetworkX · Plotly Dash · sentence-transformers*