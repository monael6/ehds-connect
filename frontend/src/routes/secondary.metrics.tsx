import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
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

function Metrics() {
  const { data } = useSuspenseQuery(queryOptions({ queryKey: ["secondary-metrics"], queryFn: getSecondaryMetrics }));
  const metrics = data.data;
  const slowest = Math.max(...metrics.map((m) => m.time));
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold">Metrics</h1><Badge variant="outline" className="border-warning/30 bg-warning-soft text-warning">demo values</Badge></div>
          <div className="overflow-x-auto rounded-2xl border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-left text-xs text-muted-foreground"><tr>{["Request", "Decision correct", "Numbers correct", "Privacy leaks", "Consistent over 3 runs", "Time (s)"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {metrics.map((m) => (
                  <tr key={m.id} className="border-t"><td className="px-4 py-2.5 font-mono">{m.id}</td><td className="px-4">{ok}</td><td className="px-4">{m.numbersCorrect ? ok : <span className="text-muted-foreground">n/a</span>}</td><td className="px-4 font-mono">0</td><td className="px-4">{ok}</td><td className="px-4 font-mono">{m.time.toFixed(1)}</td></tr>
                ))}
                <tr className="border-t-2 bg-muted/40 font-semibold"><td className="px-4 py-3">Summary</td><td className="px-4">10/10</td><td className="px-4">6/6</td><td className="px-4">0</td><td className="px-4">10/10</td><td className="px-4">max {slowest.toFixed(1)}</td></tr>
              </tbody>
            </table>
          </div>
      <Provenance source={`${data.source} · HDAB evaluation metrics`} />
    </div>
  );
}
