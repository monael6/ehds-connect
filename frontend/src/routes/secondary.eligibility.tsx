import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CheckCircle2, XCircle, BarChart3, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { submitTrackRequest } from "@/api";
import { useDemoSession } from "@/lib/demo-session";
import { pageHead } from "@/lib/page-head";

export const Route = createFileRoute("/secondary/eligibility")({ head: () => pageHead("New data request", "Request health data step by step under EHDS Art. 53, 54, 67 and 69."), component: RequestWizard });

const PURPOSES = [
  { id: "public_health", label: "Public health", hint: "e.g. monitoring diseases, health threats, occupational health" },
  { id: "policy", label: "Health policy and regulation", hint: "planning and steering the health system" },
  { id: "statistics", label: "Official statistics", hint: "national or EU health statistics" },
  { id: "education", label: "Education and teaching", hint: "in health or care professions" },
  { id: "research", label: "Scientific research", hint: "research related to health or care" },
  { id: "care_quality", label: "Better care", hint: "improving treatment, patient safety, quality of care" },
];
const PROHIBITED = [
  "Decisions that harm a person, e.g. refusing or pricing insurance or loans",
  "Decisions about a person's job, pension or benefits",
  "Advertising or marketing to patients or doctors",
  "Developing harmful products (e.g. tobacco, illicit drugs, weapons)",
  "Identifying individual people from the data",
];
const STEPS = ["Purpose", "Not allowed", "Type of data", "Your question", "Review"];

function RequestWizard() {
  const { user, log } = useDemoSession(); const navigate = useNavigate(); const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [purpose, setPurpose] = useState(""); const [description, setDescription] = useState("");
  const [prohibited, setProhibited] = useState<number[]>([]); const [noneApply, setNoneApply] = useState(false);
  const [records, setRecords] = useState(false); const [why, setWhy] = useState(""); const [safeguards, setSafeguards] = useState(false);
  const [question, setQuestion] = useState(""); const [definitions, setDefinitions] = useState("");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const chosen = PURPOSES.find((p) => p.id === purpose);
  const blocked = prohibited.length > 0;
  const canContinue = [!!purpose && description.trim().length >= 20, noneApply && !blocked, !records || (why.trim().length >= 20 && safeguards), question.trim().length >= 10, true][step];
  if (!user || user.role === "visitor") return <p className="text-sm">Sign in as an applicant to request data.</p>;
  const submit = async () => { setBusy(true); setError(""); try {
    const id = `REQ-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
    await submitTrackRequest({ id, applicant: { name: user.name, organisation: user.organisation, country: "AT" },
      requested_as: records ? "health data access application" : "health data request",
      requested_format: records ? "pseudonymised individual records in a secure processing environment" : "anonymised statistics",
      purpose: `${chosen?.label ?? purpose}: ${description}`, purpose_category: purpose, question,
      definitions: definitions.split("\n").map((d) => d.trim()).filter(Boolean), ...(records ? { why_not_statistics: why } : {}) });
    log("Submitted data request", "Waiting for HDAB review", { request: id, area: "secondary" });
    await qc.invalidateQueries({ queryKey: ["own-requests"] }); navigate({ to: "/secondary" });
  } catch (e) { setError(e instanceof Error ? e.message : "Request could not be submitted"); } finally { setBusy(false); } };
  return <div className="max-w-3xl space-y-6">
    <div><h1 className="text-2xl font-semibold">New data request</h1><p className="mt-1 text-sm text-muted-foreground">5 short steps. The Health Data Access Body (HDAB) reviews your request before you get any data.</p></div>
    <ol className="flex flex-wrap gap-2 text-xs">{STEPS.map((s, i) => <li key={s} className={`rounded-full border px-3 py-1 ${i === step ? "border-primary bg-primary-soft text-primary" : i < step ? "text-success" : "text-muted-foreground"}`}>{i + 1}. {s}</li>)}</ol>
    {step === 0 && <section className="space-y-4"><h2 className="font-semibold">What is the purpose? <span className="text-xs font-normal text-muted-foreground">Art. 53 – allowed purposes</span></h2><p className="text-sm text-muted-foreground">Health data may only be used for one of these purposes.</p>
      <div className="grid gap-2 sm:grid-cols-2">{PURPOSES.map((p) => <button key={p.id} type="button" onClick={() => setPurpose(p.id)} className={`rounded-lg border p-3 text-left text-sm ${purpose === p.id ? "border-primary bg-primary-soft" : "bg-card hover:border-primary/50"}`}><span className="block font-medium">{p.label}</span><span className="text-xs text-muted-foreground">{p.hint}</span></button>)}</div>
      <label className="block space-y-1 text-sm">Describe your project in 1–3 sentences<Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="We want to find out … so that …" /></label></section>}
    {step === 1 && <section className="space-y-4"><h2 className="font-semibold">Is any of this part of your project? <span className="text-xs font-normal text-muted-foreground">Art. 54 – prohibited purposes</span></h2><p className="text-sm text-muted-foreground">These uses are never allowed. Tick any that apply.</p>
      <div className="space-y-2">{PROHIBITED.map((p, i) => <label key={p} className="flex items-start gap-3 rounded-md border bg-card p-3 text-sm"><Checkbox checked={prohibited.includes(i)} onCheckedChange={(v) => { setProhibited((s) => (v === true ? [...s, i] : s.filter((x) => x !== i))); if (v === true) setNoneApply(false); }} />{p}</label>)}</div>
      {blocked ? <p role="alert" className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive-soft p-3 text-sm text-destructive"><XCircle className="h-4 w-4 shrink-0" />This request cannot be made. Art. 54 forbids these uses of health data.</p>
        : <label className="flex items-start gap-3 text-sm"><Checkbox checked={noneApply} onCheckedChange={(v) => setNoneApply(v === true)} />None of these apply to my project.</label>}</section>}
    {step === 2 && <section className="space-y-4"><h2 className="font-semibold">What kind of data do you need?</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <button type="button" onClick={() => setRecords(false)} className={`rounded-lg border p-4 text-left text-sm ${!records ? "border-primary bg-primary-soft" : "bg-card"}`}><BarChart3 className="h-5 w-5 text-primary" /><span className="mt-2 block font-medium">Anonymised statistics</span><span className="text-xs text-muted-foreground">Art. 69 – health data request. Counts and shares, small groups hidden. Nobody can be identified. Fastest option.</span></button>
        <button type="button" onClick={() => setRecords(true)} className={`rounded-lg border p-4 text-left text-sm ${records ? "border-primary bg-primary-soft" : "bg-card"}`}><Lock className="h-5 w-5 text-primary" /><span className="mt-2 block font-medium">Pseudonymised records</span><span className="text-xs text-muted-foreground">Art. 67 – data access application. Records without names, only inside a secure processing environment. No download.</span></button></div>
      {records && <><label className="block space-y-1 text-sm">Why are anonymised statistics not enough?<Textarea value={why} onChange={(e) => setWhy(e.target.value)} placeholder="We need individual-level data because …" /></label>
        <label className="flex items-start gap-3 text-sm"><Checkbox checked={safeguards} onCheckedChange={(v) => setSafeguards(v === true)} />I will only use the minimum data needed, inside the secure environment, and will not try to identify anyone.</label></>}</section>}
    {step === 3 && <section className="space-y-4"><h2 className="font-semibold">Your question</h2>
      <label className="block space-y-1 text-sm">What exactly do you want to know?<Textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="How many patients with … aged … have …, by …?" /></label>
      <label className="block space-y-1 text-sm">Definitions (one per line)<Textarea value={definitions} onChange={(e) => setDefinitions(e.target.value)} placeholder={"Type 2 diabetes = any condition with an ICD-10 code starting with E11.\nReport per hospital (data holder): number of patients."} /><span className="block text-xs text-muted-foreground">Numbers are calculated only from what you define here: name each condition with its ICD-10 code and say what to report per group.</span></label></section>}
    {step === 4 && <section className="space-y-3 rounded-lg border bg-card p-5 text-sm"><h2 className="font-semibold">Check and submit</h2>
      <p><CheckCircle2 className="mr-2 inline h-4 w-4 text-success" />Purpose (Art. 53): {chosen?.label} – {description}</p>
      <p><CheckCircle2 className="mr-2 inline h-4 w-4 text-success" />No prohibited use (Art. 54)</p>
      <p><CheckCircle2 className="mr-2 inline h-4 w-4 text-success" />{records ? "Pseudonymised records in a secure environment (Art. 67)" : "Anonymised statistics (Art. 69)"}</p>
      <p><CheckCircle2 className="mr-2 inline h-4 w-4 text-success" />Question: {question}</p>
      <label className="block space-y-1">Applicant<Input readOnly value={`${user.name} · ${user.organisation}`} /></label>
      <p className="text-xs text-muted-foreground">After you submit, an automatic check runs and HDAB staff decide. You see results only after approval.</p>
      {error && <p role="alert" className="text-destructive">{error}</p>}</section>}
    <div className="flex gap-2">{step > 0 && <Button variant="outline" onClick={() => setStep(step - 1)}>Back</Button>}{step < 4 ? <Button disabled={!canContinue} onClick={() => setStep(step + 1)}>Continue</Button> : <Button disabled={busy} onClick={submit}>{busy ? "Submitting…" : "Submit request"}</Button>}</div>
  </div>;
}
