import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Provenance } from "@/components/provenance";
import { getPortal } from "@/api";

export const Route = createFileRoute("/secondary/rights")({
  head: () => ({
    meta: [
      { title: "My data rights | EHDS Navigator" },
      { name: "description", content: "Citizen view: research opt-out status and approved research projects." },
      { property: "og:title", content: "My data rights | EHDS Navigator" },
      { property: "og:description", content: "Control research use of your health data and view approved projects." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Rights,
});

function Rights() {
  const { data } = useSuspenseQuery(queryOptions({ queryKey: ["portal"], queryFn: getPortal }));
  // The switch only simulates a change: the Track-3 opt-out list stays as it is, so the metrics stay comparable.
  const [simulated, setSimulated] = useState<boolean | null>(null);
  const optedOut = simulated ?? data.data.optedOut;
  return (
    <div className="space-y-6">
      <div><p className="text-sm text-muted-foreground">Signed in as</p><h1 className="text-2xl font-semibold">Maria Muster (Frau M.) · {data.data.patient}</h1></div>

      <section className="flex flex-wrap items-center gap-4 rounded-2xl border p-5">
        <ShieldCheck className="h-7 w-7 text-primary" aria-hidden />
        <div className="flex-1">
          <h2 className="font-semibold">Use of my data for research (Art. 71)</h2>
          <p className="text-sm text-muted-foreground">{optedOut ? "You have opted out. Your data is excluded from all research. Doctors can still see it to treat you." : "Your data may be used for approved research, always anonymised or in a secure environment."}</p>
          <p className="mt-1 text-xs text-muted-foreground">{simulated === null ? `Status recorded in the KIS · ${data.source}` : "Simulation only – the recorded opt-out list is not changed."}</p>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium">
          <Switch checked={optedOut} onCheckedChange={(v) => { setSimulated(v); toast.success(v ? "Opt-out activated (simulation)" : "Opt-out withdrawn (simulation)"); }} />
          Opted out
        </label>
      </section>

      <section className="rounded-2xl border p-5">
        <h2 className="font-semibold">Approved data uses (public register)</h2>
        <p className="mt-1 text-xs text-muted-foreground">Opted-out patients are excluded from every use listed here.</p>
        {data.data.uses.length ? <ul className="mt-3 divide-y text-sm">
          {data.data.uses.map((u, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span><span className="text-xs text-muted-foreground">{u.date}</span> {u.purpose} <span className="text-muted-foreground">· {u.organisation}</span></span>
              <Badge variant="outline">{u.type}</Badge>
            </li>
          ))}
        </ul> : <p className="mt-3 text-sm text-muted-foreground">No approved data uses yet.</p>}
      </section>
      <Provenance source={`${data.source} · patient portal of Frau M.`} />
    </div>
  );
}
