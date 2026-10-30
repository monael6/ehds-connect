import { createFileRoute } from "@tanstack/react-router";
import { useSuspenseQuery, queryOptions } from "@tanstack/react-query";
import { getUnregisteredFacilities } from "@/api";
import { pageHead } from "@/lib/page-head";
import { Provenance } from "@/components/provenance";
import { Badge } from "@/components/ui/badge";
export const Route = createFileRoute("/secondary/facilities")({ head: () => pageHead("Facilities not yet in the catalogue", "Facility types with potentially relevant health data and their registration status."), component: Facilities });
function Facilities() { const { data } = useSuspenseQuery(queryOptions({ queryKey: ["unregistered-facilities"], queryFn: getUnregisteredFacilities })); return <div className="space-y-6"><h1 className="text-2xl font-semibold">Facilities with relevant data not yet in the catalogue</h1><div className="space-y-4">{data.data.map((f) => <article key={f.name} className="rounded-lg border p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{f.name}</h2><Badge variant="outline">Not yet registered</Badge></div><p className="mt-3 text-sm text-muted-foreground">Likely held data: {f.data}</p></article>)}</div><Provenance source={`${data.source} · indicative facility types, not verified holdings`} /></div>; }