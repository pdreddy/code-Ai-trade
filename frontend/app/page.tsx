import { DailyResearchReport } from "@/components/daily-research-report";
import { PagePanel } from "@/components/page-panel";
import { StatusGrid } from "@/components/status-grid";
import { TerminalShell } from "@/components/terminal-shell";
import { backendCapabilities, supportedUniverse } from "@/lib/platform-data";

export default function HomePage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Live research dashboard backed by real OHLCV provider data, $10,000 paper capital, signal-on-close decisions, and fill-next-open simulated executions."
        eyebrow="Dashboard"
        title="Research Platform Status"
      >
        <><StatusGrid capabilities={backendCapabilities} /><div className="mt-6"><DailyResearchReport view="dashboard" /></div></>
      </PagePanel>
      <PagePanel
        description="The platform is designed for broad equity and ETF coverage without hard-coding provider behavior into the UI."
        eyebrow="Universe"
        title="Supported Research Universe"
      >
        <div className="flex flex-wrap gap-3">
          {supportedUniverse.map((symbol) => (
            <span className="rounded-lg border border-terminal-border bg-black/20 px-4 py-2 text-sm" key={symbol}>
              {symbol}
            </span>
          ))}
        </div>
      </PagePanel>
    </TerminalShell>
  );
}
