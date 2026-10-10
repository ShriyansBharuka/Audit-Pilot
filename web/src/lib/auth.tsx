"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserRole, UserSession } from "./types";
import { api } from "./api";

// Default demo session (Engagement Partner CA S. Mehta)
export const DEFAULT_PARTNER_SESSION: UserSession = {
  token: "ptn_HOw8AhBiFdvqvyFwCbWt6CFBk8xicWaV",
  principal: "ptn.mehta",
  role: "engagement_partner",
  name: "CA S. Mehta",
  membership_no: "ICAI-094128",
};

interface AuthContextType {
  user: UserSession | null;
  loading: boolean;
  loginWithToken: (token: string) => Promise<void>;
  switchRole: (role: UserRole) => Promise<void>;
  logout: () => void;
  identities: any[];
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  loginWithToken: async () => {},
  switchRole: async () => {},
  logout: () => {},
  identities: [],
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [identities, setIdentities] = useState<any[]>([]);

  useEffect(() => {
    // Load identities from backend for quick switcher
    api
      .getIdentities()
      .then((ids) => {
        setIdentities(ids);
        // Check stored token or default to partner
        const stored = localStorage.getItem("auditpilot_token");
        if (stored) {
          const matched = ids.find((i) => i.token === stored);
          if (matched) {
            setUser({
              token: matched.token,
              principal: matched.principal,
              role: matched.role,
              name: matched.name,
              membership_no: matched.membership_no,
            });
            return;
          }
        }
        // Fallback default demo partner
        setUser(DEFAULT_PARTNER_SESSION);
        localStorage.setItem("auditpilot_token", DEFAULT_PARTNER_SESSION.token);
      })
      .catch((err) => {
        console.warn("Could not load identities from API, using default partner:", err);
        setUser(DEFAULT_PARTNER_SESSION);
      })
      .finally(() => setLoading(false));
  }, []);

  const loginWithToken = async (token: string) => {
    setLoading(true);
    try {
      const res = await api.tokenLogin(token);
      const session: UserSession = {
        token: res.token,
        principal: res.principal,
        role: res.role,
        name: res.name,
        membership_no: res.membership_no,
      };
      setUser(session);
      localStorage.setItem("auditpilot_token", session.token);
    } finally {
      setLoading(false);
    }
  };

  const switchRole = async (targetRole: UserRole) => {
    const matched = identities.find((i) => i.role === targetRole);
    if (matched) {
      await loginWithToken(matched.token);
    }
  };

  const logout = () => {
    localStorage.removeItem("auditpilot_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        loginWithToken,
        switchRole,
        logout,
        identities,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
