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
import {
  ApiError,
  fetchOptionsPaperLedger,
  fetchOptionsPortfolioExecution,
  tickOptionsPaperLedger,
  type LedgerSnapshot,
  type OptionsPortfolioExecution,
  type OptionsStyle
} from "@/lib/api";

const DEFAULT_CAPITAL = 10000;
const FETCH_DAYS = 1825;
const TRADE_LIMIT = 200;

const STYLES: { label: string; value: OptionsStyle }[] = [
  { label: "0DTE", value: "zero_dte" },
  { label: "Weekly", value: "weekly" }
];

function Stat({ label, value, tone }: Readonly<{ label: string; value: string; tone?: "up" | "down" }>) {
  const toneClass = tone === "up" ? "text-emerald-300" : tone === "down" ? "text-terminal-danger" : "";
  return (
    <div className="rounded-xl border border-terminal-border bg-black/20 p-4">
      <p className="text-xs uppercase tracking-wide text-terminal-muted">{label}</p>
      <p className={`mt-1 font-mono text-lg ${toneClass}`}>{value}</p>
    </div>
  );
}

function StyleSelector({
  value,
  onChange,
  disabled
}: Readonly<{ value: OptionsStyle; onChange: (style: OptionsStyle) => void; disabled: boolean }>) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs uppercase tracking-wide text-terminal-muted">Style</span>
      {STYLES.map((option) => (
        <button
          className={`rounded-md border px-3 py-1 text-xs transition disabled:opacity-50 ${
            option.value === value
              ? "border-terminal-accent bg-terminal-accent/10 text-terminal-accent"
              : "border-terminal-border bg-black/20 text-terminal-muted hover:border-terminal-accent hover:text-terminal-accent"
          }`}
          disabled={disabled}
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function OptionsPortfolioWorkspace() {
  const [style, setStyle] = useState<OptionsStyle>("zero_dte");
  const [data, setData] = useState<OptionsPortfolioExecution | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (targetStyle: OptionsStyle, force = false) => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await fetchOptionsPortfolioExecution(targetStyle, DEFAULT_CAPITAL, FETCH_DAYS, { force })
      );
    } catch (caught) {
      setData(null);
      setError(
        caught instanceof ApiError ? caught.message : "Unexpected error running the options backtest."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(style, false);
  }, [style, load]);

  const totalReturn = data ? Number(data.total_return) : 0;
  const totalPnl = data ? Number(data.total_pnl) : 0;

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">
              Options Portfolio
            </p>
            <h2 className="mt-3 text-2xl font-semibold">$10,000 0DTE / Weekly Options Track Record</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">
              A dedicated $10,000 capital base, separate from the stock portfolio, deployed into
              0DTE and weekly calls/puts across SPY, QQQ, IWM (true same-day expiries) and AAPL,
              MSFT, NVDA, TSLA, AMD, META, GOOGL (weekly). The AI master decision picks direction —
              calls on BUY, puts on SELL.
            </p>
          </div>
          <button
            className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 text-sm transition hover:border-terminal-accent hover:text-terminal-accent disabled:opacity-50"
            disabled={loading}
            onClick={() => void load(style, true)}
            type="button"
          >
            {loading ? "Executing…" : "Re-run"}
          </button>
        </div>
        <div className="mt-4">
          <StyleSelector disabled={loading} onChange={setStyle} value={style} />
        </div>
      </section>

      {data ? (
        <div className="rounded-xl border border-terminal-warning/40 bg-terminal-warning/5 p-4 text-xs leading-5 text-terminal-muted">
          <span className="font-semibold text-terminal-warning">⚠ Modeled backtest.</span>{" "}
          {data.pricing_note}
        </div>
      ) : null}

      {data && data.errors.length ? (
        <ErrorNote
          message={`${data.errors.length} of ${data.errors.length + data.symbol_count} symbol(s) unavailable from the market-data provider: ${data.errors
            .map((item) => `${item.symbol} (${item.detail})`)
            .join("; ")}`}
        />
      ) : null}

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Running the modeled options strategy across the universe…" /> : null}

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
              <Stat label="Success rate" value={formatPercent(data.success_rate)} />
              <Stat
                label="Closed trades"
                value={`${data.winning_trades}W / ${data.losing_trades}L`}
              />
              <Stat label="Total trades" value={formatNumber(data.trade_count)} />
              <Stat label="Symbols" value={formatNumber(data.symbol_count)} />
            </div>
            <div className="mt-4">
              <Sparkline values={data.equity_curve.map((point) => Number(point.equity))} />
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <h3 className="text-lg font-semibold">Sleeves by symbol</h3>
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4 text-right">Allocated</th>
                    <th className="py-2 pr-4 text-right">Final equity</th>
                    <th className="py-2 pr-4 text-right">Return</th>
                    <th className="py-2 pr-4 text-right">Trades</th>
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
                        <td className="py-2 pr-4 text-right">{formatCurrency(sleeve.allocated)}</td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(sleeve.final_equity)}</td>
                        <td
                          className={`py-2 pr-4 text-right ${
                            ret >= 0 ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {formatSignedPercent(ret)}
                        </td>
                        <td className="py-2 pr-4 text-right">{sleeve.trade_count}</td>
                        <td className="py-2 pr-4 text-right">{formatPercent(sleeve.win_rate)}</td>
                        <td className="py-2 text-right">
                          {sleeve.next_signal ? <ActionBadge action={sleeve.next_signal.action} /> : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-lg font-semibold">Modeled trade blotter</h3>
              <p className="text-xs text-terminal-muted">
                {data.trades.length === 0
                  ? "No trades in this window"
                  : `Showing latest ${Math.min(TRADE_LIMIT, data.trades.length)} of ${formatNumber(data.trades.length)}`}
              </p>
            </div>
            {data.trades.length ? (
              <div className="mt-4 max-h-[32rem] overflow-auto">
                <table className="w-full min-w-[900px] text-left text-sm">
                  <thead className="sticky top-0 bg-terminal-panel text-xs uppercase tracking-wide text-terminal-muted">
                    <tr>
                      <th className="py-2 pr-4">Symbol</th>
                      <th className="py-2 pr-4">Side</th>
                      <th className="py-2 pr-4 text-right">Strike</th>
                      <th className="py-2 pr-4">Entry</th>
                      <th className="py-2 pr-4">Exit</th>
                      <th className="py-2 pr-4 text-right">Contracts</th>
                      <th className="py-2 text-right">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {[...data.trades]
                      .reverse()
                      .slice(0, TRADE_LIMIT)
                      .map((trade, index) => {
                        const pnl = Number(trade.realized_pnl);
                        return (
                          <tr
                            className="border-t border-terminal-border/60"
                            key={`${trade.symbol}-${trade.entry_at}-${index}`}
                          >
                            <td className="py-2 pr-4 font-semibold">{trade.symbol}</td>
                            <td className="py-2 pr-4 uppercase">{trade.option_side}</td>
                            <td className="py-2 pr-4 text-right">{formatCurrency(trade.strike)}</td>
                            <td className="py-2 pr-4">{trade.entry_at}</td>
                            <td className="py-2 pr-4">{trade.exit_at}</td>
                            <td className="py-2 pr-4 text-right">{trade.contracts}</td>
                            <td
                              className={`py-2 text-right ${
                                pnl >= 0 ? "text-emerald-300" : "text-terminal-danger"
                              }`}
                            >
                              {formatCurrency(pnl)}
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
        <EmptyState message="No options backtest could be produced." />
      ) : null}

      <LivePaperLedger />
    </div>
  );
}

function LivePaperLedger() {
  const [snapshot, setSnapshot] = useState<LedgerSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [ticking, setTicking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSnapshot(await fetchOptionsPaperLedger());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unexpected error loading the ledger.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runTick = async () => {
    setTicking(true);
    setError(null);
    try {
      setSnapshot(await tickOptionsPaperLedger("weekly", 8));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unexpected error running the ledger tick.");
    } finally {
      setTicking(false);
    }
  };

  return (
    <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">
            Live paper ledger · real quotes, no modeling
          </p>
          <h3 className="mt-2 text-lg font-semibold">Forward-Looking Track Record</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-terminal-muted">
            Positions here are opened and marked at real quoted prices from the live options
            chain — never a Black-Scholes estimate. This track record only grows forward from
            whenever it was first run; there is no way to backfill it.
          </p>
        </div>
        <button
          className="rounded-lg border border-terminal-accent bg-terminal-accent/10 px-4 py-2 text-sm font-medium text-terminal-accent transition hover:bg-terminal-accent/20 disabled:opacity-50"
          disabled={ticking}
          onClick={() => void runTick()}
          type="button"
        >
          {ticking ? "Running…" : "Run ledger tick"}
        </button>
      </div>

      {error ? (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      ) : null}
      {loading ? (
        <div className="mt-4">
          <LoadingBlock label="Loading the live paper ledger…" />
        </div>
      ) : null}

      {snapshot ? (
        <>
          <div className="mt-4 rounded-lg border border-terminal-border bg-black/20 p-3 text-xs text-terminal-muted">
            {snapshot.note}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Stat label="Open positions" value={formatNumber(snapshot.open_positions.length)} />
            <Stat label="Closed positions" value={formatNumber(snapshot.closed_positions.length)} />
            <Stat
              label="Realized P&L"
              value={formatCurrency(snapshot.realized_pnl_total)}
              tone={Number(snapshot.realized_pnl_total) >= 0 ? "up" : "down"}
            />
          </div>

          <div className="mt-4 overflow-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                <tr>
                  <th className="py-2 pr-4">Symbol</th>
                  <th className="py-2 pr-4">Side</th>
                  <th className="py-2 pr-4 text-right">Strike</th>
                  <th className="py-2 pr-4">Expiration</th>
                  <th className="py-2 pr-4 text-right">Entry premium</th>
                  <th className="py-2 pr-4 text-right">Mark</th>
                  <th className="py-2 text-right">Unrealized P&L</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {snapshot.open_positions.length === 0 ? (
                  <tr>
                    <td className="py-3 text-terminal-muted" colSpan={7}>
                      No open positions. Click &quot;Run ledger tick&quot; to check for new signals.
                    </td>
                  </tr>
                ) : (
                  snapshot.open_positions.map((position) => {
                    const unrealized = position.unrealized_pnl ? Number(position.unrealized_pnl) : null;
                    return (
                      <tr
                        className="border-t border-terminal-border/60"
                        key={position.contract_symbol}
                      >
                        <td className="py-2 pr-4 font-semibold">{position.symbol}</td>
                        <td className="py-2 pr-4 uppercase">{position.option_side}</td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(position.strike)}</td>
                        <td className="py-2 pr-4">{position.expiration}</td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(position.entry_premium)}</td>
                        <td className="py-2 pr-4 text-right">
                          {position.mark_premium ? formatCurrency(position.mark_premium) : "—"}
                        </td>
                        <td
                          className={`py-2 text-right ${
                            unrealized === null
                              ? "text-terminal-muted"
                              : unrealized >= 0
                                ? "text-emerald-300"
                                : "text-terminal-danger"
                          }`}
                        >
                          {unrealized === null ? "—" : formatCurrency(unrealized)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {snapshot.closed_positions.length ? (
            <div className="mt-6 overflow-auto">
              <h4 className="text-sm font-semibold">Closed (real settlement)</h4>
              <table className="mt-2 w-full min-w-[720px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4">Side</th>
                    <th className="py-2 pr-4 text-right">Entry</th>
                    <th className="py-2 pr-4 text-right">Exit</th>
                    <th className="py-2 text-right">Realized P&L</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {snapshot.closed_positions.map((position) => {
                    const pnl = Number(position.realized_pnl);
                    return (
                      <tr
                        className="border-t border-terminal-border/60"
                        key={`${position.contract_symbol}-${position.closed_at}`}
                      >
                        <td className="py-2 pr-4 font-semibold">{position.symbol}</td>
                        <td className="py-2 pr-4 uppercase">{position.option_side}</td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(position.entry_premium)}</td>
                        <td className="py-2 pr-4 text-right">{formatCurrency(position.exit_premium)}</td>
                        <td
                          className={`py-2 text-right ${
                            pnl >= 0 ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {formatCurrency(pnl)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
