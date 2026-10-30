import { createContext, useContext, useState, type Context as ReactContext, type ReactNode } from "react";
import { DEMO_ACCOUNTS, type DemoAccount } from "@/mockData";
import { writeAudit, type AuditEvent } from "@/api";

interface DemoSession {
  user: (DemoAccount & { signedInAt: string }) | null;
  audit: AuditEvent[];
  signIn: (id: string) => void;
  signOut: () => void;
  log: (what: string, outcome?: string, target?: { patient?: string; request?: string; area?: string }) => void;
}
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
  return <Context.Provider value={{ user, audit,
    signIn: (id) => { const a = DEMO_ACCOUNTS.find((a) => a.id === id); if (!a) return; setUser({ ...a, signedInAt: new Date().toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }) }); record(a, "Sign in", "Demo account selected", { area: "account" }); },
    signOut: () => { if (user) record(user, "Sign out", "Demo session ended", { area: "account" }); setUser(null); },
    log: (what, outcome, target) => { if (user) record(user, what, outcome, target); },
  }}>{children}</Context.Provider>;
}
export function useDemoSession() { const c = useContext(Context); if (!c) throw new Error("DemoSessionProvider missing"); return c; }