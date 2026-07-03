import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

const panels = [
  "Candlestick chart",
  "Indicators",
  "AI votes",
  "Support / resistance",
  "Recent trades",
  "Signal history",
  "Backtest summary",
  "Portfolio position"
];

export default function StockDetailsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Stock details will compose market data, decisions, trades, and portfolio state without embedding business logic in UI components."
        eyebrow="Stock Details"
        title="Instrument Research Workspace"
      >
        <div className="grid gap-3 md:grid-cols-4">
          {panels.map((panel) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4 text-sm" key={panel}>
              {panel}
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="No chart data is rendered until market-data and analytics APIs are available." />
    </TerminalShell>
  );
}
