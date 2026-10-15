import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { CurrentUser, TokenPair } from "./types";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function fetchCurrentUser() {
    try {
      const res = await api.get<CurrentUser>("/api/auth/me");
      setUser(res.data);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const token = localStorage.getItem("medintel_access_token");
    if (token) {
      fetchCurrentUser();
    } else {
      setIsLoading(false);
    }
  }, []);

  async function login(email: string, password: string) {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);

    const res = await api.post<TokenPair>("/api/auth/login", body, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    localStorage.setItem("medintel_access_token", res.data.access_token);
    localStorage.setItem("medintel_refresh_token", res.data.refresh_token);
    await fetchCurrentUser();
  }

  function logout() {
    localStorage.removeItem("medintel_access_token");
    localStorage.removeItem("medintel_refresh_token");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
