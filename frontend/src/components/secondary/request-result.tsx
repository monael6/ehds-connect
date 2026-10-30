import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { getRequestDetail } from "@/api";

type Row = Record<string, unknown>;
const isRows = (v: unknown): v is Row[] => Array.isArray(v) && v.every((r) => r && typeof r === "object" && !Array.isArray(r));

/** Released results of an approved request; the backend withholds them until the HDAB approves. */
export function RequestResult({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const detail = useQuery({ queryKey: ["request-result", id], queryFn: () => getRequestDetail(id), enabled: open });
  const answer = detail.data?.answer as Row | Row[] | undefined;
  const tables = isRows(answer) ? [["Result", answer] as const] : answer && typeof answer === "object" ? Object.entries(answer).filter(([, v]) => isRows(v)) as [string, Row[]][] : [];
  return <div className="mt-3"><Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}>{open ? "Hide results" : "Show results"}</Button>
    {open && <div className="mt-3 space-y-4 text-sm">{detail.error ? <p className="text-destructive">{detail.error.message}</p> : !detail.data ? <p className="text-muted-foreground">Loading…</p>
      : tables.length ? tables.map(([name, rows]) => <div key={name} className="overflow-x-auto"><p className="mb-1 font-medium">{name.replaceAll("_", " ")}</p><table className="w-full text-left text-xs"><thead><tr>{Object.keys(rows[0] ?? {}).map((k) => <th key={k} className="border-b p-2">{k.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j} className="border-b p-2">{v === null ? "<suppressed>" : String(v)}</td>)}</tr>)}</tbody></table></div>)
      : <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(answer ?? detail.data.explanation?.en ?? "No result", null, 2)}</pre>}
      <p className="text-xs text-muted-foreground">Small groups are suppressed. Opted-out patients are excluded.</p></div>}
  </div>;
}
