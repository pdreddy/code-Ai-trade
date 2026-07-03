import { EmptyState, PagePanel } from "@/components/page-panel";
import { TerminalShell } from "@/components/terminal-shell";

const states = ["Pending", "Filled", "Cancelled", "Rejected"];

export default function PaperTradesPage() {
  return (
    <TerminalShell>
      <PagePanel
        description="The paper broker lifecycle exists in the backend application layer. This view is prepared for real paper order/fill/trade APIs."
        eyebrow="Paper Trades"
        title="Paper Broker Monitor"
      >
        <div className="grid gap-3 md:grid-cols-4">
          {states.map((state) => (
            <div className="rounded-xl border border-terminal-border bg-black/20 p-4" key={state}>
              <p className="font-medium">{state}</p>
              <p className="mt-2 text-xs text-terminal-muted">Order state supported</p>
            </div>
          ))}
        </div>
      </PagePanel>
      <EmptyState message="No fake paper trades are displayed. Real paper trades will appear after persistence and API endpoints are implemented." />
    </TerminalShell>
  );
}
