"use client";

import { useEffect, useState } from "react";

type ReadinessGap = {
  area: string;
  status: string;
  severity: "critical" | "high" | "medium" | "low" | string;
  impact: string;
  required_next_step: string;
};

type ReadinessState =
  | { status: "loading"; gaps: null; error: null }
  | { status: "ready"; gaps: ReadinessGap[]; error: null }
  | { status: "error"; gaps: null; error: string };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function PlatformReadiness() {
  const [state, setState] = useState<ReadinessState>({ status: "loading", gaps: null, error: null });

  useEffect(() => {
    let cancelled = false;

    async function loadGaps() {
      try {
        const response = await fetch(`${apiBaseUrl}/platform/readiness-gaps`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error(`readiness gaps failed with HTTP ${response.status}`);
        const gaps = (await response.json()) as ReadinessGap[];
        if (!cancelled) setState({ status: "ready", gaps, error: null });
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            gaps: null,
            error: error instanceof Error ? error.message : "readiness gaps failed",
          });
        }
      }
    }

    void loadGaps();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return <p className="text-sm text-terminal-muted">Loading production-readiness gap matrix...</p>;
  }

  if (state.status === "error") {
    return <p className="text-sm text-terminal-muted">Readiness matrix unavailable: {state.error}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-terminal-border">
      <table className="w-full min-w-[980px] text-left text-xs text-terminal-muted">
        <thead className="bg-black/30 text-terminal-text">
          <tr>
            {[
              "Area",
              "Status",
              "Severity",
              "Current impact",
              "Required next step",
            ].map((header) => (
              <th className="px-3 py-2" key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {state.gaps.map((gap) => (
            <tr className="border-t border-terminal-border" key={gap.area}>
              <td className="px-3 py-3 text-terminal-text">{gap.area}</td>
              <td className="px-3 py-3">{gap.status}</td>
              <td className={severityClassName(gap.severity)}>{gap.severity}</td>
              <td className="px-3 py-3">{gap.impact}</td>
              <td className="px-3 py-3">{gap.required_next_step}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function severityClassName(severity: string) {
  if (severity === "critical") return "px-3 py-3 text-red-300";
  if (severity === "high") return "px-3 py-3 text-amber-200";
  return "px-3 py-3 text-sky-200";
}
