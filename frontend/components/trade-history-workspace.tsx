"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/page-panel";
import { ErrorNote, LoadingBlock, formatCurrency, formatNumber } from "@/components/research";
import {
  ApiError,
  fetchOptionsPortfolioExecution,
  fetchPortfolioExecution,
  type OptionsPortfolioExecution,
  type OptionsStyle,
  type PortfolioExecution
} from "@/lib/api";

const STOCK_CAPITAL = 10000;
const STOCK_DAYS = 1095;
const OPTIONS_CAPITAL = 10000;
const OPTIONS_DAYS = 1825;

type UnifiedTrade = {
  kind: "stock" | "option";
  symbol: string;
  detail: string;
  entryAt: string;
  exitAt: string | null;
  realizedPnl: number | null;
  entryReason: string;
  exitReason: string | null;
};

type DayGroup = {
  day: string;
  trades: UnifiedTrade[];
  pnl: number;
  winning: number;
  losing: number;
};

function groupByDay(trades: UnifiedTrade[]): DayGroup[] {
  const byDay = new Map<string, UnifiedTrade[]>();
  for (const trade of trades) {
    const day = (trade.exitAt ?? trade.entryAt).slice(0, 10);
    const bucket = byDay.get(day) ?? [];
    bucket.push(trade);
    byDay.set(day, bucket);
  }
  return Array.from(byDay.entries())
    .map(([day, dayTrades]) => {
      const pnls = dayTrades.map((t) => t.realizedPnl).filter((v): v is number => v !== null);
      return {
        day,
        trades: dayTrades,
        pnl: pnls.reduce((sum, v) => sum + v, 0),
        winning: pnls.filter((v) => v > 0).length,
        losing: pnls.filter((v) => v < 0).length
      };
    })
    .sort((a, b) => (a.day < b.day ? 1 : -1));
}

function Stat({ label, value, tone }: Readonly<{ label: string; value: string; tone?: "up" | "down" }>) {
  const toneClass = tone === "up" ? "text-emerald-300" : tone === "down" ? "text-terminal-danger" : "";
  return (
    <div className="rounded-xl border border-terminal-border bg-black/20 p-4">
      <p className="text-xs uppercase tracking-wide text-terminal-muted">{label}</p>
      <p className={`mt-1 font-mono text-lg ${toneClass}`}>{value}</p>
    </div>
  );
}

export function TradeHistoryWorkspace() {
  const [optionsStyle, setOptionsStyle] = useState<OptionsStyle>("weekly");
  const [trades, setTrades] = useState<UnifiedTrade[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState<string | null>(null);

  const load = useCallback(async (style: OptionsStyle, force = false) => {
    setLoading(true);
    setError(null);
    setPartial(null);

    let stock: PortfolioExecution | null = null;
    let stockError: string | null = null;
    try {
      stock = await fetchPortfolioExecution(STOCK_CAPITAL, STOCK_DAYS, "master", { force });
    } catch (caught) {
      stockError = caught instanceof ApiError ? caught.message : "Unexpected error.";
    }

    let options: OptionsPortfolioExecution | null = null;
    let optionsError: string | null = null;
    try {
      options = await fetchOptionsPortfolioExecution(style, OPTIONS_CAPITAL, OPTIONS_DAYS, {
        force
      });
    } catch (caught) {
      optionsError = caught instanceof ApiError ? caught.message : "Unexpected error.";
    }

    if (!stock && !options) {
      setError(stockError ?? optionsError ?? "Unexpected error loading trade history.");
      setTrades(null);
      setLoading(false);
      return;
    }

    const unified: UnifiedTrade[] = [];
    if (stock) {
      for (const trade of stock.trades) {
        unified.push({
          kind: "stock",
          symbol: trade.symbol,
          detail: "LONG",
          entryAt: trade.entry_at,
          exitAt: trade.exit_at,
          realizedPnl: trade.realized_pnl !== null ? Number(trade.realized_pnl) : null,
          entryReason: trade.entry_reason,
          exitReason: trade.exit_reason
        });
      }
    }
    if (options) {
      for (const trade of options.trades) {
        unified.push({
          kind: "option",
          symbol: trade.symbol,
          detail: trade.option_side.toUpperCase(),
          entryAt: trade.entry_at,
          exitAt: trade.exit_at,
          realizedPnl: Number(trade.realized_pnl),
          entryReason: trade.entry_reason,
          exitReason: trade.exit_reason
        });
      }
    }

    if (!stock || !options) {
      setPartial(
        !stock
          ? "Stock trade history is unavailable right now — showing options trades only."
          : "Options trade history is unavailable right now — showing stock trades only."
      );
    }

    setTrades(unified);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load(optionsStyle, false);
  }, [optionsStyle, load]);

  const groups = useMemo(() => (trades ? groupByDay(trades) : []), [trades]);
  const totalPnl = trades
    ? trades.reduce((sum, t) => sum + (t.realizedPnl ?? 0), 0)
    : 0;
  const winning = trades ? trades.filter((t) => (t.realizedPnl ?? 0) > 0).length : 0;
  const losing = trades ? trades.filter((t) => (t.realizedPnl ?? 0) < 0).length : 0;

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">Trade History</p>
            <h2 className="mt-3 text-2xl font-semibold">Every Executed Trade, Day By Day</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">
              Combines the stock portfolio&apos;s executed round-trips with the options portfolio&apos;s
              modeled trades into one day-grouped history. Each day shows every fill that closed
              that day and the day&apos;s net P&amp;L.
            </p>
          </div>
          <button
            className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 text-sm transition hover:border-terminal-accent hover:text-terminal-accent disabled:opacity-50"
            disabled={loading}
            onClick={() => void load(optionsStyle, true)}
            type="button"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-terminal-muted">Options style</span>
          {(["zero_dte", "weekly"] as const).map((style) => (
            <button
              className={`rounded-md border px-3 py-1 text-xs transition disabled:opacity-50 ${
                style === optionsStyle
                  ? "border-terminal-accent bg-terminal-accent/10 text-terminal-accent"
                  : "border-terminal-border bg-black/20 text-terminal-muted hover:border-terminal-accent hover:text-terminal-accent"
              }`}
              disabled={loading}
              key={style}
              onClick={() => setOptionsStyle(style)}
              type="button"
            >
              {style === "zero_dte" ? "0DTE" : "Weekly"}
            </button>
          ))}
        </div>
      </section>

      {error ? <ErrorNote message={error} /> : null}
      {partial ? <ErrorNote message={partial} /> : null}
      {loading && !trades ? <LoadingBlock label="Loading stock and options trade history…" /> : null}

      {trades ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total trades" value={formatNumber(trades.length)} />
              <Stat
                label="Total P&L"
                value={formatCurrency(totalPnl)}
                tone={totalPnl >= 0 ? "up" : "down"}
              />
              <Stat label="Winners" value={formatNumber(winning)} tone="up" />
              <Stat label="Losers" value={formatNumber(losing)} tone="down" />
            </div>
          </section>

          {groups.length ? (
            <div className="flex flex-col gap-4">
              {groups.map((group) => (
                <section
                  className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl"
                  key={group.day}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 className="font-mono text-lg font-semibold">{group.day}</h3>
                    <p className="text-xs text-terminal-muted">
                      {group.trades.length} trade(s) · {group.winning}W / {group.losing}L
                    </p>
                    <p
                      className={`font-mono text-sm ${
                        group.pnl >= 0 ? "text-emerald-300" : "text-terminal-danger"
                      }`}
                    >
                      {formatCurrency(group.pnl)}
                    </p>
                  </div>
                  <div className="mt-3 overflow-auto">
                    <table className="w-full min-w-[900px] text-left text-sm">
                      <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                        <tr>
                          <th className="py-2 pr-4">Symbol</th>
                          <th className="py-2 pr-4">Kind</th>
                          <th className="py-2 pr-4">Entry</th>
                          <th className="py-2 pr-4">Exit</th>
                          <th className="py-2 pr-4 text-right">P&L</th>
                          <th className="py-2">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono">
                        {group.trades.map((trade, index) => {
                          const reason = trade.exitReason ?? trade.entryReason;
                          const fullReason = `Entry: ${trade.entryReason}${
                            trade.exitReason ? ` · Exit: ${trade.exitReason}` : ""
                          }`;
                          return (
                            <tr
                              className="border-t border-terminal-border/60"
                              key={`${trade.symbol}-${trade.entryAt}-${index}`}
                            >
                              <td className="py-2 pr-4 font-semibold">{trade.symbol}</td>
                              <td className="py-2 pr-4">
                                <span
                                  className={`rounded-full border px-2 py-0.5 text-xs uppercase ${
                                    trade.kind === "option"
                                      ? "border-terminal-accent/40 bg-terminal-accent/10 text-terminal-accent"
                                      : "border-terminal-border bg-black/20 text-terminal-muted"
                                  }`}
                                >
                                  {trade.kind === "option" ? `option · ${trade.detail}` : "stock · long"}
                                </span>
                              </td>
                              <td className="py-2 pr-4">{trade.entryAt.slice(0, 10)}</td>
                              <td className="py-2 pr-4">
                                {trade.exitAt ? trade.exitAt.slice(0, 10) : "open"}
                              </td>
                              <td
                                className={`py-2 pr-4 text-right ${
                                  trade.realizedPnl === null
                                    ? "text-terminal-muted"
                                    : trade.realizedPnl >= 0
                                      ? "text-emerald-300"
                                      : "text-terminal-danger"
                                }`}
                              >
                                {trade.realizedPnl === null ? "—" : formatCurrency(trade.realizedPnl)}
                              </td>
                              <td className="py-2 text-xs text-terminal-muted" title={fullReason}>
                                {reason.length > 44 ? `${reason.slice(0, 43)}…` : reason}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <EmptyState message="No executed trades in either portfolio yet." />
          )}
        </>
      ) : null}

      {!loading && !error && !trades ? (
        <EmptyState message="No trade history could be produced." />
      ) : null}
    </div>
  );
}
