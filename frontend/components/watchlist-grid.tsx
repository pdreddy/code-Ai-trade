"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState } from "@/components/page-panel";
import { ActionBadge, ErrorNote, LoadingBlock, formatCurrency, formatSignedPercent } from "@/components/research";
import { ApiError, fetchWatchlist, type Watchlist } from "@/lib/api";

export function WatchlistGrid() {
  const [data, setData] = useState<Watchlist | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchWatchlist({ force }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unexpected error loading quotes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-terminal-muted">
          {data ? `Updated ${new Date(data.generated_at).toLocaleTimeString()}` : "Live quotes and AI signals"}
        </p>
        <button
          className="rounded-md border border-terminal-border bg-black/20 px-3 py-1 text-xs transition hover:border-terminal-accent hover:text-terminal-accent disabled:opacity-50"
          disabled={loading}
          onClick={() => void load(true)}
          type="button"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <LoadingBlock label="Loading real quotes and AI signals…" /> : null}

      {data && data.errors.length ? (
        <ErrorNote
          message={`${data.errors.length} symbol(s) unavailable: ${data.errors
            .map((item) => item.symbol)
            .join(", ")}`}
        />
      ) : null}

      {data && data.quotes.length ? (
        <div className="grid gap-3 md:grid-cols-3">
          {data.quotes.map((quote) => {
            const change = quote.change_pct !== null ? Number(quote.change_pct) : null;
            return (
              <Link
                className="rounded-xl border border-terminal-border bg-black/20 p-4 transition hover:border-terminal-accent"
                href={`/stocks?symbol=${quote.symbol}`}
                key={quote.symbol}
              >
                <div className="flex items-center justify-between">
                  <p className="font-mono font-semibold">{quote.symbol}</p>
                  <ActionBadge action={quote.action} />
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <p className="font-mono text-lg">{formatCurrency(quote.last_close)}</p>
                  {change !== null ? (
                    <p
                      className={`font-mono text-sm ${
                        change >= 0 ? "text-emerald-300" : "text-terminal-danger"
                      }`}
                    >
                      {formatSignedPercent(change)}
                    </p>
                  ) : null}
                </div>
                <p className="mt-2 text-xs text-terminal-muted">Open live research workspace →</p>
              </Link>
            );
          })}
        </div>
      ) : null}

      {!loading && !error && data && data.quotes.length === 0 ? (
        <EmptyState message="No quotes could be loaded for this universe." />
      ) : null}
    </div>
  );
}
