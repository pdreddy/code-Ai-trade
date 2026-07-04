"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EmptyState } from "@/components/page-panel";
import {
  ActionBadge,
  ErrorNote,
  LoadingBlock,
  RangeSelector,
  Sparkline,
  SymbolBar,
  formatCurrency,
  formatNumber,
  formatPercent,
  formatSignedPercent
} from "@/components/research";
import { ApiError, fetchBacktest, type Backtest } from "@/lib/api";

const DEFAULT_SYMBOL = "AAPL";
const DEFAULT_RANGE_DAYS = 1825; // 5 years
const TRADE_LIMIT = 100;

export function BacktestWorkspace() {
  const searchParams = useSearchParams();
  const initialSymbol = (searchParams.get("symbol") ?? DEFAULT_SYMBOL).toUpperCase();

  const [symbol, setSymbol] = useState(initialSymbol);
  const [rangeDays, setRangeDays] = useState(DEFAULT_RANGE_DAYS);
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (target: string, days: number) => {
    setLoading(true);
    setError(null);
    try {
      setBacktest(await fetchBacktest(target, days));
    } catch (caught) {
      setBacktest(null);
      setError(caught instanceof ApiError ? caught.message : "Unexpected error running backtest.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(symbol, rangeDays);
  }, [symbol, rangeDays, load]);

  const metrics = backtest?.metrics;
  const totalReturn = metrics ? Number(metrics.total_return) : 0;
  const equityValues = backtest?.equity_curve.map((point) => Number(point.equity)) ?? [];

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">Backtests</p>
        <h2 className="mt-3 text-2xl font-semibold">Proven System Track Record</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">
          The AI master decision is generated for every historical bar and executed by the
          event-driven backtester (signal-on-close, fill-next-open). Below is every trade the
          system took, its win/success rate, risk-adjusted metrics, and the forward-looking
          signal for the next session.
        </p>
        <div className="mt-4 flex flex-col gap-4">
          <SymbolBar loading={loading} onSubmit={setSymbol} symbol={symbol} />
          <RangeSelector disabled={loading} onChange={setRangeDays} value={rangeDays} />
        </div>
      </section>

      {error ? <ErrorNote message={error} /> : null}

      {loading ? (
        <LoadingBlock label={`Executing ${symbol} strategy across the selected history…`} />
      ) : null}

      {backtest && metrics ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">
                  Success rate (closed trades)
                </p>
                <p className="mt-1 font-mono text-4xl font-semibold text-terminal-accent">
                  {formatPercent(metrics.success_rate)}
                </p>
                <p className="mt-1 text-xs text-terminal-muted">
                  {metrics.winning_trades}W / {metrics.losing_trades}L across {metrics.trade_count}{" "}
                  trades · {backtest.start.slice(0, 10)} → {backtest.end.slice(0, 10)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">
                  Total return
                </p>
                <p
                  className={`mt-1 font-mono text-2xl ${
                    totalReturn >= 0 ? "text-emerald-300" : "text-terminal-danger"
                  }`}
                >
                  {formatSignedPercent(totalReturn)}
                </p>
                <p className="mt-1 text-xs text-terminal-muted">
                  {formatCurrency(backtest.initial_capital)} → {formatCurrency(backtest.final_equity)}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Sparkline values={equityValues} />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Stat label="CAGR" value={formatPercent(metrics.cagr)} />
              <Stat label="Max drawdown" value={formatPercent(metrics.max_drawdown)} />
              <Stat label="Sharpe" value={Number(metrics.sharpe).toFixed(2)} />
              <Stat label="Sortino" value={Number(metrics.sortino).toFixed(2)} />
              <Stat label="Profit factor" value={Number(metrics.profit_factor).toFixed(2)} />
              <Stat label="Exposure" value={formatPercent(metrics.exposure)} />
            </div>
          </section>

          {backtest.next_signal ? (
            <section className="rounded-2xl border border-terminal-accent/40 bg-terminal-accent/5 p-6 shadow-2xl">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">
                    Next signal · forward-looking
                  </p>
                  <h3 className="mt-2 text-xl font-semibold">
                    What the system says to do next on {backtest.symbol}
                  </h3>
                </div>
                <ActionBadge action={backtest.next_signal.action} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Confidence" value={formatPercent(backtest.next_signal.confidence)} />
                <Stat label="Risk score" value={formatPercent(backtest.next_signal.risk_score)} />
                <Stat
                  label="Stop loss"
                  value={
                    backtest.next_signal.stop_loss
                      ? formatCurrency(backtest.next_signal.stop_loss)
                      : "—"
                  }
                />
                <Stat
                  label="Take profit"
                  value={
                    backtest.next_signal.take_profit
                      ? formatCurrency(backtest.next_signal.take_profit)
                      : "—"
                  }
                />
              </div>
              <p className="mt-4 text-sm leading-6 text-terminal-muted">
                {backtest.next_signal.explanation}
              </p>
            </section>
          ) : null}

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-lg font-semibold">Executed trades</h3>
              <p className="text-xs text-terminal-muted">
                {backtest.trades.length === 0
                  ? "No round-trip trades in this window"
                  : `Showing latest ${Math.min(TRADE_LIMIT, backtest.trades.length)} of ${formatNumber(backtest.trades.length)}`}
              </p>
            </div>
            {backtest.trades.length ? (
              <div className="mt-4 max-h-96 overflow-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="sticky top-0 bg-terminal-panel text-xs uppercase tracking-wide text-terminal-muted">
                    <tr>
                      <th className="py-2 pr-4">Entry</th>
                      <th className="py-2 pr-4 text-right">Entry px</th>
                      <th className="py-2 pr-4">Exit</th>
                      <th className="py-2 pr-4 text-right">Exit px</th>
                      <th className="py-2 pr-4 text-right">Qty</th>
                      <th className="py-2 text-right">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {[...backtest.trades]
                      .reverse()
                      .slice(0, TRADE_LIMIT)
                      .map((trade, index) => {
                        const pnl = trade.realized_pnl ? Number(trade.realized_pnl) : null;
                        return (
                          <tr
                            className="border-t border-terminal-border/60"
                            key={`${trade.entry_at}-${index}`}
                          >
                            <td className="py-2 pr-4">{trade.entry_at.slice(0, 10)}</td>
                            <td className="py-2 pr-4 text-right">{formatCurrency(trade.entry_price)}</td>
                            <td className="py-2 pr-4">{trade.exit_at ? trade.exit_at.slice(0, 10) : "open"}</td>
                            <td className="py-2 pr-4 text-right">
                              {trade.exit_price ? formatCurrency(trade.exit_price) : "—"}
                            </td>
                            <td className="py-2 pr-4 text-right">{Number(trade.quantity).toFixed(2)}</td>
                            <td
                              className={`py-2 text-right ${
                                pnl === null
                                  ? "text-terminal-muted"
                                  : pnl >= 0
                                    ? "text-emerald-300"
                                    : "text-terminal-danger"
                              }`}
                            >
                              {pnl === null ? "—" : formatCurrency(pnl)}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        </>
      ) : null}

      {!loading && !error && !backtest ? (
        <EmptyState message="No backtest could be produced for this symbol." />
      ) : null}
    </div>
  );
}

function Stat({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="rounded-xl border border-terminal-border bg-black/20 p-4">
      <p className="text-xs uppercase tracking-wide text-terminal-muted">{label}</p>
      <p className="mt-1 font-mono text-lg">{value}</p>
    </div>
  );
}
