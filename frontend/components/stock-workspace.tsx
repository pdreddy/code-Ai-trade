"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EmptyState } from "@/components/page-panel";
import {
  ActionBadge,
  ErrorNote,
  Sparkline,
  SymbolBar,
  formatCurrency,
  formatNumber,
  formatPercent,
  formatSignedPercent
} from "@/components/research";
import {
  ApiError,
  fetchMarketData,
  fetchSignals,
  type MarketData,
  type Signals
} from "@/lib/api";

const DEFAULT_SYMBOL = "SPY";

export function StockWorkspace() {
  const searchParams = useSearchParams();
  const initialSymbol = (searchParams.get("symbol") ?? DEFAULT_SYMBOL).toUpperCase();

  const [symbol, setSymbol] = useState(initialSymbol);
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const [signals, setSignals] = useState<Signals | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (target: string) => {
    setLoading(true);
    setError(null);
    try {
      const [data, signalData] = await Promise.all([
        fetchMarketData(target),
        fetchSignals(target)
      ]);
      setMarketData(data);
      setSignals(signalData);
    } catch (caught) {
      setMarketData(null);
      setSignals(null);
      setError(caught instanceof ApiError ? caught.message : "Unexpected error loading data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(symbol);
  }, [symbol, load]);

  const bars = marketData?.bars ?? [];
  const latest = bars.at(-1);
  const previous = bars.at(-2);
  const closes = bars.map((bar) => Number(bar.close));
  const dayChange =
    latest && previous ? Number(latest.close) / Number(previous.close) - 1 : null;
  const periodHigh = bars.length ? Math.max(...bars.map((bar) => Number(bar.high))) : null;
  const periodLow = bars.length ? Math.min(...bars.map((bar) => Number(bar.low))) : null;

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">Stock Details</p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-2xl font-semibold">
            {symbol} <span className="text-terminal-muted">· Instrument Research Workspace</span>
          </h2>
        </div>
        <div className="mt-4">
          <SymbolBar loading={loading} onSubmit={setSymbol} symbol={symbol} />
        </div>
      </section>

      {error ? <ErrorNote message={error} /> : null}

      {latest ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">Latest close</p>
              <p className="mt-1 font-mono text-3xl font-semibold">
                {formatCurrency(latest.close)}
              </p>
            </div>
            {dayChange !== null ? (
              <p
                className={`font-mono text-lg ${
                  dayChange >= 0 ? "text-emerald-300" : "text-terminal-danger"
                }`}
              >
                {formatSignedPercent(dayChange)}
              </p>
            ) : null}
          </div>
          <div className="mt-4">
            <Sparkline values={closes} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label={`${bars.length}-bar high`} value={periodHigh !== null ? formatCurrency(periodHigh) : "—"} />
            <Stat label={`${bars.length}-bar low`} value={periodLow !== null ? formatCurrency(periodLow) : "—"} />
            <Stat label="Latest volume" value={formatNumber(latest.volume)} />
            <Stat label="Bars loaded" value={formatNumber(marketData?.bar_count ?? 0)} />
          </div>
          <p className="mt-4 text-xs text-terminal-muted">
            Source: {marketData?.provider} · retrieved {marketData?.retrieved_at_utc}
          </p>
        </section>
      ) : null}

      {signals ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">Master decision</p>
              <h3 className="mt-2 text-xl font-semibold">Deterministic aggregate signal</h3>
            </div>
            <ActionBadge action={signals.master_decision.action} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Confidence" value={formatPercent(signals.master_decision.confidence)} />
            <Stat label="Risk score" value={formatPercent(signals.master_decision.risk_score)} />
            <Stat
              label="Stop loss"
              value={
                signals.master_decision.stop_loss
                  ? formatCurrency(signals.master_decision.stop_loss)
                  : "—"
              }
            />
            <Stat
              label="Take profit"
              value={
                signals.master_decision.take_profit
                  ? formatCurrency(signals.master_decision.take_profit)
                  : "—"
              }
            />
          </div>
          <p className="mt-4 text-sm leading-6 text-terminal-muted">
            {signals.master_decision.explanation}
          </p>
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            {signals.votes.map((vote) => (
              <article
                className="rounded-xl border border-terminal-border bg-black/20 p-4"
                key={vote.agent_name}
              >
                <div className="flex items-center justify-between gap-3">
                  <h4 className="font-medium capitalize">{vote.agent_name.replace(/_/g, " ")}</h4>
                  <ActionBadge action={vote.action} />
                </div>
                <p className="mt-2 text-xs text-terminal-muted">
                  Confidence {formatPercent(vote.confidence)} · Score {Number(vote.score).toFixed(2)}
                </p>
                <ul className="mt-2 list-disc pl-4 text-xs leading-5 text-terminal-muted">
                  {vote.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {bars.length ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
          <h3 className="text-lg font-semibold">Recent bars</h3>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                <tr>
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 pr-4 text-right">Open</th>
                  <th className="py-2 pr-4 text-right">High</th>
                  <th className="py-2 pr-4 text-right">Low</th>
                  <th className="py-2 pr-4 text-right">Close</th>
                  <th className="py-2 text-right">Volume</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {[...bars]
                  .slice(-12)
                  .reverse()
                  .map((bar) => (
                    <tr className="border-t border-terminal-border/60" key={bar.timestamp}>
                      <td className="py-2 pr-4">{bar.timestamp.slice(0, 10)}</td>
                      <td className="py-2 pr-4 text-right">{formatCurrency(bar.open)}</td>
                      <td className="py-2 pr-4 text-right">{formatCurrency(bar.high)}</td>
                      <td className="py-2 pr-4 text-right">{formatCurrency(bar.low)}</td>
                      <td className="py-2 pr-4 text-right">{formatCurrency(bar.close)}</td>
                      <td className="py-2 text-right">{formatNumber(bar.volume)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {!loading && !error && !latest ? (
        <EmptyState message="No bars were returned for this symbol." />
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
