import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Check, Loader2, Plus, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { REQUESTS, type ResearchRequest } from "@/mockData";
import { evaluateRequest, type Evaluation } from "@/api";
import { requestType, type LiveRequest } from "@/lib/backend-mappers";
import { DecisionView } from "@/components/decision";
import { OwnApplications } from "@/components/secondary/own-applications";
import { PermitCriteria } from "@/components/secondary/permit-criteria";
import { useDemoSession } from "@/lib/demo-session";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { getRequests } from "@/api";
import { Provenance } from "@/components/provenance";

type Search = { req?: string | undefined; run?: number | undefined; role?: "applicant" | "staff" | undefined };

export const Route = createFileRoute("/secondary/")({
  validateSearch: (s: Record<string, unknown>): Search => ({
    req: typeof s["req"] === "string" ? (s["req"] as string) : undefined,
    run: s["run"] ? Number(s["run"]) : undefined,
    role: s["role"] === "staff" ? "staff" : s["role"] === "applicant" ? "applicant" : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Secondary use – Research requests | EHDS Navigator" },
      { name: "description", content: "Health Data Access Body: evaluate research requests under EHDS Art. 53, 54, 66–73." },
      { property: "og:title", content: "Research requests | EHDS Navigator" },
      { property: "og:description", content: "See how a Health Data Access Body decides on research requests." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Requests,
});

const STEPS = ["Reading request", "Mapping terms to codes", "Applying decision rules", "Computing results", "Applying small-cell rule"];

const SAMPLE = {
  id: "R11",
  applicant: "Your organisation",
  purpose: "Share of hypertensive patients on ramipril",
  type: "health data request",
  text: "What share of patients with hypertension takes ramipril, by hospital?",
};

function Requests() { const { user } = useDemoSession(); return user?.role === "hdab" ? <StaffRequests /> : <OwnApplications />; }
function StaffRequests() {
  const { log } = useDemoSession();
  const { data: requests } = useSuspenseQuery(queryOptions({ queryKey: ["hdab-requests"], queryFn: getRequests }));
  const { req = "R01", run } = Route.useSearch();
  const navigate = useNavigate({ from: "/secondary/" });
  const [custom, setCustom] = useState<ResearchRequest[]>([]);
  const all = [...requests, ...custom];
  const selected = all.find((r) => r.id === req) ?? all[0];
  if (!selected) throw new Error("No requests available");
  const [phase, setPhase] = useState<"idle" | "running" | "done">("idle");
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Evaluation | null>(null);
  const [editor, setEditor] = useState(false);
  const [json, setJson] = useState(JSON.stringify(SAMPLE, null, 2));
  const [jsonErr, setJsonErr] = useState("");
  const timers = useRef<number[]>([]);

  const evaluate = (r: ResearchRequest, fast = false) => {
    timers.current.forEach(clearTimeout);
    setPhase("running"); setStep(0); setResult(null);
    const per = fast ? 200 : 400;
    STEPS.forEach((_, i) => timers.current.push(window.setTimeout(() => setStep(i + 1), per * (i + 1))));
    timers.current.push(window.setTimeout(async () => { try { const ev = await evaluateRequest(r); setResult(ev); setPhase("done"); log("Evaluated request", ev.decision, { request: r.id, area: "secondary" }); } catch (e) { setPhase("idle"); setJsonErr(e instanceof Error ? e.message : "Evaluation unavailable"); } }, per * STEPS.length + 50));
  };

  useEffect(() => { setPhase("idle"); setResult(null); timers.current.forEach(clearTimeout); }, [req]);
  useEffect(() => { if (run) { evaluate(selected); navigate({ search: (s) => ({ ...s, run: undefined }), replace: true }); } }, [run]); // eslint-disable-line react-hooks/exhaustive-deps

  const addCustom = () => {
    try {
      const o = JSON.parse(json);
      // Accepts the form below or a Track-3 request JSON (requested_as, question, definitions), which goes to the backend unchanged.
      const track3 = typeof o.requested_as === "string";
      if (!o.id || !o.purpose || !(o.type || track3)) throw new Error("Needs id, purpose and type (or a Track-3 request with requested_as)");
      const r: LiveRequest = { ...o, applicant: typeof o.applicant === "string" ? o.applicant : o.applicant?.organisation ?? o.applicant?.name ?? "Applicant", type: o.type ?? requestType(o.requested_as), text: o.text ?? o.question ?? "", terms: [], sql: "-- SQL generated by backend", raw: track3 ? o : undefined };
      setCustom((c) => [...c.filter((x) => x.id !== r.id), r]);
      setEditor(false); setJsonErr("");
      navigate({ search: (s) => ({ ...s, req: r.id }) });
    } catch (e) { setJsonErr((e as Error).message); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Research requests</h1>
        <Badge variant="outline">HDAB staff</Badge>
      </div>

      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <div className="space-y-2">
          <Button variant="outline" className="w-full" onClick={() => setEditor(true)}><Plus className="h-4 w-4" />New request</Button>
          <ul className="max-h-[70vh] space-y-1.5 overflow-auto pr-1">
            {all.map((r) => (
              <li key={r.id}>
                <Button variant="ghost" aria-pressed={r.id === selected.id} onClick={() => navigate({ search: (s) => ({ ...s, req: r.id }) })}
                  className={`block h-auto w-full whitespace-normal rounded-md border-l-2 p-3 text-left transition-colors ${r.id === selected.id ? "border-primary bg-primary-soft" : "border-transparent hover:bg-muted"}`}>
                  <div className="flex items-center gap-2"><span className="font-mono text-xs font-semibold text-primary">{r.id}</span><span className="truncate text-xs text-muted-foreground">{r.applicant}</span></div>
                  <div className="mt-1 text-sm font-medium leading-snug">{r.purpose}</div>
                  <Badge variant="outline" className="mt-2 text-[11px] font-normal">{r.type === "health data request" ? "Statistics" : "Record-level"} · {r.type}</Badge>
                </Button>
              </li>
            ))}
          </ul>
        </div>

        <div className="min-w-0 space-y-5">
          <div className="border-b bg-background px-5 py-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-mono text-xs text-muted-foreground">{selected.id} · {selected.applicant}</div>
                <h2 className="mt-1 text-lg font-semibold">{selected.purpose}</h2>
              </div>
              <Button onClick={() => evaluate(selected)} disabled={phase === "running"}>
                {phase === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}Evaluate request
              </Button>
            </div>
            {selected.text && <p className="mt-3 text-sm text-muted-foreground">"{selected.text}"</p>}
            {selected.whyNotStatistics && <p className="mt-2 text-sm"><span className="font-medium">Why statistics are not enough: </span><span className="text-muted-foreground">{selected.whyNotStatistics}</span></p>}
          </div>

          {phase === "running" && (
            <ol className="space-y-2 border-y p-5" aria-live="polite">
              {STEPS.map((s, i) => (
                <li key={s} className={`flex items-center gap-3 text-sm ${i < step ? "text-foreground" : i === step ? "text-primary" : "text-muted-foreground"}`}>
                  {i < step ? <Check className="h-4 w-4 text-success" /> : i === step ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="h-4 w-4 rounded-full border" />}{s}
                </li>
              ))}
            </ol>
          )}
          {phase === "done" && result && <><DecisionView ev={result} staff /><PermitCriteria key={result.request.id} ev={result} /></>}
          {phase === "idle" && <p className="border-y border-dashed p-8 text-center text-sm text-muted-foreground">Press "Evaluate request" to see the decision.</p>}
        </div>
      </div>

      {jsonErr && <p role="alert" className="text-destructive">{jsonErr}</p>}<Provenance source="FastAPI request service · synthetic fallback when unavailable" />
      <Dialog open={editor} onOpenChange={setEditor}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New request</DialogTitle><DialogDescription>Edit the JSON, or paste a Track-3 request file (with requested_as, question and definitions). Use type "health data request" or "health data access application" (add "whyNotStatistics" for record-level access).</DialogDescription></DialogHeader>
          <Textarea value={json} onChange={(e) => setJson(e.target.value)} rows={12} className="font-mono text-xs" aria-label="Request JSON" />
          {jsonErr && <p className="text-sm text-destructive">{jsonErr}</p>}
          <DialogFooter><Button variant="outline" onClick={() => setEditor(false)}>Cancel</Button><Button onClick={addCustom}>Add request</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
