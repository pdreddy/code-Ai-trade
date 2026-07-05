"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState } from "@/components/page-panel";
import {
  ConfidenceBadge,
  ErrorNote,
  LoadingBlock,
  formatCurrency,
  formatNumber,
  formatPercent
} from "@/components/research";
import { ApiError, fetchOptionsScan, type OptionsScan } from "@/lib/api";

export function ScannerWorkspace() {
  const [data, setData] = useState<OptionsScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchOptionsScan({ force }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unexpected error scanning the universe.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">Scanner</p>
            <h2 className="mt-3 text-2xl font-semibold">Options Flow, Universe-Wide</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">
              Every symbol in the scanner universe checked at once for three real signals — unusual
              volume, call/put open-interest buildup, and price breakouts — each scored with an
              honest confidence so you can triage at a glance instead of reading raw numbers.
              Real chain and price data only; a symbol that can&apos;t be fetched surfaces as an
              error rather than a guess.
            </p>
          </div>
          <button
            className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 text-sm transition hover:border-terminal-accent hover:text-terminal-accent disabled:opacity-50"
            disabled={loading}
            onClick={() => void load(true)}
            type="button"
          >
            {loading ? "Scanning…" : "Rescan"}
          </button>
        </div>
        {data ? (
          <p className="mt-3 text-xs text-terminal-muted">
            {data.symbols_scanned} symbol(s) scanned · generated{" "}
            {new Date(data.generated_at).toLocaleTimeString()}
          </p>
        ) : null}
      </section>

      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <LoadingBlock label="Scanning the universe for options flow…" /> : null}

      {data && data.errors.length ? (
        <ErrorNote
          message={`${data.errors.length} symbol(s) unavailable: ${data.errors
            .map((item) => `${item.symbol} (${item.detail})`)
            .join("; ")}`}
        />
      ) : null}

      {data ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h3 className="text-lg font-semibold">Call/put OI buildup</h3>
              <p className="mt-1 max-w-2xl text-xs text-terminal-muted">
                Where standing open interest right now is lopsided toward calls or puts — a
                snapshot of positioning, not a historical trend (the provider only exposes
                current OI). Ranked by confidence.
              </p>
            </div>
            <p className="text-xs text-terminal-muted">
              {data.oi_skew.length ? `${data.oi_skew.length} symbol(s)` : ""}
            </p>
          </div>
          {data.oi_skew.length ? (
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4">Building toward</th>
                    <th className="py-2 pr-4 text-right">Call OI</th>
                    <th className="py-2 pr-4 text-right">Put OI</th>
                    <th className="py-2 pr-4 text-right">Skew</th>
                    <th className="py-2 text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.oi_skew.map((item) => (
                    <tr className="border-t border-terminal-border/60" key={item.symbol}>
                      <td className="py-2 pr-4 font-semibold">
                        <Link className="hover:text-terminal-accent" href={`/options?symbol=${item.symbol}`}>
                          {item.symbol}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`uppercase ${
                            item.direction === "calls" ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {item.direction}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right">{formatNumber(item.call_open_interest)}</td>
                      <td className="py-2 pr-4 text-right">{formatNumber(item.put_open_interest)}</td>
                      <td className="py-2 pr-4 text-right text-terminal-accent">{item.ratio}×</td>
                      <td className="py-2 text-right">
                        <ConfidenceBadge value={item.confidence} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 text-sm text-terminal-muted">
              No symbol cleared the open-interest skew threshold right now.
            </p>
          )}
        </section>
      ) : null}

      {data ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h3 className="text-lg font-semibold">Price breakouts</h3>
              <p className="mt-1 max-w-2xl text-xs text-terminal-muted">
                Underlying closes that broke above or below the prior 20-session range — the same
                breakout agent that votes in the master decision, run standalone across the whole
                universe.
              </p>
            </div>
            <p className="text-xs text-terminal-muted">
              {data.breakouts.length ? `${data.breakouts.length} symbol(s)` : ""}
            </p>
          </div>
          {data.breakouts.length ? (
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4">Direction</th>
                    <th className="py-2 pr-4">Reason</th>
                    <th className="py-2 text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.breakouts.map((item) => (
                    <tr className="border-t border-terminal-border/60" key={item.symbol}>
                      <td className="py-2 pr-4 font-semibold">
                        <Link className="hover:text-terminal-accent" href={`/options?symbol=${item.symbol}`}>
                          {item.symbol}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`uppercase ${
                            item.direction === "bullish" ? "text-emerald-300" : "text-terminal-danger"
                          }`}
                        >
                          {item.direction}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-xs text-terminal-muted">{item.reason}</td>
                      <td className="py-2 text-right">
                        <ConfidenceBadge value={item.confidence} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 text-sm text-terminal-muted">
              No symbol broke out of its prior 20-session range right now.
            </p>
          )}
        </section>
      ) : null}

      {data ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-lg font-semibold">Unusual volume activity</h3>
            <p className="text-xs text-terminal-muted">
              Ranked by volume ÷ open interest{" "}
              {data.unusual_activity.length ? `· top ${data.unusual_activity.length}` : ""}
            </p>
          </div>
          {data.unusual_activity.length ? (
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[940px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4 text-right">Strike</th>
                    <th className="py-2 pr-4 text-right">DTE</th>
                    <th className="py-2 pr-4 text-right">Volume</th>
                    <th className="py-2 pr-4 text-right">OI</th>
                    <th className="py-2 pr-4 text-right">Vol/OI</th>
                    <th className="py-2 pr-4 text-right">IV</th>
                    <th className="py-2 text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.unusual_activity.map((item, index) => (
                    <tr
                      className="border-t border-terminal-border/60"
                      key={`${item.symbol}-${item.contract.contract_symbol}-${index}`}
                    >
                      <td className="py-2 pr-4 font-semibold">
                        <Link className="hover:text-terminal-accent" href={`/options?symbol=${item.symbol}`}>
                          {item.symbol}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`uppercase ${
                            item.contract.option_type === "call"
                              ? "text-emerald-300"
                              : "text-terminal-danger"
                          }`}
                        >
                          {item.contract.option_type}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right">{formatCurrency(item.contract.strike)}</td>
                      <td className="py-2 pr-4 text-right">{item.contract.days_to_expiry}</td>
                      <td className="py-2 pr-4 text-right">{formatNumber(item.contract.volume)}</td>
                      <td className="py-2 pr-4 text-right">{formatNumber(item.contract.open_interest)}</td>
                      <td className="py-2 pr-4 text-right text-terminal-accent">
                        {item.volume_oi_ratio}
                      </td>
                      <td className="py-2 pr-4 text-right">
                        {item.contract.implied_volatility
                          ? formatPercent(item.contract.implied_volatility)
                          : "—"}
                      </td>
                      <td className="py-2 text-right">
                        <ConfidenceBadge value={item.confidence} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 text-sm text-terminal-muted">
              No contracts cleared the liquidity threshold across the scanned universe.
            </p>
          )}
        </section>
      ) : null}

      {data && data.planned_trades.length ? (
        <section className="rounded-2xl border border-terminal-accent/40 bg-terminal-accent/5 p-6 shadow-2xl">
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">
                Upcoming planned option trades · universe-wide
              </p>
              <h3 className="mt-2 text-lg font-semibold">AI-aligned plays across the board</h3>
            </div>
            <p className="text-xs text-terminal-muted">{data.planned_trades.length} plan(s)</p>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {data.planned_trades.map((plan, index) => (
              <Link
                className="rounded-xl border border-terminal-border bg-black/20 p-4 transition hover:border-terminal-accent"
                href={`/options?symbol=${plan.symbol}`}
                key={`${plan.symbol}-${plan.contract.contract_symbol}-${index}`}
              >
                <div className="flex items-center justify-between">
                  <p className="font-mono font-semibold">{plan.symbol}</p>
                  <span
                    className={`text-xs uppercase ${
                      plan.contract.option_type === "call" ? "text-emerald-300" : "text-terminal-danger"
                    }`}
                  >
                    {plan.contract.option_type}
                  </span>
                </div>
                <p className="mt-2 font-mono text-sm text-terminal-muted">
                  {formatCurrency(plan.contract.strike)} · {plan.contract.days_to_expiry}DTE
                </p>
                <p className="mt-2 text-xs leading-5 text-terminal-muted">{plan.rationale}</p>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {!loading && !error && !data ? (
        <EmptyState message="No scan results could be produced." />
      ) : null}
    </div>
  );
}
