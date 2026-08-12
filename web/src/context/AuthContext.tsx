import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Me } from "../api/types";

interface AuthState {
  user: Me | null;
  loading: boolean;
  /** Re-runs the initial /me check, e.g. right after logging out. */
  refresh: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    // Deliberately a plain fetch, not api/client's apiFetch: a 401 here just
    // means "not logged in yet", which is the normal starting state, not a
    // session that expired mid-use -- apiFetch's blanket "401 -> reload"
    // handling is for the latter and would otherwise loop on this page.
    fetch("/api/me", { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error("unauthenticated");
        return res.json() as Promise<Me>;
      })
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [nonce]);

  const refresh = () => setNonce((n) => n + 1);

  return (
    <AuthContext.Provider value={{ user, loading, refresh }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
