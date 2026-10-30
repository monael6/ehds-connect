import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoSessionProvider, useDemoSession } from "@/lib/demo-session";
import { AppStateProvider, useAppState } from "@/lib/app-state";

vi.mock("@/api", () => ({ writeAudit: vi.fn().mockResolvedValue({ source: "Synthetic fallback" }) }));
afterEach(cleanup);
function Probe() {
  const { user, signIn, signOut } = useDemoSession();
  const { optedOut } = useAppState();
  return <><output aria-label="Account">{user?.id ?? "signed-out"}</output><output aria-label="Opt-out">{String(optedOut)}</output><button onClick={() => signIn("anna")}>Sign in</button><button onClick={signOut}>Sign out</button></>;
}
describe("Demo provider lifecycle", () => {
  it("Keeps demo identity through a consumer rerender and clears it on sign-out", () => {
    const tree = () => <DemoSessionProvider><AppStateProvider><Probe /></AppStateProvider></DemoSessionProvider>;
    const view = render(tree());
    expect(screen.getByLabelText("Account")).toHaveTextContent("signed-out");
    fireEvent.click(screen.getByText("Sign in"));
    expect(screen.getByLabelText("Account")).toHaveTextContent("anna");
    view.rerender(tree());
    expect(screen.getByLabelText("Account")).toHaveTextContent("anna");
    expect(screen.getByLabelText("Opt-out")).toHaveTextContent("true");
    fireEvent.click(screen.getByText("Sign out"));
    expect(screen.getByLabelText("Account")).toHaveTextContent("signed-out");
  });
});