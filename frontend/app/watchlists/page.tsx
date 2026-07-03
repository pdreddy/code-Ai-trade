import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";
import { supportedUniverse } from "@/lib/platform-data";

export default function WatchlistsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Universe monitoring for ETFs, S&P 500 constituents, Nasdaq listings, and future tickers. No synthetic market prices are rendered."
        eyebrow="Watchlists"
        title="Research Universe"
      >
        <div className="grid gap-3 md:grid-cols-3">
          {supportedUniverse.map((symbol) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={symbol}>
              <p className="font-medium">{symbol}</p>
              <p className="mt-2 text-xs text-terminal-muted">Awaiting persisted market-data API wiring.</p>
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Watchlist CRUD and live scanner outputs will be enabled after API and persistence milestones." />
    </TerminalShell>
  );
}
