"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ConsoleRequest, QueryConsole } from "@/components/graph/QueryConsole";
import { RelatedArticles } from "@/components/graph/RelatedArticles";
import { relKey, SchemaDiagram, SchemaSelection } from "@/components/graph/SchemaDiagram";
import { LABEL_COLOR } from "@/lib/graphStyle";
import {
  GraphArticle,
  GraphPreset,
  GraphSchema,
  GraphSyncReport,
} from "@/lib/types";

type Tab = "schema" | "explore" | "related";

const TABS: { id: Tab; label: string }[] = [
  { id: "schema", label: "Schema" },
  { id: "explore", label: "Explore" },
  { id: "related", label: "Related articles" },
];

// Neo4j's own UI, for anything the console here does not do (writes,
// EXPLAIN plans, saved favourites). Published on the host by
// docker-compose.yml's 7474 mapping.
const NEO4J_BROWSER_URL = process.env.NEXT_PUBLIC_NEO4J_BROWSER_URL ?? "http://localhost:7474";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? data.error ?? `${path} failed (${response.status})`);
  return data as T;
}

export default function GraphPage() {
  const [schema, setSchema] = useState<GraphSchema | null>(null);
  const [presets, setPresets] = useState<GraphPreset[]>([]);
  const [articles, setArticles] = useState<GraphArticle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [tab, setTab] = useState<Tab>("schema");
  const [selection, setSelection] = useState<SchemaSelection | null>(null);
  const [consoleRequest, setConsoleRequest] = useState<ConsoleRequest | null>(null);
  const [relatedUrl, setRelatedUrl] = useState<string | null>(null);

  const [syncing, setSyncing] = useState(false);
  const [syncReport, setSyncReport] = useState<GraphSyncReport | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    // Presets need no database, so the console's starting points show
    // even while Neo4j is down; the other two say why they are empty.
    try {
      const data = await getJson<{ presets: GraphPreset[] }>("/api/graph/presets");
      setPresets(data.presets);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }

    try {
      const [schemaData, articleData] = await Promise.all([
        getJson<GraphSchema>("/api/graph/schema"),
        getJson<{ articles: GraphArticle[] }>("/api/graph/articles?limit=200"),
      ]);
      setSchema(schemaData);
      setArticles(articleData.articles);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The tab lives in the URL (?tab=explore), so a view can be linked to
  // and survives a reload. Read once on arrival; written on every switch.
  //
  // Written in switchTab, not in an effect on `tab`: in dev, Strict Mode
  // runs effects twice on mount, and the write from the first pass put
  // tab=schema back into the URL before the second pass read it.
  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const requested = search.get("tab");
    if (TABS.some((item) => item.id === requested)) setTab(requested as Tab);
    // ?article=<url> opens the related view on that article.
    const article = search.get("article");
    if (article) setRelatedUrl(article);
  }, []);

  function switchTab(next: Tab) {
    setTab(next);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", next);
    window.history.replaceState(null, "", url);
  }

  async function sync() {
    setSyncing(true);
    setError(null);
    try {
      const response = await fetch("/api/graph/sync", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? data.error ?? `Sync failed (${response.status})`);
      setSyncReport(data as GraphSyncReport);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSyncing(false);
    }
  }

  function query(cypher: string, params?: Record<string, string>) {
    setConsoleRequest({ cypher, params, nonce: Date.now() });
    switchTab("explore");
  }

  function showRelated(url: string) {
    setRelatedUrl(url);
    switchTab("related");
  }

  const totals = useMemo(() => {
    if (!schema) return null;
    const count = (label: string) => schema.live.labels[label] ?? 0;
    return {
      nodes: schema.nodes.reduce((sum, node) => sum + count(node.label), 0),
      relationships: schema.live.patterns.reduce((sum, p) => sum + p.count, 0),
      articles: count("Article"),
      claims: count("Claim"),
      entities: count("Entity"),
      sources: count("Source"),
    };
  }, [schema]);

  return (
    <>
      <h1>Graph</h1>
      <p className="subtitle">
        Every analysed article in Neo4j, with the entities and topics it is about, the claims it
        makes, their verdicts, and the sources those verdicts rest on. Hand-labelled facts from the
        labeller land here too, next to the pipeline&apos;s verdict for the same claim.
      </p>

      <div className="stats-toolbar graph-toolbar">
        <div className="stats-totals">
          {totals &&
            (
              [
                ["Articles", totals.articles],
                ["Claims", totals.claims],
                ["Entities", totals.entities],
                ["Sources", totals.sources],
                ["Relationships", totals.relationships],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="stats-total">
                <div className="stats-total-value">{value.toLocaleString()}</div>
                <div className="stats-total-label">{label}</div>
              </div>
            ))}
        </div>
        <div className="graph-toolbar-actions">
          <a className="graph-browser-link" href={NEO4J_BROWSER_URL} target="_blank" rel="noreferrer">
            Open Neo4j Browser ↗
          </a>
          <button type="button" className="graph-secondary" onClick={load} disabled={loading}>
            Refresh
          </button>
          <button
            type="button"
            onClick={sync}
            disabled={syncing}
            title="Configured sources, hand-labelled facts and the lake's verified articles, into the graph. Safe to repeat."
          >
            {syncing && <span className="spinner" aria-hidden="true" />}
            {syncing ? "Syncing…" : "Sync from lake + labels"}
          </button>
        </div>
      </div>

      {syncReport && (
        <p className="graph-wide graph-sync-report">
          Synced {syncReport.sources} sources, {syncReport.facts} hand-labelled facts and{" "}
          {syncReport.articles} analysed articles.
          {syncReport.errors.length > 0 && (
            <span className="stats-bad">
              {" "}
              {syncReport.errors.length} failed: {syncReport.errors.map((e) => e.item).join(", ")}
            </span>
          )}
        </p>
      )}

      {error && <div className="graph-wide error-banner graph-error">{error}</div>}

      <div className="graph-wide graph-tabs" role="tablist" aria-label="Graph views">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`graph-tab${tab === item.id ? " is-active" : ""}`}
            onClick={() => switchTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Hidden rather than unmounted: a query result, a picked article
          and a laid-out graph survive switching tabs. */}
      <div className="graph-wide" hidden={tab !== "schema"}>
        {loading && !schema && (
          <p className="stats-muted">
            <span className="spinner" aria-hidden="true" /> Reading the graph…
          </p>
        )}
        {schema && (
          <div className="schema-layout">
            <div className="card schema-card">
              <SchemaDiagram schema={schema} selected={selection} onSelect={setSelection} />
              <div className="graph-legend">
                <span className="stats-muted">
                  Each circle is a node label and its count; each arrow a relationship and how many
                  exist. Click either.
                </span>
              </div>
            </div>
            <SchemaDetail schema={schema} selection={selection} onQuery={query} />
          </div>
        )}
      </div>

      <div className="graph-wide" hidden={tab !== "explore"}>
        {presets.length > 0 && (
          <QueryConsole
            presets={presets}
            articles={articles}
            request={consoleRequest}
            onRelated={showRelated}
          />
        )}
      </div>

      <div className="graph-wide" hidden={tab !== "related"}>
        <RelatedArticles
          articles={articles}
          url={relatedUrl}
          onPick={setRelatedUrl}
          onShowGraph={(url) =>
            query(presets.find((p) => p.id === "article-neighbourhood")?.cypher ?? "", { url })
          }
        />
      </div>
    </>
  );
}

function SchemaDetail({
  schema,
  selection,
  onQuery,
}: {
  schema: GraphSchema;
  selection: SchemaSelection | null;
  onQuery: (cypher: string) => void;
}) {
  const declared = new Set(schema.relationships.map(relKey));

  // Present in the database, absent from schema.py: written by something
  // other than GraphWriter (a hand-typed query in Neo4j Browser, say).
  const undeclared = schema.live.patterns.filter((p) => !declared.has(relKey(p)));

  if (!selection) {
    return (
      <aside className="card schema-detail">
        <h2>The schema</h2>
        <p className="stats-muted">
          Declared in <code>backend/src/services/graph/schema.py</code>; the counts are what Neo4j
          holds now. Every relationship carries <code>method</code>: <strong>pipeline</strong> for
          what an analysis wrote, <strong>manual</strong> for a hand label, so both verdicts on one
          claim sit side by side.
        </p>

        <p className="section-label">Entity types</p>
        <EntityTypes schema={schema} />

        {undeclared.length > 0 && (
          <>
            <p className="section-label">In the database but not declared</p>
            <ul className="schema-undeclared">
              {undeclared.map((p) => (
                <li key={relKey(p)}>
                  (:{p.from ?? "?"})-[:{p.type}]→(:{p.to ?? "?"}) <span className="stats-muted">{p.count}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </aside>
    );
  }

  if (selection.kind === "node") {
    const node = schema.nodes.find((n) => n.label === selection.label);
    if (!node) return null;

    const outgoing = schema.relationships.filter((r) => r.from === node.label);
    const incoming = schema.relationships.filter((r) => r.to === node.label);
    const counts = new Map(schema.live.patterns.map((p) => [relKey(p), p.count]));

    return (
      <aside className="card schema-detail">
        <h2>
          <span className="graph-swatch" style={{ background: LABEL_COLOR[node.label] }} /> :{node.label}{" "}
          <span className="stats-muted">{(schema.live.labels[node.label] ?? 0).toLocaleString()} nodes</span>
        </h2>
        <p>{node.description}</p>

        <p className="section-label">Properties</p>
        <div className="chip-row">
          {node.properties.map((prop) => (
            <span key={prop} className={`chip${prop === node.key ? " schema-key" : ""}`}>
              {prop}
              {prop === node.key ? " · key" : ""}
            </span>
          ))}
        </div>

        {node.label === "Entity" && (
          <>
            <p className="section-label">Types</p>
            <EntityTypes schema={schema} />
          </>
        )}

        <p className="section-label">Relationships</p>
        <ul className="schema-rel-list">
          {outgoing.map((r) => (
            <li key={relKey(r)}>
              → [:{r.type}] → :{r.to} <span className="stats-muted">{counts.get(relKey(r)) ?? 0}</span>
            </li>
          ))}
          {incoming.map((r) => (
            <li key={relKey(r)}>
              ← [:{r.type}] ← :{r.from} <span className="stats-muted">{counts.get(relKey(r)) ?? 0}</span>
            </li>
          ))}
        </ul>

        <button type="button" onClick={() => onQuery(`MATCH (n:${node.label})\nRETURN n\nLIMIT 50`)}>
          Query these nodes
        </button>
      </aside>
    );
  }

  const rel = selection.rel;
  const count = schema.live.patterns.find((p) => relKey(p) === relKey(rel))?.count ?? 0;
  const methods = schema.live.methods.filter((m) => m.type === rel.type);

  return (
    <aside className="card schema-detail">
      <h2>
        (:{rel.from})-[:{rel.type}]→(:{rel.to}){" "}
        <span className="stats-muted">{count.toLocaleString()}</span>
      </h2>
      <p>{rel.description}</p>

      {rel.properties.length > 0 && (
        <>
          <p className="section-label">Properties</p>
          <div className="chip-row">
            {rel.properties.map((prop) => (
              <span key={prop} className="chip">
                {prop}
              </span>
            ))}
          </div>
        </>
      )}

      {methods.length > 0 && (
        <>
          <p className="section-label">
            By method <span className="section-label-note">(all :{rel.type}, whatever the endpoints)</span>
          </p>
          <div className="chip-row">
            {methods.map((m) => (
              <span key={m.method} className="chip">
                {m.method} <span className="stats-muted">{m.count}</span>
              </span>
            ))}
          </div>
        </>
      )}

      <button
        type="button"
        onClick={() =>
          onQuery(`MATCH p = (:${rel.from})-[:${rel.type}]->(:${rel.to})\nRETURN p\nLIMIT 100`)
        }
      >
        Query these relationships
      </button>
    </aside>
  );
}

function EntityTypes({ schema }: { schema: GraphSchema }) {
  const rows = Object.entries(schema.entityTypes)
    .map(([type, label]) => ({ type, label, count: schema.live.labels[label] ?? 0 }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="chip-row">
      {rows.map((row) => (
        <span key={row.label} className={`chip${row.count === 0 ? " stats-muted" : ""}`}>
          :{row.label} <span className="stats-muted">{row.count}</span>
        </span>
      ))}
    </div>
  );
}
