import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Stethoscope, Landmark, GraduationCap, ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DEMO_ACCOUNTS } from "@/mockData";
import { useDemoSession } from "@/lib/demo-session";
import { getRegistrationOptions, loginWithPassword, registerAccount } from "@/api";
import type { DemoRole } from "@/lib/role-rules";
import { pageHead } from "@/lib/page-head";

export const Route = createFileRoute("/")({ head: () => pageHead("Sign in", "Sign in or register as hospital staff, HDAB staff or applicant."), component: SignIn });

const CATEGORIES = [
  { id: "healthcare", label: "Healthcare", hint: "Senior Doctor · Doctor · IT Admin", icon: Stethoscope, accounts: ["anna", "markus", "thomas"] },
  { id: "institute", label: "Institute", hint: "HDAB Staff", icon: Landmark, accounts: ["petra"] },
  { id: "applicant", label: "Researcher / Applicant", hint: "Request data and get results", icon: GraduationCap, accounts: ["lena"] },
] as const;
const HOME: Record<DemoRole, string> = { hospital: "/primary", it_admin: "/admin", hdab: "/secondary", interested: "/secondary", visitor: "/secondary/catalog" };

function SignIn() {
  const { signIn, signInAs } = useDemoSession(); const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const go = (role: DemoRole) => navigate({ to: HOME[role] });
  const submit = async () => { setBusy(true); setError(""); try { go(signInAs(await loginWithPassword(email, password)).role); } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed"); } finally { setBusy(false); } };
  return <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
    <h1 className="text-3xl font-semibold">EHDS Navigator</h1>
    <p className="mt-2 text-muted-foreground">Treatment in the hospital and research with health data, in one place.</p>
    <div className="mt-8 inline-flex rounded-lg border bg-card p-1">{(["signin", "register"] as const).map((m) => <Button key={m} variant={mode === m ? "default" : "ghost"} size="sm" onClick={() => { setMode(m); setError(""); }}>{m === "signin" ? "Sign in" : "Register"}</Button>)}</div>
    {mode === "signin" ? <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
      <form className="space-y-4 rounded-lg border bg-card p-6" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <h2 className="text-lg font-semibold">Sign in with your account</h2>
        <label className="block space-y-1 text-sm">Email<Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="block space-y-1 text-sm">Password<Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={busy || !email || !password}>Sign in</Button>
        <p className="text-xs text-muted-foreground">Demo accounts use the password demo1234.</p>
      </form>
      <div className="space-y-4"><h2 className="text-lg font-semibold">Or try a demo account</h2>
        {CATEGORIES.map((c) => <section key={c.id} className="rounded-lg border bg-card p-4"><h3 className="flex items-center gap-2 font-medium"><c.icon className="h-5 w-5 text-primary" />{c.label}</h3>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">{c.accounts.map((id) => { const a = DEMO_ACCOUNTS.find((x) => x.id === id); if (!a) return null; return <button key={id} type="button" onClick={() => { signIn(a.id); go(a.role); }} className="rounded-md border p-3 text-left text-sm transition-colors hover:border-primary hover:bg-primary-soft"><span className="block font-medium">{a.roleLabel}</span><span className="block text-xs text-muted-foreground">{a.name}</span></button>; })}</div></section>)}
        <Button variant="ghost" size="sm" onClick={() => { signIn("visitor"); go("visitor"); }}>Browse the public catalogue without an account <ArrowRight className="h-4 w-4" /></Button>
      </div>
    </div> : <Register onActive={(role) => go(role)} />}
    <p className="mt-8 text-xs text-muted-foreground">Prototype · Synthetic data only · All actions are logged</p>
  </div>;
}

function Register({ onActive }: { onActive: (role: DemoRole) => void }) {
  const { signInAs } = useDemoSession();
  const options = useQuery({ queryKey: ["registration-options"], queryFn: getRegistrationOptions });
  const [category, setCategory] = useState<string>(""); const [role, setRole] = useState("");
  const [f, setF] = useState({ name: "", email: "", password: "", organisation: "", hospital: "" });
  const [error, setError] = useState(""); const [done, setDone] = useState(""); const [busy, setBusy] = useState(false);
  const cat = options.data?.find((o) => o.category === category);
  const healthcare = category === "healthcare";
  const submit = async () => { setBusy(true); setError(""); try { const r = await registerAccount({ ...f, category, role, organisation: healthcare ? f.hospital : f.organisation, ...(healthcare ? { hospital: f.hospital } : {}) }); if (r.status === "active") onActive(signInAs(r.user).role); else setDone(r.message); } catch (e) { setError(e instanceof Error ? e.message : "Registration failed"); } finally { setBusy(false); } };
  if (done) return <div className="mt-6 max-w-xl rounded-lg border border-success/30 bg-success-soft p-6"><CheckCircle2 className="h-6 w-6 text-success" /><p className="mt-3 font-medium">{done}</p></div>;
  return <div className="mt-6 max-w-3xl space-y-6">
    <section><h2 className="font-semibold">1. Who are you?</h2><div className="mt-3 grid gap-3 sm:grid-cols-3">{CATEGORIES.map((c) => <button key={c.id} type="button" onClick={() => { setCategory(c.id); setRole(options.data?.find((o) => o.category === c.id)?.roles.length === 1 ? options.data.find((o) => o.category === c.id)?.roles[0]?.id ?? "" : ""); }} className={`rounded-lg border p-4 text-left transition-colors ${category === c.id ? "border-primary bg-primary-soft" : "bg-card hover:border-primary/50"}`}><c.icon className="h-6 w-6 text-primary" /><span className="mt-2 block font-medium">{c.label}</span><span className="block text-xs text-muted-foreground">{c.hint}</span></button>)}</div>
      {options.error && <p className="mt-2 text-sm text-destructive">Registration needs the backend. Start it, or use a demo account.</p>}</section>
    {cat && <section><h2 className="font-semibold">2. Your role</h2><div className="mt-3 flex flex-wrap gap-2">{cat.roles.map((r) => <Button key={r.id} variant={role === r.id ? "default" : "outline"} onClick={() => setRole(r.id)}>{r.label}</Button>)}</div>{cat.needs_activation && <p className="mt-2 text-xs text-muted-foreground">Your hospital's IT admin activates new accounts.</p>}</section>}
    {cat && role && <form className="space-y-3 rounded-lg border bg-card p-6" onSubmit={(e) => { e.preventDefault(); void submit(); }}><h2 className="font-semibold">3. Your details</h2>
      <label className="block space-y-1 text-sm">Full name<Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
      <label className="block space-y-1 text-sm">Email<Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
      <label className="block space-y-1 text-sm">Password (at least 8 characters)<Input type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
      {healthcare ? <label className="block space-y-1 text-sm">Hospital<select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={f.hospital} onChange={(e) => setF({ ...f, hospital: e.target.value })}><option value="">Choose your hospital</option>{(cat.hospitals ?? []).map((h) => <option key={h} value={h}>{h}</option>)}</select></label>
        : <label className="block space-y-1 text-sm">Organisation<Input value={f.organisation} onChange={(e) => setF({ ...f, organisation: e.target.value })} /></label>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={busy || !f.name || !f.email || f.password.length < 8 || (healthcare ? !f.hospital : !f.organisation)}>Create account</Button></form>}
  </div>;
}
