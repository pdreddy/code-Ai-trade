"use client";

import { useCallback, useEffect, useState } from "react";
import { EmptyState } from "@/components/page-panel";
import {
  ActionBadge,
  ErrorNote,
  LoadingBlock,
  Sparkline,
  formatCurrency,
  formatNumber,
  formatPercent,
  formatSignedPercent
} from "@/components/research";
import { ApiError, fetchPortfolioExecution, type PortfolioExecution } from "@/lib/api";

// Three years balances a meaningful trade history against the cost of running the
// whole universe on demand; the single-symbol Backtests tab covers deeper history.
const DEFAULT_DAYS = 1095;
const DEFAULT_CAPITAL = 10000;

type PortfolioState = {
  data: PortfolioExecution | null;
  loading: boolean;
  error: string | null;
  reload: (force?: boolean) => void;
};

function usePortfolio(days = DEFAULT_DAYS): PortfolioState {
  const [data, setData] = useState<PortfolioExecution | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (force = false) => {
      setLoading(true);
      setError(null);
      try {
        setData(await fetchPortfolioExecution(DEFAULT_CAPITAL, days, { force }));
      } catch (caught) {
        setData(null);
        setError(
          caught instanceof ApiError ? caught.message : "Unexpected error executing the portfolio."
        );
      } finally {
        setLoading(false);
      }
    },
    [days]
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  return { data, loading, error, reload: (force = true) => void load(force) };
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

function WorkspaceHeader({
  eyebrow,
  title,
  description,
  state
}: Readonly<{ eyebrow: string; title: string; description: string; state: PortfolioState }>) {
  return (
    <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">{eyebrow}</p>
          <h2 className="mt-3 text-2xl font-semibold">{title}</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">{description}</p>
        </div>
        <button
          className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 text-sm transition hover:border-terminal-accent hover:text-terminal-accent disabled:opacity-50"
          disabled={state.loading}
          onClick={() => state.reload(true)}
          type="button"
        >
          {state.loading ? "Executing…" : "Re-run"}
        </button>
      </div>
      {state.data ? (
        <p className="mt-3 text-xs text-terminal-muted">
          {formatCurrency(state.data.initial_capital)} deployed across {state.data.symbol_count}{" "}
          symbols · generated {state.data.generated_at.slice(0, 10)}
          {state.data.errors.length
            ? ` · ${state.data.errors.length} symbol(s) unavailable: ${state.data.errors
                .map((item) => item.symbol)
                .join(", ")}`
            : ""}
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Portfolio monitor
// ---------------------------------------------------------------------------

export function PortfolioMonitor() {
  const state = usePortfolio();
  const { data, loading, error } = state;
  const totalReturn = data ? Number(data.total_return) : 0;
  const totalPnl = data ? Number(data.total_pnl) : 0;

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        description="The AI master decision is executed on every symbol in the research universe from one shared $10,000 base (signal-on-close, fill-next-open). Below is the live portfolio: total equity, cash-versus-invested split, open holdings, and the upcoming planned trades from each symbol's forward-looking signal."
        eyebrow="Portfolio"
        state={state}
        title="Portfolio And Risk Monitor"
      />

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Executing the strategy across the universe…" /> : null}

      {data ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total equity" value={formatCurrency(data.total_equity)} />
              <Stat
                label="Total P&L"
                value={formatCurrency(totalPnl)}
                tone={totalPnl >= 0 ? "up" : "down"}
              />
              <Stat
                label="Total return"
                value={formatSignedPercent(totalReturn)}
                tone={totalReturn >= 0 ? "up" : "down"}
              />
              <Stat label="Max drawdown" value={formatPercent(data.max_drawdown)} />
              <Stat label="Cash" value={formatCurrency(data.cash)} />
              <Stat label="Invested" value={formatCurrency(data.invested)} />
              <Stat label="Success rate" value={formatPercent(data.success_rate)} />
              <Stat
                label="Closed trades"
                value={`${data.winning_trades}W / ${data.losing_trades}L`}
              />
            </div>
            <div className="mt-4">
              <Sparkline values={data.equity_curve.map((point) => Number(point.equity))} />
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <h3 className="text-lg font-semibold">Holdings by symbol</h3>
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4">State</th>
                    <th className="py-2 pr-4 text-right">Allocated</th>
                    <th className="py-2 pr-4 text-right">Value</th>
                    <th className="py-2 pr-4 text-right">Return</th>
                    <th className="py-2 pr-4 text-right">Win rate</th>
                    <th className="py-2 text-right">Next</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.sleeves.map((sleeve) => {
                    const ret = Number(sleeve.return_pct);
                    return (
                      <tr className="border-t border-terminal-border/60" key={sleeve.symbol}>
                        <td className="py-2 pr-4 font-semibold">{sleeve.symbol}</td>
                        <td className="py-2 pr-4">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-xs ${
                              sleeve.holding
                                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                                : "border-terminal-border bg-black/20 text-terminal-muted"
                            }`}
                          >
                            {sleeve.holding ? "invested" : "cash"}
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(sleeve.allocated)}</td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(sleeve.current_value)}</td>
                        <td
                          className={`py-2 pr-4 text-right ${
                            ret >= 0 ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {formatSignedPercent(ret)}
                        </td>
                        <td className="py-2 pr-4 text-right">{formatPercent(sleeve.win_rate)}</td>
                        <td className="py-2 text-right">
                          <ActionBadge action={sleeve.next_signal.action} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <PlannedTrades data={data} />
        </>
      ) : null}

      {!loading && !error && !data ? (
        <EmptyState message="No portfolio execution could be produced." />
      ) : null}
    </div>
  );
}

function PlannedTrades({ data }: Readonly<{ data: PortfolioExecution }>) {
  if (data.planned_trades.length === 0) {
    return (
      <EmptyState message="No actionable next signals — every symbol is currently HOLD." />
    );
  }
  return (
    <section className="rounded-2xl border border-terminal-accent/40 bg-terminal-accent/5 p-6 shadow-2xl">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">
            Upcoming planned trades · forward-looking
          </p>
          <h3 className="mt-2 text-lg font-semibold">What the system plans to do next</h3>
        </div>
        <p className="text-xs text-terminal-muted">{data.planned_trades.length} signal(s)</p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {data.planned_trades.map((plan) => (
          <div
            className="rounded-xl border border-terminal-border bg-black/20 p-4"
            key={plan.symbol}
          >
            <div className="flex items-center justify-between">
              <p className="font-mono font-semibold">{plan.symbol}</p>
              <ActionBadge action={plan.action} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs text-terminal-muted">
              <span>Last close {formatCurrency(plan.last_close)}</span>
              <span className="text-right">Conf {formatPercent(plan.confidence)}</span>
              <span>Stop {plan.stop_loss ? formatCurrency(plan.stop_loss) : "—"}</span>
              <span className="text-right">
                Target {plan.take_profit ? formatCurrency(plan.take_profit) : "—"}
              </span>
            </div>
            <p className="mt-3 text-xs leading-5 text-terminal-muted">{plan.explanation}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Paper-trade blotter
// ---------------------------------------------------------------------------

const BLOTTER_LIMIT = 200;

export function PaperTradeBlotter() {
  const state = usePortfolio();
  const { data, loading, error } = state;

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        description="Every fill the system executed across the universe from the shared $10,000 base. Each row is a round-trip trade with its entry, exit, size, and realized P&L. Open positions show as still filled with no exit."
        eyebrow="Paper Trades"
        state={state}
        title="Executed Trade Blotter"
      />

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Executing the strategy across the universe…" /> : null}

      {data ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total fills" value={formatNumber(data.trade_count)} />
              <Stat label="Winners" value={formatNumber(data.winning_trades)} tone="up" />
              <Stat label="Losers" value={formatNumber(data.losing_trades)} tone="down" />
              <Stat label="Success rate" value={formatPercent(data.success_rate)} />
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-lg font-semibold">Trade blotter</h3>
              <p className="text-xs text-terminal-muted">
                {data.trades.length === 0
                  ? "No round-trip trades in this window"
                  : `Showing latest ${Math.min(BLOTTER_LIMIT, data.trades.length)} of ${formatNumber(
                      data.trades.length
                    )}`}
              </p>
            </div>
            {data.trades.length ? (
              <div className="mt-4 max-h-[32rem] overflow-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="sticky top-0 bg-terminal-panel text-xs uppercase tracking-wide text-terminal-muted">
                    <tr>
                      <th className="py-2 pr-4">Symbol</th>
                      <th className="py-2 pr-4">Entry</th>
                      <th className="py-2 pr-4 text-right">Entry px</th>
                      <th className="py-2 pr-4">Exit</th>
                      <th className="py-2 pr-4 text-right">Exit px</th>
                      <th className="py-2 pr-4 text-right">Qty</th>
                      <th className="py-2 text-right">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {[...data.trades]
                      .reverse()
                      .slice(0, BLOTTER_LIMIT)
                      .map((trade, index) => {
                        const pnl = trade.realized_pnl ? Number(trade.realized_pnl) : null;
                        return (
                          <tr
                            className="border-t border-terminal-border/60"
                            key={`${trade.symbol}-${trade.entry_at}-${index}`}
                          >
                            <td className="py-2 pr-4 font-semibold">{trade.symbol}</td>
                            <td className="py-2 pr-4">{trade.entry_at.slice(0, 10)}</td>
                            <td className="py-2 pr-4 text-right">{formatCurrency(trade.entry_price)}</td>
                            <td className="py-2 pr-4">
                              {trade.exit_at ? trade.exit_at.slice(0, 10) : "open"}
                            </td>
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

      {!loading && !error && !data ? (
        <EmptyState message="No executed trades could be produced." />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Performance analytics
// ---------------------------------------------------------------------------

export function PerformanceAnalytics() {
  const state = usePortfolio();
  const { data, loading, error } = state;
  const totalReturn = data ? Number(data.total_return) : 0;

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        description="Performance attribution computed from the real executed track record across the universe — blended success rate, returns, drawdown, and the combined equity curve. No fabricated performance data is shown."
        eyebrow="Analytics"
        state={state}
        title="Performance Analytics"
      />

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Executing the strategy across the universe…" /> : null}

      {data ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">
                  Blended success rate (closed trades)
                </p>
                <p className="mt-1 font-mono text-4xl font-semibold text-terminal-accent">
                  {formatPercent(data.success_rate)}
                </p>
                <p className="mt-1 text-xs text-terminal-muted">
                  {data.winning_trades}W / {data.losing_trades}L across {data.trade_count} trades
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
                  {formatCurrency(data.initial_capital)} → {formatCurrency(data.total_equity)}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Sparkline values={data.equity_curve.map((point) => Number(point.equity))} />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total P&L" value={formatCurrency(data.total_pnl)} />
              <Stat label="Max drawdown" value={formatPercent(data.max_drawdown)} />
              <Stat label="Winners" value={formatNumber(data.winning_trades)} />
              <Stat label="Losers" value={formatNumber(data.losing_trades)} />
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <h3 className="text-lg font-semibold">Success rate by symbol</h3>
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4 text-right">Trades</th>
                    <th className="py-2 pr-4 text-right">Win rate</th>
                    <th className="py-2 pr-4 text-right">Realized P&L</th>
                    <th className="py-2 text-right">Return</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.sleeves.map((sleeve) => {
                    const ret = Number(sleeve.return_pct);
                    const pnl = Number(sleeve.realized_pnl);
                    return (
                      <tr className="border-t border-terminal-border/60" key={sleeve.symbol}>
                        <td className="py-2 pr-4 font-semibold">{sleeve.symbol}</td>
                        <td className="py-2 pr-4 text-right">{sleeve.trade_count}</td>
                        <td className="py-2 pr-4 text-right">{formatPercent(sleeve.win_rate)}</td>
                        <td
                          className={`py-2 pr-4 text-right ${
                            pnl >= 0 ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {formatCurrency(pnl)}
                        </td>
                        <td
                          className={`py-2 text-right ${
                            ret >= 0 ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {formatSignedPercent(ret)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}

      {!loading && !error && !data ? (
        <EmptyState message="No analytics could be produced." />
      ) : null}
    </div>
  );
}
