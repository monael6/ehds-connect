import { createFileRoute } from "@tanstack/react-router";
import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { METRICS, PRIMARY_METRICS, REFERENCE_P00421 } from "@/mockData";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { getSecondaryMetrics } from "@/api";
import { Provenance } from "@/components/provenance";

export const Route = createFileRoute("/secondary/metrics")({
  head: () => ({
    meta: [
      { title: "Metrics | EHDS Navigator" },
      { name: "description", content: "Evaluation metrics for research requests and the primary-use treatment workflow." },
      { property: "og:title", content: "Metrics | EHDS Navigator" },
      { property: "og:description", content: "Decision accuracy, privacy leaks, letter completeness, FHIR validity and access log coverage." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Metrics,
});

const ok = <Check className="h-4 w-4 text-success" aria-label="yes" />;
const no = <X className="h-4 w-4 text-destructive" aria-label="no" />;
const seconds = (t: number) => (t < 1 ? t.toFixed(3) : t.toFixed(1));

function Metrics() {
  const { data } = useSuspenseQuery(queryOptions({ queryKey: ["secondary-metrics"], queryFn: getSecondaryMetrics }));
  const metrics = data.data;
  const slowest = Math.max(...metrics.map((m) => m.time));
  const count = (f: (m: (typeof metrics)[number]) => boolean) => metrics.filter(f).length;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold">Metrics</h1>{data.source === "FastAPI" ? <Badge variant="outline" className="border-success/30 bg-success-soft text-success">measured by the backend</Badge> : <Badge variant="outline" className="border-warning/30 bg-warning-soft text-warning">demo values</Badge>}</div>
          <div className="overflow-x-auto rounded-2xl border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-left text-xs text-muted-foreground"><tr>{["Request", "Decision correct", "Numbers correct", "Privacy leaks", "Consistent over 3 runs", "Time (s)"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {metrics.map((m) => (
                  <tr key={m.id} className="border-t"><td className="px-4 py-2.5 font-mono">{m.id}</td><td className="px-4">{m.decisionCorrect ? ok : no}</td><td className="px-4">{m.numbersCorrect === null ? <span className="text-muted-foreground">n/a</span> : m.numbersCorrect ? ok : no}</td><td className="px-4 font-mono">{m.privacyLeaks}</td><td className="px-4">{m.consistent ? ok : no}</td><td className="px-4 font-mono">{seconds(m.time)}</td></tr>
                ))}
                <tr className="border-t-2 bg-muted/40 font-semibold"><td className="px-4 py-3">Summary</td><td className="px-4">{count((m) => m.decisionCorrect)}/{metrics.length}</td><td className="px-4">{count((m) => m.numbersCorrect === true)}/{count((m) => m.numbersCorrect !== null)}</td><td className="px-4">{metrics.reduce((n, m) => n + m.privacyLeaks, 0)}</td><td className="px-4">{count((m) => m.consistent)}/{metrics.length}</td><td className="px-4">max {seconds(slowest)}</td></tr>
              </tbody>
            </table>
          </div>
      <Provenance source={`${data.source} · HDAB evaluation metrics`} />
    </div>
  );
}
