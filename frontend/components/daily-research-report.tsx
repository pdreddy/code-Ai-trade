"use client";

import { useEffect, useMemo, useState } from "react";

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

type Portfolio = {
  starting_capital: string;
  ending_equity: string;
  total_return: string;
  open_positions: number;
  closed_trades: number;
  win_rate: string;
  max_drawdown: string;
  cash_policy: string;
};

type OptionsWatch = {
  symbol: string;
  signal_date: string;
  underlying_action: "BUY" | "SELL" | "HOLD";
  watch_type: string;
  urgency: string;
  underlying_last_close: string;
  suggested_underlying_notional: string;
  rationale: string[];
};

type ResearchReport = {
  generated_at: string;
  candidates: Candidate[];
  backtests: Backtest[];
  portfolio: Portfolio;
  options_watchlist: OptionsWatch[];
};

type ReportState =
  | { status: "loading"; report: null; error: null }
  | { status: "ready"; report: ResearchReport; error: null }
  | { status: "error"; report: null; error: string };

type View = "signals" | "backtests" | "paper-trades" | "analytics" | "portfolio" | "dashboard" | "stocks";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const capital = 10000;

export function DailyResearchReport({ view }: Readonly<{ view: View }>) {
  const [state, setState] = useState<ReportState>({ status: "loading", report: null, error: null });

  useEffect(() => {
    let cancelled = false;
    async function loadReport() {
      try {
        const response = await fetch(`${apiBaseUrl}/research/daily-report?capital=${capital}`, {
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
    return <p className="text-sm text-terminal-muted">Loading real five-year research report with $10,000 paper capital...</p>;
  }
  if (state.status === "error") {
    return <p className="text-sm text-terminal-muted">Provider unavailable: {state.error}. No synthetic trades are shown.</p>;
  }

  if (view === "signals") {
    return <CandidateGrid candidates={state.report.candidates} generatedAt={state.report.generated_at} optionsWatchlist={state.report.options_watchlist} />;
  }
  if (view === "paper-trades") {
    return <TradeJournal backtests={state.report.backtests} portfolio={state.report.portfolio} />;
  }
  if (view === "analytics") {
    return <AnalyticsGrid report={state.report} />;
  }
  if (view === "portfolio") {
    return <PortfolioGrid report={state.report} />;
  }
  if (view === "dashboard") {
    return <DashboardResearch report={state.report} />;
  }
  if (view === "stocks") {
    return <StockResearch report={state.report} />;
  }
  return <BacktestGrid backtests={state.report.backtests} portfolio={state.report.portfolio} />;
}

function CandidateGrid({ candidates, generatedAt, optionsWatchlist }: Readonly<{ candidates: Candidate[]; generatedAt: string; optionsWatchlist: OptionsWatch[] }>) {
  return (
    <div className="space-y-5">
      <SummaryStrip items={[["Paper capital", "$10,000"], ["Candidates", String(candidates.length)], ["Options watch", String(optionsWatchlist.length)], ["Generated", generatedAt.slice(0, 10)]]} />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {candidates.map((candidate) => <CandidateCard candidate={candidate} key={candidate.symbol} />)}
      </div>
      <OptionsWatchPanel optionsWatchlist={optionsWatchlist} />
      <p className="text-xs text-terminal-muted">These are next-session paper/research candidates. The app does not place live orders.</p>
    </div>
  );
}

function CandidateCard({ candidate }: Readonly<{ candidate: Candidate }>) {
  return (
    <div className="rounded-xl border border-terminal-border bg-black/20 p-4">
      <div className="flex items-center justify-between">
        <p className="font-medium">{candidate.symbol}</p>
        <Badge value={candidate.action} />
      </div>
      <p className="mt-2 text-xs text-terminal-muted">Signal close: {candidate.signal_date}</p>
      <p className="mt-1 text-xs text-terminal-muted">Execution plan: {candidate.planned_execution}</p>
      <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
        <Row k="Confidence" v={pct(candidate.confidence)} />
        <Row k="Last close" v={usd(candidate.last_close)} />
        <Row k="Stop" v={candidate.stop_loss ? usd(candidate.stop_loss) : "n/a"} />
        <Row k="Target" v={candidate.take_profit ? usd(candidate.take_profit) : "n/a"} />
        <Row k="Paper qty" v={candidate.suggested_quantity} />
        <Row k="Paper notional" v={usd(candidate.suggested_notional)} />
      </dl>
      <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px] text-terminal-muted">
        {candidate.reasons.map((reason) => <li key={reason}>{reason}</li>)}
      </ul>
    </div>
  );
}

function BacktestGrid({ backtests, portfolio }: Readonly<{ backtests: Backtest[]; portfolio: Portfolio }>) {
  return (
    <div className="space-y-4">
      <SummaryStrip items={[["Portfolio start", usd(portfolio.starting_capital)], ["Portfolio equity", usd(portfolio.ending_equity)], ["Portfolio return", pct(portfolio.total_return)], ["Closed trades", String(portfolio.closed_trades)]]} />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {backtests.map((backtest) => (
          <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={backtest.symbol}>
            <p className="font-medium">{backtest.symbol}</p>
            <p className="mt-2 text-xs text-terminal-muted">{backtest.start_date} → {backtest.end_date} · {backtest.bars} bars</p>
            <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
              <Row k="Sleeve capital" v={usd(backtest.starting_capital)} />
              <Row k="Ending equity" v={usd(backtest.ending_equity)} />
              <Row k="Total return" v={pct(backtest.total_return)} />
              <Row k="Win rate" v={pct(backtest.win_rate)} />
              <Row k="Max DD" v={pct(backtest.max_drawdown)} />
              <Row k="Trades" v={String(backtest.trade_count)} />
              <Row k="Open" v={backtest.open_position ? "YES" : "NO"} />
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}

function TradeJournal({ backtests, portfolio }: Readonly<{ backtests: Backtest[]; portfolio: Portfolio }>) {
  const trades = useMemo(
    () => backtests.flatMap((backtest) => backtest.trades).sort((a, b) => (b.exit_date ?? b.entry_date).localeCompare(a.exit_date ?? a.entry_date)),
    [backtests]
  );
  return (
    <div className="space-y-4">
      <SummaryStrip items={[["$10k ending equity", usd(portfolio.ending_equity)], ["Realized trades", String(portfolio.closed_trades)], ["Open positions", String(portfolio.open_positions)], ["Win rate", pct(portfolio.win_rate)]]} />
      {trades.length === 0 ? <p className="text-sm text-terminal-muted">No strategy trades were generated from the current real-data report.</p> : <TradeTable trades={trades} />}
    </div>
  );
}

function TradeTable({ trades }: Readonly<{ trades: Trade[] }>) {
  return (
    <div className="overflow-x-auto rounded-xl border border-terminal-border">
      <table className="w-full min-w-[1000px] text-left text-xs text-terminal-muted">
        <thead className="bg-black/30 text-terminal-text">
          <tr>
            <th className="px-3 py-2">Symbol</th><th className="px-3 py-2">Entry</th><th className="px-3 py-2">Exit / status</th><th className="px-3 py-2">Qty</th><th className="px-3 py-2">PnL</th><th className="px-3 py-2">Return</th><th className="px-3 py-2">Execution rule</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr className="border-t border-terminal-border" key={`${trade.symbol}-${trade.entry_date}-${trade.exit_date ?? "open"}`}>
              <td className="px-3 py-2 text-terminal-text">{trade.symbol}</td>
              <td className="px-3 py-2">{trade.entry_date} @ {usd(trade.entry_price)}</td>
              <td className="px-3 py-2">{trade.exit_date ? `${trade.exit_date} @ ${usd(trade.exit_price ?? "0")}` : "OPEN / marked to latest close"}</td>
              <td className="px-3 py-2">{trade.quantity}</td>
              <td className="px-3 py-2">{trade.pnl ? usd(trade.pnl) : "open"}</td>
              <td className="px-3 py-2">{trade.return_pct ? pct(trade.return_pct) : "open"}</td>
              <td className="px-3 py-2">{trade.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnalyticsGrid({ report }: Readonly<{ report: ResearchReport }>) {
  const trades = report.backtests.flatMap((backtest) => backtest.trades);
  return (
    <div className="space-y-4">
      <SummaryStrip items={[["Generated", report.generated_at.slice(0, 10)], ["Portfolio return", pct(report.portfolio.total_return)], ["Worst drawdown", pct(report.portfolio.max_drawdown)], ["Trade rows", String(trades.length)]]} />
      <BacktestGrid backtests={report.backtests} portfolio={report.portfolio} />
      <TradeJournal backtests={report.backtests} portfolio={report.portfolio} />
    </div>
  );
}

function PortfolioGrid({ report }: Readonly<{ report: ResearchReport }>) {
  return (
    <div className="space-y-4">
      <SummaryStrip items={[["Starting capital", usd(report.portfolio.starting_capital)], ["Ending equity", usd(report.portfolio.ending_equity)], ["Return", pct(report.portfolio.total_return)], ["Open positions", String(report.portfolio.open_positions)]]} />
      <p className="text-xs text-terminal-muted">Capital policy: {report.portfolio.cash_policy}</p>
      <BacktestGrid backtests={report.backtests} portfolio={report.portfolio} />
    </div>
  );
}

function DashboardResearch({ report }: Readonly<{ report: ResearchReport }>) {
  return (
    <div className="space-y-4">
      <SummaryStrip items={[["Paper capital", usd(report.portfolio.starting_capital)], ["Equity", usd(report.portfolio.ending_equity)], ["Next-day candidates", String(report.candidates.filter((candidate) => candidate.action !== "HOLD").length)], ["Options watch", String(report.options_watchlist.length)]]} />
      <CandidateGrid candidates={report.candidates} generatedAt={report.generated_at} optionsWatchlist={report.options_watchlist} />
    </div>
  );
}

function StockResearch({ report }: Readonly<{ report: ResearchReport }>) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {report.backtests.map((backtest) => (
        <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={backtest.symbol}>
          <p className="text-lg font-semibold">{backtest.symbol}</p>
          <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
            <Row k="Latest research period" v={`${backtest.start_date} → ${backtest.end_date}`} />
            <Row k="Bars" v={String(backtest.bars)} />
            <Row k="Sleeve equity" v={usd(backtest.ending_equity)} />
            <Row k="Trades" v={String(backtest.trade_count)} />
            <Row k="Open position" v={backtest.open_position ? "YES" : "NO"} />
          </dl>
        </div>
      ))}
    </div>
  );
}

function OptionsWatchPanel({ optionsWatchlist }: Readonly<{ optionsWatchlist: OptionsWatch[] }>) {
  if (optionsWatchlist.length === 0) {
    return <p className="text-sm text-terminal-muted">No unusual-options watch candidates from the current underlying report. Options chain execution is still not enabled.</p>;
  }
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-terminal-accent">Unusual Options Watch Plan</h3>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {optionsWatchlist.map((candidate) => (
          <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-4" key={candidate.symbol}>
            <div className="flex justify-between">
              <p className="font-medium">{candidate.symbol}</p><span className="text-amber-200">{candidate.watch_type}</span>
            </div>
            <dl className="mt-3 grid gap-2 text-xs text-terminal-muted">
              <Row k="Underlying" v={candidate.underlying_action} />
              <Row k="Urgency" v={pct(candidate.urgency)} />
              <Row k="Close" v={usd(candidate.underlying_last_close)} />
              <Row k="Underlying notional" v={usd(candidate.suggested_underlying_notional)} />
            </dl>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px] text-terminal-muted">
              {candidate.rationale.map((rationale) => <li key={rationale}>{rationale}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryStrip({ items }: Readonly<{ items: [string, string][] }>) {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {items.map(([label, value]) => (
        <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={label}>
          <p className="text-xs uppercase tracking-[0.2em] text-terminal-muted">{label}</p>
          <p className="mt-2 font-medium">{value}</p>
        </div>
      ))}
    </div>
  );
}

function Row({ k, v }: Readonly<{ k: string; v: string }>) {
  return <div className="flex justify-between gap-3"><dt>{k}</dt><dd className="text-right text-terminal-text">{v}</dd></div>;
}

function Badge({ value }: Readonly<{ value: Candidate["action"] }>) {
  return <span className={value === "BUY" ? "text-emerald-300" : value === "SELL" ? "text-red-300" : "text-terminal-muted"}>{value}</span>;
}

function usd(value: string) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }) : value;
}

function pct(value: string) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? `${(numericValue * 100).toFixed(2)}%` : value;
}
