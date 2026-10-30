import { useQuery } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getPatientDocuments } from "@/api";

export function PatientDocuments({ patientId }: { patientId: string }) {
  const { data, isLoading } = useQuery({ queryKey: ["patient-documents", patientId], queryFn: () => getPatientDocuments(patientId) });
  if (isLoading) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading documents…</p>;
  const docs = data?.data ?? [];
  if (!docs.length) return <p className="text-sm text-muted-foreground">No clinical documents in the record for this patient.</p>;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{docs.length} documents, newest first. The discharge letter and Patient Summary name the document each entry comes from.</p>
      <ul className="divide-y rounded-lg border">
        {docs.map((d) => (
          <li key={d.id}>
            <details className="group px-4 py-3">
              <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1">
                <FileText className="h-4 w-4 shrink-0 text-primary" aria-hidden />
                <span className="font-medium">{d.title}</span>
                <Badge variant="outline">{d.type}</Badge>
                <span className="text-xs text-muted-foreground">{d.date.replace("T", " ")} · {d.specialty} · {d.author_role}</span>
                <span className="ml-auto font-mono text-xs text-muted-foreground">{d.id}</span>
              </summary>
              <p className="mt-2 text-xs text-muted-foreground">{d.facility}</p>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm leading-relaxed">{d.text}</pre>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}
