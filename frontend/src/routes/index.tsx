import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Building2, ShieldCheck, GraduationCap, ArrowRight, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DEMO_ACCOUNTS } from "@/mockData";
import { useDemoSession } from "@/lib/demo-session";
import { pageHead } from "@/lib/page-head";
export const Route = createFileRoute("/")({ head: () => pageHead("Sign in", "Choose a synthetic hospital, authority or researcher account for the role-based EHDS Navigator."), component: SignIn });
function SignIn() {
  const { signIn, user } = useDemoSession(); const navigate = useNavigate();
  const open = (id: string, role: string) => { signIn(id); navigate({ to: role === "hospital" ? "/primary" : role === "hdab" ? "/secondary" : "/secondary/catalog" }); };
  return <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
    <h1 className="text-3xl font-semibold">EHDS Navigator</h1><h2 className="mt-3 text-lg text-muted-foreground">Sign in</h2>
    <p className="mt-3 text-muted-foreground">Hospital · Health Data Access Body · Research</p>
    <div className="mt-8 grid gap-4 md:grid-cols-3">{DEMO_ACCOUNTS.filter((a) => a.role !== "visitor").map((a, i) => { const Icon = [Building2, ShieldCheck, GraduationCap][i] ?? Building2; return <article key={a.id} className="flex flex-col rounded-lg border bg-card p-6 transition-colors hover:border-primary/40"><span className="grid h-11 w-11 place-items-center rounded-md bg-primary-soft text-primary"><Icon className="h-6 w-6" /></span><h2 className="mt-5 text-lg font-semibold">{a.role === "hospital" ? "Hospital" : a.role === "hdab" ? "Health Data Access Body" : "Interested party"}</h2><p className="mt-4 font-semibold">{a.name}</p><p className="text-sm text-muted-foreground">{a.roleLabel}<br />{a.organisation}</p><p className="my-5 flex items-start gap-2 border-t pt-4 text-xs text-muted-foreground"><KeyRound className="h-4 w-4 shrink-0" />{a.method}</p><Button className="mt-auto w-full" onClick={() => open(a.id, a.role)}>Sign in as {a.name.split(" ").at(-1)}<ArrowRight className="h-4 w-4" /></Button>{a.role === "interested" && <Button variant="ghost" className="mt-2" onClick={() => open("visitor", "visitor")}>Browse without account</Button>}</article>; })}</div>
    <p className="mt-6 text-xs text-muted-foreground">Demo accounts · No real passwords · Synthetic data</p>{user && <p className="mt-3 text-sm text-muted-foreground">Current account: {user.name}</p>}
  </div>;
}
