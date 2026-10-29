"use client";

import Link from "next/link";
import { useState } from "react";

import { accountCall, useAccount, type AccountUser } from "@/lib/account";
import styles from "@/components/map/MapPage.module.css";

type Mode = "signin" | "register";

function Field({ label, hint, ...input }: { label: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className={styles.field}>
      <span>{label}</span>
      <input className={styles.searchInput} {...input} />
      {hint && <span className={styles.muted}>{hint}</span>}
    </label>
  );
}

function Privacy() {
  return (
    <section className="claims-note" aria-label="What an account keeps">
      <p>
        <strong>What an account keeps, and why.</strong> Your username and, only if you give it, an email address
        (nothing is sent to it: there is no mail). Your password as an argon2id hash, never the password itself. When
        each of your sessions began and was last used, so a session nobody uses ends after 30 days. Later, the topics,
        names and stories you choose to follow or save, and the connections you draw, for your own map.
      </p>
      <p>
        It is kept apart from the newsroom&apos;s data, never logged, never shown to anyone else and never used for
        anything but your own map. One cookie, the session; no tracking, no analytics. You can download all of it or
        delete all of it, at once, below.
      </p>
    </section>
  );
}

export default function AccountPage() {
  const { user, csrf, loading, refresh } = useAccount();

  return (
    <div className={styles.narrow}>
      <h1>Your account</h1>
      {loading ? <p className={styles.muted}>Loading…</p> : user ? <SignedIn user={user} csrf={csrf} refresh={refresh} /> : <SignedOut refresh={refresh} />}
      <Privacy />
    </div>
  );
}

function SignedOut({ refresh }: { refresh(): Promise<void> }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await accountCall(mode === "signin" ? "login" : "register", {
        body: mode === "signin" ? { username, password } : { username, password, email: email || null },
      });
      setPassword("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <p className="subtitle">
        An account keeps your interests, so <Link href="/map">the map</Link> can show you what you follow. Reading needs
        none.
      </p>
      <div className={styles.toolbar} role="tablist" aria-label="Sign in or create an account">
        <button type="button" role="tab" aria-selected={mode === "signin"} className={mode === "signin" ? undefined : "button-secondary"} onClick={() => setMode("signin")}>
          Sign in
        </button>
        <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? undefined : "button-secondary"} onClick={() => setMode("register")}>
          Create an account
        </button>
      </div>
      <form onSubmit={submit} className={styles.form}>
        <Field label="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required minLength={3} maxLength={32} hint={mode === "register" ? "3 to 32 letters, digits, dots, dashes or underscores." : undefined} />
        <Field label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "signin" ? "current-password" : "new-password"} required minLength={10} maxLength={128} hint={mode === "register" ? "At least 10 characters." : undefined} />
        {mode === "register" && (
          <Field label="Email (optional)" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} hint="Kept only if you give it. Nothing is sent to it." />
        )}
        {error && <p className="error-banner" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>
          {mode === "signin" ? "Sign in" : "Create the account"}
        </button>
      </form>
    </>
  );
}

function SignedIn({ user, csrf, refresh }: { user: AccountUser; csrf: string | null; refresh(): Promise<void> }) {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const run = async (action: () => Promise<unknown>, done: string) => {
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(done);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <p>
        Signed in as <strong>{user.username}</strong>
        {user.email ? ` (${user.email})` : ""}, since {user.createdAt.slice(0, 10)}.
      </p>
      <div className={styles.toolbar}>
        <button type="button" className="button-secondary" onClick={() => run(async () => { await accountCall("logout", { method: "POST", csrf }); await refresh(); }, "Signed out.")}>
          Sign out
        </button>
        <a className="button-secondary" href="/api/account/export" download>
          Download everything kept about you
        </a>
      </div>

      {message && <p className="claims-note" role="status">{message}</p>}
      {error && <p className="error-banner" role="alert">{error}</p>}

      <h2 className="section-label">Change the password</h2>
      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await accountCall("password", { body: { current, new: next }, csrf });
            setCurrent("");
            setNext("");
          }, "Password changed. Every other session has been signed out.");
        }}
      >
        <Field label="Current password" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required />
        <Field label="New password" type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" required minLength={10} maxLength={128} />
        <button type="submit">Change the password</button>
      </form>

      <h2 className="section-label">Delete the account</h2>
      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          if (!window.confirm("Delete the account and everything kept about you? This cannot be undone.")) return;
          void run(async () => {
            await accountCall("delete", { body: { password: confirm }, csrf });
            await refresh();
          }, "The account and everything kept about you are deleted.");
        }}
      >
        <p className={styles.muted}>Removes the account and everything it keeps, at once. It cannot be undone.</p>
        <Field label="Password, to confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="current-password" required />
        <button type="submit" className={styles.danger}>Delete everything</button>
      </form>
    </>
  );
}
