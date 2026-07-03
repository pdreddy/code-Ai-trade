import { Suspense } from "react";
import { StockWorkspace } from "@/components/stock-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function StockDetailsPage() {
  return (
    <TerminalShell>
      <Suspense fallback={<p className="text-sm text-terminal-muted">Loading workspace…</p>}>
        <StockWorkspace />
      </Suspense>
    </TerminalShell>
  );
}
