import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { APPROVED_PROJECTS } from "@/mockData";
import { useAppState } from "@/lib/app-state";

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
  const { optedOut, setOptedOut } = useAppState();
  return (
    <div className="space-y-6">
      <div><p className="text-sm text-muted-foreground">Signed in as</p><h1 className="text-2xl font-semibold">Maria Muster (Frau M.) · P-00421</h1></div>

      <section className="flex flex-wrap items-center gap-4 rounded-2xl border p-5">
        <ShieldCheck className="h-7 w-7 text-primary" aria-hidden />
        <div className="flex-1">
          <h2 className="font-semibold">Use of my data for research (Art. 71)</h2>
          <p className="text-sm text-muted-foreground">{optedOut ? "You have opted out. Your data is excluded from all research. Doctors can still see it to treat you." : "Your data may be used for approved research, always anonymised or in a secure environment."}</p>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium">
          <Switch checked={optedOut} onCheckedChange={(v) => { setOptedOut(v); toast.success(v ? "Opt-out activated" : "Opt-out withdrawn"); }} />
          Opted out
        </label>
      </section>

      <section className="rounded-2xl border p-5">
        <h2 className="font-semibold">Approved research projects (public register)</h2>
        <ul className="mt-3 divide-y text-sm">
          {APPROVED_PROJECTS.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span><span className="font-mono text-xs text-primary">{p.id}</span> {p.title} <span className="text-muted-foreground">· {p.org}</span></span>
              <Badge variant="outline">{p.kind}</Badge>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
