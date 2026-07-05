import { DailyResearchReport } from "@/components/daily-research-report";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

export default function SignalsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Latest close-based research signals from real five-year OHLCV data. Any BUY/SELL candidate is planned for paper execution at the next session open, not the same bar."
        eyebrow="Signals"
        title="Next-Day Paper Trade Candidates"
      >
        <DailyResearchReport view="signals" />
      </PagePanel>
      <EmptyState message="Signals are generated from real provider bars. If the provider is unavailable, this page will not fabricate trades." />
    </TerminalShell>
  );
}
