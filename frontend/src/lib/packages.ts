// Ready-to-post packages of a draft (backend src/api/package_routes.py,
// src/models/writer/package.py). Mirrors the backend's shapes exactly.

export type PackageChannelName = "wordpress" | "instagram" | "stories" | "tiktok";

export interface PackageFile {
  path: string;
  channel: PackageChannelName;
  kind: string;
  bytes: number;
  sha256: string;
  width: number | null;
  height: number | null;
}

export interface WordPressDelivery {
  postId: number;
  status: string;
  link: string | null;
  sentAt: string;
}

export interface ChannelPackage {
  channel: PackageChannelName;
  files: string[];
  caption: string | null;
  link: string | null;
  steps: string[];
  delivery: WordPressDelivery | null;
}

export interface PackageManifest {
  id: string;
  draftId: string;
  createdAt: string;
  language: string;
  edition: string;
  title: string;
  contentHash: string;
  draftStatus: string;
  link: string | null;
  channels: ChannelPackage[];
  files: PackageFile[];
  notes: string[];
}

export interface PackageChannel {
  name: PackageChannelName;
  label: string;
  canSend: boolean;
  note: string | null;
}

export interface PackageList {
  packages: PackageManifest[];
  channels: PackageChannel[];
  currentContentHash: string;
}

/** Where a package's file is read from, through the packages proxy. */
export function packageFileUrl(manifest: PackageManifest, path: string): string {
  return `/api/packages/${manifest.draftId}/${manifest.id}/files/${path}`;
}

export function packageZipUrl(manifest: PackageManifest): string {
  return `/api/packages/${manifest.draftId}/${manifest.id}/zip`;
}

export async function packagesApi<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const response = await fetch(`/api/packages/${path}`, {
    method: init?.method ?? "GET",
    cache: "no-store",
    headers: init?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : null;
    throw new Error(detail ?? data?.error ?? `Request failed (${response.status}).`);
  }

  return data as T;
}
