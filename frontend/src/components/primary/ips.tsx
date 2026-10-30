import { useState } from "react";
import { Loader2, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Patient } from "@/mockData";
import { generateIps } from "@/api";
import { useDemoSession } from "@/lib/demo-session";
import { EmergencyPanel, IpsCards } from "./shared";
import { Provenance } from "@/components/provenance";
export function IpsOnDemand({ patient }: { patient: Patient }) {
  const { log } = useDemoSession(); const [summary, setSummary] = useState<Patient | null>(null); const [source, setSource] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const run = async () => { setBusy(true); setError(""); try { const data = await generateIps(patient.id); setSummary(data.patient); setSource(data.source); log("Show Patient Summary", "Displayed", { patient: patient.id, area: "primary" }); } catch (e) { setError(e instanceof Error ? e.message : "Summary unavailable"); } finally { setBusy(false); } };
  return <div className="space-y-4"><Button onClick={run} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}Show Patient Summary</Button>{error && <p role="alert" className="text-destructive">{error}</p>}{summary && <><EmergencyPanel p={summary} lang="en" showCodes={false} /><IpsCards p={summary} lang="en" showCodes={false} /><Provenance source={`${source} · hospital source system · generated on demand`} /></>}</div>;
}
