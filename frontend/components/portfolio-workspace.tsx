"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
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
  fetchPortfolioExecution,
  fetchPortfolioStrategyScreen,
  fetchStrategyOptions,
  type PortfolioExecution,
  type PortfolioTrade,
  type StrategyOption,
  type UniverseStrategyScreen
} from "@/lib/api";

// Three years balances a meaningful trade history against the cost of running the
// whole universe on demand; the single-symbol Backtests tab covers deeper history.
// It's also comfortably enough underlying data for the 1M-1Y display windows below.
const FETCH_DAYS = 1095;
const DEFAULT_CAPITAL = 10000;
const DEFAULT_STRATEGY = "master";

type PortfolioState = {
  data: PortfolioExecution | null;
  loading: boolean;
  error: string | null;
  strategy: string;
  setStrategy: (key: string) => void;
  reload: (force?: boolean) => void;
};

function usePortfolio(days = FETCH_DAYS): PortfolioState {
  const [data, setData] = useState<PortfolioExecution | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [strategy, setStrategy] = useState(DEFAULT_STRATEGY);

  const load = useCallback(
    async (strategyKey: string, force = false) => {
      setLoading(true);
      setError(null);
      try {
        setData(await fetchPortfolioExecution(DEFAULT_CAPITAL, days, strategyKey, { force }));
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
    void load(strategy, false);
  }, [strategy, load]);

  return {
    data,
    loading,
    error,
    strategy,
    setStrategy,
    reload: (force = true) => void load(strategy, force)
  };
}

// ---------------------------------------------------------------------------
// Trailing-window filter — a pure client-side zoom into the already-executed
// track record. No re-fetch is needed to change the window: the equity curve,
// trade blotter, and derived stats (success rate, P&L, drawdown) are recomputed
// from the same execution result that's already in memory.
// ---------------------------------------------------------------------------

type WindowOption = { label: string; days: number };

// days: 0 means "All" (no trailing cutoff — full fetched history).
const WINDOW_OPTIONS: WindowOption[] = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "All", days: 0 }
];
const DEFAULT_WINDOW_DAYS = 180;

type SymbolWindow = {
  tradeCount: number;
  winning: number;
  losing: number;
  successRate: number;
  realizedPnl: number;
};

type WindowedView = {
  equityCurve: { on: string; equity: string }[];
  trades: PortfolioTrade[];
  tradeCount: number;
  winningTrades: number;
  losingTrades: number;
  successRate: number;
  realizedPnl: number;
  maxDrawdown: number;
  startEquity: number;
  endEquity: number;
  windowReturn: number;
  bySymbol: Record<string, SymbolWindow>;
};

function computeMaxDrawdown(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  let peak = values[0];
  let worst = 0;
  for (const value of values) {
    peak = Math.max(peak, value);
    if (peak > 0) {
      worst = Math.min(worst, value / peak - 1);
    }
  }
  return worst;
}

function computeWindow(data: PortfolioExecution, windowDays: number): WindowedView {
  const curve = data.equity_curve;
  const cutoffIso = (() => {
    if (windowDays <= 0 || curve.length === 0) {
      return null;
    }
    const cutoff = new Date(curve[curve.length - 1].on);
    cutoff.setDate(cutoff.getDate() - windowDays);
    return cutoff.toISOString().slice(0, 10);
  })();

  const equityCurve = cutoffIso ? curve.filter((point) => point.on >= cutoffIso) : curve;
  const trades = cutoffIso
    ? data.trades.filter((trade) => (trade.exit_at ?? trade.entry_at).slice(0, 10) >= cutoffIso)
    : data.trades;

  const realized = trades
    .map((trade) => (trade.realized_pnl ? Number(trade.realized_pnl) : null))
    .filter((value): value is number => value !== null);
  const winningTrades = realized.filter((value) => value > 0).length;
  const losingTrades = realized.filter((value) => value < 0).length;
  const closed = winningTrades + losingTrades;
  const realizedPnl = realized.reduce((sum, value) => sum + value, 0);

  const startEquity = equityCurve.length ? Number(equityCurve[0].equity) : Number(data.total_equity);
  const endEquity = equityCurve.length
    ? Number(equityCurve[equityCurve.length - 1].equity)
    : Number(data.total_equity);

  const bySymbol: Record<string, SymbolWindow> = {};
  for (const trade of trades) {
    const pnl = trade.realized_pnl ? Number(trade.realized_pnl) : null;
    const bucket = bySymbol[trade.symbol] ?? {
      tradeCount: 0,
      winning: 0,
      losing: 0,
      successRate: 0,
      realizedPnl: 0
    };
    bucket.tradeCount += 1;
    if (pnl !== null) {
      bucket.realizedPnl += pnl;
      if (pnl > 0) bucket.winning += 1;
      if (pnl < 0) bucket.losing += 1;
    }
    bySymbol[trade.symbol] = bucket;
  }
  for (const bucket of Object.values(bySymbol)) {
    const symbolClosed = bucket.winning + bucket.losing;
    bucket.successRate = symbolClosed ? bucket.winning / symbolClosed : 0;
  }

  return {
    equityCurve,
    trades,
    tradeCount: trades.length,
    winningTrades,
    losingTrades,
    successRate: closed ? winningTrades / closed : 0,
    realizedPnl,
    maxDrawdown: computeMaxDrawdown(equityCurve.map((point) => Number(point.equity))),
    startEquity,
    endEquity,
    windowReturn: startEquity > 0 ? endEquity / startEquity - 1 : 0,
    bySymbol
  };
}

function usePortfolioWindow() {
  const state = usePortfolio();
  const [windowDays, setWindowDays] = useState(DEFAULT_WINDOW_DAYS);
  const view = useMemo(
    () => (state.data ? computeWindow(state.data, windowDays) : null),
    [state.data, windowDays]
  );
  return { state, windowDays, setWindowDays, view };
}

function WindowSelector({
  value,
  onChange,
  disabled
}: Readonly<{ value: number; onChange: (days: number) => void; disabled: boolean }>) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs uppercase tracking-wide text-terminal-muted">Window</span>
      {WINDOW_OPTIONS.map((option) => (
        <button
          className={`rounded-md border px-3 py-1 text-xs transition disabled:opacity-50 ${
            option.days === value
              ? "border-terminal-accent bg-terminal-accent/10 text-terminal-accent"
              : "border-terminal-border bg-black/20 text-terminal-muted hover:border-terminal-accent hover:text-terminal-accent"
          }`}
          disabled={disabled}
          key={option.label}
          onClick={() => onChange(option.days)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
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
  state,
  windowDays,
  onWindowChange
}: Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  state: PortfolioState;
  windowDays: number;
  onWindowChange: (days: number) => void;
}>) {
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
      <div className="mt-4">
        <WindowSelector disabled={state.loading} onChange={onWindowChange} value={windowDays} />
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
  const { state, windowDays, setWindowDays, view } = usePortfolioWindow();
  const { data, loading, error, strategy, setStrategy } = state;

  const [strategyOptions, setStrategyOptions] = useState<StrategyOption[]>([]);
  useEffect(() => {
    fetchStrategyOptions()
      .then(setStrategyOptions)
      .catch(() => setStrategyOptions([]));
  }, []);

  const [screen, setScreen] = useState<UniverseStrategyScreen | null>(null);
  const [screenLoading, setScreenLoading] = useState(false);
  const [screenError, setScreenError] = useState<string | null>(null);
  const runScreen = useCallback(async () => {
    setScreenLoading(true);
    setScreenError(null);
    try {
      setScreen(await fetchPortfolioStrategyScreen());
    } catch (caught) {
      setScreen(null);
      setScreenError(
        caught instanceof ApiError ? caught.message : "Unexpected error screening strategies."
      );
    } finally {
      setScreenLoading(false);
    }
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        description="The AI master decision is executed on every symbol in the research universe from one shared $10,000 base (signal-on-close, fill-next-open). Total equity, cash, and invested reflect the current state; use Window to zoom the equity curve and win/loss stats into the trailing 1M-1Y."
        eyebrow="Portfolio"
        onWindowChange={setWindowDays}
        state={state}
        title="Portfolio And Risk Monitor"
        windowDays={windowDays}
      />

      {strategyOptions.length ? (
        <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-4 shadow-2xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-terminal-muted">Strategy</span>
            {strategyOptions.map((option) => (
              <button
                className={`rounded-md border px-3 py-1 text-xs transition disabled:opacity-50 ${
                  option.key === strategy
                    ? "border-terminal-accent bg-terminal-accent/10 text-terminal-accent"
                    : "border-terminal-border bg-black/20 text-terminal-muted hover:border-terminal-accent hover:text-terminal-accent"
                }`}
                disabled={loading}
                key={option.key}
                onClick={() => setStrategy(option.key)}
                title={option.description}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Executing the strategy across the universe…" /> : null}

      {data && view ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total equity (current)" value={formatCurrency(data.total_equity)} />
              <Stat label="Cash (current)" value={formatCurrency(data.cash)} />
              <Stat label="Invested (current)" value={formatCurrency(data.invested)} />
              <Stat
                label="Max drawdown (window)"
                value={formatPercent(view.maxDrawdown)}
              />
              <Stat
                label="Window P&L"
                value={formatCurrency(view.realizedPnl)}
                tone={view.realizedPnl >= 0 ? "up" : "down"}
              />
              <Stat
                label="Window return"
                value={formatSignedPercent(view.windowReturn)}
                tone={view.windowReturn >= 0 ? "up" : "down"}
              />
              <Stat label="Window success rate" value={formatPercent(view.successRate)} />
              <Stat
                label="Window closed trades"
                value={`${view.winningTrades}W / ${view.losingTrades}L`}
              />
            </div>
            <div className="mt-4">
              <Sparkline values={view.equityCurve.map((point) => Number(point.equity))} />
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
                        <td className="py-2 pr-4 font-semibold">
                          <Link className="hover:text-terminal-accent" href={`/stocks?symbol=${sleeve.symbol}`}>
                            {sleeve.symbol}
                          </Link>
                        </td>
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

          <UniverseStrategyScreenerSection
            currentStrategy={strategy}
            error={screenError}
            loading={screenLoading}
            onApply={setStrategy}
            onRun={() => void runScreen()}
            screen={screen}
          />
        </>
      ) : null}

      {!loading && !error && !data ? (
        <EmptyState message="No portfolio execution could be produced." />
      ) : null}
    </div>
  );
}

function UniverseStrategyScreenerSection({
  currentStrategy,
  screen,
  loading,
  error,
  onRun,
  onApply
}: Readonly<{
  currentStrategy: string;
  screen: UniverseStrategyScreen | null;
  loading: boolean;
  error: string | null;
  onRun: () => void;
  onApply: (key: string) => void;
}>) {
  return (
    <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Which strategy is actually winning?</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-terminal-muted">
            Backtests every strategy variant across the whole universe and pools every
            symbol&apos;s real wins/losses into one honest win rate per variant — not
            cherry-picked off a single
            favorable symbol. This does not force or tune a number: some periods may have zero
            variants clearing the threshold, and that is reported as-is.
          </p>
        </div>
        <button
          className="rounded-lg border border-terminal-accent bg-terminal-accent/10 px-4 py-2 text-sm font-medium text-terminal-accent transition hover:bg-terminal-accent/20 disabled:opacity-50"
          disabled={loading}
          onClick={onRun}
          type="button"
        >
          {loading ? "Screening…" : "Compare all strategies"}
        </button>
      </div>

      {error ? (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      ) : null}
      {loading ? (
        <div className="mt-4">
          <LoadingBlock label="Backtesting every strategy across the universe…" />
        </div>
      ) : null}

      {screen ? (
        <>
          <p className="mt-4 text-sm text-terminal-muted">
            {screen.qualifying_count > 0
              ? `${screen.qualifying_count} of ${screen.results.length} strategies clear ${formatPercent(screen.win_rate_threshold)} real, pooled win rate across ${screen.universe.length} symbols.`
              : `No strategy cleared ${formatPercent(screen.win_rate_threshold)} pooled win rate across ${screen.universe.length} symbols — an honest result, not every period has one.`}
          </p>
          <div className="mt-4 overflow-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                <tr>
                  <th className="py-2 pr-4">Strategy</th>
                  <th className="py-2 pr-4 text-right">Pooled win rate</th>
                  <th className="py-2 pr-4 text-right">Trades</th>
                  <th className="py-2 pr-4 text-right">Symbols</th>
                  <th className="py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {screen.results.map((item) => {
                  const winRate = Number(item.win_rate);
                  const isCurrent = item.key === currentStrategy;
                  const isBest = item.key === screen.best_key;
                  return (
                    <tr className="border-t border-terminal-border/60" key={item.key}>
                      <td className="py-2 pr-4">
                        <span className="font-semibold">{item.label}</span>
                        {isBest ? (
                          <span className="ml-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] uppercase text-emerald-300">
                            Best real result
                          </span>
                        ) : null}
                      </td>
                      <td
                        className={`py-2 pr-4 text-right ${
                          item.meets_threshold ? "text-emerald-300" : ""
                        }`}
                      >
                        {formatPercent(winRate)}
                      </td>
                      <td className="py-2 pr-4 text-right">{item.trade_count}</td>
                      <td className="py-2 pr-4 text-right">{item.symbols_evaluated}</td>
                      <td className="py-2 text-right">
                        {isCurrent ? (
                          <span className="text-xs text-terminal-muted">in use</span>
                        ) : (
                          <button
                            className="rounded-md border border-terminal-border bg-black/20 px-2 py-1 text-xs transition hover:border-terminal-accent hover:text-terminal-accent"
                            onClick={() => onApply(item.key)}
                            type="button"
                          >
                            Use this
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
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
            <Link
              className="mt-3 inline-block text-xs text-terminal-accent hover:underline"
              href={`/options?symbol=${plan.symbol}`}
            >
              View {plan.symbol} 0DTE / weekly options chain →
            </Link>
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
const REASON_TRUNCATE = 46;

function truncate(text: string, limit: number): string {
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

export function PaperTradeBlotter() {
  const { state, windowDays, setWindowDays, view } = usePortfolioWindow();
  const { data, loading, error } = state;

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        description="Every fill the system executed across the research universe from the shared $10,000 base. Each row is a long equity round-trip with its entry, exit, size, realized P&L, and the AI's reasoning. These are stock trades, not options — open the linked options chain for real call/put contracts on that symbol."
        eyebrow="Paper Trades"
        onWindowChange={setWindowDays}
        state={state}
        title="Executed Trade Blotter"
        windowDays={windowDays}
      />

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Executing the strategy across the universe…" /> : null}

      {data && view ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Fills in window" value={formatNumber(view.tradeCount)} />
              <Stat label="Winners" value={formatNumber(view.winningTrades)} tone="up" />
              <Stat label="Losers" value={formatNumber(view.losingTrades)} tone="down" />
              <Stat label="Success rate" value={formatPercent(view.successRate)} />
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-lg font-semibold">Trade blotter</h3>
              <p className="text-xs text-terminal-muted">
                {view.trades.length === 0
                  ? "No round-trip trades in this window"
                  : `Showing latest ${Math.min(BLOTTER_LIMIT, view.trades.length)} of ${formatNumber(
                      view.trades.length
                    )}`}
              </p>
            </div>
            {view.trades.length ? (
              <div className="mt-4 max-h-[32rem] overflow-auto">
                <table className="w-full min-w-[1080px] text-left text-sm">
                  <thead className="sticky top-0 bg-terminal-panel text-xs uppercase tracking-wide text-terminal-muted">
                    <tr>
                      <th className="py-2 pr-4">Symbol</th>
                      <th className="py-2 pr-4">Side</th>
                      <th className="py-2 pr-4">Entry</th>
                      <th className="py-2 pr-4 text-right">Entry px</th>
                      <th className="py-2 pr-4">Exit</th>
                      <th className="py-2 pr-4 text-right">Exit px</th>
                      <th className="py-2 pr-4 text-right">Qty</th>
                      <th className="py-2 pr-4 text-right">P&L</th>
                      <th className="py-2 pr-4">Reason</th>
                      <th className="py-2 text-right">Options</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {[...view.trades]
                      .reverse()
                      .slice(0, BLOTTER_LIMIT)
                      .map((trade, index) => (
                        <TradeRow key={`${trade.symbol}-${trade.entry_at}-${index}`} trade={trade} />
                      ))}
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

function TradeRow({ trade }: Readonly<{ trade: PortfolioTrade }>) {
  const pnl = trade.realized_pnl ? Number(trade.realized_pnl) : null;
  const isOpen = trade.exit_at === null;
  const reason = isOpen ? trade.entry_reason : (trade.exit_reason ?? trade.entry_reason);
  const fullReason = `Entry: ${trade.entry_reason}${
    trade.exit_reason ? ` · Exit: ${trade.exit_reason}` : ""
  }`;
  return (
    <tr className="border-t border-terminal-border/60">
      <td className="py-2 pr-4 font-semibold">{trade.symbol}</td>
      <td className="py-2 pr-4">
        <span
          className={`rounded-full border px-2 py-0.5 text-xs uppercase ${
            isOpen
              ? "border-terminal-accent/40 bg-terminal-accent/10 text-terminal-accent"
              : "border-terminal-border bg-black/20 text-terminal-muted"
          }`}
        >
          {isOpen ? "long · open" : "long · closed"}
        </span>
      </td>
      <td className="py-2 pr-4">{trade.entry_at.slice(0, 10)}</td>
      <td className="py-2 pr-4 text-right">{formatCurrency(trade.entry_price)}</td>
      <td className="py-2 pr-4">{trade.exit_at ? trade.exit_at.slice(0, 10) : "open"}</td>
      <td className="py-2 pr-4 text-right">
        {trade.exit_price ? formatCurrency(trade.exit_price) : "—"}
      </td>
      <td className="py-2 pr-4 text-right">{Number(trade.quantity).toFixed(2)}</td>
      <td
        className={`py-2 pr-4 text-right ${
          pnl === null ? "text-terminal-muted" : pnl >= 0 ? "text-emerald-300" : "text-terminal-danger"
        }`}
      >
        {pnl === null ? "—" : formatCurrency(pnl)}
      </td>
      <td className="py-2 pr-4 text-xs text-terminal-muted" title={fullReason}>
        {truncate(reason, REASON_TRUNCATE)}
      </td>
      <td className="py-2 text-right">
        <Link className="text-terminal-accent hover:underline" href={`/options?symbol=${trade.symbol}`}>
          calls/puts →
        </Link>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Performance analytics
// ---------------------------------------------------------------------------

export function PerformanceAnalytics() {
  const { state, windowDays, setWindowDays, view } = usePortfolioWindow();
  const { data, loading, error } = state;

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        description="Performance attribution computed from the real executed track record across the research universe — success rate, returns, drawdown, and the equity curve for the selected window. No fabricated performance data is shown."
        eyebrow="Analytics"
        onWindowChange={setWindowDays}
        state={state}
        title="Performance Analytics"
        windowDays={windowDays}
      />

      {error ? <ErrorNote message={error} /> : null}
      {loading ? <LoadingBlock label="Executing the strategy across the universe…" /> : null}

      {data && view ? (
        <>
          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">
                  Success rate (window, closed trades)
                </p>
                <p className="mt-1 font-mono text-4xl font-semibold text-terminal-accent">
                  {formatPercent(view.successRate)}
                </p>
                <p className="mt-1 text-xs text-terminal-muted">
                  {view.winningTrades}W / {view.losingTrades}L across {view.tradeCount} trades
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs uppercase tracking-[0.28em] text-terminal-muted">
                  Window return
                </p>
                <p
                  className={`mt-1 font-mono text-2xl ${
                    view.windowReturn >= 0 ? "text-emerald-300" : "text-terminal-danger"
                  }`}
                >
                  {formatSignedPercent(view.windowReturn)}
                </p>
                <p className="mt-1 text-xs text-terminal-muted">
                  {formatCurrency(view.startEquity)} → {formatCurrency(view.endEquity)}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Sparkline values={view.equityCurve.map((point) => Number(point.equity))} />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Window P&L" value={formatCurrency(view.realizedPnl)} />
              <Stat label="Window max drawdown" value={formatPercent(view.maxDrawdown)} />
              <Stat label="Winners" value={formatNumber(view.winningTrades)} />
              <Stat label="Losers" value={formatNumber(view.losingTrades)} />
            </div>
          </section>

          <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
            <h3 className="text-lg font-semibold">Success rate by symbol (window)</h3>
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-terminal-muted">
                  <tr>
                    <th className="py-2 pr-4">Symbol</th>
                    <th className="py-2 pr-4 text-right">Trades</th>
                    <th className="py-2 pr-4 text-right">Win rate</th>
                    <th className="py-2 text-right">Realized P&L</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.sleeves.map((sleeve) => {
                    const symbolView = view.bySymbol[sleeve.symbol];
                    const pnl = symbolView?.realizedPnl ?? 0;
                    return (
                      <tr className="border-t border-terminal-border/60" key={sleeve.symbol}>
                        <td className="py-2 pr-4 font-semibold">{sleeve.symbol}</td>
                        <td className="py-2 pr-4 text-right">{symbolView?.tradeCount ?? 0}</td>
                        <td className="py-2 pr-4 text-right">
                          {symbolView ? formatPercent(symbolView.successRate) : "—"}
                        </td>
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
          </section>
        </>
      ) : null}

      {!loading && !error && !data ? (
        <EmptyState message="No analytics could be produced." />
      ) : null}
    </div>
  );
}
