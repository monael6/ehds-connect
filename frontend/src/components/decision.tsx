import { useState } from "react";
import { Ban, ChevronDown, Lock, Download, NotebookPen, UserX, Check } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ARTICLES, REASONING, OPTED_OUT_EXCLUDED, SPE_R05, type Lang, type Decision } from "@/mockData";
import { downloadSpe, type Evaluation } from "@/api";
import { formatCount, formatValue } from "@/lib/rules";
import { useAppState } from "@/lib/app-state";
import { CodeBlock } from "@/components/shell";

const STATUS: Record<Decision, string> = {
  REJECT: "bg-destructive text-destructive-foreground",
  APPROVE_STATISTICAL: "bg-success text-success-foreground",
  APPROVE_SPE: "bg-primary text-primary-foreground",
};

export function DecisionView({ ev, staff }: { ev: Evaluation; staff: boolean }) {
  const [lang, setLang] = useState<Lang>("en");
  const r = ev.request;
  const reasoning = REASONING[ev.decision][lang].replace("{p}", ev.prohibitedPurpose ?? "");
  return (
    <div className="space-y-5">
      <div className="rounded-2xl border p-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className={`rounded-lg px-4 py-2 font-mono text-lg font-semibold tracking-wide ${STATUS[ev.decision]}`}>{ev.decision}</span>
          {ev.articles.map((a) => (
            <Tooltip key={a}>
              <TooltipTrigger asChild><button className="rounded-full border bg-muted px-3 py-1 text-xs font-medium hover:border-primary focus-visible:outline-2 focus-visible:outline-ring">{a}</button></TooltipTrigger>
              <TooltipContent className="max-w-xs">{ARTICLES[a]}</TooltipContent>
            </Tooltip>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Explanation for the applicant</h3>
          <div className="flex gap-1 text-xs">{(["en", "de", "it"] as Lang[]).map((l) => (
            <button key={l} aria-pressed={lang === l} onClick={() => setLang(l)} className={`rounded px-2 py-1 ${lang === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}>{{ en: "English", de: "Deutsch", it: "Italiano" }[l]}</button>
          ))}</div>
        </div>
        <p className="mt-2 leading-relaxed text-muted-foreground">{reasoning}</p>


      </div>

      {ev.decision === "REJECT" && (
        <div className="rounded-2xl border-2 border-destructive/40 bg-destructive-soft p-5">
          <div className="flex items-center gap-2 font-semibold text-destructive"><Ban className="h-5 w-5" />Prohibited purpose detected: {ev.prohibitedPurpose}</div>
          <p className="mt-2 text-sm">Under <strong>Art. 54</strong>, health data may not be used for decisions that harm individuals, such as excluding them from insurance or raising premiums, nor for advertising. The request was stopped before any data was touched. You may submit a new request with a permitted purpose (Art. 53).</p>
        </div>
      )}
      {ev.decision === "APPROVE_STATISTICAL" && <StatsTable ev={ev} />}
      {ev.decision === "APPROVE_SPE" && <SpeCard />}

      {staff && (
        <div className="space-y-2">
          <Panel title="Term → code mapping">
            <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1.5 font-medium">Term</th><th className="font-medium">System</th><th className="font-medium">Code(s)</th><th className="font-medium">Found in data</th></tr></thead>
              <tbody>{r.terms.map((t) => <tr key={t.term} className="border-t"><td className="py-2">{t.term}</td><td>{t.system}</td><td className="font-mono text-xs">{t.codes}</td><td>{t.found ? <span className="text-success">yes</span> : <span className="text-destructive">no</span>}</td></tr>)}</tbody></table>
          </Panel>
          <Panel title="Generated SQL"><CodeBlock>{r.sql}</CodeBlock></Panel>
          <Panel title="Audit log"><AuditList /></Panel>
        </div>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Collapsible className="rounded-xl border">
      <CollapsibleTrigger className="group flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted">{title}<ChevronDown className="h-4 w-4 transition-transform group-data-[state=open]:rotate-180" /></CollapsibleTrigger>
      <CollapsibleContent className="overflow-x-auto border-t p-4">{children}</CollapsibleContent>
    </Collapsible>
  );
}

function AuditList() {
  const { accessLog } = useAppState();
  return (
    <ul className="space-y-1.5 text-sm">
      <li className="flex justify-between"><span>Request evaluated by HDAB pipeline</span><span className="text-muted-foreground">just now</span></li>
      {accessLog.map((e) => <li key={e.id} className="flex justify-between gap-3"><span>{e.who} · {e.kind}{e.reason ? ` · ${e.reason}` : ""}</span><span className="whitespace-nowrap text-muted-foreground">{e.when}</span></li>)}
    </ul>
  );
}

function StatsTable({ ev }: { ev: Evaluation }) {
  const r = ev.request;
  const m = r.metric;
  return (
    <div className="rounded-2xl border p-5">
      <h3 className="font-semibold">Results</h3>
      {r.results ? (
        <div className="mt-3 overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="py-2 font-medium">Group</th><th className="font-medium">Patients</th>{m && <th className="font-medium">{m.label}{m.unit ? ` (${m.unit})` : ""}</th>}</tr></thead>
          <tbody>{r.results.map((row) => {
            const v = formatValue(row.n, row.value);
            return (
              <tr key={row.group} className="border-b last:border-0"><td className="py-2.5">{row.group}</td><td className="font-mono">{formatCount(row.n)}</td>
                {m && <td className="font-mono">{v ?? (
                  <Tooltip><TooltipTrigger asChild><span tabIndex={0} className="cursor-help italic text-muted-foreground">suppressed</span></TooltipTrigger>
                    <TooltipContent className="max-w-xs">Small-cell rule: values based on fewer than 10 patients are hidden so no individual can be identified.</TooltipContent></Tooltip>)}</td>}
              </tr>
            );
          })}</tbody></table></div>
      ) : <p className="mt-2 text-sm text-muted-foreground">Results will be computed by the backend for this new request.</p>}
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t pt-4 text-sm text-muted-foreground">
        <span>Opted-out patients excluded: <strong className="text-foreground">{OPTED_OUT_EXCLUDED.toLocaleString("en-US")}</strong></span>
        <span className="flex items-center gap-1.5 text-warning"><UserX className="h-4 w-4" />Frau M. is not included (opted out of research)</span>
      </div>
    </div>
  );
}

function SpeCard() {
  const { addAccess } = useAppState();
  const [blocked, setBlocked] = useState<string | null>(null);
  const [nb, setNb] = useState(false);
  return (
    <div className="rounded-2xl border-2 border-primary/30 p-5">
      <div className="flex items-center gap-2 font-semibold"><Lock className="h-5 w-5 text-primary" />Secure Processing Environment {SPE_R05.id}</div>
      <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
        <div><dt className="text-muted-foreground">Patients</dt><dd className="font-mono text-lg">{SPE_R05.patients.toLocaleString("en-US")}</dd></div>
        <div><dt className="text-muted-foreground">Created</dt><dd>{SPE_R05.created}</dd></div>
        <div><dt className="text-muted-foreground">Record types</dt><dd className="flex flex-wrap gap-1">{SPE_R05.recordTypes.map((t) => <Badge key={t} variant="outline">{t}</Badge>)}</dd></div>
        <div><dt className="text-muted-foreground">Patient IDs</dt><dd>{SPE_R05.idsKept}</dd></div>
      </dl>
      <div className="mt-5 flex flex-wrap gap-2">
        <Button variant="outline" onClick={async () => {
          const res = await downloadSpe(SPE_R05.id);
          addAccess({ who: "TU Wien – AI in Medicine Lab", org: SPE_R05.id, sections: ["Download attempt"], kind: "blocked-download" });
          setBlocked(res.message);
        }}><Download className="h-4 w-4" />Download data</Button>
        <Button onClick={() => setNb((v) => !v)}><NotebookPen className="h-4 w-4" />Open analysis workspace</Button>
      </div>
      {nb && (
        <div className="mt-5 space-y-3 rounded-xl border bg-muted/40 p-4 font-mono text-xs">
          <div className="text-muted-foreground">In [1]: cohort.groupby("anticoagulant").stroke_1y.mean()</div>
          <pre className="rounded bg-background p-3">anticoagulant   stroke_1y_rate   n{"\n"}apixaban        0.021            1,184{"\n"}other DOAC      0.024            612{"\n"}none            0.058            521</pre>
          <div className="text-muted-foreground">In [2]: model.fit(X_train, y_train); model.score(X_test, y_test)</div>
          <pre className="rounded bg-background p-3">AUROC = 0.78  (aggregate output only – row-level export disabled)</pre>
        </div>
      )}
      <Dialog open={!!blocked} onOpenChange={(o) => !o && setBlocked(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="flex items-center gap-2 text-destructive"><Ban className="h-5 w-5" />Download blocked</DialogTitle>
            <DialogDescription>{blocked?.replace("Download blocked – ", "")}</DialogDescription></DialogHeader>
          <DialogFooter><Button onClick={() => { setBlocked(null); toast("Attempt recorded in audit log"); }}>Understood</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
