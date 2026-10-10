"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserRole, UserSession } from "./types";
import { api, setActiveTenant } from "./api";

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
    // Identities carry no tokens unless the API runs with DEMO_ROLE_SWITCHER=1 (never the partner's).
    api.getIdentities().then(setIdentities).catch(() => setIdentities([]));
    const stored = localStorage.getItem("auditpilot_token");
    if (!stored) {
      setLoading(false);
      return;
    }
    api
      .tokenLogin(stored)
      .then((res) =>
        setUser({ token: res.token, principal: res.principal, role: res.role, name: res.name, membership_no: res.membership_no })
      )
      .catch(() => localStorage.removeItem("auditpilot_token"))
      .finally(() => setLoading(false));
  }, []);

  const loginWithToken = async (token: string) => {
    const res = await api.tokenLogin(token); // throws on an unknown token; the login form shows the message
    const session: UserSession = {
      token: res.token,
      principal: res.principal,
      role: res.role,
      name: res.name,
      membership_no: res.membership_no,
    };
    // a different identity may not see the previous organisation: start from the default one
    if (session.token !== localStorage.getItem("auditpilot_token")) setActiveTenant(null);
    setUser(session);
    localStorage.setItem("auditpilot_token", session.token);
  };

  const switchRole = async (targetRole: UserRole) => {
    const matched = identities.find((i) => i.role === targetRole);
    if (matched?.token) {
      await loginWithToken(matched.token);
    }
  };

  const logout = () => {
    localStorage.removeItem("auditpilot_token");
    setActiveTenant(null);
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
