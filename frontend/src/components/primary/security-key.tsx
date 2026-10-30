import { useEffect, useState } from "react";
import { KeyRound, Nfc, ShieldAlert, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getMyKeys, reportKeyLost, type SecurityKey, type SignatureProof } from "@/api";
import { enrolKey, hasSoftwareKey, signLetterChallenge, webauthnAvailable } from "@/lib/security-key";

const message = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/** Sign with a personal security key; register one first, report a lost one, or use a recovery code from IT. */
export function SecurityKeySign({ letterId, onSigned, disabled }: { letterId: string; onSigned: (proof: SignatureProof) => Promise<void>; disabled?: boolean }) {
  const [keys, setKeys] = useState<SecurityKey[] | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [recovery, setRecovery] = useState(""); const [needsRecovery, setNeedsRecovery] = useState(false);
  const load = () => getMyKeys().then(setKeys).catch((e) => setError(message(e)));
  useEffect(() => { void load(); }, []);
  const run = async (f: () => Promise<void>) => { setBusy(true); setError(""); try { await f(); } catch (e) { setError(message(e)); const d = (e as { detail?: { needs_recovery_code?: boolean } }).detail; if (d?.needs_recovery_code) setNeedsRecovery(true); } finally { setBusy(false); } };
  const active = (keys ?? []).filter((k) => k.status === "active");
  const enrol = (kind: "webauthn" | "software") => run(async () => { await enrolKey(kind, kind === "software" ? "Simulated key (this tab)" : "Security key / NFC badge", recovery || undefined); setRecovery(""); setNeedsRecovery(false); await load(); });
  if (!keys) return <p className="text-sm text-muted-foreground">{error || "Loading your security keys…"}</p>;
  return <div className="space-y-4 text-sm">
    {active.length > 0 ? <div className="space-y-2">
      <p className="font-medium">Tap your key to sign</p>
      {active.map((k) => <div key={k.id} className="flex flex-wrap items-center gap-2 rounded-md border p-3">
        {k.kind === "webauthn" ? <Nfc className="h-4 w-4 text-primary" /> : <KeyRound className="h-4 w-4 text-muted-foreground" />}
        <span className="flex-1">{k.label}{k.kind === "software" && !hasSoftwareKey(k.id) && <span className="block text-xs text-warning">Not available in this tab</span>}</span>
        <Button size="sm" disabled={busy || disabled} onClick={() => run(async () => onSigned(await signLetterChallenge(letterId, k)))}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign"}</Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => run(async () => { await reportKeyLost(k.id); await load(); })}>Report lost</Button>
      </div>)}
    </div> : <p className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft p-3"><ShieldAlert className="h-4 w-4 shrink-0" />{keys.length ? "All your keys are blocked. Ask your IT admin for a one-time recovery code (photo ID check in person), then register a new key." : "Register your personal security key once. Then you sign with one tap."}</p>}
    {(needsRecovery || (keys.length > 0 && active.length === 0)) && <label className="block space-y-1">Recovery code from IT<Input value={recovery} onChange={(e) => setRecovery(e.target.value)} placeholder="ABCD-EF12-3456" /></label>}
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" size="sm" disabled={busy || !webauthnAvailable()} onClick={() => enrol("webauthn")}><Nfc className="h-4 w-4" />{active.length ? "Add backup key" : "Register security key / NFC badge"}</Button>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => enrol("software")}><KeyRound className="h-4 w-4" />Use simulated key (demo)</Button>
    </div>
    <p className="text-xs text-muted-foreground">FIDO2 key, NFC hospital badge or Touch ID. Lost your key? Report it lost. It's blocked at once. Sign with your backup key, or get a recovery code from IT. Until then a senior doctor can sign.</p>
    {error && <p role="alert" className="text-destructive">{error}</p>}
  </div>;
}
