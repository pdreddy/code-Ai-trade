import { Suspense } from "react";
import { SignalsWorkspace } from "@/components/signals-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function SignalsPage() {
  return (
    <TerminalShell>
      <Suspense fallback={<p className="text-sm text-terminal-muted">Loading workbench…</p>}>
        <SignalsWorkspace />
      </Suspense>
    </TerminalShell>
  );
}
