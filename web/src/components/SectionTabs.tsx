"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { itemForPath } from "@/lib/nav";

/** Underlined tabs for the section the current page belongs to (renders nothing outside a tab set). */
export function SectionTabs() {
  const pathname = usePathname();
  const tabs = itemForPath(pathname)?.tabs;
  if (!tabs) return null;
  return (
    <nav className="no-print flex gap-6 border-b border-slate-800 mb-7 -mt-1 overflow-x-auto" aria-label="Section">
      {tabs.map((t) => {
        const active = t.href === pathname;
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={`pb-2.5 -mb-px text-[13px] whitespace-nowrap border-b-2 transition-colors ${
              active ? "border-indigo-400 text-slate-50" : "border-transparent text-slate-400 hover:text-slate-50"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
