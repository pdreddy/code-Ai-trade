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
  { href: "/options", label: "Options", description: "0DTE & weekly options desk" },
  { href: "/paper-trades", label: "Paper Trades", description: "Paper broker activity" },
  { href: "/portfolio", label: "Portfolio", description: "Cash, exposure, risk" },
  { href: "/analytics", label: "Analytics", description: "Performance attribution" }
];

// The "Magnificent Seven" mega-cap tech names.
export const supportedUniverse = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"];

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
    label: "Portfolio execution & analytics",
    status: "ready",
    detail: "The strategy is executed across the universe from one $10,000 base; the Backtests, Portfolio, Paper Trades, and Analytics workspaces render the real executed trades, success rate, holdings, and upcoming planned trades."
  }
];
