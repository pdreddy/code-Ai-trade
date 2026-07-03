import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

const controls = ["Cash", "Positions", "Gross exposure", "Drawdown", "Liquidity", "Correlation", "Kill switch", "Sector exposure"];

export default function PortfolioPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="Portfolio views will consume paper broker state and risk decisions while keeping accounting and risk logic in backend services."
        eyebrow="Portfolio"
        title="Portfolio And Risk Monitor"
      >
        <div className="grid gap-3 md:grid-cols-4">
          {controls.map((control) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4 text-sm" key={control}>
              {control}
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="Portfolio values are intentionally empty until persisted paper broker state is exposed through APIs." />
    </TerminalShell>
  );
}
