import { DailyResearchReport } from "@/components/daily-research-report";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

export default function PaperTradesPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Daywise paper-trade journal generated from the five-year research simulation. Entries and exits use next-session opens after close-based signals."
        eyebrow="Paper Trades"
        title="Executed Paper Trade Journal"
      >
        <DailyResearchReport view="paper-trades" />
      </PagePanel>
      <EmptyState message="No live brokerage integration is exposed. This page shows research/paper execution records only." />
    </TerminalShell>
  );
}
