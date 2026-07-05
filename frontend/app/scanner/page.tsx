import { ScannerWorkspace } from "@/components/scanner-workspace";
import { TerminalShell } from "@/components/terminal-shell";

export default function ScannerPage() {
  return (
    <TerminalShell>
      <ScannerWorkspace />
    </TerminalShell>
  );
}
