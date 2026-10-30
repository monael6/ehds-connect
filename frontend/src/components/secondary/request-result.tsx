import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { getRequestDetail } from "@/api";

type Row = Record<string, unknown>;
const isRows = (v: unknown): v is Row[] => Array.isArray(v) && v.every((r) => r && typeof r === "object" && !Array.isArray(r));

const isObj = (v: unknown): v is Row => !!v && typeof v === "object" && !Array.isArray(v);
/** The engine answers per group ({"Klinikum West": {"patients": 281}}), with a flat object or with row lists. */
export function toTables(answer: unknown): [string, Row[]][] {
  if (isRows(answer)) return answer.length ? [["Result", answer]] : [];
  if (!isObj(answer) || !Object.keys(answer).length) return [];
  const values = Object.values(answer);
  if (values.every(isObj)) return [["Result", Object.entries(answer).map(([group, v]) => ({ group, ...(v as Row) }))]];
  if (values.every((v) => !isObj(v) && !Array.isArray(v))) return [["Result", [answer]]];
  return Object.entries(answer).filter(([, v]) => isRows(v)) as [string, Row[]][];
}

/** Released results of an approved request; the backend withholds them until the HDAB approves. */
export function RequestResult({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const detail = useQuery({ queryKey: ["request-result", id], queryFn: () => getRequestDetail(id), enabled: open });
  const answer = detail.data?.answer;
  const tables = toTables(answer);
  return <div className="mt-3"><Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}>{open ? "Hide results" : "Show results"}</Button>
    {open && <div className="mt-3 space-y-4 text-sm">{detail.error ? <p className="text-destructive">{detail.error.message}</p> : !detail.data ? <p className="text-muted-foreground">Loading…</p>
      : tables.length ? tables.map(([name, rows]) => <div key={name} className="overflow-x-auto"><p className="mb-1 font-medium">{name.replaceAll("_", " ")}</p><table className="w-full text-left text-xs"><thead><tr>{Object.keys(rows[0] ?? {}).map((k) => <th key={k} className="border-b p-2">{k.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j} className="border-b p-2">{v === null ? "<suppressed>" : String(v)}</td>)}</tr>)}</tbody></table></div>)
      : <p className="text-muted-foreground">No numbers could be calculated for this question. Submit a new request and define each term, e.g. "Type 2 diabetes = any condition with an ICD-10 code starting with E11."</p>}
      <p className="text-xs text-muted-foreground">Small groups are suppressed. Opted-out patients are excluded.</p></div>}
  </div>;
}
