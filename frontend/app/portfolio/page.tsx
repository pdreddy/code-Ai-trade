import { DailyResearchReport } from "@/components/daily-research-report";
import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

export default function PortfolioPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Portfolio view for the current $10,000 paper-research simulation across the supported ETF universe. Values are calculated from real provider-backed strategy results."
        eyebrow="Portfolio"
        title="$10,000 Paper Portfolio Monitor"
      >
        <DailyResearchReport view="portfolio" />
      </PagePanel>
      <EmptyState message="Portfolio values are simulated paper/research results only; no live brokerage orders are sent." />
    </TerminalShell>
  );
}
