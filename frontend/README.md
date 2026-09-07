# Content Tools

> **La sección "Contrato esperado del backend" de abajo está desactualizada** (el endpoint real que usa
> la página `/` es `POST /analyze/jobs` + polling de `GET /analyze/jobs/{jobId}`, no una llamada
> síncrona a `/analyze`, y la forma de la respuesta ha cambiado bastante desde entonces). Para el
> contrato actual, la fuente de verdad es `src/lib/types.ts` (que además ya está declarado como algo a
> mantener sincronizado con el backend). Ver `CLAUDE.md` en la raíz del repo, y
> `src/app/api/README.md`/`src/components/README.md` para el resto del frontend.

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