"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EmptyState } from "@/components/page-panel";
import {
  ActionBadge,
  ErrorNote,
  LoadingBlock,
  SymbolBar,
  formatCurrency,
  formatNumber,
  formatPercent
} from "@/components/research";
import {
  ApiError,
  fetchOptionsResearch,
  type OptionContract,
  type OptionsResearch,
  type PlannedOptionTrade
} from "@/lib/api";

// True same-day (0DTE) expiries are only reliably listed on broad index ETFs;
// most single stocks only list Friday weeklies. Default to SPY so 0DTE (the
// default horizon below) actually has real contracts to show.
const DEFAULT_SYMBOL = "SPY";
const ZERO_DTE_SYMBOLS = new Set(["SPY", "QQQ", "IWM"]);

// 0DTE isolates same-day expiries; the weekly horizon (8 calendar days) captures the
// front weekly expiry as well.
const HORIZONS = [
  { label: "0DTE", dte: 0 },
  { label: "Weekly", dte: 8 }
] as const;

export function OptionsWorkspace() {
  const searchParams = useSearchParams();
  const initialSymbol = (searchParams.get("symbol") ?? DEFAULT_SYMBOL).toUpperCase();

  const [symbol, setSymbol] = useState(initialSymbol);
  const [maxDte, setMaxDte] = useState<number>(0);
  const [data, setData] = useState<OptionsResearch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (target: string, dte: number) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchOptionsResearch(target, dte));
    } catch (caught) {
      setData(null);
      setError(
        caught instanceof ApiError ? caught.message : "Unexpected error loading the option chain."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(symbol, maxDte);
  }, [symbol, maxDte, load]);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">Options</p>
        <h2 className="mt-3 text-2xl font-semibold">0DTE & Weekly Options Desk</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">
          Real option chains filtered to the near-term expiries that matter for 0DTE and weekly
          trading. Contracts are ranked by unusual activity (today&apos;s volume versus standing
          open interest), and the AI master decision proposes upcoming planned option trades —
          calls when the model is bullish, puts when bearish.
        </p>
        <div className="mt-4 flex flex-col gap-4">
          <SymbolBar loading={loading} onSubmit={setSymbol} symbol={symbol} />
          <div className="flex flex-wrap gap-2">
            {HORIZONS.map((horizon) => (
              <button
                className={`rounded-lg border px-4 py-2 text-sm transition ${
                  maxDte === horizon.dte
                    ? "border-terminal-accent bg-terminal-accent/10 text-terminal-accent"
                    : "border-terminal-border bg-black/20 hover:border-terminal-accent"
                }`}
                disabled={loading}
                key={horizon.label}
                onClick={() => setMaxDte(horizon.dte)}
                type="button"
              >
                {horizon.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label={`Loading ${symbol} ${maxDte === 0 ? "0DTE" : "weekly"} chain…`} /> : null}

      {data ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">
                  {data.symbol} · underlying
                </p>
                <p className="mt-1 font-mono text-3xl font-semibold">
                  {formatCurrency(data.underlying_price)}
                </p>
                <p className="mt-1 text-xs text-terminal-muted">
                  {data.near_term_count} near-term contracts · {data.zero_dte_count} expiring today
                </p>
                {maxDte === 0 && data.zero_dte_count === 0 && !ZERO_DTE_SYMBOLS.has(symbol) ? (
                  <p className="mt-2 max-w-sm text-xs text-terminal-warning">
                    {symbol} has no same-day-expiration contracts listed today — most single
                    stocks only list Friday weeklies. True 0DTE is most reliable on SPY, QQQ, or
                    IWM.
                  </p>
                ) : null}
              </div>
              <div className="text-right">
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">AI signal</p>
                <div className="mt-2 flex items-center justify-end gap-3">
                  <ActionBadge action={data.signal.action} />
                  <span className="font-mono text-sm text-terminal-muted">
                    {formatPercent(data.signal.confidence)} conf
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-accent/40 bg-terminal-accent/5 p-6 shadow-2xl">
            <div className="flex items-baseline justify-between gap-2">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">
                  Upcoming planned option trades
                </p>
                <h3 className="mt-2 text-lg font-semibold">Today and future trade plans</h3>
              </div>
              <p className="text-xs text-terminal-muted">{data.planned_trades.length} plan(s)</p>
            </div>
            {data.planned_trades.length ? (
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <PlannedTradeGroup label="Today / 0DTE" plans={data.today_planned_trades} />
                <PlannedTradeGroup label="Future / weekly" plans={data.future_planned_trades} />
              </div>
            ) : (
              <p className="mt-4 text-sm text-terminal-muted">
                The AI signal is HOLD, so no directional {maxDte === 0 ? "0DTE" : "weekly"} plan is
                proposed. Unusual activity below is still tracked.
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-lg font-semibold">Unusual options activity</h3>
              <p className="text-xs text-terminal-muted">
                Ranked by volume ÷ open interest{" "}
                {data.unusual_activity.length ? `· top ${data.unusual_activity.length}` : ""}
              </p>
            </div>
            {data.unusual_activity.length ? (
              <div className="mt-4 overflow-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                    <tr>
                      <th className="py-2 pr-4">Type</th>
                      <th className="py-2 pr-4 text-right">Strike</th>
                      <th className="py-2 pr-4 text-right">DTE</th>
                      <th className="py-2 pr-4 text-right">Volume</th>
                      <th className="py-2 pr-4 text-right">OI</th>
                      <th className="py-2 pr-4 text-right">Vol/OI</th>
                      <th className="py-2 pr-4 text-right">Last</th>
                      <th className="py-2 text-right">IV</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {data.unusual_activity.map((item) => (
                      <UnusualRow contract={item.contract} key={item.contract.contract_symbol} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-4 text-sm text-terminal-muted">
                No contracts cleared the liquidity threshold for this horizon.
              </p>
            )}
          </section>
        </>
      ) : null}

      {!loading && !error && !data ? (
        <EmptyState message="No option chain could be loaded for this symbol." />
      ) : null}
    </div>
  );
}

function PlannedTradeGroup({
  label,
  plans
}: Readonly<{ label: string; plans: PlannedOptionTrade[] }>) {
  return (
    <div>
      <p className="mb-2 text-xs uppercase tracking-wide text-terminal-muted">{label}</p>
      {plans.length ? (
        <div className="grid gap-3">
          {plans.map((plan) => (
            <div
              className="rounded-xl border border-terminal-border bg-black/20 p-4"
              key={plan.contract.contract_symbol}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-sm font-semibold">
                  {plan.option_side.toUpperCase()} {formatCurrency(plan.contract.strike)} · {plan.contract.expiration}
                </p>
                <span className="rounded-full border border-terminal-border px-2 py-0.5 font-mono text-xs text-terminal-muted">
                  {plan.contract.days_to_expiry}DTE
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs text-terminal-muted">
                <span>Buy {plan.entry_price ? formatCurrency(plan.entry_price) : "—"}</span>
                <span className="text-right">Bid/Ask {plan.bid ? formatCurrency(plan.bid) : "—"}/{plan.ask ? formatCurrency(plan.ask) : "—"}</span>
                <span>Stop {plan.stop_loss_underlying ? formatCurrency(plan.stop_loss_underlying) : "—"}</span>
                <span className="text-right">Target {plan.take_profit_underlying ? formatCurrency(plan.take_profit_underlying) : "—"}</span>
                <span>Max loss {plan.max_loss ? formatCurrency(plan.max_loss) : "—"}/contract</span>
                <span className="text-right">Target return {plan.target_return ? formatPercent(plan.target_return) : "—"}</span>
                <span>Vol {formatNumber(plan.contract.volume)}</span>
                <span className="text-right">OI {formatNumber(plan.contract.open_interest)}</span>
              </div>
              <p className="mt-3 text-xs leading-5 text-terminal-muted">{plan.rationale}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-xl border border-terminal-border bg-black/20 p-4 text-sm text-terminal-muted">
          No {label.toLowerCase()} plans passed the current signal/chain filters.
        </p>
      )}
    </div>
  );
}

function UnusualRow({ contract }: Readonly<{ contract: OptionContract }>) {
  const ratio = Number(contract.volume_oi_ratio);
  return (
    <tr className="border-t border-terminal-border/60">
      <td className="py-2 pr-4">
        <span
          className={`uppercase ${
            contract.option_type === "call" ? "text-emerald-300" : "text-terminal-danger"
          }`}
        >
          {contract.option_type}
        </span>
      </td>
      <td className="py-2 pr-4 text-right">{formatCurrency(contract.strike)}</td>
      <td className="py-2 pr-4 text-right">{contract.days_to_expiry}</td>
      <td className="py-2 pr-4 text-right">{formatNumber(contract.volume)}</td>
      <td className="py-2 pr-4 text-right">{formatNumber(contract.open_interest)}</td>
      <td className={`py-2 pr-4 text-right ${ratio >= 1 ? "text-terminal-accent" : ""}`}>
        {contract.volume_oi_ratio}
      </td>
      <td className="py-2 pr-4 text-right">
        {contract.last_price ? formatCurrency(contract.last_price) : "—"}
      </td>
      <td className="py-2 text-right">
        {contract.implied_volatility ? formatPercent(contract.implied_volatility) : "—"}
      </td>
    </tr>
  );
}
