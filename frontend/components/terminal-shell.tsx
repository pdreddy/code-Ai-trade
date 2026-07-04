import { TerminalNav } from "@/components/terminal-nav";

export function TerminalShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <main className="min-h-screen bg-terminal-background text-terminal-text">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 lg:p-6">
        <header className="rounded-2xl border border-terminal-border bg-terminal-panel/95 p-5 shadow-2xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-terminal-accent">AI Quant Research Terminal</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">AI Quant Platform</h1>
              <p className="mt-2 max-w-3xl text-sm text-terminal-muted">
                Institutional research workspace for market data, AI signals, event-driven backtests,
                paper trading, portfolio risk, and analytics. No live-trading controls are exposed.
              </p>
            </div>
            <div className="rounded-lg border border-terminal-border bg-black/20 px-4 py-3 text-xs text-terminal-muted">
              <span className="text-terminal-accent">MODE</span> · Research / Paper Foundation
            </div>
          </div>
          <TerminalNav />
        </header>
        {children}
      </div>
    </main>
  );
}
