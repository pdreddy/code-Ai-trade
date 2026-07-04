import { PortfolioMonitor } from "@/components/portfolio-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function PortfolioPage() {
  return (
    <TerminalShell>
      <PortfolioMonitor />
    </TerminalShell>
  );
}
