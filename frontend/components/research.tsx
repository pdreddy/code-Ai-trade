"use client";

import { useState } from "react";
import type { SignalAction } from "@/lib/api";

export function formatCurrency(value: string | number): string {
  const numeric = typeof value === "number" ? value : Number(value);
  return numeric.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  });
}

export function formatNumber(value: string | number): string {
  const numeric = typeof value === "number" ? value : Number(value);
  return numeric.toLocaleString("en-US");
}

export function formatPercent(value: string | number, fractionDigits = 1): string {
  const numeric = typeof value === "number" ? value : Number(value);
  return `${(numeric * 100).toFixed(fractionDigits)}%`;
}

export function formatSignedPercent(value: number, fractionDigits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(fractionDigits)}%`;
}

const actionStyles: Record<SignalAction, string> = {
  buy: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  sell: "bg-terminal-danger/10 text-terminal-danger border-terminal-danger/30",
  hold: "bg-terminal-warning/10 text-terminal-warning border-terminal-warning/30"
};

export function ActionBadge({ action }: Readonly<{ action: SignalAction }>) {
  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${actionStyles[action]}`}
    >
      {action}
    </span>
  );
}

export function Sparkline({
  values,
  width = 640,
  height = 120
}: Readonly<{ values: number[]; width?: number; height?: number }>) {
  if (values.length < 2) {
    return null;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values
    .map((value, index) => {
      const x = index * stepX;
      const y = height - ((value - min) / span) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const rising = values[values.length - 1] >= values[0];
  const stroke = rising ? "#38f2af" : "#ff5c7a";
  return (
    <svg
      className="h-32 w-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="Closing price trend"
      viewBox={`0 0 ${width} ${height}`}
    >
      <polyline fill="none" points={points} stroke={stroke} strokeWidth={2} />
    </svg>
  );
}

export const symbolSuggestions = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN"];

export function SymbolBar({
  symbol,
  onSubmit,
  loading
}: Readonly<{ symbol: string; onSubmit: (symbol: string) => void; loading: boolean }>) {
  const [value, setValue] = useState(symbol);
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        const cleaned = value.trim().toUpperCase();
        if (cleaned) {
          onSubmit(cleaned);
        }
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <input
          aria-label="Ticker symbol"
          className="w-40 rounded-lg border border-terminal-border bg-black/30 px-3 py-2 font-mono text-sm uppercase outline-none focus:border-terminal-accent"
          onChange={(event) => setValue(event.target.value)}
          placeholder="Symbol"
          value={value}
        />
        <button
          className="rounded-lg border border-terminal-accent bg-terminal-accent/10 px-4 py-2 text-sm font-medium text-terminal-accent transition hover:bg-terminal-accent/20 disabled:opacity-50"
          disabled={loading}
          type="submit"
        >
          {loading ? "Loading…" : "Load"}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {symbolSuggestions.map((suggestion) => (
          <button
            className="rounded-md border border-terminal-border bg-black/20 px-2.5 py-1 font-mono text-xs text-terminal-muted transition hover:border-terminal-accent hover:text-terminal-accent"
            key={suggestion}
            onClick={() => {
              setValue(suggestion);
              onSubmit(suggestion);
            }}
            type="button"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </form>
  );
}

export function ErrorNote({ message }: Readonly<{ message: string }>) {
  return (
    <div className="rounded-xl border border-terminal-danger/40 bg-terminal-danger/10 p-4 text-sm text-terminal-danger">
      {message}
    </div>
  );
}
