# The WordPress import (17 Nov 2026)

The 187 published posts of `inspiringnews-buenasnoticias.WordPress.2026-11-03.xml`
as the **positive** graph holds them (`source_id = wordpress:inspiringnews.ai`).
Nothing is verified and nothing is written to the graph. The import ran with
`verify=false` on 3 Nov, so each post has its topics, entities and claims and no
verdict. Every post is kept, including the 28 that admission would have turned
away.

Everything is in **`wordpress_import.ipynb`**, which is saved with its outputs, so
it reads without running:

1. Extraction from the graph (a READ session) and the join with the dump's own
   categories and tags
2. The data profile: completeness, distributions, entity noise, admission
3. The dump's own topics: categories and the 169 tags
4. Our labels, with the WordPress ones taken into account: the
   `TAG_TO_TOPIC` / `CATEGORY_TO_GROUP` mapping, the closest topic for the 20
   posts our classifier left without one, and where the two agree
5. Claim statistics for each post
6. Entities: kinds, top names, shared names, bridges, co-occurrence, and the
   network (interactive, every name in `MIN_POSTS`+ posts)
7. How the import sits in the rest of the graph
8. Exports

## Running it

```bash
cd research && uv sync
uv run jupyter lab wordpress-import/wordpress_import.ipynb
```

The notebook reads Neo4j when it is up (credentials from `backend/.env`) and
otherwise `data/graph-export.json`, the last read. Its environment is
`research/pyproject.toml`, separate from the backend's.

## What it found

1. **The data is complete except for topics and tags.** 20 posts get no topic
   from our classifier, and 61 have no WordPress tag. None has a verdict.
2. **Our classifier's confidences are compressed.** The top topic has a median
   confidence of 0.42. In 70 of the 141 posts with two or more topics, the first
   and second are under 0.02 apart. A post carries anywhere from 0 to all 23
   topics.
3. **The site's tags are as much editorial as topical.** The most used tag is
   *Lo más leído* (most read). 119 of the 169 tags are used once. 123 tags map to
   one of our topics, covering 263 of the 376 times a tag is used.
4. **Classifier and WordPress agree on the group for 67% of the posts** that
   have both: 89% in *Medio ambiente*, 81% in *Salud* and 48% in *Ciencia*,
   whose research is often medical. Each of the 20 posts without a topic gets
   one from WordPress: 8 from their tags, 12 from their category.
5. **Claims:**
   - 9.5 per post on average, 1.3 per 100 words.
   - Check-worthiness runs from 0.5 (the floor) to 1.0.
   - 433 of the 1,782 claims carry an opinion marker.
   - Most carry a figure.
   - None was selected for checking.
6. **Places connect the sections.**
   - 1,906 of the 2,063 names appear in one section only.
   - Beyond places, what recurs comes in small clusters around one story: the
     Artemis II crew, Shakira with Karol G, and UNICEF with Pope Francis.
   - The organisations that cross sections (ONU, BBC, NASA) are mostly cited as
     sources.
7. **Entity extraction is noisy in Spanish.**
   - 318 of the 2,383 distinct entities are common nouns.
   - 110 names appear under more than one type.
   - Aliases are not merged (OMS / Organización Mundial de la Salud).
8. **Sentiment does not see the edition.** 167 of 187 posts read as neutral.

## Files

| File | What |
|---|---|
| `wordpress_import.ipynb` | The analysis, with its outputs |
| `data/graph-export.json` | The last read of the graph (the notebook's fallback) |
| `data/wordpress-labels.json` | Each post's categories, tags, WordPress topics and closest topic. The news map reads it (`MAP_GRAPH_LABELS`) |
| `data/articles.csv` | One row per post, with both sets of labels |
| `data/claims_per_article.csv` | Claim statistics for each post |
| `data/entities.csv` | One row per (post, name) |
