import type { Metadata } from "next";
import { NavLinks } from "@/components/NavLinks";
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
          <NavLinks />
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
