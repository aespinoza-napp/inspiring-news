"use client";

import { useCallback, useEffect, useState } from "react";

// Reader accounts (backend src/api/account_routes.py), through
// app/api/account/[...path].

export interface AccountUser {
  username: string;
  email: string | null;
  createdAt: string;
}

export interface AccountState {
  user: AccountUser | null;
  csrf: string | null;
  loading: boolean;
}

// What the backend reads as "from our own pages" on sign-in and
// registration: a cross-site form cannot set a header.
const OURS = { "X-Requested-With": "inspiring-news" };

export class AccountRequestError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

// A call to /api/account/<path>: JSON in and out, the CSRF token on every
// state change, the backend's own message on failure.
export async function accountCall<T = unknown>(path: string, options: { method?: "GET" | "POST"; body?: unknown; csrf?: string | null } = {}): Promise<T | null> {
  const method = options.method ?? (options.body === undefined ? "GET" : "POST");
  const response = await fetch(`/api/account/${path}`, {
    method,
    cache: "no-store",
    headers: {
      ...OURS,
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(options.csrf ? { "X-CSRF-Token": options.csrf } : {}),
    },
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
  });

  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? "Please check the form." : `The request failed (${response.status}).`;
    throw new AccountRequestError(message, response.status);
  }

  return data as T;
}

// Who is signed in, if anyone, and the CSRF token their page sends back.
export function useAccount(): AccountState & { refresh(): Promise<void> } {
  const [state, setState] = useState<AccountState>({ user: null, csrf: null, loading: true });

  const refresh = useCallback(async () => {
    try {
      const me = await accountCall<{ user: AccountUser; csrf: string }>("me");
      setState({ user: me?.user ?? null, csrf: me?.csrf ?? null, loading: false });
    } catch {
      setState({ user: null, csrf: null, loading: false });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { ...state, refresh };
}
