/**
 * The reader's words, in the three languages its stories are written in
 * (roadmap, Phase 6: the reader in Catalan and Spanish). One dictionary
 * per language and no i18n library: `ReaderText` is the contract, so a
 * string added to one language and forgotten in another fails the
 * typecheck - the frontend's form of backend invariant 8 (complete
 * lexicons in every language).
 *
 * Which language a page is in: `?lang=` when the reader chose one (the
 * switch keeps it in the URL like the feed's filters), else the content's
 * own language (an article page, a story), else the browser's, else
 * English. Only the page around the content is translated: a headline,
 * a claim, the model's explanation and a source's title stay as written.
 */

import type { EvidenceStance, QueryKind, Verdict } from "@/lib/types";

export type ReaderLang = "ca" | "es" | "en";

/** In the order the switch shows them. */
export const READER_LANGS: ReaderLang[] = ["ca", "es", "en"];

/** Each language named in itself, for the switch. */
export const LANG_SELF_NAME: Record<ReaderLang, string> = {
  ca: "Català",
  es: "Español",
  en: "English",
};

export function readerLang(value: string | null | undefined): ReaderLang | null {
  const code = (value ?? "").toLowerCase().slice(0, 2);
  return (READER_LANGS as string[]).includes(code) ? (code as ReaderLang) : null;
}

/** The first that names a language the reader has: chosen, content, browser. */
export function pickLang(...candidates: (string | null | undefined)[]): ReaderLang {
  for (const candidate of candidates) {
    const lang = readerLang(candidate);
    if (lang) return lang;
  }
  return "en";
}

/**
 * The first language the reader has in a browser's list, in order of
 * preference: an Accept-Language header ("fr,es;q=0.9,en;q=0.8" gives
 * es) or navigator.languages. Null when none is one of ours.
 */
export function preferredLang(list: string | readonly string[] | null | undefined): ReaderLang | null {
  const tags = typeof list === "string" ? list.split(",").map((part) => part.split(";")[0].trim()) : list ?? [];
  for (const tag of tags) {
    const lang = readerLang(tag);
    if (lang) return lang;
  }
  return null;
}

/** `?lang=` set to `lang` on `href`, keeping the rest of its query. */
export function withLang(href: string, lang: ReaderLang): string {
  const [path, query = ""] = href.split("?");
  const search = new URLSearchParams(query);
  search.set("lang", lang);
  return `${path}?${search}`;
}

type Count = (n: number) => string;

export interface ReaderText {
  locale: string;
  verdict: Record<Verdict, string>;
  /** One part of a tally: "2 true", "1 verdadera", "2 certes" (claims are feminine in es and ca). */
  verdictTally: (verdict: Verdict, n: number) => string;
  notChecked: string;
  languageName: Record<string, string>;
  unknownLanguage: string;
  /** Topic display names as the classifier sends them (backend/src/config/topics.py). */
  topic: Record<string, string>;
  stance: Record<EvidenceStance, string>;
  queryKind: Record<QueryKind, string>;

  switchLabel: string;
  backToFeed: string;

  // The feed.
  feedTitle: string;
  feedSubtitle: string;
  loadingFeed: string;
  feedFailed: (status: number) => string;
  articles: Count;
  match: string;
  shown: (from: number, to: number) => string;
  pages: string;
  newer: string;
  older: string;
  pageOf: (page: number, of: number) => string;
  filterTopic: string;
  filterLanguage: string;
  all: string;
  emptyNothingAnalysedTitle: string;
  emptyNothingAnalysed: { before: string; analyzer: string; middle: string; scraper: string; after: string };
  emptyNothingPublishedTitle: string;
  emptyNothingPublished: (analysed: number) => string;
  emptyNothingPublishedLink: string;
  emptyNothingPublishedAfter: string;
  emptyPastEndTitle: string;
  emptyPastEnd: (total: number) => string;
  firstPage: string;
  emptyNoMatchTitle: string;
  emptyNoMatch: (published: number, filtered: boolean) => string;
  clearFilters: string;

  // A card.
  checkedOn: (date: string) => string;
  untitled: string;

  // The verdict.
  notCheckedCount: Count;
  searchFailedFor: Count;
  modelUnreachableFor: Count;
  noAnswerFor: Count;
  confidence: (pct: string) => string;
  noneCouldBeChecked: string;
  claimsSelected: (checked: number, total: number, parts: string[]) => string;
  couldNotBeChecked: Count;
  ourFailureArticle: string;
  notCountedAsVerdict: (n: number, reasons: string) => string;
  unverifiedByFailure: Count;
  weakestClaim: string;
  belowAnchorFloor: string;

  // The article page.
  loadingArticle: string;
  articleFailed: (status: number) => string;
  missingTitle: string;
  missingText: string;
  by: (author: string) => string;
  openingLabel: string;
  openingOnly: string;
  readWhole: (domain: string) => string;
  claimsTitle: string;
  claimsUnavailable: string;
  noClaims: string;
  statementsNotChecked: Count;
  notCheckedExplained: string;
  andMore: Count;
  topicsAndKeywords: string;
  provenance: (date: string | null, model: string | null, pipeline: string | null) => string;

  // How to read the sources.
  guideTitle: string;
  guide: { term: string; text: string }[];

  // A claim.
  outcome: Record<"ungrounded" | "no_evidence" | "search_unavailable" | "llm_unreachable" | "no_answer", string>;
  confident: (pct: string) => string;
  modelAnswered: string;
  /** Followed by the pipeline's own reason, in English, and a full stop. */
  changedBecause: string;
  searchFailedNote: string;
  sourcesAgree: string;
  sourcesDiffer: string;
  /** "3 sources found" (the check failed) or "3 sources weighed, 2 cited by the model": one string, so they agree. */
  sourcesLine: (n: number, cited: number | null) => string;
  independentSites: Count;
  setAside: Count;
  citedByModel: string;
  notCited: string;
  checkedHereBefore: string;
  whyTrusted: string;
  rating: { reliability: string; pertinence: string; relevance: string; semantic: string; lexical: string; recency: string };
  unrated: string;
  ratedSite: (pct: string) => string;
  unratedSite: (pct: string) => string;
  foundBySearch: (kinds: string) => string;
  and: string;

  // Our newsroom's stories.
  newsroomTitle: string;
  newsroomIntro: string;
  storiesFailed: (error: string) => string;
  storiesLoadFailed: (status: number) => string;
  loading: string;
  showMore: (n: number) => string;
  ourNewsroom: string;
  howWritten: string;
  disclosure: (aiWritten: boolean, humanEdited: boolean, models: string[]) => string;
  disclosureShort: (aiWritten: boolean, humanEdited: boolean) => string;
  startsFrom: { before: string; link: string; after: string };
  tags: string;
  publishedOn: (date: string) => string;
  moreNews: string;
  sourcesTitle: string;
  origin: Record<"analysed" | "related" | "evidence" | "angle", string>;
  /**
   * A story found through what is trending (docs/decisions/trends.md): which
   * trend, and that popularity proves nothing.
   */
  trendFound: (name: string, signal: string) => string;
  /** The TikTok video a person gave with the trend: loaded only after a click. */
  video: { title: string; notice: string; load: string; open: string; frameTitle: string };
  checkedTitle: string;
  checkedIntro: string;
  restsOn: string;
  storyFailed: string;
  storyMissingText: { before: string; link: string; after: string };
  storyNotFound: string;

  // The RSS feed (/reader/feed.xml) and the article pages' metadata.
  rssTitle: string;
  rssDescription: string;
  /** An item's first line: "Verdict: Unverified · 1 true, 1 not checked". */
  rssVerdict: (label: string, detail: string) => string;
  metaDescription: (label: string, excerpt: string) => string;

  // The guide to the verdicts (/reader/guide), linked from every badge.
  badgeHelp: (label: string) => string;
  guidePage: {
    title: string;
    intro: string;
    verdictsTitle: string;
    verdicts: Record<Verdict, string>;
    notCheckedTitle: string;
    notChecked: string;
    articleTitle: string;
    article: string;
    confidenceTitle: string;
    confidence: string[];
    sourcesTitle: string;
    sources: string;
    accuracyTitle: string;
    accuracy: string;
  };
}

const en: ReaderText = {
  locale: "en-GB",
  verdict: { TRUE: "True", PARTIALLY_TRUE: "Partly true", FALSE: "False", MISLEADING: "Misleading", UNVERIFIED: "Unverified" },
  verdictTally: (verdict, n) =>
    `${n} ${{ TRUE: "true", PARTIALLY_TRUE: "partly true", FALSE: "false", MISLEADING: "misleading", UNVERIFIED: "unverified" }[verdict]}`,
  notChecked: "Not checked",
  languageName: { en: "English", es: "Spanish", ca: "Catalan" },
  unknownLanguage: "Unknown language",
  topic: {},
  stance: { supports: "supports the claim", contradicts: "contradicts the claim", unrelated: "judged unrelated", silent: "says nothing on the claim" },
  queryKind: { anchor: "who & what", proposition: "what it claims", refutation: "counter-evidence" },

  switchLabel: "Language of this page",
  backToFeed: "← Checked articles",

  feedTitle: "Checked articles",
  feedSubtitle:
    "Articles that passed every step: on a topic we cover, constructive, not a duplicate, and not judged false or " +
    "misleading. Each says how its claims came out and what the verdict rests on.",
  loadingFeed: "Loading the feed…",
  feedFailed: (status) => `Loading the feed failed (${status}).`,
  articles: (n) => `${n} ${n === 1 ? "article" : "articles"}`,
  match: " match",
  shown: (from, to) => ` · ${from}–${to} shown`,
  pages: "Pages",
  newer: "← Newer",
  older: "Older →",
  pageOf: (page, of) => `Page ${page} of ${of}`,
  filterTopic: "Topic",
  filterLanguage: "Language",
  all: "All",
  emptyNothingAnalysedTitle: "Nothing has been analysed yet",
  emptyNothingAnalysed: {
    before: "The store holds no analysed article, so there is nothing to publish. Analyse one on the ",
    analyzer: "Analyzer",
    middle: ", or queue a batch from the ingest panel on ",
    scraper: "Scraper",
    after: "; every article that passes appears here.",
  },
  emptyNothingPublishedTitle: "Nothing has been published",
  emptyNothingPublished: (analysed) =>
    `${en.articles(analysed)} analysed, and none passed. Each was turned away before checking (off-topic, not ` +
    "constructive, or a duplicate) or was judged false or misleading. ",
  emptyNothingPublishedLink: "Scraper",
  emptyNothingPublishedAfter: " shows what became of each one.",
  emptyPastEndTitle: "This page is past the end",
  emptyPastEnd: (total) => `There are ${en.articles(total)} on fewer pages than that.`,
  firstPage: "Go to the first page",
  emptyNoMatchTitle: "No published article matches",
  emptyNoMatch: (published, filtered) =>
    `${en.articles(published)} published; none matches ${filtered ? "these filters" : "this view"}.`,
  clearFilters: "Clear the filters",

  checkedOn: (date) => `checked ${date}`,
  untitled: "No headline was extracted; this one is taken from the link or the text.",

  notCheckedCount: (n) => `${n} not checked`,
  searchFailedFor: (n) => `web search failed for ${n}`,
  modelUnreachableFor: (n) => `the model was unreachable for ${n}`,
  noAnswerFor: (n) => `the model was unavailable or gave no usable answer for ${n}`,
  confidence: (pct) => `confidence ${pct}`,
  noneCouldBeChecked: "None of this article's claims could be checked.",
  claimsSelected: (checked, total, parts) =>
    `${checked} ${checked === 1 ? "claim" : "claims"} selected` +
    (total > checked ? ` from ${total} ${total === 1 ? "statement" : "statements"}` : "") +
    `: ${parts.join(", ")}.`,
  couldNotBeChecked: (n) => `${n} could not be checked`,
  ourFailureArticle: "That is a failure on our side, not a finding about the article.",
  notCountedAsVerdict: (n, reasons) =>
    `${n === 1 ? "The one" : `The ${n}`} that could not be checked ${reasons ? `(${reasons}) ` : ""}` +
    `${n === 1 ? "is" : "are"} not counted as a verdict: that is a failure on our side, not a finding about the claim.`,
  unverifiedByFailure: (n) =>
    ` The article reads Unverified because of ${n === 1 ? "it" : "them"} alone: no claim that was checked came out unverified.`,
  weakestClaim:
    "The article takes its weakest claim's verdict, so one unverified claim outweighs any number of true ones. " +
    "Confidence is the average across its claims.",
  belowAnchorFloor:
    "Fewer central claims than usual were found in this article, so the verdict rests on less than usual.",

  loadingArticle: "Loading the article…",
  articleFailed: (status) => `Loading the article failed (${status}).`,
  missingTitle: "No published article here",
  missingText:
    "Either nothing was published under this link, or the article has been withdrawn: when an article is checked " +
    "again its newest check decides, and one judged false or misleading leaves the reader.",
  by: (author) => `By ${author}`,
  openingLabel: "Opening of the article",
  openingOnly: "Only the opening is shown here.",
  readWhole: (domain) => `Read the whole article on ${domain}`,
  claimsTitle: "The claims, one by one",
  claimsUnavailable:
    "The record holding this article's claims and their sources could not be read, so only the overall verdict is known.",
  noClaims: "No claim of this article was checked.",
  statementsNotChecked: (n) => `${n} ${n === 1 ? "statement" : "statements"} not checked`,
  notCheckedExplained:
    "Only the statements an article's credibility rests on are checked. These were left out; they are listed, not judged.",
  andMore: (n) => `and ${n} more.`,
  topicsAndKeywords: "Topics and keywords",
  provenance: (date, model, pipeline) =>
    `Checked ${date ?? "on an unknown date"}${model ? ` with ${model}` : ""}${pipeline ? `, pipeline ${pipeline}` : ""}.`,

  guideTitle: "How to read the sources",
  guide: [
    {
      term: "Site reliability",
      text: "Our rating of the site. Most sites have none; those are marked unrated and ranked with a neutral default, not with a rating.",
    },
    {
      term: "Addresses the claim",
      text: "Whether the page is about this claim at all. Below a floor it is cut before the model sees it, however reliable the site.",
    },
    {
      term: "Relevance",
      text: "What put the source in front of the model: wording match, the claim's own terms on the page, how recent it is, and the site's reliability, combined.",
    },
    {
      term: "Cited by the model",
      text: "The verdict rests on the cited sources. A verdict the model could not back with one is not kept.",
    },
  ],

  outcome: {
    ungrounded:
      "The model gave an answer but could not point to a source that bears it out, so the claim stands as unverified.",
    no_evidence:
      "Searched for, and nothing that addresses this claim came back. Unverified here means looked for and not found.",
    search_unavailable:
      "Not checked: the web search failed, so nothing was looked at. This is not a verdict on the claim.",
    llm_unreachable:
      "Not checked: the model could not be reached. The sources found are listed below, but nobody weighed them.",
    no_answer:
      "Not checked: the model was unavailable or gave no usable answer. The sources found are listed below, but nobody weighed them.",
  },
  confident: (pct) => `${pct} confident`,
  modelAnswered: "The model itself answered",
  changedBecause: "; it was changed because ",
  searchFailedNote:
    "The web search failed for this claim; the verdict rests only on articles this site had already checked.",
  sourcesAgree: "Where the sources agree",
  sourcesDiffer: "Where they differ",
  sourcesLine: (n, cited) =>
    `${n} ${n === 1 ? "source" : "sources"}` + (cited === null ? " found" : ` weighed, ${cited} cited by the model`),
  independentSites: (n) => ` · ${n} independent ${n === 1 ? "site" : "sites"}`,
  setAside: (n) => `${n} more ${n === 1 ? "page" : "pages"} found and set aside`,
  citedByModel: "cited by the model",
  notCited: "not cited",
  checkedHereBefore: "an article checked here before",
  whyTrusted: "Why this source was trusted",
  rating: {
    reliability: "Site reliability",
    pertinence: "Addresses the claim",
    relevance: "Relevance",
    semantic: "Wording match",
    lexical: "Claim terms",
    recency: "Recency",
  },
  unrated: "unrated",
  ratedSite: (pct) => `A site with a reliability rating of ${pct}.`,
  unratedSite: (pct) => `Nobody has rated this site; ranking assumed ${pct}.`,
  foundBySearch: (kinds) => ` Found by the search for ${kinds}.`,
  and: " and ",

  newsroomTitle: "From our newsroom",
  newsroomIntro:
    "Articles we wrote from the checked news below and the fact-checks behind it. Each is written with AI and " +
    "approved by a person, and links to every source it cites.",
  storiesFailed: (error) => `Our own articles could not be loaded: ${error}`,
  storiesLoadFailed: (status) => `Loading our articles failed (${status}).`,
  loading: "Loading…",
  showMore: (n) => `Show more (${n})`,
  ourNewsroom: "Our newsroom",
  howWritten: "How this article was written",
  disclosure: (aiWritten, humanEdited, models) => {
    // Only what the record shows: a person approved every published
    // article, and `humanEdited` says whether they also changed the text.
    const person = humanEdited
      ? "edited and approved for publication by a person on our team"
      : "approved for publication by a person on our team";
    if (!aiWritten) return `Written by our newsroom from the sources listed below, and ${person}.`;
    const who =
      models.length === 0
        ? "an AI model"
        : models.length === 1
          ? `an AI model (${models[0]})`
          : `AI models (${models.join(", ")})`;
    return `Written by ${who} from the sources listed below, then ${person}.`;
  },
  disclosureShort: (aiWritten, humanEdited) =>
    !aiWritten
      ? "Written by our newsroom"
      : humanEdited
        ? "Written with AI · edited and approved by a person"
        : "Written with AI · approved by a person",
  startsFrom: {
    before: "It starts from ",
    link: "a news article we checked",
    after: ", where each of its claims and the sources behind the verdict are shown.",
  },
  tags: "Tags",
  publishedOn: (date) => `Published ${date}.`,
  moreNews: "More checked news and our articles",
  sourcesTitle: "Sources",
  origin: {
    analysed: "The article we checked",
    related: "Related coverage",
    evidence: "Evidence behind a fact-check",
    angle: "Behind a constructive angle we checked",
  },
  trendFound: (name, signal) =>
    `We found this story through what is trending: “${name}”${signal ? ` (${signal})` : ""}. Being popular proves nothing: what the article states rests on the sources below.`,
  video: {
    title: "The video behind the trend",
    notice: "This video is on TikTok. Loading it connects your browser to TikTok, which may set cookies and track your visit.",
    load: "Load the TikTok video",
    open: "Open it on TikTok instead",
    frameTitle: "TikTok video",
  },
  checkedTitle: "What was checked",
  checkedIntro: "The claims of the article we started from, as our fact-checker judged them.",
  restsOn: "Rests on ",
  storyFailed: "This article could not be loaded just now. Try again in a moment.",
  storyMissingText: {
    before: "Either nothing was published under this link, or the article has been taken down. Our articles are listed on the ",
    link: "reader",
    after: ".",
  },
  storyNotFound: "Story not found",

  rssTitle: "Inspiring News: checked news and our articles",
  rssDescription:
    "Constructive news whose claims we checked one by one, and the articles our newsroom wrote from them, newest first.",
  rssVerdict: (label, detail) => `Verdict: ${label}${detail ? ` · ${detail}` : ""}`,
  metaDescription: (label, excerpt) => `Our verdict: ${label}. ${excerpt}`.trim(),
  badgeHelp: (label) => `${label}: what this verdict means`,
  guidePage: {
    title: "How to read our verdicts",
    intro:
      "Each checked claim gets one of five verdicts, or none at all when our check failed. This page says what each " +
      "means here, what it does not mean, and how the article's own verdict follows from its claims.",
    verdictsTitle: "The five verdicts",
    verdicts: {
      TRUE: "The sources we found support the claim as it is made.",
      PARTIALLY_TRUE:
        "The central assertion holds, but a detail - a figure, a date, who said it - does not match the sources.",
      FALSE: "The sources contradict the claim.",
      MISLEADING:
        "What the claim says may be accurate, but it is framed so as to deceive, or leaves out context that changes its meaning.",
      UNVERIFIED:
        "We looked, and found nothing that addresses the claim either way - or the model could not point to a source for " +
        "its answer, which we do not keep. It is a finding about the evidence, not about the claim: it may well be true.",
    },
    notCheckedTitle: "Not checked is not Unverified",
    notChecked:
      "Not checked means the check itself failed - the web search was unavailable, or the model could not be reached - " +
      "so nothing was weighed. That is a failure on our side, never a verdict, and it is counted apart from the verdicts.",
    articleTitle: "The article's verdict",
    article:
      "An article takes the verdict of its weakest checked claim, so one unverified claim outweighs any number of true " +
      "ones. That is why an article can read Unverified while most of its claims are true: the line under the badge says how each came out.",
    confidenceTitle: "What a confidence is, and is not",
    confidence: [
      "It is how sure the model was of its verdict, blended with how relevant its evidence was, how much of it it cited and how much there was.",
      "It is not a probability that the claim is true, and not a measured accuracy: a 90% verdict can still be wrong.",
      "An article's confidence is the average across its claims.",
    ],
    sourcesTitle: "The sources",
    sources:
      "Every verdict lists the sources the model weighed, the ones it cited, and the passage it relied on. Most sites " +
      "have no reliability rating of ours: they are marked unrated, not given a score they have not earned.",
    accuracyTitle: "How often are we right?",
    accuracy:
      "We measure the verdicts against claims a person checked by hand. That set is still being reviewed, so no " +
      "accuracy figure is published here yet; it will be, with its margin of error, once the review is done. Until " +
      "then, read each verdict with its sources.",
  },
};

const es: ReaderText = {
  locale: "es-ES",
  verdict: { TRUE: "Verdadero", PARTIALLY_TRUE: "Parcialmente verdadero", FALSE: "Falso", MISLEADING: "Engañoso", UNVERIFIED: "No verificado" },
  verdictTally: (verdict, n) => {
    const word = { TRUE: "verdadera", PARTIALLY_TRUE: "parcialmente verdadera", FALSE: "falsa", MISLEADING: "engañosa", UNVERIFIED: "no verificada" }[verdict];
    return `${n} ${word}${n === 1 ? "" : "s"}`;
  },
  notChecked: "Sin comprobar",
  languageName: { en: "Inglés", es: "Español", ca: "Catalán" },
  unknownLanguage: "Idioma desconocido",
  topic: {
    Education: "Educación",
    "Community & Social Impact": "Comunidad e impacto social",
    Employment: "Empleo",
    "Cities & Society": "Ciudades y sociedad",
    Space: "Espacio",
    Technology: "Tecnología",
    "Scientific Research": "Investigación científica",
    Biology: "Biología",
    Climate: "Clima",
    "Nature & Biodiversity": "Naturaleza y biodiversidad",
    Energy: "Energía",
    Sustainability: "Sostenibilidad",
    "Food & Agriculture": "Alimentación y agricultura",
    Arts: "Artes",
    Entertainment: "Entretenimiento",
    "History & Heritage": "Historia y patrimonio",
    Literature: "Literatura",
    "Inspirational Stories": "Historias inspiradoras",
    Medicine: "Medicina",
    "Mental Health": "Salud mental",
    Nutrition: "Nutrición",
    Fitness: "Actividad física",
    "Public Health": "Salud pública",
  },
  stance: { supports: "respalda la afirmación", contradicts: "contradice la afirmación", unrelated: "considerada no relacionada", silent: "no dice nada sobre la afirmación" },
  queryKind: { anchor: "quién y qué", proposition: "lo que afirma", refutation: "pruebas en contra" },

  switchLabel: "Idioma de esta página",
  backToFeed: "← Artículos verificados",

  feedTitle: "Artículos verificados",
  feedSubtitle:
    "Artículos que han superado cada paso: tratan un tema que cubrimos, son constructivos, no están duplicados y no " +
    "se han considerado falsos ni engañosos. Cada uno explica cómo han salido sus afirmaciones y en qué se basa el veredicto.",
  loadingFeed: "Cargando los artículos…",
  feedFailed: (status) => `No se han podido cargar los artículos (${status}).`,
  articles: (n) => `${n} ${n === 1 ? "artículo" : "artículos"}`,
  match: " coinciden",
  shown: (from, to) => ` · se muestran ${from}–${to}`,
  pages: "Páginas",
  newer: "← Más recientes",
  older: "Más antiguos →",
  pageOf: (page, of) => `Página ${page} de ${of}`,
  filterTopic: "Tema",
  filterLanguage: "Idioma",
  all: "Todos",
  emptyNothingAnalysedTitle: "Todavía no se ha analizado nada",
  emptyNothingAnalysed: {
    before: "No hay ningún artículo analizado, así que no hay nada que publicar. Analiza uno en el ",
    analyzer: "Analizador",
    middle: " o envía un lote desde el panel de ingesta de ",
    scraper: "Scraper",
    after: "; cada artículo que lo supere aparecerá aquí.",
  },
  emptyNothingPublishedTitle: "No se ha publicado nada",
  emptyNothingPublished: (analysed) =>
    `${es.articles(analysed)} ${analysed === 1 ? "analizado" : "analizados"}, y ninguno ha pasado. Cada uno se ` +
    "descartó antes de verificarlo (fuera de tema, no constructivo o duplicado) o se consideró falso o engañoso. ",
  emptyNothingPublishedLink: "Scraper",
  emptyNothingPublishedAfter: " muestra qué ha sido de cada uno.",
  emptyPastEndTitle: "Esta página está más allá del final",
  emptyPastEnd: (total) => `Hay ${es.articles(total)} en menos páginas.`,
  firstPage: "Ir a la primera página",
  emptyNoMatchTitle: "Ningún artículo publicado coincide",
  emptyNoMatch: (published, filtered) =>
    `${es.articles(published)} ${published === 1 ? "publicado" : "publicados"}; ninguno coincide con ` +
    `${filtered ? "estos filtros" : "esta vista"}.`,
  clearFilters: "Quitar los filtros",

  checkedOn: (date) => `verificado el ${date}`,
  untitled: "No se ha extraído ningún titular; este procede del enlace o del texto.",

  notCheckedCount: (n) => `${n} sin comprobar`,
  searchFailedFor: (n) => `la búsqueda web falló en ${n}`,
  modelUnreachableFor: (n) => `no se pudo contactar con el modelo en ${n}`,
  noAnswerFor: (n) => `el modelo no estaba disponible o no dio una respuesta utilizable en ${n}`,
  confidence: (pct) => `confianza ${pct}`,
  noneCouldBeChecked: "No se ha podido comprobar ninguna afirmación de este artículo.",
  claimsSelected: (checked, total, parts) =>
    `${checked} ${checked === 1 ? "afirmación seleccionada" : "afirmaciones seleccionadas"}` +
    (total > checked ? ` de ${total} ${total === 1 ? "enunciado" : "enunciados"}` : "") +
    `: ${parts.join(", ")}.`,
  couldNotBeChecked: (n) => `${n} no se ${n === 1 ? "ha" : "han"} podido comprobar`,
  ourFailureArticle: "Es un fallo nuestro, no una conclusión sobre el artículo.",
  notCountedAsVerdict: (n, reasons) =>
    `${n === 1 ? "La que" : `Las ${n} que`} no se ${n === 1 ? "ha" : "han"} podido comprobar ` +
    `${reasons ? `(${reasons}) ` : ""}no ${n === 1 ? "cuenta" : "cuentan"} como veredicto: es un fallo nuestro, ` +
    "no una conclusión sobre la afirmación.",
  unverifiedByFailure: (n) =>
    ` El artículo figura como No verificado solo por ${n === 1 ? "ella" : "ellas"}: ninguna afirmación comprobada ha salido no verificada.`,
  weakestClaim:
    "El artículo toma el veredicto de su afirmación más débil, de modo que una sola afirmación no verificada pesa más " +
    "que cualquier número de verdaderas. La confianza es la media de sus afirmaciones.",
  belowAnchorFloor:
    "En este artículo se han encontrado menos afirmaciones centrales de lo habitual, así que el veredicto se apoya en menos.",

  loadingArticle: "Cargando el artículo…",
  articleFailed: (status) => `No se ha podido cargar el artículo (${status}).`,
  missingTitle: "Aquí no hay ningún artículo publicado",
  missingText:
    "O no se publicó nada con este enlace, o el artículo se ha retirado: cuando se vuelve a verificar un artículo " +
    "decide su verificación más reciente, y el que se considera falso o engañoso sale del lector.",
  by: (author) => `Por ${author}`,
  openingLabel: "Inicio del artículo",
  openingOnly: "Aquí solo se muestra el inicio.",
  readWhole: (domain) => `Lee el artículo completo en ${domain}`,
  claimsTitle: "Las afirmaciones, una a una",
  claimsUnavailable:
    "No se ha podido leer el registro con las afirmaciones de este artículo y sus fuentes, así que solo se conoce el veredicto global.",
  noClaims: "No se ha comprobado ninguna afirmación de este artículo.",
  statementsNotChecked: (n) => `${n} ${n === 1 ? "enunciado sin comprobar" : "enunciados sin comprobar"}`,
  notCheckedExplained:
    "Solo se comprueban los enunciados en los que se apoya la credibilidad de un artículo. Estos se han dejado fuera; " +
    "se listan, no se juzgan.",
  andMore: (n) => `y ${n} más.`,
  topicsAndKeywords: "Temas y palabras clave",
  provenance: (date, model, pipeline) =>
    `Verificado ${date ? `el ${date}` : "en una fecha desconocida"}${model ? ` con ${model}` : ""}` +
    `${pipeline ? `, versión del proceso ${pipeline}` : ""}.`,

  guideTitle: "Cómo leer las fuentes",
  guide: [
    {
      term: "Fiabilidad del sitio",
      text: "Nuestra valoración del sitio. La mayoría no tiene ninguna; esos se marcan sin valorar y se ordenan con un valor neutro, no con una valoración.",
    },
    {
      term: "Trata la afirmación",
      text: "Si la página trata de esta afirmación. Por debajo de un mínimo se descarta antes de que el modelo la vea, por fiable que sea el sitio.",
    },
    {
      term: "Relevancia",
      text: "Lo que puso la fuente delante del modelo: la coincidencia de sentido, los términos de la afirmación en la página, lo reciente que es y la fiabilidad del sitio, combinados.",
    },
    {
      term: "Citada por el modelo",
      text: "El veredicto se apoya en las fuentes citadas. Un veredicto que el modelo no pudo respaldar con ninguna no se mantiene.",
    },
  ],

  outcome: {
    ungrounded:
      "El modelo dio una respuesta, pero no pudo señalar ninguna fuente que la respalde, así que la afirmación queda como no verificada.",
    no_evidence:
      "Se buscó y no apareció nada que trate esta afirmación. Aquí, no verificada significa buscada y no encontrada.",
    search_unavailable:
      "Sin comprobar: la búsqueda web falló, así que no se miró nada. No es un veredicto sobre la afirmación.",
    llm_unreachable:
      "Sin comprobar: no se pudo contactar con el modelo. Las fuentes encontradas se listan abajo, pero nadie las valoró.",
    no_answer:
      "Sin comprobar: el modelo no estaba disponible o no dio una respuesta utilizable. Las fuentes encontradas se listan abajo, pero nadie las valoró.",
  },
  confident: (pct) => `confianza ${pct}`,
  modelAnswered: "El propio modelo respondió",
  changedBecause: "; se cambió porque ",
  searchFailedNote:
    "La búsqueda web falló para esta afirmación; el veredicto se apoya solo en artículos que este sitio ya había verificado.",
  sourcesAgree: "En qué coinciden las fuentes",
  sourcesDiffer: "En qué difieren",
  sourcesLine: (n, cited) =>
    `${n} ${n === 1 ? "fuente" : "fuentes"} ` +
    (cited === null
      ? n === 1 ? "encontrada" : "encontradas"
      : `${n === 1 ? "valorada" : "valoradas"}, ${cited} ${cited === 1 ? "citada" : "citadas"} por el modelo`),
  independentSites: (n) => ` · ${n} ${n === 1 ? "sitio independiente" : "sitios independientes"}`,
  setAside: (n) => `${n} ${n === 1 ? "página más encontrada y descartada" : "páginas más encontradas y descartadas"}`,
  citedByModel: "citada por el modelo",
  notCited: "no citada",
  checkedHereBefore: "un artículo ya verificado aquí",
  whyTrusted: "Por qué se confió en esta fuente",
  rating: {
    reliability: "Fiabilidad del sitio",
    pertinence: "Trata la afirmación",
    relevance: "Relevancia",
    semantic: "Coincidencia de sentido",
    lexical: "Términos de la afirmación",
    recency: "Actualidad",
  },
  unrated: "sin valorar",
  ratedSite: (pct) => `Un sitio con una valoración de fiabilidad del ${pct}.`,
  unratedSite: (pct) => `Nadie ha valorado este sitio; para ordenarlo se supuso un ${pct}.`,
  foundBySearch: (kinds) => ` Encontrada por la búsqueda de ${kinds}.`,
  and: " y ",

  newsroomTitle: "De nuestra redacción",
  newsroomIntro:
    "Artículos que hemos escrito a partir de las noticias verificadas de abajo y de las verificaciones que las respaldan. " +
    "Cada uno se escribe con IA, lo aprueba una persona y enlaza todas las fuentes que cita.",
  storiesFailed: (error) => `No se han podido cargar nuestros artículos: ${error}`,
  storiesLoadFailed: (status) => `No se han podido cargar nuestros artículos (${status}).`,
  loading: "Cargando…",
  showMore: (n) => `Mostrar más (${n})`,
  ourNewsroom: "Nuestra redacción",
  howWritten: "Cómo se escribió este artículo",
  disclosure: (aiWritten, humanEdited, models) => {
    const person = humanEdited
      ? "editado y aprobado para su publicación por una persona de nuestro equipo"
      : "aprobado para su publicación por una persona de nuestro equipo";
    if (!aiWritten) return `Escrito por nuestra redacción a partir de las fuentes listadas abajo, y ${person}.`;
    const who =
      models.length === 0
        ? "un modelo de IA"
        : models.length === 1
          ? `un modelo de IA (${models[0]})`
          : `modelos de IA (${models.join(", ")})`;
    return `Escrito por ${who} a partir de las fuentes listadas abajo, y después ${person}.`;
  },
  disclosureShort: (aiWritten, humanEdited) =>
    !aiWritten
      ? "Escrito por nuestra redacción"
      : humanEdited
        ? "Escrito con IA · editado y aprobado por una persona"
        : "Escrito con IA · aprobado por una persona",
  startsFrom: {
    before: "Parte de ",
    link: "una noticia que verificamos",
    after: ", donde se muestran cada una de sus afirmaciones y las fuentes del veredicto.",
  },
  tags: "Etiquetas",
  publishedOn: (date) => `Publicado el ${date}.`,
  moreNews: "Más noticias verificadas y nuestros artículos",
  sourcesTitle: "Fuentes",
  origin: {
    analysed: "El artículo que verificamos",
    related: "Cobertura relacionada",
    evidence: "Prueba de una verificación",
    angle: "Detrás de un enfoque constructivo que verificamos",
  },
  trendFound: (name, signal) =>
    `Encontramos esta historia a través de lo que es tendencia: «${name}»${signal ? ` (${signal})` : ""}. Que sea popular no prueba nada: lo que afirma el artículo se apoya en las fuentes de abajo.`,
  video: {
    title: "El vídeo detrás de la tendencia",
    notice: "Este vídeo está en TikTok. Cargarlo conecta tu navegador con TikTok, que puede instalar cookies y seguir tu visita.",
    load: "Cargar el vídeo de TikTok",
    open: "Abrirlo en TikTok",
    frameTitle: "Vídeo de TikTok",
  },
  checkedTitle: "Qué se verificó",
  checkedIntro: "Las afirmaciones del artículo del que partimos, tal como las juzgó nuestro verificador.",
  restsOn: "Se apoya en ",
  storyFailed: "Ahora mismo no se ha podido cargar este artículo. Vuelve a intentarlo en un momento.",
  storyMissingText: {
    before: "O no se publicó nada con este enlace, o el artículo se ha retirado. Nuestros artículos se listan en el ",
    link: "lector",
    after: ".",
  },
  storyNotFound: "Artículo no encontrado",

  rssTitle: "Inspiring News: noticias verificadas y nuestros artículos",
  rssDescription:
    "Noticias constructivas cuyas afirmaciones hemos verificado una a una, y los artículos que nuestra redacción ha escrito a partir de ellas, de la más reciente a la más antigua.",
  rssVerdict: (label, detail) => `Veredicto: ${label}${detail ? ` · ${detail}` : ""}`,
  metaDescription: (label, excerpt) => `Nuestro veredicto: ${label}. ${excerpt}`.trim(),
  badgeHelp: (label) => `${label}: qué significa este veredicto`,
  guidePage: {
    title: "Cómo leer nuestros veredictos",
    intro:
      "Cada afirmación verificada recibe uno de cinco veredictos, o ninguno cuando nuestra comprobación falló. Esta " +
      "página explica qué significa cada uno aquí, qué no significa y cómo el veredicto del artículo sale de sus afirmaciones.",
    verdictsTitle: "Los cinco veredictos",
    verdicts: {
      TRUE: "Las fuentes que encontramos respaldan la afirmación tal como se hace.",
      PARTIALLY_TRUE:
        "Lo esencial se sostiene, pero un detalle (una cifra, una fecha, quién lo dijo) no coincide con las fuentes.",
      FALSE: "Las fuentes contradicen la afirmación.",
      MISLEADING:
        "Lo que dice puede ser exacto, pero está planteado para engañar u omite un contexto que cambia su sentido.",
      UNVERIFIED:
        "Buscamos y no encontramos nada que trate la afirmación en un sentido u otro, o el modelo no pudo señalar una " +
        "fuente para su respuesta, y entonces no la mantenemos. Es una conclusión sobre las pruebas, no sobre la " +
        "afirmación: puede ser perfectamente cierta.",
    },
    notCheckedTitle: "Sin comprobar no es No verificado",
    notChecked:
      "Sin comprobar significa que la comprobación misma falló (la búsqueda web no estaba disponible o no se pudo " +
      "contactar con el modelo), así que no se valoró nada. Es un fallo nuestro, nunca un veredicto, y se cuenta aparte.",
    articleTitle: "El veredicto del artículo",
    article:
      "Un artículo toma el veredicto de su afirmación comprobada más débil, de modo que una sola no verificada pesa más " +
      "que cualquier número de verdaderas. Por eso un artículo puede figurar como No verificado aunque casi todas sus " +
      "afirmaciones sean verdaderas: la línea bajo el distintivo dice cómo salió cada una.",
    confidenceTitle: "Qué es la confianza, y qué no es",
    confidence: [
      "Es lo seguro que estaba el modelo de su veredicto, combinado con lo relevantes que eran sus pruebas, cuántas citó y cuántas había.",
      "No es la probabilidad de que la afirmación sea cierta ni una precisión medida: un veredicto con un 90% puede estar equivocado.",
      "La confianza de un artículo es la media de sus afirmaciones.",
    ],
    sourcesTitle: "Las fuentes",
    sources:
      "Cada veredicto lista las fuentes que valoró el modelo, las que citó y el pasaje en que se apoyó. La mayoría de " +
      "sitios no tiene una valoración de fiabilidad nuestra: se marcan sin valorar, sin darles una nota que no se han ganado.",
    accuracyTitle: "¿Cuántas veces acertamos?",
    accuracy:
      "Medimos los veredictos frente a afirmaciones que una persona comprobó a mano. Ese conjunto aún se está revisando, " +
      "así que todavía no publicamos aquí ninguna cifra de acierto; lo haremos, con su margen de error, cuando termine " +
      "la revisión. Mientras tanto, lee cada veredicto con sus fuentes.",
  },
};

const ca: ReaderText = {
  locale: "ca-ES",
  verdict: { TRUE: "Cert", PARTIALLY_TRUE: "Parcialment cert", FALSE: "Fals", MISLEADING: "Enganyós", UNVERIFIED: "No verificat" },
  verdictTally: (verdict, n) => {
    const [one, many] = {
      TRUE: ["certa", "certes"],
      PARTIALLY_TRUE: ["parcialment certa", "parcialment certes"],
      FALSE: ["falsa", "falses"],
      MISLEADING: ["enganyosa", "enganyoses"],
      UNVERIFIED: ["no verificada", "no verificades"],
    }[verdict];
    return `${n} ${n === 1 ? one : many}`;
  },
  notChecked: "Sense comprovar",
  languageName: { en: "Anglès", es: "Castellà", ca: "Català" },
  unknownLanguage: "Llengua desconeguda",
  topic: {
    Education: "Educació",
    "Community & Social Impact": "Comunitat i impacte social",
    Employment: "Ocupació",
    "Cities & Society": "Ciutats i societat",
    Space: "Espai",
    Technology: "Tecnologia",
    "Scientific Research": "Recerca científica",
    Biology: "Biologia",
    Climate: "Clima",
    "Nature & Biodiversity": "Natura i biodiversitat",
    Energy: "Energia",
    Sustainability: "Sostenibilitat",
    "Food & Agriculture": "Alimentació i agricultura",
    Arts: "Arts",
    Entertainment: "Entreteniment",
    "History & Heritage": "Història i patrimoni",
    Literature: "Literatura",
    "Inspirational Stories": "Històries inspiradores",
    Medicine: "Medicina",
    "Mental Health": "Salut mental",
    Nutrition: "Nutrició",
    Fitness: "Activitat física",
    "Public Health": "Salut pública",
  },
  stance: { supports: "dona suport a l'afirmació", contradicts: "contradiu l'afirmació", unrelated: "considerada no relacionada", silent: "no diu res sobre l'afirmació" },
  queryKind: { anchor: "qui i què", proposition: "el que afirma", refutation: "proves en contra" },

  switchLabel: "Llengua d'aquesta pàgina",
  backToFeed: "← Articles verificats",

  feedTitle: "Articles verificats",
  feedSubtitle:
    "Articles que han superat cada pas: tracten un tema que cobrim, són constructius, no estan duplicats i no s'han " +
    "considerat falsos ni enganyosos. Cadascun explica com han sortit les seves afirmacions i en què es basa el veredicte.",
  loadingFeed: "Carregant els articles…",
  feedFailed: (status) => `No s'han pogut carregar els articles (${status}).`,
  articles: (n) => `${n} ${n === 1 ? "article" : "articles"}`,
  match: " coincideixen",
  shown: (from, to) => ` · es mostren ${from}–${to}`,
  pages: "Pàgines",
  newer: "← Més recents",
  older: "Més antics →",
  pageOf: (page, of) => `Pàgina ${page} de ${of}`,
  filterTopic: "Tema",
  filterLanguage: "Llengua",
  all: "Tots",
  emptyNothingAnalysedTitle: "Encara no s'ha analitzat res",
  emptyNothingAnalysed: {
    before: "No hi ha cap article analitzat, així que no hi ha res per publicar. Analitza'n un a l'",
    analyzer: "Analitzador",
    middle: " o envia un lot des del panell d'ingesta de l'",
    scraper: "Scraper",
    after: "; cada article que el superi apareixerà aquí.",
  },
  emptyNothingPublishedTitle: "No s'ha publicat res",
  emptyNothingPublished: (analysed) =>
    `${ca.articles(analysed)} ${analysed === 1 ? "analitzat" : "analitzats"}, i cap no ha passat. Cadascun es va ` +
    "descartar abans de verificar-lo (fora de tema, no constructiu o duplicat) o es va considerar fals o enganyós. ",
  emptyNothingPublishedLink: "Scraper",
  emptyNothingPublishedAfter: " mostra què n'ha estat de cadascun.",
  emptyPastEndTitle: "Aquesta pàgina és més enllà del final",
  emptyPastEnd: (total) => `Hi ha ${ca.articles(total)} en menys pàgines.`,
  firstPage: "Anar a la primera pàgina",
  emptyNoMatchTitle: "Cap article publicat no hi coincideix",
  emptyNoMatch: (published, filtered) =>
    `${ca.articles(published)} ${published === 1 ? "publicat" : "publicats"}; cap no coincideix amb ` +
    `${filtered ? "aquests filtres" : "aquesta vista"}.`,
  clearFilters: "Treure els filtres",

  checkedOn: (date) => `verificat el ${date}`,
  untitled: "No s'ha extret cap titular; aquest prové de l'enllaç o del text.",

  notCheckedCount: (n) => `${n} sense comprovar`,
  searchFailedFor: (n) => `la cerca web va fallar en ${n}`,
  modelUnreachableFor: (n) => `no es va poder contactar amb el model en ${n}`,
  noAnswerFor: (n) => `el model no estava disponible o no va donar una resposta utilitzable en ${n}`,
  confidence: (pct) => `confiança ${pct}`,
  noneCouldBeChecked: "No s'ha pogut comprovar cap afirmació d'aquest article.",
  claimsSelected: (checked, total, parts) =>
    `${checked} ${checked === 1 ? "afirmació seleccionada" : "afirmacions seleccionades"}` +
    (total > checked ? ` de ${total} ${total === 1 ? "enunciat" : "enunciats"}` : "") +
    `: ${parts.join(", ")}.`,
  couldNotBeChecked: (n) => `${n} no s'${n === 1 ? "ha" : "han"} pogut comprovar`,
  ourFailureArticle: "És una fallada nostra, no una conclusió sobre l'article.",
  notCountedAsVerdict: (n, reasons) =>
    `${n === 1 ? "La que" : `Les ${n} que`} no s'${n === 1 ? "ha" : "han"} pogut comprovar ` +
    `${reasons ? `(${reasons}) ` : ""}no ${n === 1 ? "compta" : "compten"} com a veredicte: és una fallada nostra, ` +
    "no una conclusió sobre l'afirmació.",
  unverifiedByFailure: (n) =>
    ` L'article figura com a No verificat només per ${n === 1 ? "ella" : "elles"}: cap afirmació comprovada no ha sortit no verificada.`,
  weakestClaim:
    "L'article pren el veredicte de la seva afirmació més feble, de manera que una sola afirmació no verificada pesa més " +
    "que qualsevol nombre de certes. La confiança és la mitjana de les seves afirmacions.",
  belowAnchorFloor:
    "En aquest article s'han trobat menys afirmacions centrals de l'habitual, així que el veredicte es recolza en menys.",

  loadingArticle: "Carregant l'article…",
  articleFailed: (status) => `No s'ha pogut carregar l'article (${status}).`,
  missingTitle: "Aquí no hi ha cap article publicat",
  missingText:
    "O no es va publicar res amb aquest enllaç, o l'article s'ha retirat: quan es torna a verificar un article en " +
    "decideix la verificació més recent, i el que es considera fals o enganyós surt del lector.",
  by: (author) => `Per ${author}`,
  openingLabel: "Inici de l'article",
  openingOnly: "Aquí només se'n mostra l'inici.",
  readWhole: (domain) => `Llegeix l'article sencer a ${domain}`,
  claimsTitle: "Les afirmacions, una per una",
  claimsUnavailable:
    "No s'ha pogut llegir el registre amb les afirmacions d'aquest article i les seves fonts, així que només se'n coneix el veredicte global.",
  noClaims: "No s'ha comprovat cap afirmació d'aquest article.",
  statementsNotChecked: (n) => `${n} ${n === 1 ? "enunciat sense comprovar" : "enunciats sense comprovar"}`,
  notCheckedExplained:
    "Només es comproven els enunciats en què es recolza la credibilitat d'un article. Aquests s'han deixat fora; " +
    "es llisten, no es jutgen.",
  andMore: (n) => `i ${n} més.`,
  topicsAndKeywords: "Temes i paraules clau",
  provenance: (date, model, pipeline) =>
    `Verificat ${date ? `el ${date}` : "en una data desconeguda"}${model ? ` amb ${model}` : ""}` +
    `${pipeline ? `, versió del procés ${pipeline}` : ""}.`,

  guideTitle: "Com llegir les fonts",
  guide: [
    {
      term: "Fiabilitat del lloc",
      text: "La nostra valoració del lloc. La majoria no en tenen cap; aquests es marquen sense valorar i s'ordenen amb un valor neutre, no amb una valoració.",
    },
    {
      term: "Tracta l'afirmació",
      text: "Si la pàgina tracta d'aquesta afirmació. Per sota d'un mínim es descarta abans que el model la vegi, per fiable que sigui el lloc.",
    },
    {
      term: "Rellevància",
      text: "El que va posar la font davant del model: la coincidència de sentit, els termes de l'afirmació a la pàgina, com n'és de recent i la fiabilitat del lloc, combinats.",
    },
    {
      term: "Citada pel model",
      text: "El veredicte es recolza en les fonts citades. Un veredicte que el model no ha pogut avalar amb cap no es manté.",
    },
  ],

  outcome: {
    ungrounded:
      "El model va donar una resposta, però no va poder assenyalar cap font que l'avali, així que l'afirmació queda com a no verificada.",
    no_evidence:
      "Es va cercar i no va aparèixer res que tracti aquesta afirmació. Aquí, no verificada vol dir cercada i no trobada.",
    search_unavailable:
      "Sense comprovar: la cerca web va fallar, així que no es va mirar res. No és un veredicte sobre l'afirmació.",
    llm_unreachable:
      "Sense comprovar: no es va poder contactar amb el model. Les fonts trobades es llisten a sota, però ningú no les va valorar.",
    no_answer:
      "Sense comprovar: el model no estava disponible o no va donar una resposta utilitzable. Les fonts trobades es llisten a sota, però ningú no les va valorar.",
  },
  confident: (pct) => `confiança ${pct}`,
  modelAnswered: "El mateix model va respondre",
  changedBecause: "; es va canviar perquè ",
  searchFailedNote:
    "La cerca web va fallar per a aquesta afirmació; el veredicte es recolza només en articles que aquest lloc ja havia verificat.",
  sourcesAgree: "En què coincideixen les fonts",
  sourcesDiffer: "En què difereixen",
  sourcesLine: (n, cited) =>
    `${n} ${n === 1 ? "font" : "fonts"} ` +
    (cited === null
      ? n === 1 ? "trobada" : "trobades"
      : `${n === 1 ? "valorada" : "valorades"}, ${cited} ${cited === 1 ? "citada" : "citades"} pel model`),
  independentSites: (n) => ` · ${n} ${n === 1 ? "lloc independent" : "llocs independents"}`,
  setAside: (n) => `${n} ${n === 1 ? "pàgina més trobada i descartada" : "pàgines més trobades i descartades"}`,
  citedByModel: "citada pel model",
  notCited: "no citada",
  checkedHereBefore: "un article ja verificat aquí",
  whyTrusted: "Per què es va confiar en aquesta font",
  rating: {
    reliability: "Fiabilitat del lloc",
    pertinence: "Tracta l'afirmació",
    relevance: "Rellevància",
    semantic: "Coincidència de sentit",
    lexical: "Termes de l'afirmació",
    recency: "Actualitat",
  },
  unrated: "sense valorar",
  ratedSite: (pct) => `Un lloc amb una valoració de fiabilitat del ${pct}.`,
  unratedSite: (pct) => `Ningú no ha valorat aquest lloc; per ordenar-lo es va suposar un ${pct}.`,
  foundBySearch: (kinds) => ` Trobada per la cerca de ${kinds}.`,
  and: " i ",

  newsroomTitle: "De la nostra redacció",
  newsroomIntro:
    "Articles que hem escrit a partir de les notícies verificades de sota i de les verificacions que les avalen. " +
    "Cadascun s'escriu amb IA, l'aprova una persona i enllaça totes les fonts que cita.",
  storiesFailed: (error) => `No s'han pogut carregar els nostres articles: ${error}`,
  storiesLoadFailed: (status) => `No s'han pogut carregar els nostres articles (${status}).`,
  loading: "Carregant…",
  showMore: (n) => `Mostra'n més (${n})`,
  ourNewsroom: "La nostra redacció",
  howWritten: "Com es va escriure aquest article",
  disclosure: (aiWritten, humanEdited, models) => {
    const person = humanEdited
      ? "editat i aprovat per publicar-lo per una persona del nostre equip"
      : "aprovat per publicar-lo per una persona del nostre equip";
    if (!aiWritten) return `Escrit per la nostra redacció a partir de les fonts llistades a sota, i ${person}.`;
    const who =
      models.length === 0
        ? "un model d'IA"
        : models.length === 1
          ? `un model d'IA (${models[0]})`
          : `models d'IA (${models.join(", ")})`;
    return `Escrit per ${who} a partir de les fonts llistades a sota, i després ${person}.`;
  },
  disclosureShort: (aiWritten, humanEdited) =>
    !aiWritten
      ? "Escrit per la nostra redacció"
      : humanEdited
        ? "Escrit amb IA · editat i aprovat per una persona"
        : "Escrit amb IA · aprovat per una persona",
  startsFrom: {
    before: "Parteix d'",
    link: "una notícia que vam verificar",
    after: ", on es mostren cadascuna de les seves afirmacions i les fonts del veredicte.",
  },
  tags: "Etiquetes",
  publishedOn: (date) => `Publicat el ${date}.`,
  moreNews: "Més notícies verificades i els nostres articles",
  sourcesTitle: "Fonts",
  origin: {
    analysed: "L'article que vam verificar",
    related: "Cobertura relacionada",
    evidence: "Prova d'una verificació",
    angle: "Darrere d'un enfocament constructiu que vam verificar",
  },
  trendFound: (name, signal) =>
    `Vam trobar aquesta història a través del que és tendència: «${name}»${signal ? ` (${signal})` : ""}. Que sigui popular no prova res: el que afirma l'article es basa en les fonts de sota.`,
  video: {
    title: "El vídeo darrere de la tendència",
    notice: "Aquest vídeo és a TikTok. Carregar-lo connecta el teu navegador amb TikTok, que pot instal·lar galetes i seguir la teva visita.",
    load: "Carrega el vídeo de TikTok",
    open: "Obre'l a TikTok",
    frameTitle: "Vídeo de TikTok",
  },
  checkedTitle: "Què es va verificar",
  checkedIntro: "Les afirmacions de l'article del qual vam partir, tal com les va jutjar el nostre verificador.",
  restsOn: "Es recolza en ",
  storyFailed: "Ara mateix no s'ha pogut carregar aquest article. Torna-ho a provar d'aquí a un moment.",
  storyMissingText: {
    before: "O no es va publicar res amb aquest enllaç, o l'article s'ha retirat. Els nostres articles es llisten al ",
    link: "lector",
    after: ".",
  },
  storyNotFound: "Article no trobat",

  rssTitle: "Inspiring News: notícies verificades i els nostres articles",
  rssDescription:
    "Notícies constructives les afirmacions de les quals hem verificat una per una, i els articles que la nostra redacció n'ha escrit, de la més recent a la més antiga.",
  rssVerdict: (label, detail) => `Veredicte: ${label}${detail ? ` · ${detail}` : ""}`,
  metaDescription: (label, excerpt) => `El nostre veredicte: ${label}. ${excerpt}`.trim(),
  badgeHelp: (label) => `${label}: què vol dir aquest veredicte`,
  guidePage: {
    title: "Com llegir els nostres veredictes",
    intro:
      "Cada afirmació verificada rep un de cinc veredictes, o cap quan la nostra comprovació ha fallat. Aquesta pàgina " +
      "explica què vol dir cadascun aquí, què no vol dir i com el veredicte de l'article surt de les seves afirmacions.",
    verdictsTitle: "Els cinc veredictes",
    verdicts: {
      TRUE: "Les fonts que hem trobat avalen l'afirmació tal com es fa.",
      PARTIALLY_TRUE:
        "L'essencial es manté, però un detall (una xifra, una data, qui ho va dir) no coincideix amb les fonts.",
      FALSE: "Les fonts contradiuen l'afirmació.",
      MISLEADING:
        "El que diu pot ser exacte, però està plantejat per enganyar o omet un context que en canvia el sentit.",
      UNVERIFIED:
        "Hem cercat i no hem trobat res que tracti l'afirmació en un sentit o en un altre, o el model no ha pogut " +
        "assenyalar una font per a la seva resposta, i llavors no la mantenim. És una conclusió sobre les proves, no " +
        "sobre l'afirmació: pot ser perfectament certa.",
    },
    notCheckedTitle: "Sense comprovar no és No verificat",
    notChecked:
      "Sense comprovar vol dir que la comprovació mateixa ha fallat (la cerca web no estava disponible o no s'ha pogut " +
      "contactar amb el model), així que no s'ha valorat res. És una fallada nostra, mai un veredicte, i es compta a part.",
    articleTitle: "El veredicte de l'article",
    article:
      "Un article pren el veredicte de la seva afirmació comprovada més feble, de manera que una sola no verificada pesa " +
      "més que qualsevol nombre de certes. Per això un article pot figurar com a No verificat encara que gairebé totes " +
      "les seves afirmacions siguin certes: la línia sota el distintiu diu com ha sortit cadascuna.",
    confidenceTitle: "Què és la confiança, i què no és",
    confidence: [
      "És com n'estava de segur el model del seu veredicte, combinat amb com n'eren de rellevants les proves, quantes en va citar i quantes n'hi havia.",
      "No és la probabilitat que l'afirmació sigui certa ni una precisió mesurada: un veredicte amb un 90% pot ser erroni.",
      "La confiança d'un article és la mitjana de les seves afirmacions.",
    ],
    sourcesTitle: "Les fonts",
    sources:
      "Cada veredicte llista les fonts que ha valorat el model, les que ha citat i el passatge en què s'ha basat. La " +
      "majoria de llocs no tenen una valoració de fiabilitat nostra: es marquen sense valorar, sense donar-los una nota que no s'han guanyat.",
    accuracyTitle: "Quantes vegades l'encertem?",
    accuracy:
      "Mesurem els veredictes amb afirmacions que una persona ha comprovat a mà. Aquest conjunt encara s'està revisant, " +
      "així que encara no publiquem aquí cap xifra d'encert; ho farem, amb el seu marge d'error, quan acabi la revisió. " +
      "Mentrestant, llegeix cada veredicte amb les seves fonts.",
  },
};

export const READER_TEXT: Record<ReaderLang, ReaderText> = { ca, es, en };

export function readerText(lang: ReaderLang): ReaderText {
  return READER_TEXT[lang];
}

export function topicName(t: ReaderText, topic: string): string {
  return t.topic[topic] ?? topic;
}

export function languageNameIn(t: ReaderText, code: string | null): string {
  if (!code) return t.unknownLanguage;
  return t.languageName[code.toLowerCase()] ?? code.toUpperCase();
}

/**
 * A date in the page's language: "18 Sep 2026", "18 sept 2026", "18 de
 * set. del 2026". Read and printed in UTC, so the server and every
 * browser agree. A timestamp without a zone ("2026-09-12T00:00:00", how
 * the backend writes a source's date) is taken as UTC: JavaScript would
 * read it as local time, and printed in UTC it fell on the day before
 * east of Greenwich - found serving a story from a +02:00 machine.
 */
export function dateIn(t: ReaderText, iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(/T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(iso) ? `${iso}Z` : iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(t.locale, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
