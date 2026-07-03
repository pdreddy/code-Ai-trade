import { EmptyState, PagePanel } from "@/components/page-panel";
import { StatusGrid } from "@/components/status-grid";
import { TerminalShell } from "@/components/terminal-shell";
import { backendCapabilities, supportedUniverse } from "@/lib/platform-data";

export default function HomePage() {
  return (
    <TerminalShell>
      <PagePanel
        description="A production-oriented foundation is in place across market data, agents, decisions, backtesting, paper trading, and risk. UI workspaces intentionally show empty states until API endpoints and persistence adapters are added."
        eyebrow="Dashboard"
        title="Research Platform Status"
      >
        <StatusGrid capabilities={backendCapabilities} />
      </PagePanel>
      <PagePanel
        description="The platform is designed for broad equity and ETF coverage without hard-coding provider behavior into the UI."
        eyebrow="Universe"
        title="Supported Research Universe"
      >
        <div className="flex flex-wrap gap-3">
          {supportedUniverse.map((symbol) => (
            <span className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 text-sm" key={symbol}>
              {symbol}
            </span>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Next implementation step: API endpoints and persistence adapters for backtests, paper trading, risk decisions, and analytics." />
    </TerminalShell>
  );
}
