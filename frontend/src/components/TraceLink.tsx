import Link from "next/link";
import { traceHref } from "@/lib/trace";

/**
 * "Where else has this article been?" - one link, the same everywhere a
 * page shows an article, a job or a draft, to the page that follows it
 * through every stage (app/trace/page.tsx). Takes whatever id the page
 * holds: the backend resolves a URL, a job id or a draft id alike.
 *
 * Never on the public reader: /trace is behind the site password.
 */
export function TraceLink({ q, label = "Trace its journey" }: { q: string; label?: string }) {
  return (
    <Link className="trace-link" href={traceHref(q)} title="Every stage this article went through, and why">
      <span aria-hidden="true">⤳</span> {label}
    </Link>
  );
}
