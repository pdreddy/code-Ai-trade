import { DailyResearchReport } from "@/components/daily-research-report";
import { PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";


export default function StockDetailsPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Per-symbol research cards built from real five-year provider bars, paper executions, open-position state, and portfolio sleeves."
        eyebrow="Stock Details"
        title="Instrument Research Workspace"
      >
        <DailyResearchReport view="stocks" />
      </PagePanel>
    </TerminalShell>
  );
}
