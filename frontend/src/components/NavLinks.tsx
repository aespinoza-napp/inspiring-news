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

export function NavLinks() {
  const pathname = usePathname();

  return (
    <nav>
      {LINKS.map((link) => {
        // A section's own pages count too: /reader/<id> is still Reader.
        const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
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
