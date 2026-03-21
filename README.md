# SkillForge ⚡ — AI Adaptive Onboarding Engine

> Intelligent skill-gap analysis and personalized learning pathway generation — powered by Groq LLaMA 3.3, NetworkX DAG, sentence-transformers, and a custom adaptive algorithm.

## 🚀 Live Demo

**Try it now → [skill-forge-345.streamlit.app](https://skill-forge-345.streamlit.app/)**

No setup needed. Click any demo scenario on the landing page for instant results.

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