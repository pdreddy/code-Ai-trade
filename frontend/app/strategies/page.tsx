import { PagePanel } from "@/components/page-panel";
import { StrategyLab } from "@/components/strategy-lab";
import { TerminalShell } from "@/components/terminal-shell";

export default function StrategiesPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Institutional strategy research lab with executable horizon buttons for 1, 3, 5, and 10 years. Results are provider-backed and never fabricate trades."
        eyebrow="Strategies"
        title="Strategy Builder and Optimization Lab"
      >
        <StrategyLab />
      </PagePanel>
    </TerminalShell>
  );
}
