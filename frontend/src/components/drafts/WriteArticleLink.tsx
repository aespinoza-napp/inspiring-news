import Link from "next/link";
import styles from "./WriteArticleLink.module.css";

/**
 * "Write an article" from a finished analysis, on the operator's pages
 * (Analyze, Live). Shown only for a run the reader publishes, because
 * that is the only kind a draft can start from (docs/decisions/writing.md).
 * By URL, not reader id: the analysis result carries the URL, and the
 * backend matches it the way the reader does (host and path).
 *
 * Never on /reader or /reader/[id]: those pages are public (Caddy's
 * @reader) and carry no operator controls.
 */
export function WriteArticleLink({ url }: { url: string }) {
  return (
    <p className={styles.next}>
      Passed: it is on the <Link href="/reader">reader</Link>.{" "}
      <Link href={`/drafts?url=${encodeURIComponent(url)}`}>Write an article from it →</Link>
    </p>
  );
}
