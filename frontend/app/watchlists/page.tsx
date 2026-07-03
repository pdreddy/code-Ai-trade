import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";
import { marketSnapshotGeneratedAt, marketSnapshots } from "@/lib/generated-market-snapshot";
import { supportedUniverse } from "@/lib/platform-data";

export default function WatchlistsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Universe monitoring for ETFs, S&P 500 constituents, Nasdaq listings, and future tickers. No synthetic market prices are rendered."
        eyebrow="Watchlists"
        title="Research Universe"
      >
        {marketSnapshots.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {marketSnapshots.map((snapshot) => (
              <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={snapshot.symbol}>
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{snapshot.symbol}</p>
                  <span className="text-xs text-terminal-muted">{snapshot.bars} bars</span>
                </div>
                <dl className="mt-4 grid gap-2 text-xs text-terminal-muted">
                  <div className="flex justify-between"><dt>Last close</dt><dd>${snapshot.lastClose}</dd></div>
                  <div className="flex justify-between"><dt>5Y return</dt><dd>{snapshot.totalReturn}</dd></div>
                  <div className="flex justify-between"><dt>CAGR</dt><dd>{snapshot.cagr}</dd></div>
                  <div className="flex justify-between"><dt>Max DD</dt><dd>{snapshot.maxDrawdown}</dd></div>
                  <div className="flex justify-between"><dt>Realized vol</dt><dd>{snapshot.realizedVolatility}</dd></div>
                </dl>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {supportedUniverse.map((symbol) => (
              <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={symbol}>
                <p className="font-medium">{symbol}</p>
                <p className="mt-2 text-xs text-terminal-muted">Run the five-year snapshot command to populate real historical data.</p>
              </div>
            ))}
          </div>
        )}
        <p className="mt-4 text-xs text-terminal-muted">
          Snapshot generated at: {marketSnapshotGeneratedAt ?? "not generated"}.
        </p>
      </PagePanel>
      <EmptyState message="To load real five-year market data locally, run: python scripts/generate_market_snapshot.py && cd frontend && npm run build" />
    </TerminalShell>
  );
}
