import { DailyResearchReport } from "@/components/daily-research-report";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

export default function BacktestsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Five-year strategy summaries generated from real OHLCV bars with signal-on-close and fill-next-open semantics."
        eyebrow="Backtests"
        title="Event-Driven Backtest Results"
      >
        <DailyResearchReport view="backtests" />
      </PagePanel>
      <EmptyState message="These summaries are research results only; they do not place live orders." />
    </TerminalShell>
  );
}
