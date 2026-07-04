import Link from "next/link";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { StatusGrid } from "@/components/status-grid";
import { TerminalShell } from "@/components/terminal-shell";
import { backendCapabilities, supportedUniverse } from "@/lib/platform-data";

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
        description="Select a symbol to open its live research workspace. Bars and signals are fetched from the configured provider — no synthetic prices are rendered."
        eyebrow="Universe"
        title="Supported Research Universe"
      >
        <div className="flex flex-wrap gap-3">
          {supportedUniverse.map((symbol) => (
            <Link
              className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 font-mono text-sm transition hover:border-terminal-accent hover:text-terminal-accent"
              href={`/stocks?symbol=${symbol}`}
              key={symbol}
            >
              {symbol}
            </Link>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Open Backtests for a single-symbol proven track record, or Portfolio / Paper Trades / Analytics for the $10,000 universe execution with live holdings, trade blotter, and upcoming planned trades." />
    </TerminalShell>
  );
}
