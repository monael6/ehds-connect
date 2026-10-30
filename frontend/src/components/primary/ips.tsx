import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, FileText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Patient } from "@/mockData";
import { approveIpsPipeline, generateIps, getIpsPipeline, getPatientDocuments, runIpsPipeline } from "@/api";
import { useDemoSession } from "@/lib/demo-session";
import { EmergencyPanel, IpsCards } from "./shared";
import { Provenance } from "@/components/provenance";

function displayDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-GB");
}

export function IpsOnDemand({ patient }: { patient: Patient }) {
  const { log } = useDemoSession();
  const queryClient = useQueryClient();
  const [summary, setSummary] = useState<Patient | null>(null);
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const documentsQuery = useQuery({
    queryKey: ["patient-documents", patient.id],
    queryFn: () => getPatientDocuments(patient.id),
  });
  const hasDocuments = !!documentsQuery.data?.data.length;
  const summaryQuery = useQuery({
    queryKey: ["patient-summary", patient.id],
    queryFn: () => generateIps(patient.id),
    enabled: hasDocuments,
  });
  const pipelineQuery = useQuery({
    queryKey: ["ips-pipeline", patient.id],
    queryFn: () => getIpsPipeline(patient.id),
    enabled: hasDocuments,
  });
  const pipeline = pipelineQuery.data;
  const visibleSummary = hasDocuments ? summaryQuery.data?.patient ?? null : summary;
  const visibleSource = hasDocuments ? summaryQuery.data?.source ?? "" : source;

  const runReference = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await generateIps(patient.id);
      setSummary(data.patient);
      setSource(data.source);
      log("Show Patient Summary", "Displayed", { patient: patient.id, area: "primary" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Summary unavailable");
    } finally {
      setBusy(false);
    }
  };

  const refreshClinicalQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["patient-summary", patient.id] }),
      queryClient.invalidateQueries({ queryKey: ["clinical-letter", patient.id] }),
    ]);
  };

  const generateFromDocuments = async () => {
    setBusy(true);
    setGenerating(true);
    try {
      const draft = await runIpsPipeline(patient.id);
      queryClient.setQueryData(["ips-pipeline", patient.id], draft);
      await refreshClinicalQueries();
      log("Generate Patient Summary from documents", "AI draft created", { patient: patient.id, area: "primary" });
    } catch (e) {
      if ((e as { status?: number }).status === 503) {
        toast.error("No OpenAI key configured. Add OPENAI_API_KEY to backend/.env and restart the backend.");
      } else {
        toast.error(e instanceof Error ? e.message : "Could not generate the Patient Summary");
      }
    } finally {
      setBusy(false);
      setGenerating(false);
    }
  };

  const approve = async () => {
    setBusy(true);
    try {
      const draft = await approveIpsPipeline(patient.id);
      queryClient.setQueryData(["ips-pipeline", patient.id], draft);
      await refreshClinicalQueries();
      log("Approve AI Patient Summary", "Approved", { patient: patient.id, area: "primary" });
      toast.success("Patient Summary approved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not approve the Patient Summary");
    } finally {
      setBusy(false);
    }
  };

  const leakCount = pipeline?.eval_report?.must_not_include_leaks?.length;
  const leakTotal = pipeline?.eval_report?.must_not_include_total;
  const evaluateLine = leakCount !== undefined && leakTotal !== undefined
    ? `Reference check: ${leakCount} of ${leakTotal} statements from the reference "do not include" list appear in the AI summary.`
    : "";

  return (
    <div className="space-y-4">
      {!hasDocuments && !documentsQuery.isLoading && (
        <Button onClick={runReference} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
          Show Patient Summary
        </Button>
      )}
      {documentsQuery.isLoading && <p className="text-sm text-muted-foreground">Checking for clinical documents…</p>}
      {hasDocuments && (
        <section className="space-y-3 rounded-lg border p-4" aria-label="Patient Summary generation">
          {pipeline?.status === "draft" ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">AI draft – doctor review required</Badge>
                {pipeline.created_at && <span className="text-sm text-muted-foreground">Generated {displayDate(pipeline.created_at)} · {String(pipeline.intermediate?.["extraction_model"] ?? "model unavailable")}</span>}
              </div>
              {evaluateLine && <p className="text-sm text-muted-foreground">{evaluateLine}</p>}
              <div className="flex flex-wrap gap-2">
                <Button onClick={approve} disabled={busy || pipelineQuery.isLoading}>Approve summary</Button>
                <Button variant="outline" onClick={generateFromDocuments} disabled={busy || pipelineQuery.isLoading}>
                  {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {generating ? "Reading the documents… this takes up to a minute." : "Regenerate"}
                </Button>
              </div>
            </>
          ) : pipeline?.status === "approved" ? (
            <>
              <p className="text-sm"><Badge variant="outline">Approved by {pipeline.approved_by ?? "clinician"} on {pipeline.approved_at ? displayDate(pipeline.approved_at) : "date unavailable"}</Badge></p>
              <Button variant="outline" onClick={generateFromDocuments} disabled={busy}>
                {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {generating ? "Reading the documents… this takes up to a minute." : "Regenerate"}
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm">Shown: reference record from the patient file.</p>
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={generateFromDocuments} disabled={busy || pipelineQuery.isLoading}>
                  {busy || pipelineQuery.isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                  {busy ? "Reading the documents… this takes up to a minute." : pipelineQuery.isLoading ? "Checking for an AI draft…" : "Generate from documents (AI)"}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">Documents are pseudonymised before they are sent to OpenAI. The doctor reviews and approves the result.</p>
            </>
          )}
        </section>
      )}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      {summaryQuery.isLoading && hasDocuments && <p className="text-sm text-muted-foreground">Loading the Patient Summary…</p>}
      {visibleSummary && <><EmergencyPanel p={visibleSummary} lang="en" showCodes={false} /><IpsCards p={visibleSummary} lang="en" showCodes={false} /><Provenance source={`${visibleSource} · hospital source system · generated on demand`} /></>}
    </div>
  );
}
