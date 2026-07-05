// Typed client for the AI Quant backend API.
//
// Numeric fields are serialized by the backend as strings (Decimal precision is
// preserved end-to-end), so they are typed as `string` here and formatted at the
// edge rather than parsed into lossy floats.

// Full API base including the version prefix (matches docker-compose and render.yaml).
export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1";

export type Bar = {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  adjusted_close: string | null;
};

export type MarketData = {
  symbol: string;
  provider: string;
  retrieved_at_utc: string;
  bar_count: number;
  bars: Bar[];
};

export type SignalAction = "buy" | "sell" | "hold";

export type AgentVote = {
  agent_name: string;
  action: SignalAction;
  confidence: string;
  score: string;
  reasons: string[];
};

export type MasterDecision = {
  action: SignalAction;
  confidence: string;
  risk_score: string;
  stop_loss: string | null;
  take_profit: string | null;
  expected_r_multiple: string;
  explanation: string;
};

export type Signals = {
  symbol: string;
  as_of: string;
  latest_close: string;
  bar_count: number;
  votes: AgentVote[];
  master_decision: MasterDecision;
};

export type TradeRecord = {
  entry_at: string;
  entry_price: string;
  exit_at: string | null;
  exit_price: string | null;
  quantity: string;
  realized_pnl: string | null;
  entry_reason: string;
  exit_reason: string | null;
};

export type EquityPoint = {
  timestamp: string;
  equity: string;
};

export type BacktestMetrics = {
  success_rate: string;
  total_return: string;
  cagr: string;
  sharpe: string;
  sortino: string;
  calmar: string;
  profit_factor: string;
  max_drawdown: string;
  exposure: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
};

export type Backtest = {
  symbol: string;
  strategy: string;
  start: string;
  end: string;
  bar_count: number;
  initial_capital: string;
  final_equity: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
  next_signal: MasterDecision | null;
};

export type StrategyOption = {
  key: string;
  label: string;
  description: string;
};

export class ApiError extends Error {}

// The backend proxies to a live market-data provider, so a request can legitimately
// take several seconds; cap it so a stalled upstream surfaces as an error instead of
// an indefinitely blank screen.
const REQUEST_TIMEOUT_MS = 45_000;

async function getJson<T>(path: string, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      cache: "no-store",
      signal: controller.signal
    });
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw new ApiError(
        `Request to ${apiBaseUrl} timed out after ${timeoutMs / 1000}s. The market-data provider may be slow or unreachable.`
      );
    }
    throw new ApiError(
      `Unable to reach the backend at ${apiBaseUrl}. Confirm the API is running and NEXT_PUBLIC_API_BASE_URL is set.`
    );
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error body; fall back to the status text.
    }
    throw new ApiError(`${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

export function fetchMarketData(symbol: string, days = 180): Promise<MarketData> {
  return getJson<MarketData>(
    `/market-data/${encodeURIComponent(symbol)}/history?days=${days}`
  );
}

export function fetchSignals(symbol: string, days = 420): Promise<Signals> {
  return getJson<Signals>(
    `/market-data/${encodeURIComponent(symbol)}/signals?days=${days}`
  );
}

export function fetchBacktest(
  symbol: string,
  days = 1825,
  strategy = "master"
): Promise<Backtest> {
  return getJson<Backtest>(
    `/market-data/${encodeURIComponent(symbol)}/backtest?days=${days}&strategy=${strategy}`
  );
}

let strategyOptionsCache: Promise<StrategyOption[]> | null = null;

export function fetchStrategyOptions(): Promise<StrategyOption[]> {
  strategyOptionsCache ??= getJson<StrategyOption[]>("/market-data/strategies");
  return strategyOptionsCache;
}

export type StrategyScreenResult = {
  key: string;
  label: string;
  description: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string;
  total_return: string;
  max_drawdown: string;
  meets_threshold: boolean;
  next_signal: MasterDecision | null;
};

export type StrategyScreen = {
  symbol: string;
  win_rate_threshold: string;
  qualifying_count: number;
  results: StrategyScreenResult[];
};

export function fetchStrategyScreen(
  symbol: string,
  days = 1825,
  winRateThreshold = 0.8
): Promise<StrategyScreen> {
  return getJson<StrategyScreen>(
    `/market-data/${encodeURIComponent(symbol)}/strategy-screen?days=${days}&win_rate_threshold=${winRateThreshold}`,
    90_000
  );
}

export type PortfolioSleeve = {
  symbol: string;
  allocated: string;
  current_value: string;
  realized_pnl: string;
  return_pct: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string;
  holding: boolean;
  last_close: string;
  next_signal: MasterDecision;
};

export type PortfolioTrade = {
  symbol: string;
  entry_at: string;
  entry_price: string;
  exit_at: string | null;
  exit_price: string | null;
  quantity: string;
  realized_pnl: string | null;
  entry_reason: string;
  exit_reason: string | null;
};

export type PlannedTrade = {
  symbol: string;
  last_close: string;
  action: SignalAction;
  confidence: string;
  risk_score: string;
  stop_loss: string | null;
  take_profit: string | null;
  expected_r_multiple: string;
  explanation: string;
};

export type PortfolioEquityPoint = {
  on: string;
  equity: string;
};

export type SleeveError = {
  symbol: string;
  detail: string;
};

export type PortfolioExecution = {
  generated_at: string;
  initial_capital: string;
  total_equity: string;
  cash: string;
  invested: string;
  total_pnl: string;
  total_return: string;
  success_rate: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
  max_drawdown: string;
  symbol_count: number;
  sleeves: PortfolioSleeve[];
  planned_trades: PlannedTrade[];
  trades: PortfolioTrade[];
  equity_curve: PortfolioEquityPoint[];
  errors: SleeveError[];
};

// Running the strategy across the whole universe fans out several multi-year
// provider fetches, so allow it more headroom than a single-symbol request.
const PORTFOLIO_TIMEOUT_MS = 120_000;

// The Portfolio, Paper Trades, and Analytics tabs are three views of one universe
// execution. Caching the in-flight/last result for a short TTL means moving between
// those tabs reuses a single run instead of re-executing every symbol each time.
const PORTFOLIO_CACHE_TTL_MS = 10 * 60 * 1000;
const portfolioCache = new Map<string, { at: number; value: Promise<PortfolioExecution> }>();

export function fetchPortfolioExecution(
  capital = 10000,
  days = 1825,
  { force = false }: { force?: boolean } = {}
): Promise<PortfolioExecution> {
  const key = `${capital}:${days}`;
  const cached = portfolioCache.get(key);
  if (!force && cached && Date.now() - cached.at < PORTFOLIO_CACHE_TTL_MS) {
    return cached.value;
  }
  const value = getJson<PortfolioExecution>(
    `/portfolio/execute?capital=${capital}&days=${days}`,
    PORTFOLIO_TIMEOUT_MS
  ).catch((error: unknown) => {
    // Don't cache failures — a transient upstream error shouldn't stick.
    portfolioCache.delete(key);
    throw error;
  });
  portfolioCache.set(key, { at: Date.now(), value });
  return value;
}

export type OptionContract = {
  contract_symbol: string;
  option_type: "call" | "put";
  strike: string;
  expiration: string;
  days_to_expiry: number;
  last_price: string | null;
  bid: string | null;
  ask: string | null;
  volume: number;
  open_interest: number;
  implied_volatility: string | null;
  in_the_money: boolean;
  volume_oi_ratio: string;
};

export type UnusualContract = {
  contract: OptionContract;
  volume_oi_ratio: string;
};

export type PlannedOptionTrade = {
  contract: OptionContract;
  rationale: string;
};

export type OptionsResearch = {
  symbol: string;
  underlying_price: string;
  as_of: string;
  max_dte: number;
  near_term_count: number;
  zero_dte_count: number;
  signal: MasterDecision;
  unusual_activity: UnusualContract[];
  planned_trades: PlannedOptionTrade[];
};

export function fetchOptionsResearch(symbol: string, maxDte = 8): Promise<OptionsResearch> {
  return getJson<OptionsResearch>(
    `/options/${encodeURIComponent(symbol)}?max_dte=${maxDte}`
  );
}

export type OptionsStyle = "zero_dte" | "weekly";

export type OptionsTrade = {
  option_side: "call" | "put";
  strike: string;
  expiration: string;
  entry_at: string;
  entry_underlying: string;
  entry_premium: string;
  contracts: number;
  exit_at: string;
  exit_underlying: string;
  exit_premium: string;
  realized_pnl: string;
  entry_reason: string;
  exit_reason: string;
};

export type OptionsBacktestMetrics = {
  win_rate: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
  total_return: string;
  max_drawdown: string;
  profit_factor: string;
};

export type OptionsBacktest = {
  symbol: string;
  style: OptionsStyle;
  modeled: boolean;
  pricing_note: string;
  initial_capital: string;
  final_equity: string;
  metrics: OptionsBacktestMetrics;
  equity_curve: { on: string; equity: string }[];
  trades: OptionsTrade[];
  next_signal: MasterDecision | null;
};

export function fetchOptionsBacktest(
  symbol: string,
  style: OptionsStyle = "weekly",
  days = 1825,
  capital = 10000
): Promise<OptionsBacktest> {
  return getJson<OptionsBacktest>(
    `/options/${encodeURIComponent(symbol)}/backtest?style=${style}&days=${days}&capital=${capital}`,
    PORTFOLIO_TIMEOUT_MS
  );
}

export type OptionsPortfolioSleeve = {
  symbol: string;
  allocated: string;
  final_equity: string;
  return_pct: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string;
  next_signal: MasterDecision | null;
};

export type OptionsPortfolioTrade = {
  symbol: string;
  option_side: "call" | "put";
  strike: string;
  expiration: string;
  entry_at: string;
  entry_underlying: string;
  entry_premium: string;
  contracts: number;
  exit_at: string;
  exit_underlying: string;
  exit_premium: string;
  realized_pnl: string;
  entry_reason: string;
  exit_reason: string;
};

export type OptionsPortfolioExecution = {
  generated_at: string;
  style: OptionsStyle;
  modeled: boolean;
  pricing_note: string;
  initial_capital: string;
  total_equity: string;
  total_pnl: string;
  total_return: string;
  success_rate: string;
  trade_count: number;
  winning_trades: number;
  losing_trades: number;
  max_drawdown: string;
  symbol_count: number;
  sleeves: OptionsPortfolioSleeve[];
  trades: OptionsPortfolioTrade[];
  equity_curve: { on: string; equity: string }[];
  errors: { symbol: string; detail: string }[];
};

const optionsPortfolioCache = new Map<
  string,
  { at: number; value: Promise<OptionsPortfolioExecution> }
>();

export function fetchOptionsPortfolioExecution(
  style: OptionsStyle = "weekly",
  capital = 10000,
  days = 1825,
  { force = false }: { force?: boolean } = {}
): Promise<OptionsPortfolioExecution> {
  const key = `${style}:${capital}:${days}`;
  const cached = optionsPortfolioCache.get(key);
  if (!force && cached && Date.now() - cached.at < PORTFOLIO_CACHE_TTL_MS) {
    return cached.value;
  }
  const value = getJson<OptionsPortfolioExecution>(
    `/options-portfolio/execute?style=${style}&capital=${capital}&days=${days}`,
    PORTFOLIO_TIMEOUT_MS
  ).catch((error: unknown) => {
    optionsPortfolioCache.delete(key);
    throw error;
  });
  optionsPortfolioCache.set(key, { at: Date.now(), value });
  return value;
}

export type LedgerOpenPosition = {
  symbol: string;
  style: OptionsStyle;
  option_side: "call" | "put";
  contract_symbol: string;
  strike: string;
  expiration: string;
  opened_at: string;
  entry_underlying: string;
  entry_premium: string;
  contracts: number;
  entry_reason: string;
  mark_premium: string | null;
  unrealized_pnl: string | null;
};

export type LedgerClosedPosition = {
  symbol: string;
  style: OptionsStyle;
  option_side: "call" | "put";
  contract_symbol: string;
  strike: string;
  expiration: string;
  opened_at: string;
  entry_underlying: string;
  entry_premium: string;
  contracts: number;
  entry_reason: string;
  closed_at: string;
  exit_underlying: string;
  exit_premium: string;
  realized_pnl: string;
  settlement: string;
};

export type LedgerSnapshot = {
  generated_at: string;
  real_quotes: boolean;
  note: string;
  cash_by_symbol: Record<string, string>;
  realized_pnl_total: string;
  open_positions: LedgerOpenPosition[];
  closed_positions: LedgerClosedPosition[];
};

export function fetchOptionsPaperLedger(): Promise<LedgerSnapshot> {
  return getJson<LedgerSnapshot>("/options-portfolio/paper-ledger", PORTFOLIO_TIMEOUT_MS);
}

export async function tickOptionsPaperLedger(
  style: OptionsStyle = "weekly",
  maxDte = 8
): Promise<LedgerSnapshot> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PORTFOLIO_TIMEOUT_MS);
  try {
    const response = await fetch(
      `${apiBaseUrl}/options-portfolio/paper-ledger/tick?style=${style}&max_dte=${maxDte}`,
      { method: "POST", cache: "no-store", signal: controller.signal }
    );
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) {
          detail = body.detail;
        }
      } catch {
        // Non-JSON error body; fall back to the status text.
      }
      throw new ApiError(`${response.status}: ${detail}`);
    }
    return (await response.json()) as LedgerSnapshot;
  } catch (caught) {
    if (caught instanceof ApiError) {
      throw caught;
    }
    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw new ApiError(
        `Request to ${apiBaseUrl} timed out after ${PORTFOLIO_TIMEOUT_MS / 1000}s.`
      );
    }
    throw new ApiError(`Unable to reach the backend at ${apiBaseUrl}.`);
  } finally {
    clearTimeout(timeout);
  }
}

export type WatchlistQuote = {
  symbol: string;
  last_close: string;
  prior_close: string | null;
  change_pct: string | null;
  as_of: string;
  action: SignalAction;
  confidence: string;
};

export type WatchlistErrorEntry = {
  symbol: string;
  detail: string;
};

export type Watchlist = {
  generated_at: string;
  quotes: WatchlistQuote[];
  errors: WatchlistErrorEntry[];
};

// Fanning out real quote+signal fetches across the whole universe takes longer
// than a single-symbol request but is still bounded by the concurrent backend
// fetch, so a shorter cache than the portfolio views is enough to feel snappy.
const WATCHLIST_CACHE_TTL_MS = 5 * 60 * 1000;
let watchlistCache: { at: number; value: Promise<Watchlist> } | null = null;

export function fetchWatchlist({ force = false }: { force?: boolean } = {}): Promise<Watchlist> {
  if (!force && watchlistCache && Date.now() - watchlistCache.at < WATCHLIST_CACHE_TTL_MS) {
    return watchlistCache.value;
  }
  const value = getJson<Watchlist>("/watchlist", PORTFOLIO_TIMEOUT_MS).catch((error: unknown) => {
    watchlistCache = null;
    throw error;
  });
  watchlistCache = { at: Date.now(), value };
  return value;
}

export type ScannedUnusualContract = {
  symbol: string;
  contract: OptionContract;
  volume_oi_ratio: string;
};

export type ScannedPlannedTrade = {
  symbol: string;
  contract: OptionContract;
  rationale: string;
};

export type OptionsScan = {
  generated_at: string;
  symbols_scanned: number;
  unusual_activity: ScannedUnusualContract[];
  planned_trades: ScannedPlannedTrade[];
  errors: { symbol: string; detail: string }[];
};

const SCANNER_CACHE_TTL_MS = 5 * 60 * 1000;
let scannerCache: { at: number; value: Promise<OptionsScan> } | null = null;

export function fetchOptionsScan({ force = false }: { force?: boolean } = {}): Promise<OptionsScan> {
  if (!force && scannerCache && Date.now() - scannerCache.at < SCANNER_CACHE_TTL_MS) {
    return scannerCache.value;
  }
  const value = getJson<OptionsScan>("/scanner", PORTFOLIO_TIMEOUT_MS).catch((error: unknown) => {
    scannerCache = null;
    throw error;
  });
  scannerCache = { at: Date.now(), value };
  return value;
}
