# Project Coin Flip

Project Coin Flip is a deterministic job targeting and ATS optimization engine.

It identifies high-value job postings early, evaluates them against a candidate profile, and generates tailored, ATS-aligned resumes using controlled LLM workflows.

---

## 🧠 Problem

Modern hiring pipelines are dominated by Applicant Tracking Systems (ATS) that:

- Filter candidates using keyword and structure-based scoring
- Penalize generic resumes
- Require per-role customization at scale

Most tools attempt to solve this with:
- Resume scoring
- Spray-and-pray auto apply
- Generic AI rewriting

They fail because they do not enforce **truth constraints** or **precise requirement alignment**.

---

## 🎯 Solution

Project Coin Flip treats job applications as a **matching and transformation problem**, not a writing problem.

It combines deterministic filtering with controlled AI generation to:

1. Detect relevant job postings in near real-time
2. Score roles based on content relevance, not just titles
3. Map job requirements to verified candidate experience
4. Generate resumes that mirror job language without fabricating experience

---

## ⚙️ System Architecture
Job Boards (Greenhouse API)
↓
Normalization Layer
↓
Title + Location Filters
↓
Content Scoring Engine
↓
Top-N Job Selection
↓
LLM Resume Generation (Constrained)
↓
Schema Validation + Output

---

## 🔍 Core Components

### 1. Job Ingestion
- Pulls live job postings via Greenhouse API
- Normalizes title, location, content, and metadata

### 2. Deterministic Filtering
- Title keyword inclusion/exclusion
- Location gating (Remote US / NC hybrid/onsite)
- Eliminates noise before AI is used

### 3. Content Scoring Engine
- Weighted keyword model:
  - High-value signals (e.g. threat intelligence, SIEM, EDR)
  - Medium signals (program ownership, IAM, automation)
  - Negative signals (irrelevant domains like frontend, sales)

- Produces:
  - `content_score`
  - `strong_match | review | reject`

### 4. Resume Transformation Engine
- Maps job requirements → verified candidate evidence
- Enforces strict constraints:
  - No hallucinated experience
  - No inferred skills
  - All claims must trace to source evidence

### 5. Structured Output
Generates schema-validated JSON including:
- Tailored experience bullets
- Requirement-to-evidence mapping
- Confidence scoring
- Explicit rejection of unsupported requirements

---

## 🔐 Design Principles

- **Deterministic before AI**
- **Truth-bound generation**
- **No hallucinations, ever**
- **Traceability of every claim**
- **Schema-enforced outputs**

---

## 📁 Project Structure
project-coin-flip/
│
├── src/
│ └── coin_flip_engine.py
│
├── data/
│ ├── boards.json
│ ├── title_keywords.json
│ └── README.md
│
├── requirements.txt
├── config.example.env
├── .gitignore
└── README.md

---

## 🛠️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
-------------------------------------------------------------------------------------------------------------------
⚠️ Notes on Data

Some components are intentionally excluded from this repository:

candidate_truth_source.json
keyword_phrase_map.json

These files contain structured candidate evidence and mapping logic used to enforce truth-bound resume generation.

They are not included to preserve data integrity and prevent misuse.

📈 Current Capabilities
Multi-board job ingestion (Greenhouse)
Keyword + location filtering
Content-based scoring engine
Top-N job selection for processing
Constrained LLM resume generation pipeline

🚧 Roadmap
Additional job board integrations
Semantic matching via embeddings
UI dashboard for job review
Automated application workflows
Feedback loop for scoring optimization

🧪 Purpose

This project was built to demonstrate:

Applied AI system design under constraints
Deterministic + probabilistic hybrid workflows
Real-world automation against imperfect systems (ATS)

⚠️ Disclaimer

This project is intended for educational and personal use.

It is not designed to bypass hiring systems, but to demonstrate how structured, truthful data can be aligned with automated evaluation pipelines.
