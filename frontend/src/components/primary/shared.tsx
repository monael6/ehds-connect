import { AlertTriangle, Bone, Droplet, Pill } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { UI, CODE_SYSTEM, type Lang, type Patient, type AccessEntry } from "@/mockData";
import { term } from "@/api";
import { useAppState } from "@/lib/app-state";

const CodeTag = ({ c, sys }: { c: string; sys: string }) => (
  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">{sys} {c}</span>
);

/** IPS cards. `lang` = clinical terms, `labelLang` = section headings. Hidden sections are omitted. */
export function IpsCards({ p, lang, labelLang = lang, showCodes = true, hidden = [] }: { p: Patient; lang: Lang; labelLang?: Lang; showCodes?: boolean; hidden?: string[] }) {
  const sec = (k: keyof typeof UI) => UI[k][labelLang];
  const show = (k: string) => !hidden.includes(k);
  const row = "flex flex-wrap items-center justify-between gap-2 text-sm";
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {show("problems") && <Card><CardHeader className="pb-3"><CardTitle className="text-base">{sec("problems")}</CardTitle></CardHeader><CardContent className="space-y-2">
        {p.problems.length ? p.problems.map((x) => <div key={x.code} className={row}><span>{term(x.code, lang)}{x.since && <span className="text-muted-foreground"> ({x.since})</span>}{x.source && <span className="block text-xs text-muted-foreground">Source: {x.source}</span>}</span>{showCodes && <CodeTag c={x.code} sys={CODE_SYSTEM.problems} />}</div>) : <p className="text-sm text-muted-foreground">{UI.none[labelLang]}</p>}
      </CardContent></Card>}
      {show("medications") && <Card><CardHeader className="pb-3"><CardTitle className="text-base">{sec("medications")}</CardTitle></CardHeader><CardContent className="space-y-2">
        {p.medications.length ? p.medications.map((x) => <div key={x.code} className={row}><span>{term(x.code, lang).replace(/ \(.*\)$/, "")} · <span className="text-muted-foreground">{x.dose[lang]}</span>{x.source && <span className="block text-xs text-muted-foreground">Source: {x.source}</span>}</span>{showCodes && <CodeTag c={x.code} sys="ATC" />}</div>) : <p className="text-sm text-muted-foreground">{UI.none[labelLang]}</p>}
      </CardContent></Card>}
      {show("allergies") && <Card><CardHeader className="pb-3"><CardTitle className="text-base">{sec("allergies")}</CardTitle></CardHeader><CardContent className="space-y-2">
        {p.allergies.length ? p.allergies.map((x) => <div key={x.code} className={row}><span className="flex flex-wrap items-center gap-2">{term(x.code, lang)}{x.source && <span className="w-full text-xs text-muted-foreground">Source: {x.source}</span>}{x.severity === "high" && <Badge variant="outline" className="border-destructive/30 bg-destructive-soft text-destructive">high</Badge>}</span>{showCodes && <CodeTag c={x.code} sys="SNOMED" />}</div>)
          : <p className="text-sm font-medium">{UI.noAllergies[labelLang]}</p>}
      </CardContent></Card>}
      {show("implants") && <Card><CardHeader className="pb-3"><CardTitle className="text-base">{sec("implants")}</CardTitle></CardHeader><CardContent className="space-y-2">
        {p.implants.length ? p.implants.map((x) => <div key={x.code} className={row}><span>{term(x.code, lang)}{x.source && <span className="block text-xs text-muted-foreground">Source: {x.source}</span>}</span>{showCodes && !x.source && <CodeTag c={x.code} sys="SNOMED" />}</div>) : <p className="text-sm text-muted-foreground">{UI.none[labelLang]}</p>}
      </CardContent></Card>}
      {p.checks?.length ? <Card className="border-warning/40 md:col-span-2"><CardHeader className="pb-3"><CardTitle className="text-base">For the doctor to review</CardTitle><p className="text-sm text-muted-foreground">Mentioned in the documents but not taken into this summary. The system makes no diagnosis – please check the sources and decide.</p></CardHeader><CardContent className="space-y-2">
        {p.checks.map((c) => <div key={c.text} className="text-sm"><span className="font-medium">{c.text}</span><span className="block text-xs text-muted-foreground">Source: {c.source}</span></div>)}
      </CardContent></Card> : null}
      {show("measurements") && p.measurements.length > 0 && <Card className="md:col-span-2"><CardHeader className="pb-3"><CardTitle className="text-base">{sec("measurements")}</CardTitle></CardHeader><CardContent>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1.5 font-medium">Test</th>{showCodes && <th className="font-medium">LOINC</th>}<th className="font-medium">Value</th><th className="font-medium">Date</th></tr></thead>
          <tbody>{p.measurements.map((m) => <tr key={m.code} className="border-t"><td className="py-2">{term(m.code, lang)}</td>{showCodes && <td className="font-mono text-xs">{m.code}</td>}<td>{m.value} {m.unit}</td><td className="text-muted-foreground">{m.date}</td></tr>)}</tbody>
        </table></div>
      </CardContent></Card>}
    </div>
  );
}

function EItem({ icon: Icon, label, value, code }: { icon: typeof Pill; label: string; value: string; code?: string | undefined }) {
  return (
    <div className="rounded-xl bg-background p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-destructive"><Icon className="h-4 w-4" />{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
      {code && <div className="font-mono text-xs text-muted-foreground">{code}</div>}
    </div>
  );
}

const CRITICAL: Record<string, Record<Lang, string>> = {
  medication: { en: "Critical medication", de: "Kritische Medikation", it: "Farmaco critico" },
  condition: { en: "Critical condition", de: "Kritische Erkrankung", it: "Condizione critica" },
};

export function EmergencyPanel({ p, lang, showCodes = true }: { p: Patient; lang: Lang; showCodes?: boolean }) {
  // Emergency information selected by the backend, when the summary came from FastAPI.
  if (p.emergency?.length) return (
    <div className="rounded-2xl border-2 border-destructive/40 bg-destructive-soft p-5" role="alert">
      <div className="flex items-center gap-2 font-semibold text-destructive"><AlertTriangle className="h-5 w-5" />{UI.emergency[lang]}</div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {p.emergency.map((e) => <EItem key={`${e.type}-${e.code ?? e.text}`} icon={e.type === "medication" ? Droplet : AlertTriangle} label={(CRITICAL[e.type] ?? CRITICAL["condition"])?.[lang] ?? ""} value={e.text} code={showCodes && e.code ? `${e.type === "medication" ? "ATC" : "ICD-10"} ${e.code}` : undefined} />)}
      </div>
    </div>
  );
  const anticoag = p.medications.filter((m) => m.anticoagulant);
  const crit = p.allergies.filter((a) => a.severity === "high");
  if (anticoag.length + crit.length + p.implants.length === 0) return null;
  return (
    <div className="rounded-2xl border-2 border-destructive/40 bg-destructive-soft p-5" role="alert">
      <div className="flex items-center gap-2 font-semibold text-destructive"><AlertTriangle className="h-5 w-5" />{UI.emergency[lang]}</div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {anticoag.map((m) => <EItem key={m.code} icon={Droplet} label={UI.anticoag[lang]} value={`${term(m.code, lang).replace(/ \(.*\)$/, "")} ${m.dose[lang]}`} code={showCodes ? `ATC ${m.code}` : undefined} />)}
        {crit.map((a) => <EItem key={a.code} icon={Pill} label={UI.allergies[lang]} value={term(a.code, lang)} code={showCodes ? `SNOMED CT ${a.code}` : undefined} />)}
        {p.implants.map((i) => <EItem key={i.code} icon={Bone} label={UI.implants[lang]} value={term(i.code, lang)} code={showCodes ? `SNOMED CT ${i.code}` : undefined} />)}
      </div>
    </div>
  );
}

const decisionStyle: Record<string, string> = {
  ALLOW: "border-success/30 bg-success-soft text-success",
  ALLOW_CROSS_BORDER: "border-success/30 bg-success-soft text-success",
  ALLOW_EMERGENCY: "border-destructive/30 bg-destructive-soft text-destructive",
  DENY: "border-destructive/30 bg-destructive-soft text-destructive",
  LOGGED: "",
};

export function DecisionBadge({ d }: { d: string }) {
  return <Badge variant="outline" className={`font-mono text-[11px] ${decisionStyle[d] ?? ""}`}>{d}</Badge>;
}

export function AccessLogTable({ entries }: { entries: AccessEntry[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-muted-foreground">{["When", "Who", "Patient", "Sections", "Decision · rule", "Reason", "Type"].map((h) => <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>)}</tr></thead>
        <tbody>{entries.map((e) => (
          <tr key={e.id} className={`border-t align-top ${e.kind === "break-the-glass" ? "bg-destructive-soft/60" : ""}`}>
            <td className="whitespace-nowrap py-2 pr-3 font-mono text-xs">{e.when}</td>
            <td className="pr-3"><div className="font-medium">{e.who}</div><div className="text-xs text-muted-foreground">{[e.role, e.org, e.country].filter(Boolean).join(" · ")}</div></td>
            <td className="whitespace-nowrap pr-3 font-mono text-xs">{e.patient ?? "—"}</td>
            <td className="pr-3">{e.sections.join(", ")}</td>
            <td className="pr-3">{e.decision ? <div className="flex flex-col items-start gap-1"><DecisionBadge d={e.decision} />{e.rule && <span className="text-xs text-muted-foreground">Rule {e.rule}</span>}</div> : "—"}</td>
            <td className="pr-3 text-xs text-muted-foreground">{e.reason ?? "—"}</td>
            <td>{e.kind === "break-the-glass" ? <Badge variant="outline" className="border-destructive/30 bg-destructive text-destructive-foreground">EMERGENCY</Badge> : <Badge variant="outline">Normal</Badge>}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

export function GlobalAccessLog() {
  const { accessLog } = useAppState();
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-base">Access log</CardTitle></CardHeader>
      <CardContent><AccessLogTable entries={accessLog.filter((e) => e.kind !== "blocked-download")} /></CardContent>
    </Card>
  );
}
