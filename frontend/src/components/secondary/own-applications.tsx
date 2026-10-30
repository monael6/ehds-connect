import { useState } from "react";
import { useSuspenseQuery, queryOptions, useQueryClient } from "@tanstack/react-query";
import { useDemoSession } from "@/lib/demo-session";
import { getOwnRequests, type Evaluation } from "@/api";
import { REASONING } from "@/mockData";
import { Button } from "@/components/ui/button";
import { Link } from "@tanstack/react-router";
import { ApplicationForm } from "./application";
import { useAppState } from "@/lib/app-state";
import { Provenance } from "@/components/provenance";
import { RequestResult } from "./request-result";
// A just-submitted application keeps its full answer; the backend adds the HDAB's current status.
const pick = (ev?: Evaluation) => (ev?.status ? { status: ev.status } : {});
// The decision engine's approval text applies only once the HDAB has approved; until then say what is pending.
const explain = (ev: Evaluation) => {
  const base = ev.explanation?.en ?? REASONING[ev.decision].en.replace("{p}", ev.prohibitedPurpose ?? "");
  if (ev.decision === "REJECT" || !ev.status || ev.status.startsWith("Approved") || ev.status === "Automatic decision") return base;
  if (ev.status.startsWith("Rejected")) return "The HDAB rejected your request. No data has been shared.";
  const what = ev.decision === "APPROVE_SPE" ? "pseudonymised records in a secure processing environment (Art. 67)" : "anonymised statistics (Art. 69)";
  return `The automatic check found that your request meets the conditions for ${what}. You get access only after the HDAB approves it.`;
};
export function OwnApplications() { const { user } = useDemoSession(); const { data } = useSuspenseQuery(queryOptions({ queryKey: ["own-requests", user?.id], queryFn: () => getOwnRequests(user?.id ?? "visitor") })); const { applications, setApplications } = useAppState(); const local = applications[user?.id ?? ""] ?? []; const [form, setForm] = useState(false); const queryClient = useQueryClient(); const all = [...local.map((l) => ({ ...l, ...pick(data.data.find((ev) => ev.request.id === l.request.id)) })), ...data.data.filter((ev) => !local.some((l) => l.request.id === ev.request.id))]; return <div className="space-y-6"><div className="flex flex-wrap justify-between gap-3"><h1 className="text-2xl font-semibold">My requests</h1>{user?.role !== "visitor" && <Button asChild><Link to="/secondary/eligibility">New data request</Link></Button>}</div>{form && <section className="max-w-2xl border-y py-5"><ApplicationForm onSubmitted={(ev) => { const next = [ev, ...local]; if (user) setApplications((s) => ({ ...s, [user.id]: next })); setForm(false); void queryClient.invalidateQueries({ queryKey: ["own-requests"] }); }} /></section>}{all.length ? all.map((ev) => <article key={ev.request.id} className="rounded-lg border p-5"><p className="text-xs text-muted-foreground">{ev.request.id} · {ev.request.applicant}</p><h2 className="mt-2 font-semibold">{ev.request.purpose}</h2><p className={`mt-3 text-sm font-medium ${ev.decision === "REJECT" ? "text-destructive" : "text-primary"}`}>{ev.decision === "REJECT" ? "Not eligible" : ev.decision === "APPROVE_SPE" ? "Secure environment application" : "Statistics application"}</p><p className="mt-2 text-sm text-muted-foreground">{explain(ev)} {data.source === "Synthetic fallback" && "Synthetic demonstration decision; not a legal permit."}</p>{ev.status && <p className={`mt-3 inline-block rounded-full border px-3 py-1 text-xs font-medium ${ev.status.startsWith("Approved") ? "border-success/30 bg-success-soft text-success" : ev.status.startsWith("Rejected") ? "border-destructive/30 bg-destructive-soft text-destructive" : "border-warning/30 bg-warning-soft text-warning"}`}>{ev.status}</p>}{ev.staffNote && <p className="mt-2 text-sm">HDAB note: {ev.staffNote}</p>}{ev.status?.startsWith("Approved") && ev.decision === "APPROVE_STATISTICAL" && <RequestResult id={ev.request.id} />}</article>) : <p className="border-y py-8 text-sm text-muted-foreground">No requests yet. Start with "New data request".</p>}<Provenance source={`${data.source} · current account applications only`} /></div>; }
