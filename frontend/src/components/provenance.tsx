export function Provenance({ source, editor = "Source system; no manual changes recorded" }: { source: string; editor?: string }) {
  return <p className="border-t pt-3 text-xs text-muted-foreground">Source: {source} · Last changed by: {editor}</p>;
}