# News Pipeline

A scalable, microservice-based news aggregation and publishing system.

---

## Pipeline Overview

```
Source Management      →  define and monitor trusted sources
      ↓
News Collection        →  crawl / poll sources for new articles
      ↓
Validation & Fact Check→  score credibility, cross-reference claims
      ↓
Content Enrichment     →  NLP: entities, sentiment, keywords, summary
      ↓
Content Transformation →  reformat per channel (web, RSS, social, newsletter)
      ↓
Media Selection        →  find and score relevant images / video
      ↓
Quality Assurance      →  automated checks + optional human review
      ↓
Publishing             →  dispatch to channels, generate public URL
      ↓
Analytics & Feedback   →  track engagement, feed back into source scores
```

> **Two steps not shown in some pipelines that are included here:**
> - **NLP / Enrichment** is kept as its own service (`nlp-service`) and called by `content-service`, because NLP models are compute-heavy and should scale independently.
> - **Analytics → Source feedback loop**: performance metrics are wired back to `source-service` to update `reputation_score` automatically over time.

---

## Repository Structure

```
news-pipeline/
│
├── shared/
│   └── types/
│       └── models.ts          ← All domain types (NewsArticle, Source, MediaAsset, Publication)
│
├── backend/
│   ├── shared/
│   │   └── utils/
│   │       └── BaseService.ts ← THE single base class all services extend
│   │
│   ├── config/                ← Environment configs, channel templates, editorial policies
│   │
│   └── services/
│       ├── source/            → port 3001
│       ├── news/              → port 3002
│       ├── fact-check/        → port 3003
│       ├── nlp/               → port 3004
│       ├── content/           → port 3005
│       ├── media/             → port 3006
│       ├── qa/                → port 3007
│       ├── publishing/        → port 3008
│       └── analytics/         → port 3009
│
├── frontend/                  ← Next.js app (one page per pipeline stage)
│   ├── app/
│   │   ├── source-management/
│   │   ├── news-collection/
│   │   ├── fact-checking/
│   │   ├── enrichment/
│   │   ├── transformation/
│   │   ├── media/
│   │   ├── qa/
│   │   ├── publishing/
│   │   └── analytics/
│   ├── components/
│   │   ├── shared/            ← Reusable UI (tables, cards, status badges)
│   │   └── workflow/          ← Pipeline diagram, step indicators
│   └── lib/
│       ├── api/               ← One file per service: sourceApi.ts, newsApi.ts, etc.
│       ├── types/             ← Frontend-specific types (re-exports from shared/)
│       └── utils/
│
├── docker-compose.yml
├── package.json
└── tsconfig.json
```

---

## The One Class You Need to Understand

Every backend microservice is one file that extends `BaseService`:

```ts
// backend/shared/utils/BaseService.ts
abstract class BaseService {
  protected app: express.Application   // Express instance, pre-configured
  protected config: ServiceConfig      // name, port, dependencies

  abstract registerRoutes(): void      // ← implement this in each service

  protected ok(res, data)              // send success response
  protected fail(res, message, code)   // send error response
  protected callService(key, path)     // call another service by name
  protected asyncRoute(fn)             // wrap async handlers safely
}
```

To create a new service, you only need:

```ts
class MyService extends BaseService {
  constructor() {
    super({ name: "my-service", port: 3010, dependencies: { ... } });
  }
  protected registerRoutes() {
    this.app.get("/items", this.asyncRoute(async (req, res) => {
      this.ok(res, { items: [] });
    }));
  }
}
new MyService().start();
```

---

## What You Must Implement (in order of priority)

### 1. Database layer — `backend/shared/database/`

All services currently use in-memory Maps. Replace them with a real DB client.

**Recommended:** PostgreSQL + Prisma ORM.

```
backend/shared/database/
├── prisma.ts        ← PrismaClient singleton
└── schema.prisma    ← define Source, NewsArticle, MediaAsset, Publication, Metrics tables
```

Every service then replaces `this.articles.get(id)` with `prisma.newsArticle.findUnique(...)`.

### 2. News Collection — `backend/services/news/index.ts`

The `triggerCollection` handler is stubbed. Implement:
- RSS parsing (`rss-parser` npm package)
- HTML scraping (`playwright` or `cheerio` for simpler sites)
- Deduplication by URL hash before inserting

### 3. NLP — `backend/services/nlp/index.ts`

The `analyzeText` handler returns nulls. Connect one provider:
- **Easiest**: OpenAI (`gpt-4o-mini`) with a structured output prompt for sentiment + entities + summary
- **Free/self-hosted**: Hugging Face Inference API or spaCy running as a Python sidecar

### 4. Fact Checking — `backend/services/fact-check/index.ts`

Options (cheapest first):
- Google Fact Check Tools API (free, limited)
- ClaimBuster API
- LLM-based: send article + context to GPT and ask for a credibility assessment

### 5. Media Selection — `backend/services/media/index.ts`

Connect at least one image source:
- Unsplash API (free, attribution required)
- Getty / AP / Reuters (editorial licensing, paid)

### 6. Content Transformation — `backend/services/content/index.ts`

Create channel templates in `backend/config/channels.ts`:
```ts
export const channelTemplates = {
  web:        (article) => ({ html: renderHTMLTemplate(article) }),
  rss:        (article) => ({ xml: renderRSSItem(article) }),
  newsletter: (article) => ({ mjml: renderEmailTemplate(article) }),
  social:     (article) => ({ text: `${article.title} ${article.published_url}` }),
};
```

### 7. Publishing Adapters — `backend/services/publishing/index.ts`

Wire up adapters per channel. Each adapter gets the transformed payload and returns a `published_url`:
- **web**: WordPress REST API, Contentful, or a custom CMS
- **social**: Twitter/X API v2, Facebook Graph, LinkedIn
- **newsletter**: Mailchimp, SendGrid, Resend
- **rss**: write to a static file served from a CDN

### 8. Frontend pages — `frontend/app/*/page.tsx`

Each page talks to exactly one service. Scaffold each as:
```tsx
// frontend/lib/api/sourceApi.ts  ← one file per service
export const sourceApi = {
  list: () => fetch(`${process.env.NEXT_PUBLIC_SOURCE_SERVICE_URL}/sources`).then(r => r.json()),
  create: (data) => fetch(..., { method: "POST", body: JSON.stringify(data) }).then(r => r.json()),
};
```

---

## Service Map

| Service | Port | Stage | Key env vars to add |
|---|---|---|---|
| source-service | 3001 | Source Management | `DATABASE_URL` |
| news-service | 3002 | News Collection | `DATABASE_URL`, RSS/scraping config |
| fact-check-service | 3003 | Validation | `FACT_CHECK_API_KEY` |
| nlp-service | 3004 | Enrichment | `OPENAI_API_KEY` or `HF_API_KEY` |
| content-service | 3005 | Transformation | channel template config |
| media-service | 3006 | Media Selection | `UNSPLASH_ACCESS_KEY`, `GETTY_API_KEY` |
| qa-service | 3007 | Quality Assurance | `LANGUAGE_TOOL_URL` |
| publishing-service | 3008 | Publishing | `CMS_API_KEY`, `TWITTER_API_KEY`, `REDIS_URL` |
| analytics-service | 3009 | Analytics | `DATABASE_URL` |
| frontend | 3000 | All stages | All `NEXT_PUBLIC_*_SERVICE_URL` vars |

---

## Running Locally

```bash
# Start everything with Docker
docker-compose up --build

# Or run one service at a time (Node 18+ required)
npm install
npm run dev:source
npm run dev:news
# etc.
```

Health check for any service:
```bash
curl http://localhost:3001/health
```

---

## Notes on the Workflow Design

**Steps that were considered but not added as separate services:**

- **Duplicate detection** — handled inside `news-service` before insertion, not a separate stage, since it's a write-side concern tied to ingestion.
- **Translation** — lives inside `content-service` as an optional step per channel, not a standalone stage, because it depends on knowing the target channel's language requirements.
- **Archiving / cold storage** — handled at the DB/infrastructure level (S3, Glacier), not a pipeline stage. Add a cron job in `scripts/` when needed.

**The feedback loop from Analytics back to Source Management** is the most important architectural decision: `analytics-service` aggregates per-source performance and periodically PATCHes `reputation_score` on `source-service`. This makes the pipeline self-improving over time without human intervention.
