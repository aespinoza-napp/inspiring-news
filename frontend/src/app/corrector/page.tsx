"use client";

import { useState } from "react";
import { CorrectionReport } from "@/lib/types";
import { ScoreBar } from "@/components/ScoreBar";

const METRICS: { key: keyof CorrectionReport; label: string }[] = [
  { key: "grammar", label: "Grammar" },
  { key: "factConsistency", label: "Fact Consistency" },
  { key: "coverageVerification", label: "Coverage Verification" },
  { key: "seo", label: "SEO" },
  { key: "readability", label: "Readability" },
  { key: "hallucinationIndex", label: "Hallucination Index" },
  { key: "style", label: "Writing Style" },
];

export default function CorrectorPage() {
  const [text, setText] = useState("");
  const [report, setReport] = useState<CorrectionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!text.trim()) return;

    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const response = await fetch("/api/correct", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }

      setReport(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1>Corrector</h1>
      <p className="subtitle">
        Paste a piece of writing to evaluate it across grammar, factual
        consistency, coverage, SEO, readability, hallucination risk and
        writing style.
      </p>

      <form onSubmit={handleSubmit}>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Paste your text here..."
        />
        <div>
          <button type="submit" disabled={loading}>
            {loading ? "Evaluating..." : "Evaluate"}
          </button>
        </div>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {report && (
        <div className="metric-grid">
          {METRICS.map(({ key, label }) => {
            const metric = report[key];

            return (
              <div className="metric-card" key={key}>
                <div className="metric-title">{label}</div>
                <ScoreBar label="Score" value={metric.score} />
                <p className="metric-summary">{metric.summary}</p>
                {metric.issues.length > 0 && (
                  <ul className="metric-issues">
                    {metric.issues.map((issue, index) => (
                      <li key={index}>{issue}</li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
