import { createContext, useContext, useState, type Context as ReactContext, type ReactNode } from "react";
import { DEMO_ACCOUNTS, type DemoAccount } from "@/mockData";
import { endApiSession, startApiSession, writeAudit, type AuditEvent, type BackendUser } from "@/api";
import type { DemoRole } from "@/lib/role-rules";

type SessionUser = DemoAccount & { signedInAt: string };
interface DemoSession {
  user: SessionUser | null;
  audit: AuditEvent[];
  signIn: (id: string) => void;
  /** Adopts an account the backend has already signed in (email + password or registration). */
  signInAs: (backend: BackendUser) => SessionUser;
  signOut: () => void;
  log: (what: string, outcome?: string, target?: { patient?: string; request?: string; area?: string }) => void;
}
const ROLE_OF: Record<string, DemoRole> = { hospital: "hospital", hospital_it: "it_admin", hdab_staff: "hdab", interested_party: "interested" };
const LABEL_OF: Record<string, string> = { hdab_staff: "HDAB Staff", interested_party: "Applicant" };
export function fromBackendUser(u: BackendUser): DemoAccount {
  const hospitalRole = u.hospital_role === "senior_doctor" || u.hospital_role === "doctor" || u.hospital_role === "it_admin" ? u.hospital_role : undefined;
  return { id: u.id, name: u.name, role: ROLE_OF[u.role] ?? "visitor", roleLabel: u.hospital_role_label ?? LABEL_OF[u.role] ?? u.role, organisation: u.organisation, method: u.sign_in_method ?? "email + password", email: u.email ?? undefined, hospitalRole, permissions: u.permissions };
}
export const canReleaseLetters = (u: DemoAccount | null | undefined) => !!u?.permissions?.includes("release_letters");
const now = () => new Date().toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
// Keep the context identity during preview updates; old providers and refreshed
// consumers must use the same context. This stores no account or session data.
const previousContext = import.meta.hot?.data?.["demoSessionContext"] as ReactContext<DemoSession | null> | undefined;
const Context = previousContext ?? createContext<DemoSession | null>(null);
if (import.meta.hot?.data) import.meta.hot.data["demoSessionContext"] = Context;
export function DemoSessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DemoSession["user"]>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const record = (account: DemoAccount, what: string, outcome = "Completed", target: { patient?: string; request?: string; area?: string } = {}) => {
    const event: AuditEvent = { id: crypto.randomUUID(), userId: account.id, who: account.name, role: account.role, organisation: account.organisation, what, when: new Date().toISOString(), outcome, ...target };
    setAudit((a) => [event, ...a]);
    void writeAudit(event);
  };
  const signIn = (id: string) => {
    const a = DEMO_ACCOUNTS.find((a) => a.id === id); if (!a) return;
    // Permissions shown in the UI come from the backend once it answers; the backend enforces them either way.
    void startApiSession(a.id).then((b) => { if (b) setUser((u) => (u?.id === a.id ? { ...u, permissions: b.permissions, roleLabel: b.hospital_role_label ?? u.roleLabel } : u)); });
    setUser({ ...a, signedInAt: now() }); record(a, "Sign in", "Demo account selected", { area: "account" });
  };
  const signInAs = (b: BackendUser) => { const a = { ...fromBackendUser(b), signedInAt: now() }; setUser(a); record(a, "Sign in", "Email and password", { area: "account" }); return a; };
  return <Context.Provider value={{ user, audit, signIn, signInAs,
    signOut: () => { if (user) record(user, "Sign out", "Session ended", { area: "account" }); endApiSession(); setUser(null); },
    log: (what, outcome, target) => { if (user) record(user, what, outcome, target); },
  }}>{children}</Context.Provider>;
}
export function useDemoSession() { const c = useContext(Context); if (!c) throw new Error("DemoSessionProvider missing"); return c; }
