import { Suspense } from "react";
import { OptionsWorkspace } from "@/components/options-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function OptionsPage() {
  return (
    <TerminalShell>
      <Suspense fallback={<p className="text-sm text-terminal-muted">Loading options desk…</p>}>
        <OptionsWorkspace />
      </Suspense>
    </TerminalShell>
  );
}
