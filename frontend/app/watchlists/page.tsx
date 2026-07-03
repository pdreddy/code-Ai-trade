import Link from "next/link";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";
import { supportedUniverse } from "@/lib/platform-data";

export default function WatchlistsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Universe monitoring for ETFs and large-cap equities. Open any symbol to load its live bars and AI signals. No synthetic market prices are rendered."
        eyebrow="Watchlists"
        title="Research Universe"
      >
        <div className="grid gap-3 md:grid-cols-3">
          {supportedUniverse.map((symbol) => (
            <Link
              className="rounded-xl border border-terminal-border bg-black/20 p-4 transition hover:border-terminal-accent"
              href={`/stocks?symbol=${symbol}`}
              key={symbol}
            >
              <p className="font-mono font-medium">{symbol}</p>
              <p className="mt-2 text-xs text-terminal-muted">Open live research workspace →</p>
            </Link>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Persisted watchlist CRUD and live scanner outputs will be enabled after the persistence milestone." />
    </TerminalShell>
  );
}
