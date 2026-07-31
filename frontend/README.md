# Content Tools

Next.js (App Router + TypeScript) con dos páginas:

- `/` — Analizador de noticias: pega una o varias URLs, devuelve keywords (≤10),
  entities (≤4), topics (≤6), claims (≤10) y validez (no duplicado + al menos un tema).
- `/corrector` — Evalúa un texto en 7 métricas: Grammar, Fact Consistency,
  Coverage Verification, SEO, Readability, Hallucination Index, Writing Style.

Next.js hace de proxy server-side (`app/api/analyze`, `app/api/correct`) hacia
tu backend, para no exponer su URL/credenciales al navegador.

## Poner en marcha

```bash
npm install
cp .env.local.example .env.local   # y rellena BACKEND_URL
npm run dev
```

## Contrato esperado del backend

**POST `{BACKEND_URL}/analyze`**
```json
// request
{ "urls": ["https://...", "https://..."] }

// response
{
  "results": [
    {
      "url": "https://...",
      "title": "opcional",
      "keywords": ["..."],
      "entities": ["..."],
      "topics": ["..."],
      "claims": ["..."],
      "validity": {
        "isValid": true,
        "isDuplicate": false,
        "hasTopic": true,
        "reasons": []
      }
    }
  ]
}
```

**POST `{BACKEND_URL}/correct`**
```json
// request
{ "text": "..." }

// response — una entrada por métrica, score 0-100
{
  "grammar": { "score": 92, "summary": "...", "issues": ["..."] },
  "factConsistency": { "score": 80, "summary": "..." },
  "coverageVerification": { "score": 75, "summary": "..." },
  "seo": { "score": 68, "summary": "..." },
  "readability": { "score": 88, "summary": "..." },
  "hallucinationIndex": { "score": 95, "summary": "..." },
  "style": { "score": 84, "summary": "..." }
}
```

Ajusta `lib/types.ts` si tu backend devuelve campos distintos.