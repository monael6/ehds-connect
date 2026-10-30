import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { decideRequest, getRequestDetail, getRequestInbox, type InboxRow } from "@/api";
import { useDemoSession } from "@/lib/demo-session";

const STATUS: Record<string, { label: string; tone: string }> = {
  submitted: { label: "Waiting for review", tone: "border-warning/30 bg-warning-soft text-warning" },
  more_information_requested: { label: "More information requested", tone: "border-warning/30 bg-warning-soft text-warning" },
  confirmed: { label: "Approved", tone: "border-success/30 bg-success-soft text-success" },
  rejected: { label: "Rejected", tone: "border-destructive/30 bg-destructive-soft text-destructive" },
};
const RECOMMENDATION = { REJECT: "Reject (prohibited purpose, Art. 54)", APPROVE_STATISTICAL: "Approve as anonymised statistics (Art. 69)", APPROVE_SPE: "Approve for secure environment (Art. 67/73)" } as const;
const org = (a: InboxRow["applicant"]) => (typeof a === "string" ? a : a?.organisation ?? a?.name ?? "Unknown applicant");

/** HDAB staff see requests that applicants submitted and approve, reject or ask for more information. */
export function ApplicantInbox() {
  const { log } = useDemoSession(); const qc = useQueryClient();
  const inbox = useQuery({ queryKey: ["applicant-inbox"], queryFn: getRequestInbox });
  const rows = (inbox.data ?? []).filter((r) => r.submitted_by && r.status !== "automatic").sort((a, b) => Number(b.status === "submitted") - Number(a.status === "submitted"));
  if (inbox.error) return <p className="text-sm text-destructive">Applicant requests unavailable: {inbox.error.message}</p>;
  return <section className="mb-8 space-y-3"><h2 className="text-xl font-semibold">Requests from applicants</h2>
    {rows.length === 0 && <p className="border-y py-6 text-sm text-muted-foreground">{inbox.isLoading ? "Loading…" : "No applicant requests yet."}</p>}
    {rows.map((r) => <Row key={r.request_id} row={r} onDone={async (what) => { log(what, "Saved", { request: r.request_id, area: "secondary" }); await qc.invalidateQueries({ queryKey: ["applicant-inbox"] }); }} />)}
  </section>;
}

function Row({ row, onDone }: { row: InboxRow; onDone: (what: string) => Promise<void> }) {
  const [open, setOpen] = useState(false); const [note, setNote] = useState(""); const [busy, setBusy] = useState(false);
  const detail = useQuery({ queryKey: ["request-detail", row.request_id], queryFn: () => getRequestDetail(row.request_id), enabled: open });
  const s = STATUS[row.status] ?? { label: row.status, tone: "" };
  const act = async (action: "confirm" | "reject" | "ask-info", what: string) => { setBusy(true); try { await decideRequest(row.request_id, action, note); toast.success(what); setNote(""); await onDone(what); } catch (e) { toast.error(e instanceof Error ? e.message : "Not saved"); } finally { setBusy(false); } };
  const pending = row.status === "submitted" || row.status === "more_information_requested";
  return <article className="rounded-lg border bg-card p-4 text-sm">
    <div className="flex flex-wrap items-start gap-3"><div className="min-w-0 flex-1"><p className="text-xs text-muted-foreground">{row.request_id} · {org(row.applicant)} · {row.requested_as === "health data access application" ? "Records (Art. 67)" : "Statistics (Art. 69)"}</p><p className="mt-1 font-medium">{row.purpose}</p><p className="mt-1 text-xs">Automatic check: {RECOMMENDATION[row.decision]}</p>{row.staff_note && <p className="mt-1 text-xs text-muted-foreground">Note: {row.staff_note}</p>}</div><Badge variant="outline" className={s.tone}>{s.label}</Badge></div>
    <Button variant="ghost" size="sm" className="mt-2 px-0" onClick={() => setOpen((o) => !o)}>{open ? "Hide details" : "Review"}</Button>
    {open && <div className="mt-2 space-y-3 border-t pt-3">
      {detail.data ? <><p className="text-muted-foreground"><span className="font-medium text-foreground">Automatic recommendation: </span>{detail.data.explanation?.en}</p><p className="text-xs">Articles: {detail.data.articles.map((a) => `Art. ${a}`).join(", ")}</p></> : <p className="text-muted-foreground">{detail.error?.message ?? "Loading…"}</p>}
      {pending && <><Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note to the applicant (required to reject or ask for information)" aria-label="Note to the applicant" />
        <div className="flex flex-wrap gap-2"><Button size="sm" disabled={busy || row.decision === "REJECT"} onClick={() => act("confirm", "Request approved")}>Approve</Button><Button size="sm" variant="outline" disabled={busy || !note.trim()} onClick={() => act("ask-info", "Asked for more information")}>Ask for information</Button><Button size="sm" variant="destructive" disabled={busy || !note.trim()} onClick={() => act("reject", "Request rejected")}>Reject</Button></div>
        {row.decision === "REJECT" && <p className="text-xs text-destructive">Prohibited purpose under Art. 54. This request cannot be approved.</p>}</>}
    </div>}
  </article>;
}
