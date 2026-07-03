import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

const metrics = ["CAGR", "Sharpe", "Sortino", "Calmar", "Profit Factor", "Win Rate", "Max Drawdown", "Exposure"];

export default function BacktestsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="The event-driven backend enforces signal-on-close and fill-next-open execution. UI submission is withheld until a real backtest API endpoint exists."
        eyebrow="Backtests"
        title="Event-Driven Backtest Workspace"
      >
        <div className="grid gap-3 md:grid-cols-4">
          {metrics.map((metric) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={metric}>
              <p className="text-xs uppercase tracking-[0.2em] text-terminal-muted">Metric</p>
              <p className="mt-2 font-medium">{metric}</p>
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Backtest run controls will be enabled only after API endpoints persist real run requests and results." />
    </TerminalShell>
  );
}
