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

export class ApiError extends Error {}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiError(
      `Unable to reach the backend at ${apiBaseUrl}. Confirm the API is running and NEXT_PUBLIC_API_BASE_URL is set.`
    );
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
