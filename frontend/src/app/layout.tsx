import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Inspiring News Tools",
  description: "Analyze and correct news content",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <span className="brand">Inspiring News Tools</span>
          <nav>
            <Link href="/">Analyzer</Link>
            <Link href="/corrector">Corrector</Link>
          </nav>
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
