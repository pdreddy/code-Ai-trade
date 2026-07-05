import { DailyResearchReport } from "@/components/daily-research-report";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

export default function AnalyticsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Portfolio-level analytics calculated from the current real-data research report, including trade count, average returns, win rate, and drawdown."
        eyebrow="Analytics"
        title="Performance Analytics"
      >
        <DailyResearchReport view="analytics" />
      </PagePanel>
      <EmptyState message="Analytics are computed from real provider-backed results and do not use fabricated performance data." />
    </TerminalShell>
  );
}
