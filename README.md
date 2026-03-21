# SkillForge ⚡ — AI Adaptive Onboarding Engine

> **ARTPARK CodeForge Hackathon 2025**
> Intelligent skill-gap analysis and personalized learning pathway generation — powered by Groq LLaMA 3.3, NetworkX DAG, sentence-transformers, and a custom adaptive algorithm.

---

## The Problem

Corporate onboarding is broken. Everyone gets the same 60-hour curriculum regardless of what they already know. Experienced hires waste time on concepts they mastered years ago. Beginners get overwhelmed by advanced modules out of sequence. Nobody wins.

## The Solution

Upload a **resume** + **job description**. SkillForge:

1. Extracts every skill with proficiency score (0–10) and year last used
2. Applies a **skill decay model** — skills unused 2+ years have proficiency reduced
3. Computes the exact **Known / Partial / Missing** gap against the JD
4. Generates a **dependency-aware learning roadmap** using a NetworkX DAG with topological sort
5. Detects the **critical path** using node-weighted dynamic programming
6. Scores **interview readiness** based on actual required skill coverage
7. Audits the resume for **ATS compliance** and rewrites it — without fabricating experience

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
Resume (PDF / DOCX / Image) + Job Description
              │
              ▼
     ┌─────────────────┐
     │   File Parser   │  pdfplumber · python-docx · base64 image
     └────────┬────────┘
              │ raw text / image_b64
              ▼
     ┌─────────────────────────────────────┐
     │   Groq LLM Mega Call                │
     │   LLaMA 3.3-70b (text)              │
     │   Llama 4 Scout Vision (images)     │
     │   → skills, proficiency, ATS audit  │
     └────────┬────────────────────────────┘
              │
              ▼
     ┌─────────────────────────┐
     │  Semantic Skill Matcher  │  sentence-transformers all-MiniLM-L6-v2
     │  + SKILL_ALIASES dict    │  30+ explicit alias mappings
     │  + Skill Decay Model     │  max(0.5, 1 - years_since/5)
     └────────────┬────────────┘
                  │
                  ▼
     ┌─────────────────────────┐
     │     Gap Analyzer        │  Known (≥7) / Partial (1-6) / Missing (0)
     │  + Seniority Check      │  auto-injects LD01/LD02/LD03 on mismatch
     └────────────┬────────────┘
                  │ Gap Profile
                  ▼
     ┌──────────────────────────────────────┐
     │      Adaptive Path Generator         │
     │   NetworkX DAG topological sort      │
     │   Node-weighted DP critical path     │
     │   Prereq skip for known skills       │
     │   Dedicated reasoning Groq call      │
     └──────────────┬───────────────────────┘
                    │
                    ▼
     ┌──────────────────────────────────────┐
     │         Streamlit UI                 │
     │  Gap Analysis · Roadmap · 3D DAG     │
     │  Interview Prep · Research · Export  │
     └──────────────────────────────────────┘
```

---

## Adaptive Algorithm — Logic Detail

The path generator is **deterministic Python**, not an LLM choosing order:

```
1. Collect catalog modules for all Missing + Partial gap skills
2. Walk NetworkX ancestors() to pull prerequisite modules
   → Skip if candidate already has proficiency ≥ 6 for that prereq skill
   → MERN Stack → expands to React + JavaScript + REST APIs
3. Build induced subgraph of all needed modules
4. topological_sort() → guarantees foundational-first ordering
5. Node-weighted DP for critical path:
   required_skill_node weight = 10
   prereq_only_node weight    = 1
   Trace back from highest-score terminal node
6. Seniority mismatch → inject LD01/LD02/LD03 leadership modules
7. Separate Groq call for personalized 2-sentence reasoning per module
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **UI Framework** | Streamlit ≥1.35.0 |
| **Charts** | Plotly ≥5.20 (Radar, Bar, Timeline, animated) |
| **3D Visualization** | Custom Three.js force-directed DAG (Canvas 2D renderer) |
| **LLM — Text** | Groq API — LLaMA 3.3-70b-versatile |
| **LLM — Vision** | Groq API — Llama 4 Scout 17B (image resume OCR) |
| **Skill Matching** | `sentence-transformers` all-MiniLM-L6-v2 + cosine similarity |
| **Dependency Graph** | `networkx` — DiGraph, topological sort, ancestor traversal |
| **PDF Parsing** | `pdfplumber` |
| **DOCX Parsing** | `python-docx` |
| **PDF Export** | `reportlab` |
| **Web Search** | `ddgs` (DuckDuckGo Search) |
| **Env Management** | `python-dotenv` |

---

## Datasets & Model Citations

All datasets are publicly available and used for testing and skill taxonomy reference only.

| Resource | Source | Usage |
|---|---|---|
| Resume Dataset | [Kaggle — snehaanbhawal/resume-dataset](https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset/data) | Resume parsing validation |
| Occupational Skills Taxonomy | [O*NET OnLine Database](https://www.onetcenter.org/db_releases.html) | Skill taxonomy reference |
| Job Descriptions Dataset | [Kaggle — kshitizregmi/jobs-and-job-description](https://www.kaggle.com/datasets/kshitizregmi/jobs-and-job-description) | JD parsing testing |
| LLM — Text | [LLaMA 3.3-70b-versatile](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) via [Groq](https://groq.com) | Skill extraction, ATS audit, reasoning |
| LLM — Vision | [Llama 4 Scout 17B](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct) via Groq | Image resume OCR |
| Embeddings | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Semantic skill matching |

---

## Key Features

### Core Pipeline
- **Groq LLM Parsing** — Structured JSON extraction from raw resume and JD text in a single call
- **Vision OCR** — Image resumes (JPG/PNG) analyzed via Llama 4 Scout vision model
- **Semantic Skill Matching** — Three-layer: alias dict → substring → cosine similarity (≥0.52 threshold)
- **Skill Gap Analysis** — Proficiency score (0–10) per skill: Known / Partial / Missing
- **Skill Decay Model** — Skills unused 2+ years: `max(0.5, 1 - years_since/5)`
- **Adaptive Path Generator** — NetworkX topological sort + prerequisite chaining
- **Zero Hallucinations** — All recommendations sourced strictly from the 47-course catalog
- **Dedicated Reasoning** — Separate Groq call generates 2-sentence personalized reasoning per module

### Advanced Features
- **Node-weighted Critical Path** — DP algorithm weights required JD skills at 10x vs prerequisites
- **Interview Readiness Score** — Required known + (partial×0.4) / total, seniority-adjusted
- **ATS Resume Rewrite** — Anti-hallucination prompt: never adds experience not in original resume
- **Before/After ATS Score** — Quantified improvement from rewrite
- **3D DAG Visualization** — Three.js force-directed graph of course dependency network
- **Animated Radar Chart** — Eased fill-in animation showing skill gap visually
- **Interview Prep Tab** — AI-generated questions per skill, targeted to proficiency level
- **Peer Percentile** — Candidate ranking based on in-demand skill coverage
- **Transfer Advantages** — Shows how existing skills accelerate learning new ones
- **Progress Persistence** — Completed modules persist via localStorage
- **Weekly Study Plan** — Configurable pace (1–8h/day), week-by-week breakdown
- **ROI Ranking** — Modules ranked by demand × required × inverse hours
- **Live Salary Fetch** — DuckDuckGo search → Groq extraction → chart
- **Course Finder** — Real links from Coursera, Udemy, YouTube, edX
- **PDF / JSON / CSV Export** — Full roadmap with personalized reasoning

---

## Course Catalog — 47 Courses

| Domain | Count | Examples |
|---|---|---|
| **Tech** | 28 | Python, ML, SQL, Docker, Kubernetes, AWS, React, FastAPI, NLP, Deep Learning |
| **Non-Tech** | 13 | HR, Recruitment, Logistics, Finance, Operations, Inventory, Employee Relations |
| **Soft Skills** | 6 | Communication, Leadership, Strategic Thinking, Collaboration, Project Management |

Each course: `id`, `title`, `skill`, `domain`, `level`, `duration_hrs`, `prereqs[]`

---

## Project Structure

```
SkillForge/
├── main.py              ← Streamlit UI — all tabs, rendering, state management
├── backend.py           ← Core logic: AI pipeline, DAG, analysis, charts
├── components/
│   └── dag_3d.html      ← Three.js 3D dependency graph component
├── .env                 ← GROQ_API_KEY=gsk_... (never committed)
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

### Installation

```bash
# 1. Clone
git clone https://github.com/Sarika-stack23/Skill.git
cd Skill

# 2. Install dependencies
pip install -r requirements.txt

# Optional: better semantic matching
pip install sentence-transformers scikit-learn

# 3. Set your Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" > .env

# 4. Run
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

---

## Evaluation Criteria Coverage

| Criterion | Weight | How Covered |
|---|---|---|
| **Technical Sophistication** | 20% | Semantic matching · NetworkX DAG · skill decay · node-weighted DP critical path · vision OCR |
| **Communication & Docs** | 20% | This README · 5-slide deck · demo video · inline code comments |
| **User Experience** | 15% | Dark UI · 3D DAG view · animated radar · interview prep tab · loading states · error handling |
| **Grounding & Reliability** | 15% | Catalog-only enforcement · anti-hallucination rewrite prompt · zero fabrication guarantee |
| **Reasoning Trace** | 10% | Dedicated Groq call per module · personalized 2-sentence reasoning · visible in UI + exports |
| **Product Impact** | 10% | Hours saved · role fit delta · interview readiness % · peer percentile · before/after ATS |
| **Cross-Domain Scalability** | 10% | Tech + Non-Tech + Soft Skills · 3 demo scenarios · seniority gap injection |

---

*Built with Groq · NetworkX · Streamlit · sentence-transformers · Three.js · DuckDuckGo*
*ARTPARK CodeForge Hackathon 2025*