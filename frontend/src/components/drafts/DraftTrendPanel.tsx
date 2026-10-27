import { DraftAngle, DraftStageProps } from "@/lib/drafts";
import { safeHref } from "@/lib/links";
import { percent } from "@/lib/reader";
import styles from "./DraftTrendPanel.module.css";

/**
 * For a draft whose article came from a trending round
 * (docs/decisions/trends.md): the trend, and every constructive angle the
 * writer model proposed with what the fact-check made of it. A kept angle
 * shows its sources by number, as the body cites them; a refused one says
 * why. Nothing to do here: the angles were found before the text was
 * written, and the writer took one or none.
 */
export function DraftTrendPanel({ draft }: DraftStageProps) {
  const trend = draft.trend;

  if (!trend) return null;

  const number = new Map(draft.sources.map((source, index) => [source.url, index + 1]));
  const link = trend.link ? safeHref(trend.link) : null;
  const video = trend.video?.url ? safeHref(trend.video.url) : null;

  return (
    <section className={`card ${styles.panel}`} aria-labelledby="trend-title">
      <h2 id="trend-title">From a trend</h2>
      <p className={styles.trend}>
        {link ? (
          <a href={link} target="_blank" rel="noopener noreferrer">
            {trend.name}
          </a>
        ) : (
          trend.name
        )}
        <span className={styles.meta}>
          {" "}
          · {trend.signalName || trend.signal}
          {trend.traffic !== null && ` · ${trend.traffic.toLocaleString()}+ searches`}
        </span>
      </p>
      {video && (
        <p className={styles.meta}>
          Its TikTok video goes with the story, behind a click:{" "}
          <a href={video} target="_blank" rel="noopener noreferrer">
            {trend.video?.title || trend.video?.url}
          </a>
        </p>
      )}

      {trend.angleNote && <p className={styles.note}>{trend.angleNote}</p>}

      {trend.angles.length > 0 && (
        <ol className={styles.angles}>
          {trend.angles.map((angle, index) => (
            <Angle key={index} angle={angle} number={number} />
          ))}
        </ol>
      )}
    </section>
  );
}

function Angle({ angle, number }: { angle: DraftAngle; number: Map<string, number> }) {
  const cited = angle.sourceUrls.map((url) => number.get(url)).filter((n): n is number => n !== undefined);

  return (
    <li className={angle.kept ? styles.kept : styles.refused}>
      <span className={styles.badge}>{angle.kept ? "Confirmed" : "Refused"}</span>{" "}
      <strong>{angle.question}</strong>
      <p className={styles.claim}>“{angle.claim}”</p>
      <p className={styles.meta}>
        {angle.reason}
        {angle.verdict && angle.confidence !== null && ` (${angle.verdict}, ${percent(angle.confidence)})`}
        {cited.length > 0 && (
          <>
            {" "}
            Sources:{" "}
            {cited.map((n) => (
              <a key={n} href={`#source-${n}`}>
                [{n}]
              </a>
            ))}
          </>
        )}
      </p>
    </li>
  );
}
