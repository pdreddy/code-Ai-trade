import { EmptyState, PagePanel } from "@/components/page-panel";
import { StatusGrid } from "@/components/status-grid";
import { TerminalShell } from "@/components/terminal-shell";
import { WatchlistGrid } from "@/components/watchlist-grid";
import { backendCapabilities } from "@/lib/platform-data";

export default function HomePage() {
  return (
    <TerminalShell>
      <PagePanel
        description="A production-oriented foundation is in place across market data, agents, decisions, backtesting, paper trading, and risk. Market-data and signal APIs are live; the remaining workspaces show honest empty states until persistence adapters are added."
        eyebrow="Dashboard"
        title="Research Platform Status"
      >
        <StatusGrid capabilities={backendCapabilities} />
      </PagePanel>
      <PagePanel
        description="Real last close, day-over-day change, and the AI master decision for every symbol in the research universe. Open any card for its full workspace."
        eyebrow="Universe"
        title="Supported Research Universe"
      >
        <WatchlistGrid />
      </PagePanel>
      <EmptyState message="Open Backtests for a single-symbol proven track record, or Portfolio / Paper Trades / Analytics for the $10,000 universe execution with live holdings, trade blotter, and upcoming planned trades." />
    </TerminalShell>
  );
}
