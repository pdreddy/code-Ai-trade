"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EmptyState } from "@/components/page-panel";
import {
  ActionBadge,
  ErrorNote,
  SymbolBar,
  formatCurrency,
  formatPercent
} from "@/components/research";
import { ApiError, fetchSignals, type Signals } from "@/lib/api";

const DEFAULT_SYMBOL = "SPY";

export function SignalsWorkspace() {
  const searchParams = useSearchParams();
  const initialSymbol = (searchParams.get("symbol") ?? DEFAULT_SYMBOL).toUpperCase();

  const [symbol, setSymbol] = useState(initialSymbol);
  const [signals, setSignals] = useState<Signals | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (target: string) => {
    setLoading(true);
    setError(null);
    try {
      setSignals(await fetchSignals(target));
    } catch (caught) {
      setSignals(null);
      setError(caught instanceof ApiError ? caught.message : "Unexpected error loading signals.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(symbol);
  }, [symbol, load]);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
        <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">Signals</p>
        <h2 className="mt-3 text-2xl font-semibold">AI Signal Workbench</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">
          Ten independent agents evaluate real market data and their votes aggregate into one
          deterministic master decision with confidence, risk score, and trade levels.
        </p>
        <div className="mt-4">
          <SymbolBar loading={loading} onSubmit={setSymbol} symbol={symbol} />
        </div>
      </section>

      {error ? <ErrorNote message={error} /> : null}

      {signals ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-accent">
                  {signals.symbol} · Master decision
                </p>
                <p className="mt-2 font-mono text-sm text-terminal-muted">
                  Latest close {formatCurrency(signals.latest_close)} · {signals.bar_count} bars ·
                  as of {signals.as_of.slice(0, 10)}
                </p>
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
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <h3 className="text-lg font-semibold">Agent votes</h3>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Agent</th>
                    <th className="py-2 pr-4">Action</th>
                    <th className="py-2 pr-4 text-right">Confidence</th>
                    <th className="py-2 pr-4 text-right">Score</th>
                    <th className="py-2">Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.votes.map((vote) => (
                    <tr className="border-t border-terminal-border/60 align-top" key={vote.agent_name}>
                      <td className="py-3 pr-4 font-medium capitalize">
                        {vote.agent_name.replace(/_/g, " ")}
                      </td>
                      <td className="py-3 pr-4">
                        <ActionBadge action={vote.action} />
                      </td>
                      <td className="py-3 pr-4 text-right font-mono">
                        {formatPercent(vote.confidence)}
                      </td>
                      <td className="py-3 pr-4 text-right font-mono">
                        {Number(vote.score).toFixed(2)}
                      </td>
                      <td className="py-3 text-xs text-terminal-muted">{vote.reasons.join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}

      {!loading && !error && !signals ? (
        <EmptyState message="No signals were returned for this symbol." />
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
