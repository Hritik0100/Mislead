import { create } from 'zustand';
import { User, Case, Account, Post, Claim, Evidence, GraphData, TimelineEvent } from './types';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string) => void;
  logout: () => void;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: (user, token) => {
    localStorage.setItem('osint-nexus-token', token);
    localStorage.setItem('osint-nexus-user', JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem('osint-nexus-token');
    localStorage.removeItem('osint-nexus-user');
    set({ user: null, token: null, isAuthenticated: false });
  },
  updateUser: (userData) =>
    set((state) => ({
      user: state.user ? { ...state.user, ...userData } : null,
    })),
}));

interface CaseState {
  cases: Case[];
  currentCase: Case | null;
  loading: boolean;
  error: string | null;
  setCases: (cases: Case[]) => void;
  setCurrentCase: (caseData: Case | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addCase: (caseData: Case) => void;
  updateCase: (id: string, caseData: Partial<Case>) => void;
  removeCase: (id: string) => void;
}

export const useCaseStore = create<CaseState>((set) => ({
  cases: [],
  currentCase: null,
  loading: false,
  error: null,
  setCases: (cases) => set({ cases }),
  setCurrentCase: (caseData) => set({ currentCase: caseData }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  addCase: (caseData) =>
    set((state) => ({ cases: [...state.cases, caseData] })),
  updateCase: (id, caseData) =>
    set((state) => ({
      cases: state.cases.map((c) => (c.id === id ? { ...c, ...caseData } : c)),
      currentCase:
        state.currentCase?.id === id
          ? { ...state.currentCase, ...caseData }
          : state.currentCase,
    })),
  removeCase: (id) =>
    set((state) => ({
      cases: state.cases.filter((c) => c.id !== id),
      currentCase: state.currentCase?.id === id ? null : state.currentCase,
    })),
}));

interface InvestigationState {
  accounts: Account[];
  posts: Post[];
  claims: Claim[];
  evidence: Evidence[];
  graph: GraphData | null;
  timeline: TimelineEvent[];
  loading: boolean;
  error: string | null;
  setAccounts: (accounts: Account[]) => void;
  setPosts: (posts: Post[]) => void;
  setClaims: (claims: Claim[]) => void;
  setEvidence: (evidence: Evidence[]) => void;
  setGraph: (graph: GraphData | null) => void;
  setTimeline: (timeline: TimelineEvent[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addAccount: (account: Account) => void;
  addPost: (post: Post) => void;
  addClaim: (claim: Claim) => void;
  addEvidence: (evidence: Evidence) => void;
  clearInvestigation: () => void;
}

export const useInvestigationStore = create<InvestigationState>((set) => ({
  accounts: [],
  posts: [],
  claims: [],
  evidence: [],
  graph: null,
  timeline: [],
  loading: false,
  error: null,
  setAccounts: (accounts) => set({ accounts }),
  setPosts: (posts) => set({ posts }),
  setClaims: (claims) => set({ claims }),
  setEvidence: (evidence) => set({ evidence }),
  setGraph: (graph) => set({ graph }),
  setTimeline: (timeline) => set({ timeline }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  addAccount: (account) =>
    set((state) => ({ accounts: [...state.accounts, account] })),
  addPost: (post) =>
    set((state) => ({ posts: [...state.posts, post] })),
  addClaim: (claim) =>
    set((state) => ({ claims: [...state.claims, claim] })),
  addEvidence: (evidence) =>
    set((state) => ({ evidence: [...state.evidence, evidence] })),
  clearInvestigation: () =>
    set({
      accounts: [],
      posts: [],
      claims: [],
      evidence: [],
      graph: null,
      timeline: [],
      error: null,
    }),
}));
