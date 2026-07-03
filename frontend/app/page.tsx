const modules = [
  "Market Research",
  "Quantitative Analysis",
  "AI Signal Generation",
  "Event-Driven Backtesting",
  "Paper Trading",
  "Portfolio Risk"
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-terminal-background p-6 text-terminal-text">
      <section className="mx-auto flex max-w-6xl flex-col gap-8">
        <div className="rounded-2xl border border-terminal-border bg-terminal-panel p-8 shadow-2xl">
          <p className="text-sm uppercase tracking-[0.35em] text-terminal-accent">Foundation Online</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight">KOC3 Quant Platform</h1>
          <p className="mt-4 max-w-3xl text-terminal-muted">
            Institutional research terminal foundation for market data, AI agents,
            event-driven backtesting, paper trading, and portfolio analytics.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {modules.map((module) => (
            <article key={module} className="rounded-xl border border-terminal-border bg-terminal-panel p-5">
              <h2 className="text-lg font-medium">{module}</h2>
              <p className="mt-2 text-sm text-terminal-muted">Architecture-ready module boundary.</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
