import { createContext, useContext, useState, type Context, type ReactNode } from "react";
import { INITIAL_ACCESS_LOG, type AccessEntry } from "@/mockData";
import type { LetterDocument, Evaluation } from "@/api";

export interface EditEntry { id: string; section: string; before: string; after: string; who: string; when: string }
export interface LetterState {
  generated: boolean;
  status: "DRAFT" | "SIGNED";
  overrides: Record<string, string>;
  edits: EditEntry[];
  signedAt?: string;
}
export interface ConsentState { loggedIn: boolean; crossBorder: boolean; hidden: string[]; saved: boolean; since?: string }
export interface CrossBorderSession { identityChecked: boolean; informed: boolean; emergency: boolean; reason: string; logged: boolean }

interface AppState {
  applications: Record<string, Evaluation[]>;
  setApplications: (f: (a: Record<string, Evaluation[]>) => Record<string, Evaluation[]>) => void;
  providedRequests: Record<string, string>;
  setProvidedRequests: (f: (a: Record<string, string>) => Record<string, string>) => void;
  datasetDescription: string | null;
  setDatasetDescription: (s: string) => void;
  documents: Record<string, LetterDocument>;
  setDocuments: (f: (d: Record<string, LetterDocument>) => Record<string, LetterDocument>) => void;
  superseded: LetterDocument[];
  setSuperseded: (f: (d: LetterDocument[]) => LetterDocument[]) => void;
  accessLog: AccessEntry[];
  addAccess: (e: Omit<AccessEntry, "id" | "when"> & { when?: string }) => void;
  optedOut: boolean;
  setOptedOut: (v: boolean) => void;
  tourStep: number | null;
  setTourStep: (n: number | null) => void;
  letter: LetterState;
  setLetter: (f: (l: LetterState) => LetterState) => void;
  consent: ConsentState;
  setConsent: (f: (c: ConsentState) => ConsentState) => void;
  xb: CrossBorderSession;
  setXb: (f: (c: CrossBorderSession) => CrossBorderSession) => void;
  ipsGenerated: boolean;
  setIpsGenerated: (v: boolean) => void;
}

// Preserve only context identity across preview updates, never the private state.
const previousContext = import.meta.hot?.data?.["appStateContext"] as Context<AppState | null> | undefined;
const Ctx = previousContext ?? createContext<AppState | null>(null);
if (import.meta.hot?.data) import.meta.hot.data["appStateContext"] = Ctx;

export const INITIAL_XB: CrossBorderSession = { identityChecked: false, informed: false, emergency: false, reason: "", logged: false };

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [applications, setApplications] = useState<Record<string, Evaluation[]>>({});
  const [providedRequests, setProvidedRequests] = useState<Record<string, string>>({});
  const [datasetDescription, setDatasetDescription] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Record<string, LetterDocument>>({});
  const [superseded, setSuperseded] = useState<LetterDocument[]>([]);
  const [accessLog, setLog] = useState<AccessEntry[]>(INITIAL_ACCESS_LOG);
  const [optedOut, setOptedOut] = useState(true);
  const [tourStep, setTourStep] = useState<number | null>(null);
  const [letter, setLetter] = useState<LetterState>({ generated: false, status: "DRAFT", overrides: {}, edits: [] });
  const [consent, setConsent] = useState<ConsentState>({ loggedIn: false, crossBorder: true, hidden: [], saved: false });
  const [xb, setXb] = useState<CrossBorderSession>(INITIAL_XB);
  const [ipsGenerated, setIpsGenerated] = useState(false);
  const addAccess: AppState["addAccess"] = (e) => {
    const when = e.when ?? new Date().toISOString().slice(0, 16).replace("T", " ");
    setLog((l) => [{ ...e, id: crypto.randomUUID(), when }, ...l]);
  };
  return (
    <Ctx.Provider value={{ applications, setApplications, providedRequests, setProvidedRequests, datasetDescription, setDatasetDescription, documents, setDocuments, superseded, setSuperseded, accessLog, addAccess, optedOut, setOptedOut, tourStep, setTourStep, letter, setLetter, consent, setConsent, xb, setXb, ipsGenerated, setIpsGenerated }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAppState() {
  const c = useContext(Ctx);
  if (!c) throw new Error("AppStateProvider missing");
  return c;
}
