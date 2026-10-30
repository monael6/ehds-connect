import { createFileRoute } from "@tanstack/react-router";
import { Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { getCatalogue } from "@/api";
import { Provenance } from "@/components/provenance";
import { useDemoSession } from "@/lib/demo-session";

export const Route = createFileRoute("/secondary/catalog")({
  head: () => ({
    meta: [
      { title: "Data catalog | EHDS Navigator" },
      { name: "description", content: "HealthDCAT-AP style descriptions of three synthetic hospital datasets." },
      { property: "og:title", content: "Data catalog | EHDS Navigator" },
      { property: "og:description", content: "Dataset descriptions available through the Health Data Access Body." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Catalog,
});

function Catalog() {
  const { user } = useDemoSession();
  const { data } = useSuspenseQuery(queryOptions({ queryKey: ["catalogue"], queryFn: getCatalogue }));
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Data catalog</h1>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {data.data.map((d) => (
          <article key={d.holder} className="flex flex-col rounded-2xl border p-5">
            <Database className="h-6 w-6 text-primary" aria-hidden />
            <h2 className="mt-3 font-semibold leading-snug">{d.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{d.description}</p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-muted-foreground">Time range</dt><dd>{d.from} – {d.to}</dd></div>
              {user?.role === "hdab" && <div className="flex justify-between"><dt className="text-muted-foreground">Patients</dt><dd>≈ {d.patients.toLocaleString("en-US")}</dd></div>}
              <div><dt className="text-muted-foreground">Record types</dt><dd className="mt-1 flex flex-wrap gap-1">{d.recordTypes.map((t) => <Badge key={t} variant="outline">{t}</Badge>)}</dd></div>
              <div><dt className="text-muted-foreground">Code systems</dt><dd className="mt-1 flex flex-wrap gap-1">{["ICD-10", "ATC", "LOINC"].map((t) => <Badge key={t} variant="secondary">{t}</Badge>)}</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">Access</dt><dd>via HDAB</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <Provenance source={`${data.source} · EU dataset catalogue`} />
    </div>
  );
}
