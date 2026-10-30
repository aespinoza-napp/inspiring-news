import type { Metadata } from "next";
import { EditionSwitch } from "@/components/EditionSwitch";
import { NavLinks } from "@/components/NavLinks";
import { EditionProvider } from "@/lib/edition";
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
        <EditionProvider>
          <header className="site-header">
            <EditionSwitch />
            <NavLinks />
          </header>
          <main className="site-main">{children}</main>
        </EditionProvider>
      </body>
    </html>
  );
}
