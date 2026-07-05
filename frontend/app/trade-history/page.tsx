import { TerminalShell } from "@/components/terminal-shell";
import { TradeHistoryWorkspace } from "@/components/trade-history-workspace";

export default function TradeHistoryPage() {
  return (
    <TerminalShell>
      <TradeHistoryWorkspace />
    </TerminalShell>
  );
}
