"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserRole, UserSession } from "./types";
import { api, getActiveTenant, setActiveTenant } from "./api";
import { supabase } from "./supabase";

const TOKEN_KEY = "auditpilot_token";
const MODE_KEY = "auditpilot_account"; // "supabase" when the token is a Supabase session

interface AuthContextType {
  user: UserSession | null;
  loading: boolean;
  loginWithToken: (token: string) => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<{ confirm: boolean }>;
  refresh: () => Promise<void>;
  switchRole: (role: UserRole) => Promise<void>;
  logout: () => void;
  identities: any[];
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  loginWithToken: async () => {},
  signInWithEmail: async () => {},
  signUpWithEmail: async () => ({ confirm: false }),
  refresh: async () => {},
  switchRole: async () => {},
  logout: () => {},
  identities: [],
});

// sign-in and Supabase's SIGNED_IN event arrive together: share one lookup per token instead of racing
let inflight: { token: string; p: Promise<UserSession> } | null = null;
function supabaseSession(accessToken: string): Promise<UserSession> {
  if (inflight?.token === accessToken) return inflight.p;
  const p = loadSupabaseSession(accessToken).finally(() => {
    if (inflight?.p === p) inflight = null;
  });
  inflight = { token: accessToken, p };
  return p;
}

/** Supabase access token -> session: memberships decide the active organisation, the server decides the role. */
async function loadSupabaseSession(accessToken: string): Promise<UserSession> {
  const previous = getActiveTenant();
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(MODE_KEY, "supabase");
  setActiveTenant(null); // ask for memberships without an organisation this account may not open
  const m = await api.getMemberships();
  const keep = m.items.find((x) => x.slug === previous);
  setActiveTenant(keep ? keep.slug : m.items[0]?.slug ?? null);
  const res = await api.tokenLogin(accessToken); // role in the active organisation (null when it has none)
  return {
    token: accessToken,
    principal: res.principal,
    role: res.role,
    name: res.name,
    membership_no: res.membership_no,
    account: "supabase",
    email: m.email,
    memberships: m.items,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [identities, setIdentities] = useState<any[]>([]);

  useEffect(() => {
    // Identities carry no tokens unless the API runs with DEMO_ROLE_SWITCHER=1 (never the partner's).
    api.getIdentities().then(setIdentities).catch(() => setIdentities([]));

    (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (data.session) {
          setUser(await supabaseSession(data.session.access_token));
          return;
        }
        const stored = localStorage.getItem(TOKEN_KEY);
        if (stored && localStorage.getItem(MODE_KEY) !== "supabase") {
          const res = await api.tokenLogin(stored);
          setUser({ token: res.token, principal: res.principal, role: res.role, name: res.name, membership_no: res.membership_no, account: "token" });
        } else {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(MODE_KEY);
        }
      } catch {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(MODE_KEY);
      } finally {
        setLoading(false);
      }
    })();

    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "TOKEN_REFRESHED" && session) {
        localStorage.setItem(TOKEN_KEY, session.access_token);
        setUser((u) => (u && u.account === "supabase" ? { ...u, token: session.access_token } : u));
      }
      // e.g. returning from the e-mail confirmation link
      if (event === "SIGNED_IN" && session && localStorage.getItem(TOKEN_KEY) !== session.access_token) {
        supabaseSession(session.access_token).then(setUser).catch(() => setUser(null));
      }
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const loginWithToken = async (token: string) => {
    const res = await api.tokenLogin(token); // throws on an unknown token; the login form shows the message
    // a different identity may not see the previous organisation: start from the default one
    if (token !== localStorage.getItem(TOKEN_KEY)) setActiveTenant(null);
    localStorage.setItem(TOKEN_KEY, res.token);
    localStorage.setItem(MODE_KEY, "token");
    setUser({ token: res.token, principal: res.principal, role: res.role, name: res.name, membership_no: res.membership_no, account: "token" });
  };

  const signInWithEmail = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error || !data.session) throw new Error(error?.message || "Sign-in failed");
    setUser(await supabaseSession(data.session.access_token));
  };

  const signUpWithEmail = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/signin` },
    });
    if (error) throw new Error(error.message);
    if (data.session) {
      setUser(await supabaseSession(data.session.access_token));
      return { confirm: false };
    }
    return { confirm: true }; // e-mail confirmation is on for this project
  };

  /** Re-read memberships and the role (after onboarding, an invite, or switching organisation). */
  const refresh = async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    if (localStorage.getItem(MODE_KEY) === "supabase") setUser(await supabaseSession(token));
    else await loginWithToken(token);
  };

  const switchRole = async (targetRole: UserRole) => {
    const matched = identities.find((i) => i.role === targetRole);
    if (matched?.token) {
      await loginWithToken(matched.token);
    }
  };

  const logout = () => {
    if (localStorage.getItem(MODE_KEY) === "supabase") supabase.auth.signOut().catch(() => undefined);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(MODE_KEY);
    setActiveTenant(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, loginWithToken, signInWithEmail, signUpWithEmail, refresh, switchRole, logout, identities }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
