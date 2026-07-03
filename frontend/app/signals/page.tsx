import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

const agents = [
  "Trend",
  "Momentum",
  "Volatility",
  "Risk",
  "Portfolio",
  "Mean Reversion",
  "Breakout",
  "Support / Resistance",
  "Volume",
  "Market Regime"
];

export default function SignalsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="The backend agent framework and master decision engine are implemented. This page avoids fake signals until decision APIs and persistence are exposed."
        eyebrow="Signals"
        title="AI Signal Workbench"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {agents.map((agent) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={agent}>
              <p className="font-medium">{agent}</p>
              <p className="mt-2 text-xs text-emerald-300">Backend agent ready</p>
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Persisted agent votes and master decisions will appear here once API endpoints are added." />
    </TerminalShell>
  );
}
