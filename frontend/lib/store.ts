import { create } from "zustand";
import { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  setUser: (u: User | null) => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  setUser: (u) => set({ user: u }),
}));

interface UiState {
  sidebarCollapsed: boolean;
  chatOpen: boolean;
  toggleSidebar: () => void;
  setChatOpen: (open: boolean) => void;
}

export const useUi = create<UiState>((set) => ({
  sidebarCollapsed: false,
  chatOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setChatOpen: (open) => set({ chatOpen: open }),
}));
