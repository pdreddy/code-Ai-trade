"use client";

import { useEffect, useState } from "react";
import { marketSnapshotGeneratedAt, marketSnapshots, type MarketSnapshot } from "@/lib/generated-market-snapshot";
import { supportedUniverse } from "@/lib/platform-data";

type ApiSnapshot = {
  symbol: string;
  start_date: string;
  end_date: string;
  bars: number;
  last_close: string;
  total_return: string;
  cagr: string;
  max_drawdown: string;
  realized_volatility: string;
};

type ApiResponse = {
  generated_at: string;
  snapshots: ApiSnapshot[];
};

type SnapshotState =
  | { status: "loading"; snapshots: MarketSnapshot[]; generatedAt: string | null; error: null }
  | { status: "ready"; snapshots: MarketSnapshot[]; generatedAt: string | null; error: null }
  | { status: "error"; snapshots: MarketSnapshot[]; generatedAt: string | null; error: string };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function LiveMarketSnapshots() {
  const [state, setState] = useState<SnapshotState>({
    status: marketSnapshots.length > 0 ? "ready" : "loading",
    snapshots: marketSnapshots,
    generatedAt: marketSnapshotGeneratedAt,
    error: null
  });

  useEffect(() => {
    let cancelled = false;
    async function loadSnapshots() {
      try {
        const response = await fetch(`${apiBaseUrl}/market-data/snapshots/five-year`, {
          headers: { Accept: "application/json" }
        });
        if (!response.ok) {
          throw new Error(`provider request failed with HTTP ${response.status}`);
        }
        const payload = (await response.json()) as ApiResponse;
        if (!cancelled) {
          setState({
            status: "ready",
            snapshots: payload.snapshots.map(toMarketSnapshot),
            generatedAt: payload.generated_at,
            error: null
          });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            snapshots: marketSnapshots,
            generatedAt: marketSnapshotGeneratedAt,
            error: error instanceof Error ? error.message : "provider request failed"
          });
        }
      }
    }
    void loadSnapshots();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.snapshots.length > 0) {
    return (
      <>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {state.snapshots.map((snapshot) => (
            <SnapshotCard key={snapshot.symbol} snapshot={snapshot} />
          ))}
        </div>
        <p className="mt-4 text-xs text-terminal-muted">
          Snapshot generated at: {state.generatedAt ?? "runtime provider response"}.
        </p>
      </>
    );
  }

  return (
    <>
      <div className="grid gap-3 md:grid-cols-3">
        {supportedUniverse.map((symbol) => (
          <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={symbol}>
            <p className="font-medium">{symbol}</p>
            <p className="mt-2 text-xs text-terminal-muted">
              {state.status === "loading" ? "Loading real five-year provider data..." : "Provider data unavailable; no synthetic prices shown."}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-terminal-muted">
        {state.status === "error" ? `Market-data API error: ${state.error}` : "Requesting live provider data from the backend."}
      </p>
    </>
  );
}

function SnapshotCard({ snapshot }: Readonly<{ snapshot: MarketSnapshot }>) {
  return (
    <div className="rounded-xl border border-terminal-border bg-black/20 p-4">
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
      <p className="mt-3 text-[11px] text-terminal-muted">{snapshot.startDate} → {snapshot.endDate}</p>
    </div>
  );
}

function toMarketSnapshot(snapshot: ApiSnapshot): MarketSnapshot {
  return {
    symbol: snapshot.symbol,
    startDate: snapshot.start_date,
    endDate: snapshot.end_date,
    bars: snapshot.bars,
    lastClose: snapshot.last_close,
    totalReturn: snapshot.total_return,
    cagr: snapshot.cagr,
    maxDrawdown: snapshot.max_drawdown,
    realizedVolatility: snapshot.realized_volatility
  };
}
