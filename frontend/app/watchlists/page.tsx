import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";
import { LiveMarketSnapshots } from "@/components/live-market-snapshots";

export default function WatchlistsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Universe monitoring for ETFs, S&P 500 constituents, Nasdaq listings, and future tickers. Runtime cards request real provider data and never render synthetic market prices."
        eyebrow="Watchlists"
        title="Research Universe"
      >
        <LiveMarketSnapshots />
      </PagePanel>
      <EmptyState message="If live provider access is blocked, run from the repo root: docker compose run --rm market-snapshot && docker compose up -d --build frontend" />
    </TerminalShell>
  );
}
