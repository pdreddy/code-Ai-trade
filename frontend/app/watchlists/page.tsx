import { PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";
import { WatchlistGrid } from "@/components/watchlist-grid";

export default function WatchlistsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Universe monitoring for ETFs and large-cap equities: real last close, day-over-day change, and the AI master decision for each symbol. No synthetic market prices are rendered."
        eyebrow="Watchlists"
        title="Research Universe"
      >
        <WatchlistGrid />
      </PagePanel>
    </TerminalShell>
  );
}
