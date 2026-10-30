import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { KeyRound, UserCheck, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { activateAccount, getHospitalStaff, grantRelease, issueRecoveryCode, markKeyLostFor, revokeRelease, setHospitalRole, type BackendUser } from "@/api";
import { useDemoSession } from "@/lib/demo-session";
import { pageHead } from "@/lib/page-head";

export const Route = createFileRoute("/admin")({ head: () => pageHead("Team and permissions", "Hospital roles, release permissions and security keys."), component: Admin });

const ROLE_OPTIONS = [{ id: "senior_doctor", label: "Senior Doctor" }, { id: "doctor", label: "Doctor" }, { id: "it_admin", label: "IT Admin" }];

function Admin() {
  const { user, log } = useDemoSession();
  const qc = useQueryClient();
  const isIt = user?.role === "it_admin"; const isSenior = user?.hospitalRole === "senior_doctor";
  const staff = useQuery({ queryKey: ["hospital-staff", user?.id], queryFn: getHospitalStaff, enabled: isIt || isSenior });
  const [recoveryFor, setRecoveryFor] = useState<BackendUser | null>(null); const [checked, setChecked] = useState(false);
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null);
  const act = async (what: string, f: () => Promise<unknown>) => { try { await f(); log(what, "Saved", { area: "admin" }); toast.success(what); await qc.invalidateQueries({ queryKey: ["hospital-staff"] }); } catch (e) { toast.error(e instanceof Error ? e.message : "Not saved"); } };
  if (!isIt && !isSenior) return <div className="mx-auto max-w-3xl px-6 py-12"><h1 className="text-2xl font-semibold">Team and permissions</h1><p className="mt-3 text-muted-foreground">Only senior doctors and IT admins can manage permissions.</p></div>;
  const rows = staff.data ?? [];
  const pending = rows.filter((r) => r.status === "pending");
  return <div className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-6">
    <div><h1 className="text-2xl font-semibold">{isIt ? "Users and permissions" : "My team"}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{isIt ? "Activate accounts, assign roles and help doctors who lost their security key." : "Allow a doctor to sign discharge letters and release them to ELGA."}</p></div>
    <section className="grid gap-3 rounded-lg border bg-card p-4 text-sm sm:grid-cols-3">
      <div><p className="font-semibold">Senior Doctor</p><p className="text-muted-foreground">Writes, signs and releases letters to ELGA. Can authorise doctors.</p></div>
      <div><p className="font-semibold">Doctor</p><p className="text-muted-foreground">Writes letters. Signs and releases only with a senior doctor's permission.</p></div>
      <div><p className="font-semibold">IT Admin</p><p className="text-muted-foreground">Manages accounts and keys. No access to patient data.</p></div>
    </section>
    {staff.error && <p role="alert" className="text-sm text-destructive">{staff.error.message}</p>}
    {isIt && pending.length > 0 && <section className="space-y-3"><h2 className="font-semibold">Waiting for activation</h2>{pending.map((p) => <div key={p.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/30 bg-warning-soft p-4 text-sm"><div className="flex-1"><p className="font-medium">{p.name}</p><p className="text-muted-foreground">{p.email} · registered as {p.hospital_role_label}</p></div><Button size="sm" onClick={() => act(`Activated ${p.name}`, () => activateAccount(p.id))}><UserCheck className="h-4 w-4" />Activate</Button></div>)}</section>}
    <section className="space-y-3"><h2 className="font-semibold">Staff</h2>
      {rows.filter((r) => r.status !== "pending").map((s) => { const releases = s.permissions.includes("release_letters"); const lostKeys = (s.keys ?? []).filter((k) => k.status === "lost").length; const activeKeys = (s.keys ?? []).filter((k) => k.status === "active");
        return <article key={s.id} className="space-y-3 rounded-lg border bg-card p-4 text-sm">
          <div className="flex flex-wrap items-center gap-3"><div className="flex-1"><p className="font-medium">{s.name}{s.id === user?.id && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}</p><p className="text-muted-foreground">{s.email}</p></div>
            {isIt && s.id !== user?.id ? <Select value={s.hospital_role ?? ""} onValueChange={(v) => act(`Role of ${s.name} changed`, () => setHospitalRole(s.id, v))}><SelectTrigger className="w-44" aria-label={`Role of ${s.name}`}><SelectValue /></SelectTrigger><SelectContent>{ROLE_OPTIONS.map((r) => <SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>)}</SelectContent></Select> : <Badge variant="outline">{s.hospital_role_label}</Badge>}
          </div>
          {s.role === "hospital" && <div className="flex flex-wrap items-center gap-2 border-t pt-3">
            <ShieldCheck className={`h-4 w-4 ${releases ? "text-success" : "text-muted-foreground"}`} />
            <span className="flex-1">{s.hospital_role === "senior_doctor" ? "Can sign and release letters (senior doctor)" : releases ? "Authorised to sign and release letters" : "Cannot sign or release letters"}</span>
            {s.hospital_role === "doctor" && !releases && isSenior && <Button size="sm" onClick={() => act(`${s.name} may now release letters`, () => grantRelease(s.id))}>Allow releasing letters</Button>}
            {s.hospital_role === "doctor" && releases && <Button size="sm" variant="outline" onClick={() => act(`Permission of ${s.name} revoked`, () => revokeRelease(s.id))}>Revoke</Button>}
          </div>}
          {isIt && s.role === "hospital" && <div className="flex flex-wrap items-center gap-2 border-t pt-3"><KeyRound className="h-4 w-4 text-muted-foreground" /><span className="flex-1">{activeKeys.length} active security key{activeKeys.length === 1 ? "" : "s"}{lostKeys ? ` · ${lostKeys} reported lost` : ""}</span>
            {activeKeys.map((k) => <Button key={k.id} size="sm" variant="ghost" onClick={() => act(`Key of ${s.name} blocked`, () => markKeyLostFor(s.id, k.id))}>Block "{k.label}"</Button>)}
            <Button size="sm" variant="outline" onClick={() => { setRecoveryFor(s); setChecked(false); setCode(null); }}>Issue recovery code</Button></div>}
        </article>; })}
      {staff.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
    </section>
    <Dialog open={!!recoveryFor} onOpenChange={(o) => !o && setRecoveryFor(null)}><DialogContent><DialogHeader><DialogTitle>Recovery code for {recoveryFor?.name}</DialogTitle><DialogDescription>For a doctor who lost their security key and has no backup key. The code is valid for 24 hours and registers one new key.</DialogDescription></DialogHeader>
      {code ? <div className="space-y-2 text-center"><p className="font-mono text-2xl font-semibold tracking-widest">{code.code}</p><p className="text-xs text-muted-foreground">Shown only once. Hand it over in person. Valid until {new Date(code.expires_at).toLocaleString("de-AT")}.</p></div>
        : <label className="flex items-start gap-3 text-sm"><Checkbox checked={checked} onCheckedChange={(v) => setChecked(v === true)} />I checked this person's photo ID in person.</label>}
      <DialogFooter>{!code && <Button disabled={!checked || !recoveryFor} onClick={async () => { if (!recoveryFor) return; try { setCode(await issueRecoveryCode(recoveryFor.id)); log("Issued recovery code", "Identity checked in person", { area: "admin" }); } catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); } }}>Issue code</Button>}<Button variant="outline" onClick={() => setRecoveryFor(null)}>Close</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}
