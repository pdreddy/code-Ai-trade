"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { terminalPages } from "@/lib/platform-data";

export function TerminalNav() {
  const pathname = usePathname();
  return (
    <nav className="mt-5 grid gap-2 md:grid-cols-4 lg:grid-cols-8">
      {terminalPages.map((page) => {
        const active = pathname === page.href;
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`cursor-pointer rounded-lg border px-3 py-2 text-sm transition hover:border-terminal-accent hover:text-terminal-accent ${
              active
                ? "border-terminal-accent bg-terminal-accent/10 text-terminal-accent"
                : "border-terminal-border bg-black/20"
            }`}
            href={page.href}
            key={page.href}
          >
            {page.label}
          </Link>
        );
      })}
    </nav>
  );
}
