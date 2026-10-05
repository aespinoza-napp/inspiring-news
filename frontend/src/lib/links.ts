/**
 * Only an http(s) URL becomes a link. Search results, feed entries and
 * section pages are other sites' content, which this app does not
 * control: anything else (a `javascript:` URL in a hostile result) is
 * shown as text, never made clickable. One rule for every page -
 * LiveTrace, the source health panel, the graph and Discover.
 */
export function safeHref(value: unknown): string | undefined {
  return typeof value === "string" && /^https?:\/\//i.test(value) ? value : undefined;
}
