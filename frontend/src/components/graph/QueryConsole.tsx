"use client";

import { KeyboardEvent, useEffect, useMemo, useState } from "react";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import {
  nodeCaption,
  nodeColor,
  primaryLabel,
  safeHref,
  secondaryLabels,
  truncate,
} from "@/lib/graphStyle";
import {
  GraphArticle,
  GraphData,
  GraphNode,
  GraphPreset,
  GraphQueryResult,
} from "@/lib/types";

export interface ConsoleRequest {
  cypher: string;
  params?: Record<string, string>;
  /** Changes on every request, so asking for the same query twice reruns it. */
  nonce: number;
}

const EXPAND = "MATCH (n)-[r]-(m) WHERE elementId(n) = $id RETURN n, r, m LIMIT 60";

/** The `$name` parameters a query uses, in order of first appearance. */
function paramNames(cypher: string): string[] {
  const names: string[] = [];
  const pattern = /\$([A-Za-z_][A-Za-z0-9_]*)/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(cypher)) !== null) {
    if (!names.includes(match[1])) names.push(match[1]);
  }
  return names;
}

function mergeGraphs(a: GraphData, b: GraphData): GraphData {
  const nodes = new Map(a.nodes.map((n) => [n.id, n]));
  for (const node of b.nodes) nodes.set(node.id, node);
  const rels = new Map(a.relationships.map((r) => [r.id, r]));
  for (const rel of b.relationships) rels.set(rel.id, rel);
  return { nodes: Array.from(nodes.values()), relationships: Array.from(rels.values()) };
}

async function runQuery(cypher: string, params: Record<string, string>): Promise<GraphQueryResult> {
  const response = await fetch("/api/graph/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cypher, params }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail ?? data.error ?? `Query failed (${response.status})`);
  }

  return data as GraphQueryResult;
}

export function QueryConsole({
  presets,
  articles,
  request,
  onRelated,
}: {
  presets: GraphPreset[];
  articles: GraphArticle[];
  request: ConsoleRequest | null;
  onRelated: (url: string) => void;
}) {
  const [cypher, setCypher] = useState(presets[0]?.cypher ?? "MATCH (n) RETURN n LIMIT 25");
  const [params, setParams] = useState<Record<string, string>>({});
  const [activePreset, setActivePreset] = useState<string | null>(presets[0]?.id ?? null);

  const [result, setResult] = useState<GraphQueryResult | null>(null);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], relationships: [] });
  const [view, setView] = useState<"graph" | "table">("graph");
  const [selected, setSelected] = useState<GraphNode | null>(null);

  const [running, setRunning] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const names = useMemo(() => paramNames(cypher), [cypher]);

  async function run(
    query = cypher,
    values = params,
    preferred: "graph" | "table" | null = null
  ) {
    setRunning(true);
    setError(null);
    setSelected(null);

    // Only the parameters the query actually names: a leftover `url`
    // from the previous preset is not an error, just noise.
    const used = Object.fromEntries(
      paramNames(query).map((name) => [name, values[name] ?? ""])
    );

    try {
      const data = await runQuery(query, used);
      setResult(data);
      setGraph(data.graph);
      setView(preferred ?? (data.graph.nodes.length > 0 ? "graph" : "table"));
    } catch (exc) {
      setResult(null);
      setGraph({ nodes: [], relationships: [] });
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setRunning(false);
    }
  }

  function pickPreset(preset: GraphPreset) {
    setActivePreset(preset.id);
    setCypher(preset.cypher);

    // A preset that needs an article starts from the most recent one, so
    // clicking it shows something rather than an empty form.
    const next = { ...params };
    for (const param of preset.params ?? []) {
      if (!next[param.name] && param.name === "url" && articles[0]) next[param.name] = articles[0].url;
    }
    setParams(next);

    run(preset.cypher, next, preset.view);
  }

  // Something to look at on arrival: the first preset, run once.
  useEffect(() => {
    if (!request && presets[0]) pickPreset(presets[0]);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!request) return;
    setActivePreset(null);
    setCypher(request.cypher);
    const next = { ...params, ...(request.params ?? {}) };
    setParams(next);
    run(request.cypher, next);
  }, [request?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  async function expand(node: GraphNode) {
    setExpanding(true);
    setError(null);
    try {
      const data = await runQuery(EXPAND, { id: node.id });
      setGraph((current) => mergeGraphs(current, data.graph));
      setView("graph");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setExpanding(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      run();
    }
  }

  return (
    <div className="graph-console">
      <aside className="graph-presets" aria-label="Preset queries">
        <p className="section-label">Presets</p>
        {presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`graph-preset${activePreset === preset.id ? " is-active" : ""}`}
            onClick={() => pickPreset(preset)}
            title={preset.description}
          >
            <span className="graph-preset-title">{preset.title}</span>
            <span className="graph-preset-meta">
              {preset.view === "graph" ? "graph" : "table"}
              {preset.params?.length ? " · needs an article" : ""}
            </span>
          </button>
        ))}
      </aside>

      <section className="graph-editor">
        <label className="field-label" htmlFor="graph-cypher">
          Cypher <span className="stats-muted">(read-only · Ctrl+Enter to run)</span>
        </label>
        <textarea
          id="graph-cypher"
          className="graph-cypher"
          value={cypher}
          spellCheck={false}
          onChange={(event) => {
            setCypher(event.target.value);
            setActivePreset(null);
          }}
          onKeyDown={onKeyDown}
        />

        {names.length > 0 && (
          <div className="graph-params">
            {names.map((name) => (
              <label key={name} className="graph-param">
                <span className="field-label">${name}</span>
                <input
                  type="text"
                  list={name === "url" ? "graph-article-urls" : undefined}
                  value={params[name] ?? ""}
                  onChange={(event) => setParams({ ...params, [name]: event.target.value })}
                  placeholder={name === "url" ? "an article URL - start typing" : ""}
                />
              </label>
            ))}
            <datalist id="graph-article-urls">
              {articles.map((article) => (
                <option key={article.url} value={article.url}>
                  {article.title ?? ""}
                </option>
              ))}
            </datalist>
          </div>
        )}

        <div className="form-row">
          <button type="button" onClick={() => run()} disabled={running || !cypher.trim()}>
            {running && <span className="spinner" aria-hidden="true" />}
            {running ? "Running…" : "Run query"}
          </button>
          {result && (
            <span className="stats-muted graph-result-meta">
              {result.rows.length} row{result.rows.length === 1 ? "" : "s"}
              {result.truncated && ` (first ${result.maxRows} only)`} · {graph.nodes.length} nodes ·{" "}
              {graph.relationships.length} relationships · {result.elapsedMs} ms
            </span>
          )}
        </div>

        {error && <div className="error-banner">{error}</div>}

        {result?.notices.map((notice) => (
          <p key={notice} className="graph-notice">
            {notice}
          </p>
        ))}
      </section>

      {result && (
        <section className="graph-results">
          <div className="graph-view-toggle" role="tablist" aria-label="Result view">
            {(["graph", "table"] as const).map((option) => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={view === option}
                className={`live-toggle${view === option ? " is-active" : ""}`}
                onClick={() => setView(option)}
              >
                {option === "graph" ? "Graph" : "Table"}
              </button>
            ))}
          </div>

          {view === "graph" ? (
            <div className="graph-canvas-row">
              <GraphCanvas data={graph} selectedId={selected?.id ?? null} onSelect={setSelected} />
              {selected && (
                <NodePanel
                  node={selected}
                  expanding={expanding}
                  onExpand={() => expand(selected)}
                  onRelated={onRelated}
                  onClose={() => setSelected(null)}
                />
              )}
            </div>
          ) : (
            <ResultTable result={result} />
          )}
        </section>
      )}
    </div>
  );
}

function NodePanel({
  node,
  expanding,
  onExpand,
  onRelated,
  onClose,
}: {
  node: GraphNode;
  expanding: boolean;
  onExpand: () => void;
  onRelated: (url: string) => void;
  onClose: () => void;
}) {
  const label = primaryLabel(node.labels);
  const extra = secondaryLabels(node.labels);
  const url = label === "Article" ? safeHref(node.properties.url) : null;

  return (
    <aside className="graph-node-panel" aria-label="Selected node">
      <div className="graph-node-panel-head">
        <span className="graph-swatch" style={{ background: nodeColor(node) }} />
        <strong>{label}</strong>
        {extra.map((l) => (
          <span key={l} className="chip">
            {l}
          </span>
        ))}
        <button type="button" className="live-toggle graph-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>

      <p className="graph-node-caption">{nodeCaption(node)}</p>

      <dl className="graph-props">
        {Object.entries(node.properties)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>
                <Value value={value} />
              </dd>
            </div>
          ))}
      </dl>

      <div className="graph-node-actions">
        <button type="button" onClick={onExpand} disabled={expanding}>
          {expanding && <span className="spinner" aria-hidden="true" />}
          Expand neighbours
        </button>
        {url && (
          <button type="button" className="graph-secondary" onClick={() => onRelated(url)}>
            Related articles
          </button>
        )}
      </div>
    </aside>
  );
}

function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="stats-muted">null</span>;

  const href = safeHref(value);
  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className="graph-link">
        {href.replace(/^https?:\/\/(www\.)?/, "")}
      </a>
    );
  }

  if (typeof value === "number") {
    return <span className="stats-number">{Number.isInteger(value) ? value : value.toFixed(3)}</span>;
  }

  if (typeof value === "boolean") return <span>{value ? "true" : "false"}</span>;

  if (typeof value === "string") return <span>{value}</span>;

  if (typeof value === "object" && (value as { kind?: string }).kind === "node") {
    const node = value as GraphNode;
    return (
      <span className="graph-cell-node">
        <span className="graph-swatch" style={{ background: nodeColor(node) }} />
        {primaryLabel(node.labels)} · {truncate(nodeCaption(node), 60)}
      </span>
    );
  }

  if (typeof value === "object" && (value as { kind?: string }).kind === "relationship") {
    return <span className="graph-cell-rel">:{(value as { type: string }).type}</span>;
  }

  if (typeof value === "object" && (value as { kind?: string }).kind === "path") {
    const path = value as { nodes: GraphNode[] };
    return (
      <span className="graph-cell-rel">
        {path.nodes.map((n) => primaryLabel(n.labels)).join(" → ")}
      </span>
    );
  }

  if (Array.isArray(value)) {
    return (
      <span className="graph-cell-list">
        {value.map((item, i) => (
          <span key={i}>
            <Value value={item} />
            {i < value.length - 1 ? ", " : ""}
          </span>
        ))}
      </span>
    );
  }

  return <code className="graph-cell-json">{JSON.stringify(value)}</code>;
}

function ResultTable({ result }: { result: GraphQueryResult }) {
  if (result.rows.length === 0) {
    return <p className="graph-empty">The query returned no rows.</p>;
  }

  return (
    <div className="stats-table-wrap">
      <table className="stats-table graph-table">
        <thead>
          <tr>
            {result.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i}>
              {result.columns.map((column) => (
                <td key={column}>
                  <Value value={row[column]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
