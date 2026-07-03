import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

const analytics = ["Success rate", "Equity curve", "Drawdown curve", "Trade analytics", "Portfolio analytics", "Monthly returns"];

export default function AnalyticsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Analytics will report real backtest and paper-trading performance only after result persistence exists."
        eyebrow="Analytics"
        title="Performance Analytics"
      >
        <div className="grid gap-3 md:grid-cols-3">
          {analytics.map((item) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={item}>
              <p className="font-medium">{item}</p>
              <p className="mt-2 text-xs text-terminal-muted">Waiting for real performance data</p>
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Success-rate and performance charts will not use fabricated data." />
    </TerminalShell>
  );
}
