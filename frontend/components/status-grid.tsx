import type { Capability } from "@/lib/platform-data";

export function StatusGrid({ capabilities }: Readonly<{ capabilities: Capability[] }>) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {capabilities.map((capability) => (
        <article className="rounded-xl border border-terminal-border bg-black/20 p-5" key={capability.label}>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-medium">{capability.label}</h3>
            <span
              className={
                capability.status === "ready"
                  ? "rounded-full bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300"
                  : "rounded-full bg-amber-500/10 px-2 py-1 text-xs text-amber-300"
              }
            >
              {capability.status.toUpperCase()}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-terminal-muted">{capability.detail}</p>
        </article>
      ))}
    </div>
  );
}
