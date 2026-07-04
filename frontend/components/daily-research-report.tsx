"use client";

import { useEffect, useState } from "react";

type Candidate = {
  symbol: string;
  signal_date: string;
  action: "BUY" | "SELL" | "HOLD";
  confidence: string;
  planned_execution: string;
  last_close: string;
  stop_loss: string | null;
  take_profit: string | null;
  suggested_quantity: string;
  suggested_notional: string;
  reasons: string[];
};

type Trade = {
  symbol: string;
  entry_date: string;
  entry_price: string;
  exit_date: string | null;
  exit_price: string | null;
  quantity: string;
  pnl: string | null;
  return_pct: string | null;
  reason: string;
};

type Backtest = {
  symbol: string;
  start_date: string;
  end_date: string;
  bars: number;
  total_return: string;
  win_rate: string;
  max_drawdown: string;
  trade_count: number;
  open_position: boolean;
  starting_capital: string;
  ending_equity: string;
  trades: Trade[];
};

type ResearchReport = {
  generated_at: string;
  candidates: Candidate[];
  backtests: Backtest[];
};

type ReportState =
  | { status: "loading"; report: null; error: null }
  | { status: "ready"; report: ResearchReport; error: null }
  | { status: "error"; report: null; error: string };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function DailyResearchReport({ view }: Readonly<{ view: "signals" | "backtests" | "paper-trades" | "analytics" | "portfolio" }>) {
  const [state, setState] = useState<ReportState>({ status: "loading", report: null, error: null });

  useEffect(() => {
    let cancelled = false;
    async function loadReport() {
      try {
        const response = await fetch(`${apiBaseUrl}/research/daily-report?capital=5000`, {
          headers: { Accept: "application/json" }
        });
        if (!response.ok) {
          throw new Error(`research report failed with HTTP ${response.status}`);
        }
        const report = (await response.json()) as ResearchReport;
        if (!cancelled) {
          setState({ status: "ready", report, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            report: null,
            error: error instanceof Error ? error.message : "research report failed"
          });
        }
      }
    }
    void loadReport();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return <p className="text-sm text-terminal-muted">Loading real five-year research report from backend...</p>;
  }

  if (state.status === "error") {
    return <p className="text-sm text-terminal-muted">Provider unavailable: {state.error}. No synthetic trades are shown.</p>;
  }

  if (view === "signals") {
    return <CandidateGrid candidates={state.report.candidates} generatedAt={state.report.generated_at} />;
  }
  if (view === "paper-trades") {
    return <TradeJournal backtests={state.report.backtests} />;
  }
  if (view === "analytics") {
    return <AnalyticsGrid backtests={state.report.backtests} generatedAt={state.report.generated_at} />;
  }
  if (view === "portfolio") {
    return <PortfolioGrid backtests={state.report.backtests} />;
  }
  return <BacktestGrid backtests={state.report.backtests} />;
}

function CandidateGrid({ candidates, generatedAt }: Readonly<{ candidates: Candidate[]; generatedAt: string }>) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {candidates.map((candidate) => (
          <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={candidate.symbol}>
            <div className="flex items-center justify-between">
              <p className="font-medium">{candidate.symbol}</p>
              <span className={candidate.action === "BUY" ? "text-emerald-300" : candidate.action === "SELL" ? "text-red-300" : "text-terminal-muted"}>
                {candidate.action}
              </span>
            </div>
            <p className="mt-2 text-xs text-terminal-muted">Signal close: {candidate.signal_date}</p>
            <p className="mt-1 text-xs text-terminal-muted">Next step: {candidate.planned_execution}</p>
            <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
              <div className="flex justify-between"><dt>Confidence</dt><dd>{candidate.confidence}</dd></div>
              <div className="flex justify-between"><dt>Last close</dt><dd>${candidate.last_close}</dd></div>
              <div className="flex justify-between"><dt>Stop</dt><dd>{candidate.stop_loss ?? "n/a"}</dd></div>
              <div className="flex justify-between"><dt>Target</dt><dd>{candidate.take_profit ?? "n/a"}</dd></div>
              <div className="flex justify-between"><dt>Suggested qty</dt><dd>{candidate.suggested_quantity}</dd></div>
              <div className="flex justify-between"><dt>Suggested $</dt><dd>{candidate.suggested_notional}</dd></div>
            </dl>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px] text-terminal-muted">
              {candidate.reasons.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </div>
        ))}
      </div>
      <p className="text-xs text-terminal-muted">Generated at {generatedAt}. These are paper/research candidates, not live orders.</p>
    </div>
  );
}

function BacktestGrid({ backtests }: Readonly<{ backtests: Backtest[] }>) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {backtests.map((backtest) => (
        <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={backtest.symbol}>
          <p className="font-medium">{backtest.symbol}</p>
          <p className="mt-2 text-xs text-terminal-muted">{backtest.start_date} → {backtest.end_date} · {backtest.bars} bars</p>
          <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
            <div className="flex justify-between"><dt>Capital</dt><dd>${backtest.starting_capital}</dd></div>
            <div className="flex justify-between"><dt>Ending equity</dt><dd>${backtest.ending_equity}</dd></div>
            <div className="flex justify-between"><dt>Total return</dt><dd>{backtest.total_return}</dd></div>
            <div className="flex justify-between"><dt>Win rate</dt><dd>{backtest.win_rate}</dd></div>
            <div className="flex justify-between"><dt>Max DD</dt><dd>{backtest.max_drawdown}</dd></div>
            <div className="flex justify-between"><dt>Trades</dt><dd>{backtest.trade_count}</dd></div>
            <div className="flex justify-between"><dt>Open position</dt><dd>{String(backtest.open_position)}</dd></div>
          </dl>
        </div>
      ))}
    </div>
  );
}

function TradeJournal({ backtests }: Readonly<{ backtests: Backtest[] }>) {
  const trades = backtests.flatMap((backtest) => backtest.trades);
  if (trades.length === 0) {
    return <p className="text-sm text-terminal-muted">No strategy trades were generated from the current real-data report.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-terminal-border">
      <table className="w-full min-w-[900px] text-left text-xs text-terminal-muted">
        <thead className="bg-black/30 text-terminal-text">
          <tr>
            <th className="px-3 py-2">Symbol</th><th className="px-3 py-2">Entry</th><th className="px-3 py-2">Exit</th><th className="px-3 py-2">Qty</th><th className="px-3 py-2">PnL</th><th className="px-3 py-2">Return</th><th className="px-3 py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr className="border-t border-terminal-border" key={`${trade.symbol}-${trade.entry_date}-${trade.exit_date ?? "open"}`}>
              <td className="px-3 py-2 text-terminal-text">{trade.symbol}</td>
              <td className="px-3 py-2">{trade.entry_date} @ ${trade.entry_price}</td>
              <td className="px-3 py-2">{trade.exit_date ? `${trade.exit_date} @ $${trade.exit_price}` : "OPEN"}</td>
              <td className="px-3 py-2">{trade.quantity}</td>
              <td className="px-3 py-2">{trade.pnl ?? "open"}</td>
              <td className="px-3 py-2">{trade.return_pct ?? "open"}</td>
              <td className="px-3 py-2">{trade.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnalyticsGrid({ backtests, generatedAt }: Readonly<{ backtests: Backtest[]; generatedAt: string }>) {
  const totalTrades = backtests.reduce((sum, backtest) => sum + backtest.trade_count, 0);
  const averageReturn = average(backtests.map((backtest) => Number(backtest.total_return)));
  const averageWinRate = average(backtests.map((backtest) => Number(backtest.win_rate)));
  const worstDrawdown = Math.min(...backtests.map((backtest) => Number(backtest.max_drawdown)));
  return (
    <div className="grid gap-3 md:grid-cols-4">
      <Metric label="Generated" value={generatedAt.slice(0, 10)} />
      <Metric label="Total trades" value={String(totalTrades)} />
      <Metric label="Avg return" value={averageReturn.toFixed(4)} />
      <Metric label="Avg win rate" value={averageWinRate.toFixed(4)} />
      <Metric label="Worst drawdown" value={worstDrawdown.toFixed(4)} />
    </div>
  );
}

function Metric({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="rounded-xl border border-terminal-border bg-black/20 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-terminal-muted">{label}</p>
      <p className="mt-2 font-medium">{value}</p>
    </div>
  );
}

function average(values: number[]) {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function PortfolioGrid({ backtests }: Readonly<{ backtests: Backtest[] }>) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {backtests.map((backtest) => (
        <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={backtest.symbol}>
          <p className="font-medium">{backtest.symbol}</p>
          <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
            <div className="flex justify-between"><dt>Start cash</dt><dd>${backtest.starting_capital}</dd></div>
            <div className="flex justify-between"><dt>Ending equity</dt><dd>${backtest.ending_equity}</dd></div>
            <div className="flex justify-between"><dt>Return</dt><dd>{backtest.total_return}</dd></div>
            <div className="flex justify-between"><dt>Open position</dt><dd>{String(backtest.open_position)}</dd></div>
            <div className="flex justify-between"><dt>Trades</dt><dd>{backtest.trade_count}</dd></div>
          </dl>
        </div>
      ))}
    </div>
  );
}
