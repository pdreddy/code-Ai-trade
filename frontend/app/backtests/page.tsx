import { Suspense } from "react";
import { BacktestWorkspace } from "@/components/backtest-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function BacktestsPage() {
  return (
    <TerminalShell>
      <Suspense fallback={<p className="text-sm text-terminal-muted">Loading backtester…</p>}>
        <BacktestWorkspace />
      </Suspense>
    </TerminalShell>
  );
}
