import { PaperTradeBlotter } from "@/components/portfolio-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function PaperTradesPage() {
  return (
    <TerminalShell>
      <PaperTradeBlotter />
    </TerminalShell>
  );
}
