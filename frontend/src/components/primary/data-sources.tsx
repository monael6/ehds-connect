import { Fragment, useState } from "react";
import { ArrowRight, Cog, Database, FileJson, Loader2, MonitorSmartphone, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { HL7_ORU, HL7_ADT } from "@/mockData";
import { convertWithEngine } from "@/api";
import { FIELD_MAP } from "@/lib/hl7";

export const TONE: Record<number, string> = { 1: "bg-map-1", 2: "bg-map-2", 3: "bg-map-3", 4: "bg-map-4", 5: "bg-map-5", 6: "bg-map-6" };

function Node({ icon: Icon, title, sub }: { icon: typeof Server; title: string; sub?: string }) {
  return (
    <div className="flex min-w-[150px] flex-1 items-center gap-2 rounded-xl border-2 bg-card px-3 py-3">
      <Icon className="h-5 w-5 shrink-0 text-primary" aria-hidden />
      <div><div className="text-sm font-semibold leading-tight">{title}</div>{sub && <div className="text-xs text-muted-foreground">{sub}</div>}</div>
    </div>
  );
}

function Flow() {
  return (
    <div className="rounded-2xl border bg-muted/40 p-5">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
        <Node icon={Database} title="KIS Klinikum Wien Nord" sub="HL7 v2" />
        <ArrowRight className="mx-auto h-5 w-5 rotate-90 text-muted-foreground lg:rotate-0" aria-hidden />
        <Node icon={Cog} title="Integration Engine" sub="Mirth / Open Integration Engine" />
        <ArrowRight className="mx-auto h-5 w-5 rotate-90 text-muted-foreground lg:rotate-0" aria-hidden />
        <Node icon={FileJson} title="FHIR R4" />
        <ArrowRight className="mx-auto h-5 w-5 rotate-90 text-muted-foreground lg:rotate-0" aria-hidden />
        <Node icon={MonitorSmartphone} title="EHDS Navigator" />
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <div className="h-0 flex-1 border-t-2 border-dashed border-primary/50" />
        <span className="rounded-full border border-dashed border-primary/50 bg-background px-3 py-1 font-medium text-primary">Modern KIS: FHIR directly</span>
        <ArrowRight className="h-4 w-4 text-primary" aria-hidden />
      </div>
    </div>
  );
}

const Mono = ({ children }: { children: string }) => (
  <pre className="overflow-x-auto rounded-lg bg-code p-4 font-mono text-[11px] leading-relaxed text-code-foreground">{children}</pre>
);

/** Render an HL7 line with the mapped field numbers coloured. */
function Hl7Line({ line }: { line: string }) {
  const parts = line.split("|");
  const seg = parts[0];
  const toneFor = (i: number) => FIELD_MAP.find((m) => m.seg === seg && (m.fields as readonly number[]).includes(i))?.tone;
  return (
    <code className="block whitespace-pre-wrap break-all font-mono text-xs leading-6">
      {parts.map((p, i) => {
        const t = toneFor(i);
        return <Fragment key={i}>{i > 0 && "|"}{t ? <mark className={`rounded px-0.5 text-foreground ${TONE[t]}`} title={`${seg}-${i}`}>{p}</mark> : p}</Fragment>;
      })}
    </code>
  );
}

/** Render FHIR JSON with each top-level mapped element coloured. */
function ColoredJson({ obj }: { obj: object }) {
  const lines = JSON.stringify(obj, null, 2).split("\n");
  let current: number | undefined;
  return (
    <pre className="overflow-x-auto rounded-lg border bg-card p-3 font-mono text-xs leading-5">
      {lines.map((l, i) => {
        const m = /^ {2}"(\w+)":/.exec(l);
        if (m) current = FIELD_MAP.find((f) => f.fhir === m[1])?.tone;
        else if (/^[{}]/.test(l)) current = undefined;
        return <div key={i} className={current ? `${TONE[current]} -mx-1 px-1` : ""}>{l}</div>;
      })}
    </pre>
  );
}

export function DataSources() {
  const [state, setState] = useState<"idle" | "busy" | Awaited<ReturnType<typeof convertWithEngine>>>("idle");
  const run = async () => { setState("busy"); setState(await convertWithEngine(5)); };
  return (
    <div className="space-y-6">
      <Flow />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="min-w-0"><CardHeader className="pb-3"><CardTitle className="text-base">Legacy lab system – HL7 v2 ORU^R01</CardTitle></CardHeader><CardContent><Mono>{HL7_ORU}</Mono></CardContent></Card>
        <Card className="min-w-0"><CardHeader className="pb-3"><CardTitle className="text-base">Legacy KIS – HL7 v2 ADT^A03 (discharge)</CardTitle></CardHeader><CardContent className="space-y-2">
          <Mono>{HL7_ADT}</Mono>
          <p className="text-xs text-muted-foreground">Encounter ENC-7731 · admitted 2026-10-20 14:15 · discharged 2026-10-24 10:30</p>
        </CardContent></Card>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={state === "busy"}>{state === "busy" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cog className="h-4 w-4" />}Convert with Integration Engine</Button>
        {state === "busy" && <span className="text-sm text-muted-foreground">Parsing HL7 v2 → mapping fields → building FHIR Observation…</span>}
      </div>

      {typeof state === "object" && (
        <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="min-w-0"><CardHeader className="pb-2"><CardTitle className="text-sm">HL7 v2 input</CardTitle></CardHeader><CardContent className="space-y-2 rounded-lg">
              <div className="rounded-lg border bg-muted/40 p-3"><Hl7Line line={state.pid} /><Hl7Line line={state.obx} /></div>
            </CardContent></Card>
            <Card className="min-w-0"><CardHeader className="pb-2"><CardTitle className="text-sm">FHIR R4 Observation</CardTitle></CardHeader><CardContent><ColoredJson obj={state.observation} /></CardContent></Card>
          </div>
          <Card><CardContent className="p-4">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1.5 font-medium">HL7 v2 field</th><th className="font-medium">FHIR field</th></tr></thead>
              <tbody>{FIELD_MAP.map((m) => (
                <tr key={m.hl7} className="border-t"><td className="py-2"><span className={`rounded px-1.5 py-0.5 font-mono text-xs ${TONE[m.tone]}`}>{m.hl7}</span></td><td className="font-mono text-xs">Observation.{m.fhir}</td></tr>
              ))}</tbody>
            </table>
            <p className="mt-3 text-xs text-muted-foreground">In production: Mirth Connect / Open Integration Engine. In this prototype: a Python mapping module.</p>
          </CardContent></Card>
        </div>
      )}
    </div>
  );
}
