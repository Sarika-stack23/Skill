# SkillForge — AI-Adaptive Onboarding Engine

> **ARTPARK CodeForge Hackathon Submission**
> Personalized, dependency-aware learning roadmaps from a resume + job description — powered by Groq LLaMA 3.3, NetworkX, and semantic skill matching.

---

## What It Does

Upload a resume and a job description. SkillForge:

1. Parses both documents using Groq LLaMA 3.3 to extract structured skill data
2. Applies a **Skill Decay Model** — skills unused for >2 years are automatically downgraded
3. Classifies every JD skill as **Known / Partial / Missing** with a 0–10 proficiency score
4. Generates a **dependency-aware learning roadmap** using NetworkX topological sort
5. Highlights the **critical path** — the longest prerequisite chain that unlocks the most skills
6. Shows a **Role Fit Score** before and after completing the roadmap (e.g. 42 → 87)
7. Detects **seniority mismatches** and auto-injects leadership modules
8. Produces a downloadable **PDF report** with full reasoning traces

All course recommendations come strictly from a fixed catalog — zero hallucinations by design.

---

## Demo

| Scenario | What SkillForge does |
|---|---|
| Junior SWE → Mid Full-Stack role | Long roadmap, foundational modules first, Python → Docker → AWS chain |
| Senior Data Scientist → Lead DS | Short gap, NLP + MLOps flagged as decayed, leadership auto-injected |
| HR Coordinator → HR Manager | Non-tech domain, L&D Strategy + Employee Relations path, seniority warning |

Click **"Try a sample"** in the app to run any of these instantly without uploading files.

---

## Architecture

```
Resume (PDF/DOCX) + Job Description
          │
          ▼
    Text Extraction
    (pdfplumber / python-docx)
          │
          ▼
    Groq LLaMA 3.3 Parser
    → Resume: skills, proficiency 0-10, year_last_used, seniority
    → JD:     required_skills, preferred_skills, seniority_required
          │
          ▼
    Skill Decay Model
    decay_factor = max(0.5, 1 - (years_since / 5))
          │
          ▼
    Gap Analyzer
    Known (≥7) / Partial (1-6) / Missing (0)
    Semantic matching via sentence-transformers cosine similarity
          │
          ▼
    Adaptive Path Generator  ←──── Course Catalog (44 modules, fixed)
    NetworkX topological sort
    Critical path: nx.dag_longest_path()
    Seniority injection: LD01 → LD02 → LD03
          │
          ▼
    Groq LLaMA 3.3 Reasoning
    2-sentence trace per module (parallel, ThreadPoolExecutor)
          │
          ▼
    Plotly Dash UI
    Radar chart · Timeline · Role Fit Score · PDF Export
```

---

## Key Design Decisions

**The adaptive algorithm is original Python logic — not an LLM deciding the order.**
Groq is used only for: (1) parsing text → structured JSON, and (2) writing reasoning traces.
Course recommendations come strictly from the catalog. The sequencing, prioritization, decay calculation, critical path, and seniority injection are all deterministic Python.

**Skill Decay Model** — A unique feature not found in other onboarding tools. A skill used in 2019 but not since is not the same as one used last month. The formula `decay_factor = max(0.5, 1 - (years_since / 5))` reduces proficiency proportionally, with a floor of 50% (skills don't vanish, they get rusty). This makes the gap analysis more realistic and the roadmap more targeted.

**Critical Path** — Using `nx.dag_longest_path()` on the dependency subgraph, the system identifies which modules are on the longest prerequisite chain. These are highlighted in red with a ⚡ badge. Completing critical path modules first unlocks the maximum number of downstream skills.

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| UI | Plotly Dash + Dash Bootstrap Components | Interactive web app, dark/light mode |
| Charts | Plotly Graph Objects | Radar chart, training timeline |
| LLM | Groq API (LLaMA 3.3 70b) | Resume & JD parsing, reasoning traces |
| Semantic Matching | sentence-transformers (all-MiniLM-L6-v2) | Cosine similarity skill matching |
| Dependency Graph | NetworkX | Topological sort, critical path |
| PDF Parsing | pdfplumber | Resume & JD PDF extraction |
| DOCX Parsing | python-docx | Resume DOCX extraction |
| PDF Export | ReportLab | Downloadable roadmap report |
| Env Management | python-dotenv | Secure API key handling |
| Language | Python 3.10+ | 100% Python, single file |

---

## Features

- **Dark / Light mode toggle** — smooth theme switch in the nav bar
- **Skill Decay Model** — skills unused >2 years auto-downgraded with orange badge
- **Role Fit Score** — before vs after delta displayed as a credit-score-style number
- **Seniority Mismatch Warning** — yellow banner + auto leadership module injection
- **Readiness Estimator** — "Ready in ~3 weeks at 2h/day" with live dropdown
- **Critical Path Highlighting** — ⚡ red modules, `nx.dag_longest_path()` powered
- **Domain Color Badges** — Teal=Tech, Yellow=Non-Tech, Purple=Soft on every module card
- **One-Click Sample Inputs** — Junior SWE / Senior DS / HR Manager preloaded
- **Confidence Band on Radar** — pre-decay vs post-decay skill trace, 3-layer radar
- **Parallel reasoning traces** — ThreadPoolExecutor(max_workers=4), ~4× faster
- **PDF export** — full report with impact table, roadmap, gap overview
- **Zero hallucinations** — catalog validator enforced in code, not prompt

---

## Evaluation Criteria Coverage

| Criterion | Weight | How We Address It |
|---|---|---|
| Technical Sophistication | 20% | Semantic matching + NetworkX critical path + Skill Decay Model + proficiency scoring |
| Communication & Documentation | 20% | This README + 5-slide deck + demo video |
| User Experience | 15% | Dash + DBC + dark/light mode + loading spinner + sample inputs + error handling |
| Grounding & Reliability | 15% | Catalog-only recommendations enforced in Python, not prompt |
| Reasoning Trace | 10% | Groq-generated 2-sentence trace per module, visible in expandable cards |
| Product Impact | 10% | Role Fit Score delta + hours saved + readiness estimator |
| Cross-Domain Scalability | 10% | Tech + Non-Tech + Soft catalog, domain badges, 3 demo scenarios |

---

## Setup

### Prerequisites

- Python 3.10 or higher
- A Groq API key — get one free at [console.groq.com](https://console.groq.com)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/skillforge-onboarding.git
cd skillforge-onboarding

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 4. Run the app
python main.py

# 5. Open in browser
# → http://localhost:8050
```

### Docker (optional)

```bash
docker build -t skillforge .
docker run -e GROQ_API_KEY=gsk_your_key_here -p 8050:8050 skillforge
```

---

## Project Structure

```
skillforge/
├── main.py          ← entire application (1349 lines, 14 sections)
├── .env             ← GROQ_API_KEY=gsk_... (never committed)
├── .gitignore       ← ignores .env, __pycache__
├── requirements.txt ← all dependencies
├── Dockerfile       ← container deployment
└── README.md        ← this file
```

### main.py Sections

| Section | Content |
|---|---|
| 1 | Imports, config, API key guard |
| 2 | Course catalog (44 modules) + sample inputs |
| 3 | NetworkX dependency graph |
| 4 | PDF and DOCX text extractors |
| 5 | Groq API — parse_resume, parse_jd, generate_reasoning |
| 6 | Semantic skill matching + pre-computed embeddings |
| 6B | Skill Decay Model |
| 7 | Gap analyzer (Known/Partial/Missing) |
| 7B | Seniority mismatch checker |
| 8 | Adaptive path generator + critical path |
| 9 | Impact scorer + Role Fit Score delta |
| 9B | Readiness estimator |
| 10 | Plotly charts (radar + timeline) |
| 11 | ReportLab PDF export |
| 12 | Dash app layout + CSS (dark/light mode) |
| 13 | All callbacks |
| 14 | Startup |

---

## Course Catalog

44 courses across 3 domains:

| Domain | Skills Covered |
|---|---|
| **Tech** | Python, Data Analysis, ML, Deep Learning, NLP, MLOps, SQL, Docker, Kubernetes, AWS, GCP, React, FastAPI, Cybersecurity, Agile |
| **Non-Tech** | Human Resources, Recruitment, Performance Management, Logistics, Inventory, Finance, Accounting, Budgeting |
| **Soft** | Communication, Leadership, Strategic Planning, Collaboration, Project Management |

Each course has: ID, title, skill, domain, level (Beginner/Intermediate/Advanced), duration in hours, and prerequisite IDs. The catalog is the only source of truth — the LLM never generates course names.

---

## Datasets & Models Cited

| Resource | Usage |
|---|---|
| Groq API — LLaMA 3.3 70b (`llama-3.3-70b-versatile`) | Resume & JD parsing, reasoning trace generation |
| `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) | Skill embedding for cosine similarity matching |
| Custom course catalog | 44 hand-curated modules across Tech/Non-Tech/Soft |
| O*NET Occupational Database | Reference for skill taxonomy design |

---

## requirements.txt

```
dash
dash-bootstrap-components
plotly
groq
pdfplumber
python-docx
python-dotenv
reportlab
sentence-transformers
networkx
scikit-learn
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Your Groq API key — get it at console.groq.com |

---

## License

MIT License — built for the ARTPARK CodeForge Hackathon.

---

*Built with Groq · NetworkX · Plotly Dash · sentence-transformers*