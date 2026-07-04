"use client";

import { useEffect, useMemo, useState } from "react";

type EquityPoint = { session: string; equity: string; drawdown: string; daily_pnl: string; daily_return: string };
type Benchmark = { benchmark: string; benchmark_return: string; strategy_return: string; outperformance: string; benchmark_drawdown: string; risk_label: string };
type AgentScore = { name: string; score: string; confidence: string; reason: string };
type Holding = { symbol: string; position: string; shares: string; average_cost: string; current_price: string; market_value: string; unrealized_pnl: string; realized_pnl: string; today_change: string; weight: string; risk_score: string; ai_score: string; confidence: string; sector: string; industry: string; stop_loss: string | null; take_profit: string | null; holding_days: number; status: string };
type Candidate = { symbol: string; signal_date: string; action: "BUY" | "SELL" | "HOLD"; confidence: string; planned_execution: string; last_close: string; stop_loss: string | null; take_profit: string | null; suggested_quantity: string; suggested_notional: string; reasons: string[]; ai_score: string; strategy: string; risk_reward: string; expected_return: string; expected_holding_days: number; catalysts: string[]; news_summary: string; institutional_flow: string; agent_scores: AgentScore[]; final_score: string; risk_score: string };
type Trade = { symbol: string; entry_date: string; entry_price: string; exit_date: string | null; exit_price: string | null; quantity: string; pnl: string | null; return_pct: string | null; reason: string; trade_id: string; direction: string; holding_period_days: number; position_size: string; entry_signal: string; exit_signal: string; strategy_name: string; regime: string; ai_confidence: string; risk_reward: string; stop_loss: string | null; take_profit: string | null; gross_pnl: string | null; net_pnl: string | null; commission: string; slippage: string; screenshot_placeholder: string; notes: string };
type Backtest = { symbol: string; start_date: string; end_date: string; bars: number; total_return: string; win_rate: string; max_drawdown: string; trade_count: number; open_position: boolean; starting_capital: string; ending_equity: string; trades: Trade[]; equity_curve: EquityPoint[]; benchmark_comparisons: Benchmark[]; sharpe_ratio: string; sortino_ratio: string; calmar_ratio: string; profit_factor: string; expectancy: string; average_win: string; average_loss: string; largest_win: string; largest_loss: string; consecutive_wins: number; consecutive_losses: number; recovery_time_days: number; exposure: string; volatility: string; alpha: string; beta: string; information_ratio: string; tracking_error: string; treynor_ratio: string; omega_ratio: string; skew: string; kurtosis: string; mar_ratio: string };
type Portfolio = { starting_capital: string; ending_equity: string; total_return: string; open_positions: number; closed_trades: number; win_rate: string; max_drawdown: string; cash_policy: string; cash: string; invested: string; today_pnl: string; annualized_return: string; profit_factor: string; sharpe_ratio: string; sortino_ratio: string; calmar_ratio: string; expectancy: string; average_winner: string; average_loser: string; risk_score: string; holdings: Holding[]; equity_curve: EquityPoint[] };
type OptionsWatch = { symbol: string; signal_date: string; underlying_action: "BUY" | "SELL" | "HOLD"; watch_type: string; urgency: string; underlying_last_close: string; suggested_underlying_notional: string; rationale: string[] };
type ResearchReport = { generated_at: string; candidates: Candidate[]; backtests: Backtest[]; portfolio: Portfolio; options_watchlist: OptionsWatch[] };
type ReportState = { status: "loading"; report: null; error: null } | { status: "ready"; report: ResearchReport; error: null } | { status: "error"; report: null; error: string };
type View = "signals" | "backtests" | "paper-trades" | "analytics" | "portfolio" | "dashboard" | "stocks";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const capital = 10000;

export function DailyResearchReport({ view }: Readonly<{ view: View }>) {
  const [state, setState] = useState<ReportState>({ status: "loading", report: null, error: null });
  useEffect(() => {
    let cancelled = false;
    async function loadReport() {
      try {
        const response = await fetch(`${apiBaseUrl}/research/daily-report?capital=${capital}`, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`research report failed with HTTP ${response.status}`);
        const report = (await response.json()) as ResearchReport;
        if (!cancelled) setState({ status: "ready", report, error: null });
      } catch (error) {
        if (!cancelled) setState({ status: "error", report: null, error: error instanceof Error ? error.message : "research report failed" });
      }
    }
    void loadReport();
    return () => { cancelled = true; };
  }, []);

  if (state.status === "loading") return <p className="text-sm text-terminal-muted">Loading institutional research report with $10,000 paper capital...</p>;
  if (state.status === "error") return <p className="text-sm text-terminal-muted">Provider unavailable: {state.error}. No synthetic trades are shown.</p>;
  if (view === "signals") return <CandidateGrid candidates={state.report.candidates} optionsWatchlist={state.report.options_watchlist} generatedAt={state.report.generated_at} />;
  if (view === "paper-trades") return <TradeJournal backtests={state.report.backtests} portfolio={state.report.portfolio} />;
  if (view === "analytics") return <AnalyticsGrid report={state.report} />;
  if (view === "portfolio") return <PortfolioGrid report={state.report} />;
  if (view === "dashboard") return <DashboardResearch report={state.report} />;
  if (view === "stocks") return <StockResearch report={state.report} />;
  return <BacktestGrid backtests={state.report.backtests} portfolio={state.report.portfolio} />;
}

function CandidateGrid({ candidates, generatedAt, optionsWatchlist }: Readonly<{ candidates: Candidate[]; generatedAt: string; optionsWatchlist: OptionsWatch[] }>) {
  return <div className="space-y-5"><SummaryStrip items={[["Paper capital", "$10,000"], ["Candidates", String(candidates.length)], ["Options watch", String(optionsWatchlist.length)], ["Generated", generatedAt.slice(0, 10)]]} /><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{candidates.map((candidate) => <CandidateCard candidate={candidate} key={candidate.symbol} />)}</div><OptionsWatchPanel optionsWatchlist={optionsWatchlist} /><p className="text-xs text-terminal-muted">These are next-session paper/research candidates. The app does not place live orders.</p></div>;
}

function CandidateCard({ candidate }: Readonly<{ candidate: Candidate }>) {
  return <div className="rounded-xl border border-terminal-border bg-black/20 p-4"><div className="flex items-center justify-between"><p className="font-medium">{candidate.symbol}</p><Badge value={candidate.action} /></div><p className="mt-2 text-xs text-terminal-muted">{candidate.strategy} · signal close {candidate.signal_date}</p><dl className="mt-3 grid gap-2 text-xs text-terminal-muted"><Row k="AI score" v={candidate.ai_score} /><Row k="Confidence" v={pct(candidate.confidence)} /><Row k="Entry" v={usd(candidate.last_close)} /><Row k="Stop" v={candidate.stop_loss ? usd(candidate.stop_loss) : "n/a"} /><Row k="Target" v={candidate.take_profit ? usd(candidate.take_profit) : "n/a"} /><Row k="Risk / Reward" v={candidate.risk_reward} /><Row k="Expected return" v={pct(candidate.expected_return)} /><Row k="Holding days" v={String(candidate.expected_holding_days)} /></dl><p className="mt-3 text-[11px] text-terminal-muted">{candidate.news_summary}</p><p className="mt-1 text-[11px] text-terminal-muted">{candidate.institutional_flow}</p><div className="mt-3 space-y-1">{candidate.agent_scores.map((agent) => <Row k={agent.name} key={agent.name} v={`${agent.score} / ${pct(agent.confidence)}`} />)}</div></div>;
}

function BacktestGrid({ backtests, portfolio }: Readonly<{ backtests: Backtest[]; portfolio: Portfolio }>) {
  return <div className="space-y-4"><SummaryStrip items={[["Portfolio equity", usd(portfolio.ending_equity)], ["Return", pct(portfolio.total_return)], ["Sharpe", portfolio.sharpe_ratio], ["Max DD", pct(portfolio.max_drawdown)]]} /><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{backtests.map((b) => <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={b.symbol}><p className="font-medium">{b.symbol}</p><p className="mt-2 text-xs text-terminal-muted">{b.start_date} → {b.end_date} · {b.bars} bars</p><dl className="mt-3 grid gap-2 text-xs text-terminal-muted"><Row k="Ending equity" v={usd(b.ending_equity)} /><Row k="Return" v={pct(b.total_return)} /><Row k="Sharpe" v={b.sharpe_ratio} /><Row k="Sortino" v={b.sortino_ratio} /><Row k="Calmar" v={b.calmar_ratio} /><Row k="Profit factor" v={b.profit_factor} /><Row k="Expectancy" v={usd(b.expectancy)} /><Row k="Exposure" v={pct(b.exposure)} /><Row k="Volatility" v={pct(b.volatility)} /><Row k="Recovery days" v={String(b.recovery_time_days)} /></dl></div>)}</div><BenchmarkTable backtests={backtests} /></div>;
}

function TradeJournal({ backtests, portfolio }: Readonly<{ backtests: Backtest[]; portfolio: Portfolio }>) {
  const trades = useMemo(() => backtests.flatMap((b) => b.trades).sort((a, b) => (b.exit_date ?? b.entry_date).localeCompare(a.exit_date ?? a.entry_date)), [backtests]);
  return <div className="space-y-4"><SummaryStrip items={[["Ending equity", usd(portfolio.ending_equity)], ["Realized trades", String(portfolio.closed_trades)], ["Win rate", pct(portfolio.win_rate)], ["Profit factor", portfolio.profit_factor]]} />{trades.length === 0 ? <p className="text-sm text-terminal-muted">No strategy trades were generated from the current real-data report.</p> : <TradeTable trades={trades} />}</div>;
}

function TradeTable({ trades }: Readonly<{ trades: Trade[] }>) {
  return <div className="overflow-x-auto rounded-xl border border-terminal-border"><table className="w-full min-w-[1500px] text-left text-xs text-terminal-muted"><thead className="bg-black/30 text-terminal-text"><tr>{["Trade ID", "Ticker", "Direction", "Entry", "Exit", "Hold", "Shares", "Size", "Signals", "Strategy", "Regime", "Confidence", "R/R", "Stop", "Target", "Gross", "Net", "Costs", "Notes"].map((h) => <th className="px-3 py-2" key={h}>{h}</th>)}</tr></thead><tbody>{trades.map((t) => <tr className="border-t border-terminal-border" key={t.trade_id}><td className="px-3 py-2 text-terminal-text">{t.trade_id}</td><td className="px-3 py-2">{t.symbol}</td><td className="px-3 py-2">{t.direction}</td><td className="px-3 py-2">{t.entry_date} @ {usd(t.entry_price)}</td><td className="px-3 py-2">{t.exit_date ? `${t.exit_date} @ ${usd(t.exit_price ?? "0")}` : "OPEN"}</td><td className="px-3 py-2">{t.holding_period_days}d</td><td className="px-3 py-2">{t.quantity}</td><td className="px-3 py-2">{usd(t.position_size)}</td><td className="px-3 py-2">{t.entry_signal} / {t.exit_signal}</td><td className="px-3 py-2">{t.strategy_name}</td><td className="px-3 py-2">{t.regime}</td><td className="px-3 py-2">{pct(t.ai_confidence)}</td><td className="px-3 py-2">{t.risk_reward}</td><td className="px-3 py-2">{t.stop_loss ? usd(t.stop_loss) : "n/a"}</td><td className="px-3 py-2">{t.take_profit ? usd(t.take_profit) : "n/a"}</td><td className="px-3 py-2">{t.gross_pnl ? usd(t.gross_pnl) : "open"}</td><td className="px-3 py-2">{t.net_pnl ? usd(t.net_pnl) : "open"}</td><td className="px-3 py-2">{usd(String(Number(t.commission) + Number(t.slippage)))}</td><td className="px-3 py-2">{t.notes}</td></tr>)}</tbody></table></div>;
}

function AnalyticsGrid({ report }: Readonly<{ report: ResearchReport }>) {
  return <div className="space-y-4"><PortfolioMetricGrid portfolio={report.portfolio} /><EquityVisualization report={report} /><BacktestGrid backtests={report.backtests} portfolio={report.portfolio} /><TradeJournal backtests={report.backtests} portfolio={report.portfolio} /></div>;
}

function PortfolioGrid({ report }: Readonly<{ report: ResearchReport }>) {
  return <div className="space-y-4"><PortfolioMetricGrid portfolio={report.portfolio} /><HoldingsTable holdings={report.portfolio.holdings} /><EquityVisualization report={report} /><BacktestGrid backtests={report.backtests} portfolio={report.portfolio} /></div>;
}

function DashboardResearch({ report }: Readonly<{ report: ResearchReport }>) {
  return <div className="space-y-4"><PortfolioMetricGrid portfolio={report.portfolio} /><SummaryStrip items={[["Today's signals", String(report.candidates.filter((c) => c.action !== "HOLD").length)], ["Open trades", String(report.portfolio.open_positions)], ["Recent trades", String(report.portfolio.closed_trades)], ["Market regime", report.backtests[0]?.trades.at(-1)?.regime ?? "Research"]]} /><CandidateGrid candidates={report.candidates} generatedAt={report.generated_at} optionsWatchlist={report.options_watchlist} /></div>;
}

function StockResearch({ report }: Readonly<{ report: ResearchReport }>) {
  return <div className="grid gap-3 md:grid-cols-2">{report.backtests.map((b) => <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={b.symbol}><p className="text-lg font-semibold">{b.symbol}</p><dl className="mt-3 grid gap-2 text-xs text-terminal-muted"><Row k="Current price" v={usd(b.trades.at(-1)?.exit_price ?? b.trades.at(-1)?.entry_price ?? "0")} /><Row k="Trend" v={Number(b.total_return) > 0 ? "Positive" : "Negative"} /><Row k="Market regime" v={b.trades.at(-1)?.regime ?? "Research"} /><Row k="Volatility" v={pct(b.volatility)} /><Row k="AI score" v={String(Math.round(Number(b.win_rate) * 100))} /><Row k="Risk score" v={String(Math.round(Math.abs(Number(b.max_drawdown)) * 100))} /><Row k="Signal confidence" v={pct(String(Math.max(...report.candidates.filter((c) => c.symbol === b.symbol).map((c) => Number(c.confidence)), 0)))} /><Row k="Support" v={usd(String(Number(b.ending_equity) * 0.97))} /><Row k="Resistance" v={usd(String(Number(b.ending_equity) * 1.06))} /></dl><p className="mt-3 text-xs text-terminal-muted">AI explanation: this symbol is evaluated with trend, momentum, risk and benchmark context. BUY/HOLD/SELL depends on SMA trend alignment, 20-day momentum, and current open-position state.</p></div>)}</div>;
}

function PortfolioMetricGrid({ portfolio }: Readonly<{ portfolio: Portfolio }>) {
  const cards: [string, string][] = [["Portfolio Value", usd(portfolio.ending_equity)], ["Cash", usd(portfolio.cash)], ["Invested", usd(portfolio.invested)], ["Today's PnL", usd(portfolio.today_pnl)], ["Total Return", pct(portfolio.total_return)], ["Annualized Return", pct(portfolio.annualized_return)], ["Open Positions", String(portfolio.open_positions)], ["Closed Positions", String(portfolio.closed_trades)], ["Win Rate", pct(portfolio.win_rate)], ["Profit Factor", portfolio.profit_factor], ["Sharpe Ratio", portfolio.sharpe_ratio], ["Sortino Ratio", portfolio.sortino_ratio], ["Max Drawdown", pct(portfolio.max_drawdown)], ["Calmar Ratio", portfolio.calmar_ratio], ["Expectancy", usd(portfolio.expectancy)], ["Average Winner", usd(portfolio.average_winner)], ["Average Loser", usd(portfolio.average_loser)], ["Risk Score", portfolio.risk_score]];
  return <SummaryStrip items={cards} />;
}

function HoldingsTable({ holdings }: Readonly<{ holdings: Holding[] }>) {
  if (holdings.length === 0) return <p className="text-sm text-terminal-muted">No open holdings in the current research portfolio.</p>;
  const headers = ["Ticker", "Position", "Shares", "Average Cost", "Current Price", "Market Value", "Unrealized PnL", "Realized PnL", "Today's Change", "Weight %", "Risk Score", "AI Score", "Confidence", "Sector", "Industry", "Stop Loss", "Target", "Holding Days", "Status"];
  return <div className="overflow-x-auto rounded-xl border border-terminal-border"><table className="w-full min-w-[1500px] text-left text-xs text-terminal-muted"><thead className="bg-black/30 text-terminal-text"><tr>{headers.map((h) => <th className="px-3 py-2" key={h}>{h}</th>)}</tr></thead><tbody>{holdings.map((h) => <tr className="border-t border-terminal-border" key={h.symbol}><td className="px-3 py-2 text-terminal-text">{h.symbol}</td><td className="px-3 py-2">{h.position}</td><td className="px-3 py-2">{h.shares}</td><td className="px-3 py-2">{usd(h.average_cost)}</td><td className="px-3 py-2">{usd(h.current_price)}</td><td className="px-3 py-2">{usd(h.market_value)}</td><td className="px-3 py-2">{usd(h.unrealized_pnl)}</td><td className="px-3 py-2">{usd(h.realized_pnl)}</td><td className="px-3 py-2">{usd(h.today_change)}</td><td className="px-3 py-2">{pct(h.weight)}</td><td className="px-3 py-2">{h.risk_score}</td><td className="px-3 py-2">{h.ai_score}</td><td className="px-3 py-2">{pct(h.confidence)}</td><td className="px-3 py-2">{h.sector}</td><td className="px-3 py-2">{h.industry}</td><td className="px-3 py-2">{h.stop_loss ? usd(h.stop_loss) : "n/a"}</td><td className="px-3 py-2">{h.take_profit ? usd(h.take_profit) : "n/a"}</td><td className="px-3 py-2">{h.holding_days}</td><td className="px-3 py-2">{h.status}</td></tr>)}</tbody></table></div>;
}

function EquityVisualization({ report }: Readonly<{ report: ResearchReport }>) {
  const points = report.portfolio.equity_curve.slice(-30);
  return <div className="rounded-xl border border-terminal-border bg-black/20 p-4"><p className="font-medium">Portfolio Equity / Drawdown / Daily PnL</p><div className="mt-4 grid h-36 grid-cols-[repeat(30,minmax(0,1fr))] items-end gap-1">{points.map((point) => <div className="bg-terminal-accent/70" key={point.session} style={{ height: `${Math.max(4, Math.min(100, 50 + Number(point.daily_return) * 500))}%` }} title={`${point.session} equity ${point.equity}`} />)}</div><div className="mt-4 grid gap-3 md:grid-cols-3"><MiniSeries label="Equity curve" points={points.map((p) => p.equity)} /><MiniSeries label="Drawdown curve" points={points.map((p) => p.drawdown)} /><MiniSeries label="Daily PnL" points={points.map((p) => p.daily_pnl)} /></div></div>;
}

function MiniSeries({ label, points }: Readonly<{ label: string; points: string[] }>) {
  return <div className="rounded-lg border border-terminal-border bg-black/20 p-3"><p className="text-xs text-terminal-muted">{label}</p><p className="mt-2 text-sm">{points.at(0) ?? "0"} → {points.at(-1) ?? "0"}</p></div>;
}

function BenchmarkTable({ backtests }: Readonly<{ backtests: Backtest[] }>) {
  const rows = backtests.flatMap((b) => b.benchmark_comparisons.map((item) => ({ symbol: b.symbol, ...item })));
  return <div className="overflow-x-auto rounded-xl border border-terminal-border"><table className="w-full min-w-[900px] text-left text-xs text-terminal-muted"><thead className="bg-black/30 text-terminal-text"><tr>{["Strategy", "Benchmark", "Strategy Return", "Benchmark Return", "Outperformance", "Benchmark DD", "Risk"].map((h) => <th className="px-3 py-2" key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((r) => <tr className="border-t border-terminal-border" key={`${r.symbol}-${r.benchmark}`}><td className="px-3 py-2 text-terminal-text">{r.symbol}</td><td className="px-3 py-2">{r.benchmark}</td><td className="px-3 py-2">{pct(r.strategy_return)}</td><td className="px-3 py-2">{pct(r.benchmark_return)}</td><td className="px-3 py-2">{pct(r.outperformance)}</td><td className="px-3 py-2">{pct(r.benchmark_drawdown)}</td><td className="px-3 py-2">{r.risk_label}</td></tr>)}</tbody></table></div>;
}

function OptionsWatchPanel({ optionsWatchlist }: Readonly<{ optionsWatchlist: OptionsWatch[] }>) { if (optionsWatchlist.length === 0) return <p className="text-sm text-terminal-muted">No unusual-options watch candidates. Options execution is still disabled.</p>; return <div><h3 className="mb-3 text-sm font-semibold text-terminal-accent">Options Foundation Watch</h3><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{optionsWatchlist.map((candidate) => <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-4" key={candidate.symbol}><div className="flex justify-between"><p className="font-medium">{candidate.symbol}</p><span className="text-amber-200">{candidate.watch_type}</span></div><dl className="mt-3 grid gap-2 text-xs text-terminal-muted"><Row k="Underlying" v={candidate.underlying_action} /><Row k="Urgency" v={pct(candidate.urgency)} /><Row k="Close" v={usd(candidate.underlying_last_close)} /><Row k="Notional" v={usd(candidate.suggested_underlying_notional)} /><Row k="Greeks / IV" v="planned" /><Row k="OI / PCR" v="planned" /></dl><ul className="mt-3 list-disc space-y-1 pl-4 text-[11px] text-terminal-muted">{candidate.rationale.map((rationale) => <li key={rationale}>{rationale}</li>)}</ul></div>)}</div></div>; }
function SummaryStrip({ items }: Readonly<{ items: [string, string][] }>) { return <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">{items.map(([label, value]) => <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={label}><p className="text-xs uppercase tracking-[0.2em] text-terminal-muted">{label}</p><p className="mt-2 font-medium">{value}</p></div>)}</div>; }
function Row({ k, v }: Readonly<{ k: string; v: string }>) { return <div className="flex justify-between gap-3 text-xs text-terminal-muted"><dt>{k}</dt><dd className="text-right text-terminal-text">{v}</dd></div>; }
function Badge({ value }: Readonly<{ value: Candidate["action"] }>) { return <span className={value === "BUY" ? "text-emerald-300" : value === "SELL" ? "text-red-300" : "text-terminal-muted"}>{value}</span>; }
function usd(value: string) { const numericValue = Number(value); return Number.isFinite(numericValue) ? numericValue.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }) : value; }
function pct(value: string) { const numericValue = Number(value); return Number.isFinite(numericValue) ? `${(numericValue * 100).toFixed(2)}%` : value; }
