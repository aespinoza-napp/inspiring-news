# News Intelligence Backend

A lightweight backend for ingesting, enriching, fact-checking and storing news articles.

The project is designed around a modular pipeline where every processing stage has a single responsibility.

> **This README describes the project's original scaffold and is out of date** (mocked NLP/fact-checking, a `NewsPipeline`/`agents/` layer that no longer exists, a project structure that doesn't match `src/`). For the actual current architecture, endpoints, and test setup, see `CLAUDE.md` at the repo root instead.

---

# Architecture

```text
                 +------------------+
                 |   FastAPI API    |
                 +---------+--------+
                           |
                           |
                           v
                 +------------------+
                 |   NewsPipeline   |
                 +---------+--------+
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
+---------------+   +---------------+   +---------------+
| NLP Processor |   | Fact Checker  |   | Local Storage |
+---------------+   +---------------+   +---------------+
                           |
                           v
                    JSON Repository
```

The project follows a layered architecture.

| Layer      | Responsibility                    |
| ---------- | --------------------------------- |
| API        | Receives HTTP requests            |
| Workflow   | Coordinates the complete pipeline |
| Processors | Deterministic NLP transformations |
| Agents     | Intelligent reasoning components  |
| Database   | Storage abstraction               |
| Services   | External integrations             |

---

# Project structure

```text
backend/

├── data/
│   └── news/
│
├── src/
│   ├── agents/
│   │   ├── scraper.py
│   │   └── fact_checker.py
│   │
│   ├── api/
│   │   ├── routes.py
│   │   └── scraper.py
│   │
│   ├── database/
│   │   ├── repository.py
│   │   ├── local_repository.py
│   │   └── neo4j_client.py
│   │
│   ├── models/
│   │   ├── news.py
│   │   ├── claim.py
│   │   └── fact_check.py
│   │
│   ├── processors/
│   │   └── nlp.py
│   │
│   ├── services/
│   │
│   ├── workflows/
│   │   └── news_pipeline.py
│   │
│   ├── config.py
│   ├── container.py
│   └── main.py
│
├── dags/
│   └── news_pipeline_dag.py
│
└── tests/
```

---

# Current pipeline

1. Receive a news article.
2. Extract claims.
3. Extract entities.
4. Compute sentiment.
5. Fact-check every claim.
6. Store the enriched article locally.

---

# Example stored document

Every processed article is saved as

```text
data/news/

cnn_2026-07-02_a8f03d2a.json
```

Example

```json
{
  "id": "...",
  "title": "...",
  "source": "cnn",
  "url": "...",
  "published_at": "...",
  "claims": [],
  "fact_checks": [],
  "sentiment": 0.42
}
```

---

# Running the project

Install dependencies

```bash
uv sync
```

Run the API

```bash
uv run uvicorn src.main:app --reload
```

Swagger

```
http://localhost:8000/docs
```

---

# Running tests

```bash
uv run pytest
```

---

# Future work

* spaCy entity extraction
* LangChain integration
* Google Search retrieval
* Neo4j persistence
* OpenAI / Gemini fact checking
* Embeddings
* Airflow scheduling
* Knowledge Graph generation
