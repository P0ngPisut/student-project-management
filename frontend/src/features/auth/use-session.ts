"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthApiError, currentUser, errorMessage, type AuthUser } from "./api";

type SessionState = { status: "loading" } | { status: "unauthenticated" } | { status: "authenticated"; user: AuthUser } | { status: "error"; message: string };

export function useSession() {
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [revision, setRevision] = useState(0);
  const retry = useCallback(() => { setState({ status: "loading" }); setRevision((value) => value + 1); }, []);
  useEffect(() => {
    let controller: AbortController | undefined;
    let disposed = false;
    const check = () => {
      controller?.abort();
      const next = new AbortController();
      controller = next;
      void currentUser(next.signal).then((user) => {
        if (!disposed && !next.signal.aborted) setState({ status: "authenticated", user });
      }).catch((error: unknown) => {
        if (disposed || next.signal.aborted) return;
        setState(error instanceof AuthApiError && error.status === 401
          ? { status: "unauthenticated" } : { status: "error", message: errorMessage(error) });
      });
    };
    check();
    window.addEventListener("focus", check);
    window.addEventListener("pageshow", check);
    return () => {
      disposed = true;
      controller?.abort();
      window.removeEventListener("focus", check);
      window.removeEventListener("pageshow", check);
    };
  }, [revision]);
  return { state, retry };
}
