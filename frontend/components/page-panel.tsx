export function PagePanel({
  title,
  eyebrow,
  description,
  children
}: Readonly<{
  title: string;
  eyebrow: string;
  description: string;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-2xl border border-terminal-border bg-terminal-panel p-6 shadow-2xl">
      <p className="text-xs uppercase tracking-[0.32em] text-terminal-accent">{eyebrow}</p>
      <h2 className="mt-3 text-2xl font-semibold">{title}</h2>
      <p className="mt-2 max-w-4xl text-sm leading-6 text-terminal-muted">{description}</p>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function EmptyState({ message }: Readonly<{ message: string }>) {
  return (
    <div className="rounded-xl border border-dashed border-terminal-border bg-black/20 p-6 text-sm text-terminal-muted">
      {message}
    </div>
  );
}
