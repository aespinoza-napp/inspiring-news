#!/usr/bin/env node
/**
 * The reader's Catalan and Spanish, as review sheets for a native reader
 * (docs/goals.md, U4): one Markdown table per language with every string
 * of frontend/src/lib/readerText.ts beside its English and an empty
 * column for the correction.
 *
 *     node scripts/reader_strings.mjs            # writes docs/review/reader-{ca,es}.md
 *
 * Many strings are functions (plurals, counts, dates), so each is called
 * with sample arguments picked by parameter name and shown as the reader
 * would read it - a count twice, at 1 and at 3, because the plural is
 * what goes wrong. The dictionaries are transpiled with the frontend's own
 * TypeScript, so nothing is installed and nothing is re-typed by hand.
 */

import { createRequire } from "node:module";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(ROOT, "frontend", "package.json"));
const ts = require("typescript");

const source = readFileSync(join(ROOT, "frontend/src/lib/readerText.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
});

const module = { exports: {} };
new Function("module", "exports", "require", outputText)(module, module.exports, () => ({}));
const { READER_TEXT } = module.exports;

// Sample arguments by parameter name; a name not listed gets 3.
const SAMPLES = {
  n: [1, 3], count: [1, 3], status: [503], from: [1], to: [20], page: [2], of: [5],
  date: ["20/10/2026"], pct: ["72%"], checked: [2], total: [4], analysed: [3], published: [3],
  filtered: [true, false], cited: [1, 2, null], kinds: ["…"], error: ["HTTP 503"],
  label: ["…"], detail: ["…"], excerpt: ["…"], domain: ["elpais.com"], author: ["Ana Pérez"], model: ["llama3.2:3b"],
  pipeline: ["1.4"], verdict: ["TRUE"], reasons: ["…"], parts: [["…", "…"]],
  // A story's disclosure: AI-written and approved, AI-written and edited, by the newsroom.
  aiWritten: [true, true, false], humanEdited: [false, true, false],
  models: [["qwen3.5:4b"], ["qwen3.5:4b", "qwen3.5:9b"], []],
};

function parameters(fn) {
  const match = fn.toString().match(/^\s*(?:function[^(]*)?\(([^)]*)\)|^\s*([A-Za-z_$][\w$]*)\s*=>/);
  const list = match ? (match[1] ?? match[2] ?? "") : "";
  return list.split(",").map((name) => name.replace(/=.*$/, "").trim()).filter(Boolean);
}

function renderings(fn) {
  const names = parameters(fn);
  const variants = Math.max(1, ...names.map((name) => (SAMPLES[name] ?? [3]).length));
  const out = [];
  for (let i = 0; i < variants; i++) {
    const args = names.map((name) => {
      const options = SAMPLES[name] ?? [3];
      return options[Math.min(i, options.length - 1)];
    });
    let text;
    try {
      text = String(fn(...args));
    } catch (error) {
      text = `(could not render: ${error.message})`;
    }
    out.push({ label: names.length ? `(${names.map((name, j) => `${name}=${JSON.stringify(args[j])}`).join(", ")})` : "", text });
  }
  return out;
}

// [key, rendering label, text] for every leaf, in the dictionary's order.
function leaves(value, path = []) {
  if (typeof value === "string") return [[path.join("."), "", value]];
  if (typeof value === "function") {
    // verdictTally(verdict, n): every verdict, at 1 and at 3.
    if (path.at(-1) === "verdictTally") {
      return ["TRUE", "PARTIALLY_TRUE", "MISLEADING", "FALSE", "UNVERIFIED"].flatMap((verdict) =>
        [1, 3].map((n) => [path.join("."), `(${verdict}, ${n})`, value(verdict, n)]));
    }
    return renderings(value).map(({ label, text }) => [path.join("."), label, text]);
  }
  if (Array.isArray(value)) return value.flatMap((item, i) => leaves(item, [...path, i]));
  if (value && typeof value === "object") return Object.entries(value).flatMap(([key, item]) => leaves(item, [...path, key]));
  return [];
}

const cell = (text) => String(text).replace(/\|/g, "\\|").replace(/\n/g, "<br>");

const english = new Map(leaves(READER_TEXT.en).map(([key, label, text]) => [`${key}${label}`, text]));
const NAMES = { ca: "Catalan", es: "Spanish" };

mkdirSync(join(ROOT, "docs/review"), { recursive: true });

for (const lang of ["ca", "es"]) {
  const rows = leaves(READER_TEXT[lang]).filter(([key]) => key !== "locale");
  const lines = [
    `# The reader's ${NAMES[lang]}, for a native reader`,
    "",
    `Every string the public reader shows in ${NAMES[lang]} (\`frontend/src/lib/readerText.ts\`),`,
    "beside its English. Written by the AI and not yet read by a native speaker.",
    "",
    "**How to review:** read the third column as a reader of the site would. Where it is",
    "wrong, unnatural or inconsistent, write the corrected text in the last column (a short",
    "reason helps). Leave it empty where the text is fine. Sample values such as 3, 72% or",
    "20/10/2026 stand in for real ones, and … for a verdict's or a search's own name, translated",
    "elsewhere in the sheet; a count appears twice, at 1 and at 3, for the plural.",
    "Headlines, claims and sources are not translated by the site and are not here.",
    "",
    `Generated by \`node scripts/reader_strings.mjs\` from the code as it stands; ${rows.length} rows.`,
    "",
    "| Key | English | " + NAMES[lang] + " now | Correction |",
    "|---|---|---|---|",
    ...rows.map(([key, label, text]) =>
      `| \`${key}\`${label ? ` ${cell(label)}` : ""} | ${cell(english.get(`${key}${label}`) ?? "")} | ${cell(text)} |  |`),
    "",
    "## Log of changes applied",
    "",
    "| Date | Key | Was | Now | Why |",
    "|---|---|---|---|---|",
    "",
  ];
  writeFileSync(join(ROOT, `docs/review/reader-${lang}.md`), lines.join("\n"), "utf8");
  console.log(`docs/review/reader-${lang}.md: ${rows.length} rows`);
}
