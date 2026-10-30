import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PatientDocuments } from "@/components/primary/patient-documents";
import { type Lang } from "@/mockData";
import { getRolePatients } from "@/api";
import { DischargeLetter } from "@/components/primary/discharge-letter";
import { IpsOnDemand } from "@/components/primary/ips";
import { CrossBorderFlow } from "@/components/primary/crossborder";
import { GlobalAccessLog } from "@/components/primary/shared";
import { Provenance } from "@/components/provenance";
import { pageHead } from "@/lib/page-head";
const patientsQuery = queryOptions({ queryKey: ["role-patients"], queryFn: getRolePatients });
type SearchParams = { mode?: "national" | "crossborder"; lang?: Lang; pid?: string; tab?: "letter" | "ips" | "documents"; step?: number };
export const Route = createFileRoute("/primary")({
  validateSearch: (s: Record<string, unknown>): SearchParams => ({ mode: s["mode"] === "crossborder" ? "crossborder" : "national", lang: s["lang"] === "en" || s["lang"] === "de" ? s["lang"] : "it", pid: typeof s["pid"] === "string" ? s["pid"] : "p-4cfd3cf1", tab: s["tab"] === "ips" || s["tab"] === "documents" ? s["tab"] : "letter", step: [1,2,3,4,5].includes(Number(s["step"])) ? Number(s["step"]) : 1 }),
  head: () => pageHead("Primary use – Treatment", "Patient list, Austrian discharge letters and cross-border Patient Summary."),
  component: Primary,
});
function Primary() {
  const { mode = "national", lang = "it", pid, tab = "letter", step = 1 } = Route.useSearch(); const navigate = useNavigate({ from: "/primary" }); const [q, setQ] = useState("");
  const { data } = useSuspenseQuery(patientsQuery); const patient = data.data.find((p) => p.id === pid || p.legacyId === pid) ?? data.data[0];
  if (!patient) return <p className="p-8">No patients available.</p>;
  const matches = data.data.filter((p) => `${p.id} ${p.name} ${p.city}`.toLowerCase().includes(q.toLowerCase()));
  return <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6"><Tabs value={mode} onValueChange={(v) => navigate({ search: (s) => ({ ...s, mode: v as "national" | "crossborder" }) })}><TabsList className="h-11"><TabsTrigger value="national">Hospital care</TabsTrigger><TabsTrigger value="crossborder">Cross-border care</TabsTrigger></TabsList></Tabs>
    {mode === "crossborder" ? <CrossBorderFlow step={step} go={(n) => navigate({ search: (s) => ({ ...s, step: n }) })} lang={lang} setLang={(l) => navigate({ search: (s) => ({ ...s, lang: l }) })} /> : <div className="grid items-start gap-6 md:grid-cols-[200px_minmax(0,1fr)] xl:grid-cols-[224px_minmax(0,1fr)]"><aside className="space-y-4 md:sticky md:top-6"><label htmlFor="psearch" className="text-sm font-medium">Patients</label><div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input id="psearch" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search pseudonym" className="pl-9" /></div><ul className="grid max-h-64 gap-1 overflow-y-auto md:max-h-[70vh]">{matches.map((p) => <li key={p.id}><Button variant="ghost" aria-pressed={p.id === patient.id} className={`h-auto w-full justify-start whitespace-normal border-l-2 px-3 py-3 text-left ${p.id === patient.id ? "border-primary bg-primary-soft" : "border-transparent"}`} onClick={() => navigate({ search: (s) => ({ ...s, pid: p.id }) })}><span><span className="block font-semibold">{p.name}</span><span className="block font-mono text-xs text-muted-foreground">{p.id}</span><span className="block text-xs text-muted-foreground">{p.sex} · {p.born.slice(0,4)} · {p.city}</span><span className="block text-xs text-muted-foreground">{p.stays.length ? p.stays.map((s) => `${s.from} – ${s.to}`).join(", ") : "No stays recorded"}</span></span></Button></li>)}</ul>{!matches.length && <p className="text-sm text-muted-foreground">No matching patients.</p>}</aside><section className="min-w-0 space-y-5 bg-background px-4 py-5 sm:px-6"><div><h1 className="text-2xl font-semibold">{patient.name}</h1><p className="mt-1 text-sm text-muted-foreground">{patient.id} · {patient.dataHolder}</p>{patient.optedOut && <Badge variant="outline" className="mt-2 border-warning/30 bg-warning-soft text-warning">Opted out of research – still visible for treatment</Badge>}</div><Tabs value={tab} onValueChange={(v) => navigate({ search: (s) => ({ ...s, tab: v as "letter" | "ips" | "documents" }) })}><TabsList className="w-full justify-start rounded-none border-b bg-transparent p-0"><TabsTrigger className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary" value="letter">Discharge letter</TabsTrigger><TabsTrigger className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary" value="ips">Patient Summary</TabsTrigger><TabsTrigger className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary" value="documents">Documents</TabsTrigger></TabsList><TabsContent value="letter" className="mt-5"><DischargeLetter key={patient.id} patient={patient} /></TabsContent><TabsContent value="ips" className="mt-5"><IpsOnDemand key={patient.id} patient={patient} /></TabsContent><TabsContent value="documents" className="mt-5"><PatientDocuments patientId={patient.id} /></TabsContent></Tabs></section></div>}
    <details className="border-t pt-4"><summary className="cursor-pointer text-sm font-semibold">Who accessed the patient data</summary><div className="mt-4"><GlobalAccessLog /></div></details><Provenance source={`${data.source} · hospital record`} />
  </div>;
}
