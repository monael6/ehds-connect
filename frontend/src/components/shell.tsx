import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { LogOut, Activity, Shield, Stethoscope, Inbox, FlaskConical, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useDemoSession } from "@/lib/demo-session";
import { canOpen } from "@/lib/role-rules";

export const TOUR = [{ go: { to: "/" } }, { go: { to: "/primary", search: { tab: "letter" } } }] as const;
export function Shell({ children }: { children: ReactNode }) {
  const { pathname, searchStr } = useLocation();
  const navigate = useNavigate();
  const { user, log, signOut } = useDemoSession();
  const allowed = canOpen(user?.role, pathname);
  useEffect(() => { if (user) log("Opened area", allowed ? "Access allowed" : "Access denied", { area: pathname }); }, [pathname, searchStr, user?.id]);
  return <div className="flex min-h-screen flex-col bg-workspace">
    <header className="border-b bg-background">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
        <Link to="/" className="flex shrink-0 items-center gap-3 text-lg font-semibold"><span className="grid h-8 w-8 place-items-center rounded-md bg-primary font-bold text-primary-foreground">E</span>EHDS Navigator</Link>
        {user && <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2"><div className="text-xs sm:text-right"><div className="font-semibold text-foreground">{user.name}</div><div className="text-muted-foreground">{user.roleLabel} · {user.organisation}</div><div className="text-muted-foreground">{user.role === "visitor" ? "Browsing since" : "Signed in at"} {user.signedInAt}</div></div><div className="flex items-center gap-1 sm:border-l sm:pl-3"><Button asChild variant="ghost" size="sm"><Link to="/activity"><Activity className="h-4 w-4" />Activity log</Link></Button><Button variant="ghost" size="sm" onClick={() => { signOut(); navigate({ to: "/", replace: true }); }}><LogOut className="h-4 w-4" />Sign out</Button></div></div>}
      </div>
      {user && <nav aria-label="Main navigation" className="border-t"><div className="mx-auto flex max-w-7xl flex-wrap gap-x-5 px-4 sm:px-6">
        {user.role === "it_admin" ? <Link to="/admin" className="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm text-muted-foreground transition-colors hover:text-primary data-[status=active]:border-primary data-[status=active]:text-primary"><Users className="h-4 w-4" />Users and permissions</Link> : user.role === "hospital" ? <><Link to="/primary" className="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm text-muted-foreground transition-colors hover:text-primary data-[status=active]:border-primary data-[status=active]:text-primary"><Stethoscope className="h-4 w-4" />Primary use</Link><Link to="/hospital" className="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm text-muted-foreground transition-colors hover:text-primary data-[status=active]:border-primary data-[status=active]:text-primary"><Inbox className="h-4 w-4" />Data requests for our hospital</Link>{user.hospitalRole === "senior_doctor" && <Link to="/admin" className="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm text-muted-foreground transition-colors hover:text-primary data-[status=active]:border-primary data-[status=active]:text-primary"><Users className="h-4 w-4" />Team and permissions</Link>}</> : <><Link to={user.role === "hdab" ? "/secondary" : "/secondary/catalog"} className="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm text-muted-foreground transition-colors hover:text-primary data-[status=active]:border-primary data-[status=active]:text-primary"><FlaskConical className="h-4 w-4" />Secondary use</Link>{user.role === "hdab" && <Link to="/audit" className="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm text-muted-foreground hover:text-primary data-[status=active]:border-primary data-[status=active]:text-primary"><Shield className="h-4 w-4" />Audit</Link>}</>}
      </div></nav>}
    </header>
    <main className="flex-1">{allowed ? children : <div className="mx-auto max-w-3xl px-6 py-16"><Shield className="mb-4 h-9 w-9 text-muted-foreground" /><h1 className="text-2xl font-semibold">{user ? `You don't have access to this area with the role ${user.roleLabel}.` : "Sign in to open this area."}</h1><Button className="mt-6" onClick={() => navigate({ to: "/" })}>Back to sign in</Button></div>}</main>
    <footer className="border-t bg-background"><p className="mx-auto max-w-7xl px-4 py-4 text-center text-xs text-muted-foreground">Prototype with synthetic data. All actions are logged.</p></footer>
  </div>;
}
export function CodeBlock({ children }: { children: string }) { return <pre className="max-h-[520px] overflow-auto rounded-lg bg-code p-4 font-mono text-xs leading-relaxed text-code-foreground">{children}</pre>; }
