# News Intelligence Graph System

Automated news pipeline: Scraping -> Fact-checking -> Sentiment -> Social Media Formatting -> Neo4j Graph Storage.

> **This README describes the project's original scaffold and is out of date** — fact-checking is real
> (local LLM + SearXNG + Qdrant, not the "next step" described below), Neo4j is configured but unused
> by the actual pipeline, and there's no "social media formatting" stage. For the real architecture,
> see `CLAUDE.md` at the repo root, and the `README.md` in each subdirectory (`backend/src/...`,
> `frontend/src/...`, `docker/`) for that part specifically.

## Features
- **Backend**: FastAPI with `uv` for lightning-fast dependency management.
- **Scraper Agent**: Robust news extraction.
- **NLP Engine**: Sentiment analysis and fact-checking status.
- **Graph DB**: Neo4j relationships based on keywords and metadata.
- **Frontend**: Next.js 14 visualization.

## Setup Local
1. **Inference** (GLiNER, sentiment and embedding models — the backend
   calls this over HTTP and fails on `/analyze` without it, e.g. a
   `WinError 10061`/connection-refused error):
```bash
   cd inference
   uv sync
   uv run uvicorn src.main:app --port 8001
```
2. **Backend**:
```bash
   cd backend
   uv sync
   uv run uvicorn src.main:app --reload
```
3.  Frontend:
```bash
    cd frontend
    npm install && npm run dev
```

## Setup Docker
```bash
    cd docker
    docker-compose up --build
```
Starts `inference` automatically as part of the stack — no manual step
needed. First boot can take several minutes while its models download.

## Health Check

Access http://localhost:8000/health to verify Neo4j and API connectivity.


### Next Steps for you:
1.  **Fact-Checking**: To make it real, connect the `fact_check` method to the **OpenAI API** or **SearchApi** to compare headlines with official sources.
2.  **Scraping Logic**: Implement `BeautifulSoup` inside the scraper agent to target specific news RSS feeds.
3.  **Keywords**: Use `spacy` or `RAKE` (Rapid Automatic Keyword Extraction) to populate the metadata.
