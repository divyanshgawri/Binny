# AI-Based Career Guidance & Resume Builder

> A dual-purpose platform that pairs a **RAG-powered career counselor** with a **live-updating, multi-agent resume editor** — grounded in verified labor data, not guesswork.

---

## Overview

Finding accurate career advice and formatting a resume shouldn't require expensive counselors or rigid templates. This platform solves both problems:

- **Career Guidance:** Advice anchored to 1,000+ structured occupational profiles from O\*NET and the U.S. Bureau of Labor Statistics via a Retrieval-Augmented Generation (RAG) pipeline — the AI cites real data, not assumptions.
- **Resume Builder:** A coordinated three-agent workflow (Intent Router → Drafter → QA Auditor) that edits your resume with formatting and factual precision, rendered live as an A4 PDF.

---

## Screenshots

| Chat Interface & Career Advice | Live Resume PDF Rendering |
| :---: | :---: |
| ![Chat UI](docs/screenshots/chat_interface.png) | ![Resume Preview](docs/screenshots/live_resume.png) |

| Source Transparency (Proof Widget) | System Architecture |
| :---: | :---: |
| ![Sources](docs/screenshots/sources_widget.png) | ![Architecture](docs/screenshots/architecture.png) |

---

## Key Features

- **Factual, grounded advice** — Retrieves verified BLS and O\*NET data before every response. No hallucinations.
- **Multi-agent resume workflow** — An Intent Router, Drafter, and QA Auditor collaborate on every edit before it reaches your document.
- **Dual-pane experience** — Chat on the left, watch your formatted PDF update in real time on the right.
- **Source transparency** — An expandable "Proof" widget shows the exact occupational files the model read to generate your answer.
- **Persistent sessions** — SQLite backend stores your conversation history so you can pick up exactly where you left off.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| LLM | LLaMA 3.3-70B via Groq API |
| Orchestration | LangChain & LangGraph |
| Vector Database | FAISS |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Frontend | Streamlit |
| Database | SQLite3 |

---

## Repository Structure

```
.
├── schema.py                  # Career Guidance Streamlit app
├── live_resume_app.py         # Resume Builder Streamlit app
├── requirements.txt
├── .env.example
├── job_data_files_clean/      # 1,000+ cleaned occupational profiles (BLS + O*NET)
├── faiss_career_index/        # Pre-compiled FAISS vector index (plug-and-play)
├── notebooks/                 # ETL scripts: scraping, cleaning, chunking (for auditing/extending)
└── database/                  # SQLite schemas and session managers
```

The dataset and FAISS index are included in the repository so you don't need to run any preprocessing before getting started.

---

## Quick Start

Getting the app running locally takes under five minutes.

**1. Clone the repository**

```bash
git clone https://github.com/divyanshgawri/Binny.git
cd career-guidance-resume-builder
```

**2. Set up your environment**

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Add your API key**

Create a `.env` file in the root directory. A free Groq API key is available at [console.groq.com](https://console.groq.com).

```env
GROQ_API_KEY=your_groq_api_key_here
```

**4. Run the application**

```bash
# Career Guidance app
streamlit run schema.py

# Resume Builder app
streamlit run live_resume_app.py
```

---

## How It Works

### RAG Pipeline (Career Guidance)

1. **Ingestion & indexing** — Raw BLS and O\*NET data is cleaned, chunked, and embedded into a FAISS vector index using HuggingFace's `all-MiniLM-L6-v2` model.
2. **Retrieval** — On each query, the system retrieves the most semantically relevant occupational documents from the index.
3. **Grounded generation** — The LLaMA model is constrained to answer *only* using the retrieved documents, eliminating fabricated statistics.

### Agentic Resume Builder

1. **Intent Router** — Determines which section of the resume needs to change.
2. **Drafter** — Rewrites the relevant section professionally, using contextual job data where applicable.
3. **QA Auditor** — Reviews the output for formatting consistency and accuracy before committing it to the live PDF renderer.

---

## License

Distributed under the [MIT License](LICENSE). Free to use for personal projects, research, or portfolio work.

---

## Acknowledgments

- **O\*NET & U.S. Bureau of Labor Statistics** — For the comprehensive, open-source occupational data that powers the RAG pipeline.
- **Groq Cloud** — For the high-speed inference infrastructure that makes the agentic workflow feel real-time.
- **Department of Computer Science, GNDU Amritsar** — For academic support and foundation.
