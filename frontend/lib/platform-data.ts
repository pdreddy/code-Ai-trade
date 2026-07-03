export type TerminalPage = {
  href: string;
  label: string;
  description: string;
};

export type Capability = {
  label: string;
  status: "ready" | "planned";
  detail: string;
};

export const terminalPages: TerminalPage[] = [
  { href: "/", label: "Dashboard", description: "Research command center" },
  { href: "/watchlists", label: "Watchlists", description: "Universe monitoring" },
  { href: "/signals", label: "Signals", description: "Agent and master decisions" },
  { href: "/stocks", label: "Stock Details", description: "Instrument research workspace" },
  { href: "/backtests", label: "Backtests", description: "Event-driven simulations" },
  { href: "/paper-trades", label: "Paper Trades", description: "Paper broker activity" },
  { href: "/portfolio", label: "Portfolio", description: "Cash, exposure, risk" },
  { href: "/analytics", label: "Analytics", description: "Performance attribution" }
];

export const supportedUniverse = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN"];

export const backendCapabilities: Capability[] = [
  {
    label: "Market data foundation",
    status: "ready",
    detail: "Provider contracts, Yahoo adapter, storage models, and ingestion lineage are implemented."
  },
  {
    label: "AI research agents",
    status: "ready",
    detail: "Trend, momentum, volatility, risk, portfolio, mean reversion, breakout, support/resistance, volume, and regime agents are implemented."
  },
  {
    label: "Master AI decisions",
    status: "ready",
    detail: "Agent votes aggregate into deterministic decisions with confidence, risk score, stops, targets, and explanations."
  },
  {
    label: "Event-driven backtester",
    status: "ready",
    detail: "Signal-on-close and fill-next-open execution is enforced with equity, drawdown, monthly returns, and trade metrics."
  },
  {
    label: "Paper broker",
    status: "ready",
    detail: "Pending, filled, cancelled, and rejected paper order lifecycle is implemented in the application layer."
  },
  {
    label: "Risk engine",
    status: "ready",
    detail: "Kill switch, exposure, risk-per-trade, drawdown, liquidity, and correlation checks are implemented."
  },
  {
    label: "Market data & signals API",
    status: "ready",
    detail: "Live endpoints serve real provider bars and run the agents plus master decision on demand; the Stock Details and Signals workspaces render them."
  },
  {
    label: "Backtest, paper-trade & portfolio persistence",
    status: "planned",
    detail: "Those workspaces stay honest empty states until result persistence adapters are added; no fabricated data is shown."
  }
];
