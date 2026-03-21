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

Demo scenarios are available as one-click buttons on the landing page — no file upload needed.

---

## Architecture

```
Resume (PDF / DOCX / Image) + Job Description
              │
              ▼
     ┌─────────────────┐
     │   File Parser   │  pdfplumber · python-docx · base64 image
     │                 │  scanned-PDF → PyMuPDF rasterise → vision OCR
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
     │  + Regex Skill Scanner   │  60+ pattern-based fallback rules
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
     │         Streamlit UI (5 tabs)        │
     │  Gap Analysis · Roadmap              │
     │  Interview Prep · Research           │
     │  ATS & Export                        │
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
| **Charts** | Plotly ≥5.20 (Radar, Bar, Timeline, Salary — animated radar with eased fill) |
| **LLM — Text** | Groq API — LLaMA 3.3-70b-versatile |
| **LLM — Vision** | Groq API — Llama 4 Scout 17B (image resume OCR) |
| **Skill Matching** | `sentence-transformers` all-MiniLM-L6-v2 + cosine similarity |
| **Regex Fallback** | 60+ compiled patterns covering SQL, Docker, K8s, NLP, CI/CD, and more |
| **Dependency Graph** | `networkx` — DiGraph, topological sort, ancestor traversal |
| **PDF Parsing** | `pdfplumber` (text) + PyMuPDF optional (scanned PDF rasterisation) |
| **DOCX Parsing** | `python-docx` |
| **PDF Export** | `reportlab` |
| **Calendar Export** | ICS/iCal — one session/day, 7 PM start, weekdays only |
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
| LLM — Vision | [Llama 4 Scout 17B](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct) via Groq | Image resume OCR + scanned PDF fallback |
| Embeddings | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Semantic skill matching |

---

## Key Features

### Core Pipeline
- **Groq LLM Parsing** — Structured JSON extraction from raw resume and JD text in a single call
- **Vision OCR** — Image resumes (JPG/PNG) and scanned PDFs analyzed via Llama 4 Scout vision model
- **Scanned PDF Fallback** — PyMuPDF rasterises up to 3 pages, stitched vertically, then sent to vision OCR
- **Semantic Skill Matching** — Three-layer: alias dict → substring → cosine similarity (≥0.52 threshold)
- **Regex Skill Scanner** — 60+ compiled patterns applied after every LLM extraction as a safety net
- **Skill Gap Analysis** — Proficiency score (0–10) per skill: Known / Partial / Missing
- **Skill Decay Model** — Skills unused 2+ years: `max(0.5, 1 - years_since/5)`
- **Adaptive Path Generator** — NetworkX topological sort + prerequisite chaining
- **Zero Hallucinations** — All recommendations sourced strictly from the 47-course catalog
- **Dedicated Reasoning** — Separate Groq call generates 2-sentence personalized reasoning per module

### Advanced Features
- **Node-weighted Critical Path** — DP algorithm weights required JD skills at 10x vs prerequisites
- **Interview Readiness Score** — Required known + (partial×0.4) / total, seniority-adjusted
- **ATS Resume Rewrite** — Anti-hallucination prompt: never adds experience not in original resume; no gap admissions
- **Before/After ATS Score** — Quantified improvement shown as a side-by-side comparison
- **Visual Weight Hierarchy** — Gap cards sized by urgency: missing+required (large, glowing), known (subdued)
- **Top 3 Priorities Block** — Always-visible action strip showing the most critical missing skills
- **Business Case Panel** — Train vs hire cost comparison with live salary benchmark
- **Animated Radar Chart** — Eased cubic fill-in animation showing skill gap visually
- **Interview Prep Tab** — AI-generated questions per skill, calibrated to candidate seniority level
- **Peer Percentile** — Candidate ranking based on in-demand skill coverage
- **Transfer Advantages** — Shows how existing skills accelerate learning new ones
- **Progress Persistence** — Completed modules persist via localStorage per candidate+role
- **Weekly Study Plan** — Configurable pace (1/2/4/8h/day), Week 1 expanded by default
- **ROI Ranking** — Modules ranked by demand × required × inverse hours
- **Live Salary Fetch** — DuckDuckGo search → Groq extraction → bar chart + outcome insight on ATS tab
- **Course Finder** — Real links from Coursera, Udemy, YouTube, edX
- **Calendar Export** — .ics file, one session/day at 7 PM, weekdays only, no midnight slots
- **PDF / JSON / CSV Export** — Full roadmap with personalized reasoning

### UI Improvements (v14)
- DAG View tab removed (replaced by inline ROI chart and timeline)
- Shareable link block removed
- Banner redesigned: single 5-metric strip replacing two separate rows
- Landing page: sample scenario buttons as primary CTA with one-click instant demo
- Topbar simplified: Vision OCR chip, Groq chip only
- Research tab: salary + market insights surfaced above the search box
- ATS tab: salary outcome insight box added at top

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
├── .env                 ← GROQ_API_KEY=gsk_... (never committed)
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

> **Note:** The `components/dag_3d.html` Three.js component has been removed in v14.

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

# Optional: scanned PDF support (vision OCR fallback)
pip install PyMuPDF Pillow

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

Optional (for scanned PDF support):
```
PyMuPDF>=1.23.0
Pillow>=10.0.0
```

---

## Evaluation Criteria Coverage

| Criterion | Weight | How Covered |
|---|---|---|
| **Technical Sophistication** | 20% | Semantic matching · NetworkX DAG · skill decay · node-weighted DP critical path · vision OCR · scanned PDF rasterisation · 60+ regex fallback rules |
| **Communication & Docs** | 20% | This README · 5-slide deck · demo video · inline code comments |
| **User Experience** | 15% | Dark UI · animated radar · interview prep tab · one-click demo scenarios · visual urgency hierarchy · loading states · error handling |
| **Grounding & Reliability** | 15% | Catalog-only enforcement · anti-hallucination rewrite prompt · no gap admissions in rewrite · zero fabrication guarantee |
| **Reasoning Trace** | 10% | Dedicated Groq call per module · personalized 2-sentence reasoning · is_critical flag consistency · visible in UI + exports |
| **Product Impact** | 10% | Hours saved · role fit delta · interview readiness % · peer percentile · before/after ATS · business case train vs hire · salary outcome insight |
| **Cross-Domain Scalability** | 10% | Tech + Non-Tech + Soft Skills · 3 demo scenarios · seniority gap injection |

---

*Built with Groq · NetworkX · Streamlit · sentence-transformers · DuckDuckGo*
*ARTPARK CodeForge Hackathon 2025 — v14*