import type { Metadata } from "next";

/**
 * Every reader page advertises the feed, so a feed reader finds it from
 * any of them (app/reader/feed.xml). Nothing else here: the pages under
 * it set their own titles and language.
 */
export const metadata: Metadata = {
  alternates: {
    types: { "application/rss+xml": "/reader/feed.xml" },
  },
};

export default function ReaderLayout({ children }: { children: React.ReactNode }) {
  return children;
}
