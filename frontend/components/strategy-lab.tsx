"use client";

import { useEffect, useState } from "react";

type Run = { strategy: string; symbol: string; total_return: string; annualized_return: string; sharpe_ratio: string; max_drawdown: string; win_rate: string; profit_factor: string; trade_count: number; exposure: string; score: string };
type Walk = { strategy: string; symbol: string; window: string; start_date: string; end_date: string; return_pct: string; max_drawdown: string };
type Monte = { strategy: string; symbol: string; simulations: number; median_return: string; fifth_percentile: string; ninety_fifth_percentile: string; probability_positive: string };
type Parameter = { symbol: string; short_window: number; long_window: number; total_return: string; sharpe_ratio: string; max_drawdown: string; score: string };
type Feature = { feature: string; importance: string; explanation: string };
type Correlation = { left: string; right: string; correlation: string };
type Regime = { strategy: string; symbol: string; regime: string; observations: number; average_return: string; hit_rate: string };
type Intent = { strategy: string; symbol: string; action: string; planned_execution: string; capital: string; reason: string };
type Lab = { generated_at: string; horizon_years: number; leaderboard: Run[]; walk_forward: Walk[]; monte_carlo: Monte[]; parameter_optimizer: Parameter[]; feature_importance: Feature[]; correlation_heatmap: Correlation[]; regime_performance: Regime[]; paper_export_intents: Intent[] };
type State = { status: "loading"; report: null; error: null } | { status: "ready"; report: Lab; error: null } | { status: "error"; report: null; error: string };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const horizons = [1, 3, 5, 10] as const;

export function StrategyLab() {
  const [horizon, setHorizon] = useState<(typeof horizons)[number]>(5);
  const [state, setState] = useState<State>({ status: "loading", report: null, error: null });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setState({ status: "loading", report: null, error: null });
      try {
        const response = await fetch(`${apiBaseUrl}/strategies/lab?horizon_years=${horizon}&capital=10000`, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`strategy lab failed with HTTP ${response.status}`);
        const report = (await response.json()) as Lab;
        if (!cancelled) setState({ status: "ready", report, error: null });
      } catch (error) {
        if (!cancelled) setState({ status: "error", report: null, error: error instanceof Error ? error.message : "strategy lab failed" });
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [horizon]);

  return <div className="space-y-5"><div className="flex flex-wrap gap-2">{horizons.map((item) => <button className={`rounded-lg border px-4 py-2 text-sm ${item === horizon ? "border-terminal-accent text-terminal-accent" : "border-terminal-border text-terminal-muted"}`} key={item} onClick={() => setHorizon(item)} type="button">Run {item}Y</button>)}</div>{state.status === "loading" ? <p className="text-sm text-terminal-muted">Running provider-backed strategy lab...</p> : state.status === "error" ? <p className="text-sm text-terminal-muted">Provider unavailable: {state.error}. No synthetic strategy results are shown.</p> : <LabReport report={state.report} />}</div>;
}

function LabReport({ report }: Readonly<{ report: Lab }>) {
  return <div className="space-y-5"><Summary items={[["Horizon", `${report.horizon_years}Y`], ["Generated", report.generated_at.slice(0, 10)], ["Strategies ranked", String(report.leaderboard.length)], ["Paper exports", String(report.paper_export_intents.length)]]} /><Leaderboard runs={report.leaderboard} /><Optimizer rows={report.parameter_optimizer} /><WalkForward rows={report.walk_forward} /><MonteCarlo rows={report.monte_carlo} /><FeatureImportance rows={report.feature_importance} /><CorrelationHeatmap rows={report.correlation_heatmap} /><Regime rows={report.regime_performance} /><PaperExport rows={report.paper_export_intents} /></div>;
}

function Leaderboard({ runs }: Readonly<{ runs: Run[] }>) { return <Table title="Strategy Leaderboard" headers={["Rank", "Strategy", "Symbol", "Return", "Ann.", "Sharpe", "Max DD", "Win", "PF", "Trades", "Exposure", "Score"]} rows={runs.slice(0, 12).map((r, index) => [String(index + 1), r.strategy, r.symbol, pct(r.total_return), pct(r.annualized_return), r.sharpe_ratio, pct(r.max_drawdown), pct(r.win_rate), r.profit_factor, String(r.trade_count), pct(r.exposure), r.score])} />; }
function Optimizer({ rows }: Readonly<{ rows: Parameter[] }>) { return <Table title="Parameter Optimizer" headers={["Symbol", "Short", "Long", "Return", "Sharpe", "Max DD", "Score"]} rows={rows.map((r) => [r.symbol, String(r.short_window), String(r.long_window), pct(r.total_return), r.sharpe_ratio, pct(r.max_drawdown), r.score])} />; }
function WalkForward({ rows }: Readonly<{ rows: Walk[] }>) { return <Table title="Walk-Forward Optimization" headers={["Strategy", "Symbol", "Window", "Period", "Return", "Max DD"]} rows={rows.map((r) => [r.strategy, r.symbol, r.window, `${r.start_date} → ${r.end_date}`, pct(r.return_pct), pct(r.max_drawdown)])} />; }
function MonteCarlo({ rows }: Readonly<{ rows: Monte[] }>) { return <Table title="Monte Carlo Simulation" headers={["Strategy", "Symbol", "Runs", "Median", "5th %", "95th %", "P(+) "]} rows={rows.map((r) => [r.strategy, r.symbol, String(r.simulations), pct(r.median_return), pct(r.fifth_percentile), pct(r.ninety_fifth_percentile), pct(r.probability_positive)])} />; }
function FeatureImportance({ rows }: Readonly<{ rows: Feature[] }>) { return <Table title="Feature Importance / AI Explainability" headers={["Feature", "Importance", "Explanation"]} rows={rows.map((r) => [r.feature, pct(r.importance), r.explanation])} />; }
function CorrelationHeatmap({ rows }: Readonly<{ rows: Correlation[] }>) { return <Table title="Correlation Heatmap" headers={["Left", "Right", "Correlation"]} rows={rows.map((r) => [r.left, r.right, r.correlation])} />; }
function Regime({ rows }: Readonly<{ rows: Regime[] }>) { return <Table title="Regime-Based Performance" headers={["Strategy", "Symbol", "Regime", "Obs", "Avg Return", "Hit Rate"]} rows={rows.map((r) => [r.strategy, r.symbol, r.regime, String(r.observations), pct(r.average_return), pct(r.hit_rate)])} />; }
function PaperExport({ rows }: Readonly<{ rows: Intent[] }>) { return <Table title="Export to Paper Trading Intents" headers={["Strategy", "Symbol", "Action", "Execution", "Capital", "Reason"]} rows={rows.map((r) => [r.strategy, r.symbol, r.action, r.planned_execution, usd(r.capital), r.reason])} />; }

function Table({ title, headers, rows }: Readonly<{ title: string; headers: string[]; rows: string[][] }>) { return <div className="overflow-x-auto rounded-xl border border-terminal-border"><div className="bg-black/30 px-4 py-3 font-medium">{title}</div><table className="w-full min-w-[900px] text-left text-xs text-terminal-muted"><thead className="bg-black/20 text-terminal-text"><tr>{headers.map((header) => <th className="px-3 py-2" key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr className="border-t border-terminal-border" key={`${title}-${index}`}>{row.map((cell, cellIndex) => <td className="px-3 py-2" key={`${title}-${index}-${cellIndex}`}>{cell}</td>)}</tr>)}</tbody></table></div>; }
function Summary({ items }: Readonly<{ items: [string, string][] }>) { return <div className="grid gap-3 md:grid-cols-4">{items.map(([label, value]) => <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={label}><p className="text-xs uppercase tracking-[0.2em] text-terminal-muted">{label}</p><p className="mt-2 font-medium">{value}</p></div>)}</div>; }
function pct(value: string) { const n = Number(value); return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : value; }
function usd(value: string) { const n = Number(value); return Number.isFinite(n) ? n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }) : value; }
