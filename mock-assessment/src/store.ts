import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  sessionId: string | null;
  setTokens: (access: string, refresh: string, username: string) => void;
  setSession: (id: string | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      username: null,
      sessionId: null,
      setTokens: (accessToken, refreshToken, username) => set({ accessToken, refreshToken, username }),
      setSession: (sessionId) => set({ sessionId }),
      logout: () => set({ accessToken: null, refreshToken: null, username: null, sessionId: null }),
    }),
    { name: "assessment-auth", storage: { getItem: (k) => {
      const v = sessionStorage.getItem(k);
      return v ? JSON.parse(v) : null;
    }, setItem: (k, v) => sessionStorage.setItem(k, JSON.stringify(v)), removeItem: (k) => sessionStorage.removeItem(k) } },
  ),
);
