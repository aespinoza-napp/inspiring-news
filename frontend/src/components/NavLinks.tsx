"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Two groups, because the pages are two kinds of thing. The newsroom is
// the path an article takes - found, analysed, followed, published - and
// FlowSteps draws it on those pages. The lab is every tool for looking
// inside one stage on its own: one claim, one enrichment, the scraper,
// the sources, the graph, the evaluation.
const GROUPS = [
  {
    label: "Newsroom",
    links: [
      { href: "/discover", label: "Discover" },
      { href: "/", label: "Analyze" },
      { href: "/live", label: "Live" },
      { href: "/reader", label: "Reader" },
    ],
  },
  {
    label: "Lab",
    links: [
      { href: "/claim", label: "Claim Check" },
      { href: "/enrich", label: "Enrichment" },
      { href: "/corrector", label: "Corrector" },
      { href: "/scraper", label: "Scraper" },
      { href: "/sources", label: "Sources" },
      { href: "/graph", label: "Graph" },
      { href: "/evaluation", label: "Evaluation" },
    ],
  },
];

// The pages served without the site password (docker/caddy/Caddyfile,
// @reader). Everything else answers a public visitor with 401.
const PUBLIC = "/reader";

function isActive(pathname: string, href: string): boolean {
  // "/" would match every page by prefix; it is active only on itself.
  if (href === "/") return pathname === "/";
  // A section's own pages count too: /reader/<id> is still Reader.
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavLinks() {
  const pathname = usePathname();
  const onPublicPage = pathname === PUBLIC || pathname.startsWith(`${PUBLIC}/`);

  return (
    <nav className="nav-groups">
      {GROUPS.map((group) => (
        <div className="nav-group" key={group.label} role="group" aria-label={group.label}>
          <span className="nav-group-label" aria-hidden="true">
            {group.label}
          </span>
          {group.links.map((link) => {
            const active = isActive(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                // Next.js prefetches every visible link in production. On the
                // public reader that is a request per link a visitor's browser
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
        </div>
      ))}
    </nav>
  );
}
