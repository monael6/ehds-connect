import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { useDemoSession } from "@/lib/demo-session";
import { validPatientIdentity } from "@/lib/identity-rules";
import { ArrowRight, Bell, Building2, Check, CheckCircle2, Globe2, KeyRound, Landmark, ShieldAlert, X, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PATIENTS, UI, DEMO_TIME, type Lang } from "@/mockData";
import { evaluateCrossBorderAccess, getCrossBorderSummary, saveCrossBorderConsent } from "@/api";
import { Provenance } from "@/components/provenance";
import { useAppState, INITIAL_XB } from "@/lib/app-state";
import { EmergencyPanel, IpsCards } from "./shared";

export const XB_STEPS = ["Patient portal (Austria)", "Simulated hospital system Italy", "Request via MyHealth@EU", "Patient Summary in Italian", "Patient notification"];
const SECTIONS = ["problems", "medications", "allergies", "implants", "measurements"] as const;
const ROSSI = { who: "Dr. Giulia Rossi", role: "Physician", org: "Ospedale di Firenze", country: "IT", patient: "p-4cfd3cf1" };


function Stepper({ step, go }: { step: number; go: (n: number) => void }) {
  return (
    <ol className="flex flex-wrap gap-2" aria-label="Cross-border steps">
      {XB_STEPS.map((s, i) => {
        const n = i + 1;
        return (
          <li key={s}>
            <Button variant="outline" onClick={() => go(n)} aria-current={n === step ? "step" : undefined}
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${n === step ? "border-primary bg-primary text-primary-foreground" : n < step ? "border-success/30 bg-success-soft text-success" : "text-muted-foreground hover:bg-muted"}`}>
              <span className="grid h-5 w-5 place-items-center rounded-full bg-background/30 font-mono">{n < step ? <Check className="h-3 w-3" /> : n}</span>{s}
            </Button>
          </li>
        );
      })}
    </ol>
  );
}

function useDecision() {
  const { xb, consent } = useAppState();
  const input = { authorised: true, crossBorder: true, identityChecked: xb.identityChecked, informed: xb.informed, crossBorderOptIn: consent.saved && consent.crossBorder, emergency: xb.emergency, reason: xb.reason };
  return useSuspenseQuery(queryOptions({ queryKey: ["crossborder-access", input], queryFn: () => evaluateCrossBorderAccess(input) })).data.data;
}

function Portal({ next }: { next: () => void }) {
  const { consent, setConsent, addAccess } = useAppState();
  const save = async () => {
    const date = new Date().toLocaleString("de-AT");
    try { await saveCrossBorderConsent(consent, date); } catch (e) { toast.error(e instanceof Error ? e.message : "Consent could not be saved"); return; }
    setConsent((c) => ({ ...c, saved: true, since: date }));
    addAccess({ who: "Maria Muster", role: "Patient", org: "Patient portal (mock)", country: "AT", patient: "p-4cfd3cf1", sections: ["Cross-border consent"], decision: "LOGGED", reason: `Consent stored – MyHealth@EU ${consent.crossBorder ? "ON" : "OFF"}${consent.hidden.length ? `, hidden: ${consent.hidden.join(", ")}` : ""}`, kind: "normal", when: DEMO_TIME.consent });
    toast.success("Consent stored");
  };
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 bg-primary px-5 py-3 text-primary-foreground"><Landmark className="h-5 w-5" /><span className="font-semibold">Health portal Austria</span><span className="ml-auto text-xs opacity-80">mock – no official service</span></div>
      <CardContent className="space-y-5 p-6">
        {!consent.loggedIn ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-muted-foreground">Sign in to manage who may see your health data.</p>
            <Button onClick={() => setConsent((c) => ({ ...c, loggedIn: true }))}><KeyRound className="h-4 w-4" />Log in with ID Austria</Button>
          </div>
        ) : (
          <>
            <p className="text-sm">Signed in as <span className="font-semibold">Maria Muster</span> · born 17.03.1943</p>
            <label className="flex items-start justify-between gap-4 rounded-xl border p-4">
              <span><span className="font-medium">Allow doctors in other EU countries to access my Patient Summary (MyHealth@EU)</span><span className="mt-1 block text-xs text-muted-foreground">You can withdraw this at any time. Separate from your research opt-out.</span></span>
              <Switch checked={consent.crossBorder} onCheckedChange={(v) => setConsent((c) => ({ ...c, crossBorder: v, saved: false }))} />
            </label>
            {consent.crossBorder && (
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">Hide single sections</legend>
                <div className="flex flex-wrap gap-4">{SECTIONS.map((s) => (
                  <label key={s} className="flex items-center gap-2 text-sm"><Checkbox checked={consent.hidden.includes(s)} onCheckedChange={(v) => setConsent((c) => ({ ...c, saved: false, hidden: v ? [...c.hidden, s] : c.hidden.filter((x) => x !== s) }))} />Hide {UI[s].en.toLowerCase()}</label>
                ))}</div>
              </fieldset>
            )}
            {consent.saved && <p className="text-sm text-success">{consent.crossBorder ? "Cross-border access allowed" : "Cross-border access withdrawn"} since {consent.since}</p>}
            <div className="flex flex-wrap gap-2">
              <Button onClick={save} disabled={consent.saved}>{consent.saved ? <><CheckCircle2 className="h-4 w-4" />Saved</> : "Save"}</Button>
              <Button variant="outline" onClick={next}>Continue to Italy <ArrowRight className="h-4 w-4" /></Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ItalyHospital({ next }: { next: () => void }) {
  const { setXb } = useAppState();
  useEffect(() => { setXb(() => ({ ...INITIAL_XB })); }, []);
  const [docType, setDocType] = useState("passport");
  const [docNumber, setDocNumber] = useState("");
  const [name, setName] = useState("Maria Muster");
  const [born, setBorn] = useState("1943-03-17");
  const [checked, setChecked] = useState(false);
  const [informed, setInformed] = useState(false);
  const [btg, setBtg] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <Card className="overflow-hidden border-italy/40">
      <div className="bg-italy px-5 py-3 text-italy-foreground">
        <div className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-90">SIMULATION – Italian hospital system</div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm"><Building2 className="h-4 w-4" /><span className="font-semibold">Dr. Giulia Rossi, Ospedale di Firenze</span><span className="opacity-90">– logged in via Italian system, confirmed by NCPeH Italy</span></div>
      </div>
      <CardContent className="space-y-4 p-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Patient's country"><Input value="Austria" readOnly /></Field>
          <Field label="ID document type">
            <Select value={docType} onValueChange={(v) => { setDocType(v); setChecked(false); }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="passport">Passport</SelectItem><SelectItem value="idcard">National ID card</SelectItem><SelectItem value="austria-code">ID Austria one-time code (8 digits)</SelectItem></SelectContent></Select>
          </Field>
          <Field label="Document number"><Input value={docNumber} onChange={(e) => { setDocNumber(e.target.value); setChecked(false); }} placeholder={docType === "austria-code" ? "8 digits" : "Document number"} /></Field>
          <Field label="Name"><Input value={name} onChange={(e) => { setName(e.target.value); setChecked(false); }} /></Field>
          <Field label="Date of birth"><Input type="date" value={born} onChange={(e) => { setBorn(e.target.value); setChecked(false); }} /></Field>
        </div>
        <div className="space-y-2 text-sm">
          <label className="flex items-center gap-2"><Checkbox checked={checked} onCheckedChange={(v) => setChecked(v === true)} />Identity checked against ID document</label>
          <label className="flex items-center gap-2"><Checkbox checked={informed} onCheckedChange={(v) => setInformed(v === true)} />Patient informed and agrees</label>
        </div>
        <p className="text-xs text-muted-foreground">In future: patient can present EUDI Wallet instead.</p>
        <div className="flex flex-wrap gap-2">
          <Button className="bg-italy text-italy-foreground hover:bg-italy/90" disabled={!validPatientIdentity(docType, docNumber, name, born, checked, informed)} onClick={() => { setXb(() => ({ ...INITIAL_XB, identityChecked: true, informed: true })); next(); }}>
            <Globe2 className="h-4 w-4" />Request Patient Summary via MyHealth@EU
          </Button>
          <Button variant="destructive" onClick={() => setBtg(true)}><ShieldAlert className="h-4 w-4" />Patient unconscious – emergency access (Break the glass)</Button>
        </div>
      </CardContent>
      <Dialog open={btg} onOpenChange={setBtg}>
        <DialogContent>
          <DialogHeader><DialogTitle>Break the glass</DialogTitle><DialogDescription>Skips identity check and consent. Only the emergency section is shown. The access is logged as EMERGENCY and the patient will be notified.</DialogDescription></DialogHeader>
          <label htmlFor="btg" className="text-sm font-medium">Reason (required)</label>
          <Textarea id="btg" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Unconscious after fall, suspected intracranial bleeding" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setBtg(false)}>Cancel</Button>
            <Button variant="destructive" disabled={reason.trim().length < 5} onClick={() => { setXb(() => ({ ...INITIAL_XB, emergency: true, reason: reason.trim() })); setBtg(false); next(); }}>Confirm emergency access</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <label className="space-y-1 text-sm"><span className="text-xs text-muted-foreground">{label}</span>{children}</label>
);

function MyHealthEu({ next }: { next: () => void }) {
  const { xb, setXb, consent, addAccess } = useAppState();
  const d = useDecision();
  const [n, setN] = useState(0);
  const logged = useRef(false);
  const nodes = ["Ospedale di Firenze", "NCPeH Italy", "NCPeH Austria", "Austrian system"];
  const checks = [
    { t: "Doctor authorised (vouched by NCPeH Italy)", ok: true },
    { t: "Patient found (p-4cfd3cf1)", ok: true },
    xb.emergency ? { t: `Emergency reason documented: “${xb.reason}”`, ok: d.decision !== "DENY" } : { t: "Cross-border consent", ok: d.decision !== "DENY" },
    { t: xb.emergency ? "Emergency information prepared from hospital records" : "Patient Summary prepared from hospital records", ok: true },
    { t: "Securely transmitted through the national contact points", ok: true },
  ];
  const stopAt = checks.findIndex((c) => !c.ok);
  const total = stopAt === -1 ? checks.length : stopAt + 1;

  useEffect(() => {
    setN(0);
    const id = setInterval(() => setN((x) => (x >= total ? x : x + 1)), 650);
    return () => clearInterval(id);
  }, [total]);

  const done = n >= total;
  useEffect(() => {
    if (!done || xb.logged || logged.current || d.decision !== "DENY") return;
    logged.current = true;
    const visible = SECTIONS.filter((s) => !consent.hidden.includes(s));
    addAccess({ ...ROSSI, sections: d.decision === "DENY" ? [] : xb.emergency ? ["emergency section"] : visible, decision: d.decision, rule: d.rule, reason: xb.emergency ? xb.reason : d.explanation, kind: xb.emergency ? "break-the-glass" : "normal", when: DEMO_TIME.crossBorder });
    setXb((s) => ({ ...s, logged: true }));
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Card><CardContent className="space-y-6 p-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        {nodes.map((node, i) => (
          <div key={node} className="flex flex-1 items-center gap-2">
            <div className={`flex-1 rounded-xl border-2 px-3 py-3 text-center text-sm font-medium transition-all duration-500 ${n >= i ? "border-primary bg-primary-soft" : "opacity-50"}`}>{node}</div>
            {i < nodes.length - 1 && <ArrowRight className={`h-5 w-5 shrink-0 transition-colors ${n > i ? "text-primary" : "text-muted-foreground/40"}`} aria-hidden />}
          </div>
        ))}
      </div>
      <ul className="space-y-2" aria-live="polite">
        {checks.slice(0, n).map((c) => (
          <li key={c.t} className={`flex items-center gap-2 text-sm animate-in fade-in slide-in-from-left-2 ${c.ok ? "" : "text-destructive"}`}>
            {c.ok ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4" />}{c.t} {c.ok ? "✓" : "✗"}
          </li>
        ))}
      </ul>
      {done && (
        <div className="flex flex-wrap items-center gap-3 border-t pt-4">
          <span className={`text-sm ${d.decision === "DENY" ? "text-destructive" : "text-success"}`}>{d.decision === "DENY" ? `Access not possible – ${!xb.identityChecked ? "identity not checked" : "no consent from the patient"}` : xb.emergency ? "Emergency access – logged, the patient will be informed" : `Access allowed – the patient allowed cross-border access on ${consent.since ?? DEMO_TIME.consent}`}</span>
          {d.decision !== "DENY" && <Button className="ml-auto" onClick={next}>Show Patient Summary <ArrowRight className="h-4 w-4" /></Button>}
        </div>
      )}
    </CardContent></Card>
  );
}

function ItalianSummary({ lang, setLang, next }: { lang: Lang; setLang: (l: Lang) => void; next: () => void }) {
  const { xb, setXb, consent, addAccess } = useAppState();
  const { log } = useDemoSession();
  const d = useDecision();
  const releaseLogged = useRef(false);
  const [codes, setCodes] = useState(false);
  const input = { authorised: true, crossBorder: true, identityChecked: xb.identityChecked, informed: xb.informed, crossBorderOptIn: consent.saved && consent.crossBorder, emergency: xb.emergency, reason: xb.reason };
  const { data: summary } = useSuspenseQuery(queryOptions({ queryKey: ["crossborder-summary", lang, input, consent.hidden], queryFn: async () => d.decision === "DENY" ? null : getCrossBorderSummary(input, lang, consent.hidden) }));
  useEffect(() => {
    if (!summary || xb.logged || releaseLogged.current) return;
    releaseLogged.current = true;
    addAccess({ ...ROSSI, sections: summary.sections, decision: d.decision, reason: xb.emergency ? xb.reason : d.explanation, kind: xb.emergency ? "break-the-glass" : "normal" });
    setXb((s) => ({ ...s, logged: true }));
    log("Cross-border summary released", `${d.decision} · ${summary.sections.join(", ")} · ${summary.source}`, { patient: ROSSI.patient, area: "crossborder" });
  }, [summary, xb.logged]);
  const frauM = summary?.patient;
  if (d.decision === "DENY") return <Card><CardContent className="flex items-center gap-2 p-6 text-destructive"><X className="h-5 w-5" />Access denied – {d.explanation}</CardContent></Card>;
  if (!frauM) return <p>Patient Summary unavailable.</p>;
  return (
    <div className="space-y-4">
      <div className={`rounded-lg border p-3 text-sm ${xb.emergency ? "border-destructive/30 bg-destructive-soft text-destructive" : "border-success/30 bg-success-soft text-success"}`}>{xb.emergency ? "Emergency access – logged, the patient will be informed" : `Access allowed – the patient allowed cross-border access on ${consent.since ?? DEMO_TIME.consent}`}</div>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">{UI.title[lang]} · Maria Muster</h2>
        <div role="radiogroup" aria-label="Language" className="ml-auto flex rounded-lg border p-1 text-sm">
          {(["it", "en", "de"] as Lang[]).map((l) => (
            <Button variant="ghost" key={l} role="radio" aria-checked={lang === l} onClick={() => setLang(l)} className={`rounded-md px-3 py-1 ${lang === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>{l.toUpperCase()}</Button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm"><Switch checked={codes} onCheckedChange={setCodes} />{UI.codes[lang]}</label>
      </div>
      <EmergencyPanel p={frauM} lang={lang} showCodes={codes} />
      {xb.emergency ? (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive-soft p-3 text-sm text-destructive"><Bell className="h-4 w-4" />Emergency access – only the emergency section is shown. Patient will be notified.</div>
      ) : <IpsCards p={frauM} lang={lang} showCodes={codes} hidden={consent.hidden} />}
      <Button variant="outline" onClick={next}>Back to patient portal <ArrowRight className="h-4 w-4" /></Button>
      <Provenance source={`${summary?.source} · Austrian hospital records via MyHealth@EU (simulation)`} />
    </div>
  );
}

function Notification() {
  const { accessLog } = useAppState();
  const fmt = (w: string) => { const [d, t] = w.split(" "); const [y, m, day] = (d ?? "").split("-"); return `${day}.${m}.${y} at ${t}`; };
  const items = accessLog.filter((e) => e.country === "IT" && (e.patient === "p-4cfd3cf1" || e.patient === "P-00421") && e.decision !== "DENY");
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 bg-primary px-5 py-3 text-primary-foreground"><Landmark className="h-5 w-5" /><span className="font-semibold">Health portal Austria</span><span className="ml-auto text-xs opacity-80">Maria Muster</span></div>
      <CardContent className="space-y-3 p-6">
        <h2 className="flex items-center gap-2 font-semibold"><Bell className="h-4 w-4 text-primary" />Who looked at my data</h2>
        {items.length === 0 ? <p className="text-sm text-muted-foreground">No access from other EU countries yet.</p> : items.map((e) => (
          <div key={e.id} className={`rounded-xl border p-4 text-sm ${e.kind === "break-the-glass" ? "border-destructive/40 bg-destructive-soft" : ""}`}>
            {e.kind === "break-the-glass" && <Badge variant="outline" className="mb-2 border-destructive/30 bg-destructive text-destructive-foreground">EMERGENCY</Badge>}
            <p>{e.who}, {e.org}, {e.kind === "break-the-glass" ? "used emergency access to" : "viewed"} your Patient Summary on {fmt(e.when)} (sections: {e.sections.join(", ")}){e.kind === "break-the-glass" && e.reason ? `. Reason: ${e.reason}` : ""}.</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function CrossBorderFlow({ step, go, lang, setLang }: { step: number; go: (n: number) => void; lang: Lang; setLang: (l: Lang) => void }) {
  const { log } = useDemoSession();
  const move = (n: number) => { log("Cross-border step", `Step ${n}`, { patient: "p-4cfd3cf1", area: "crossborder" }); go(n); };
  return (
    <div className="space-y-6">
      <Stepper step={step} go={move} />
      {step === 1 && <Portal next={() => move(2)} />}
      {step === 2 && <ItalyHospital next={() => move(3)} />}
      {step === 3 && <MyHealthEu next={() => move(4)} />}
      {step === 4 && <ItalianSummary lang={lang} setLang={setLang} next={() => move(5)} />}
      {step === 5 && <Notification />}
      <p className="text-xs text-muted-foreground">AI support (e.g. spoken translation): planned</p>
    </div>
  );
}
