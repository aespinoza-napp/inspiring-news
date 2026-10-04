"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Analyzer" },
  { href: "/reader", label: "Reader" },
  { href: "/live", label: "Live" },
  { href: "/claim", label: "Claim Check" },
  { href: "/enrich", label: "Enrichment" },
  { href: "/corrector", label: "Corrector" },
  { href: "/scraper", label: "Scraper" },
  { href: "/sources", label: "Sources" },
  { href: "/graph", label: "Graph" },
  { href: "/evaluation", label: "Evaluation" },
];

// The pages served without the site password (docker/caddy/Caddyfile,
// @reader). Everything else answers a public visitor with 401.
const PUBLIC = "/reader";

export function NavLinks() {
  const pathname = usePathname();
  const onPublicPage = pathname === PUBLIC || pathname.startsWith(`${PUBLIC}/`);

  return (
    <nav>
      {LINKS.map((link) => {
        // A section's own pages count too: /reader/<id> is still Reader.
        const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
            // Next.js prefetches every visible link in production. On the
            // public reader that is nine requests a visitor's browser
            // cannot pass the password for - a 401 each, and possibly a
            // password prompt nobody asked for. A click still navigates.
            prefetch={onPublicPage && link.href !== PUBLIC ? false : undefined}
            className={active ? "nav-link is-active" : "nav-link"}
            aria-current={active ? "page" : undefined}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
