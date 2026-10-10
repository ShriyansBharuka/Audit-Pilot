// Sidebar + section-tab config: one source of truth for groups, items, tab routes and the "allowed" check.
import {
  BarChart3,
  Building,
  FileText,
  FolderOpen,
  GitCommit,
  Layers,
  LineChart,
  Sliders,
  Zap,
  type LucideIcon,
} from "lucide-react";

export type NavTab = { href: string; label: string };
export type BadgeKey = "risk" | "invoices" | "requests" | "proposed";
export type NavItem = { href: string; label: string; icon: LucideIcon; badge?: BadgeKey; tabs?: NavTab[] };
export type NavGroup = { key: "audit" | "admin"; label: string; defaultOpen: boolean; items: NavItem[] };

export const NAV: NavGroup[] = [
  {
    key: "audit",
    label: "Audit",
    defaultOpen: true,
    items: [
      { href: "/", label: "Overview", icon: BarChart3, badge: "risk" },
      {
        href: "/transactions",
        label: "Population",
        icon: Layers,
        badge: "invoices",
        tabs: [
          { href: "/transactions", label: "Invoices" },
          { href: "/csv-check", label: "Register check" }, // CSV agent: uploaded rows reconciled to the books
        ],
      },
      { href: "/evidence", label: "Evidence", icon: FolderOpen, badge: "requests" },
      {
        href: "/report",
        label: "Reports",
        icon: FileText,
        tabs: [
          { href: "/report", label: "Memo" },
          { href: "/report/downloads", label: "Downloads" },
          { href: "/sharing", label: "Share" },
        ],
      },
      {
        href: "/analytics",
        label: "Analytics",
        icon: LineChart,
        badge: "proposed",
        tabs: [
          { href: "/analytics", label: "Detectors" },
          { href: "/network", label: "Circular trading" },
          { href: "/shap", label: "SHAP" },
          { href: "/findings", label: "Findings" },
          { href: "/investigations", label: "Investigations" },
        ],
      },
    ],
  },
  {
    key: "admin",
    label: "Admin",
    defaultOpen: false,
    items: [
      { href: "/orgs", label: "Organizations", icon: Building },
      { href: "/permissions", label: "Access control", icon: Sliders },
      { href: "/integrations", label: "Integrations", icon: Zap },
      { href: "/trail", label: "Audit trail", icon: GitCommit },
    ],
  },
];

/** Every route an item covers: its own href plus its tab routes. */
export const itemHrefs = (item: NavItem) => [item.href, ...(item.tabs ?? []).map((t) => t.href)];

export const allHrefs = () => NAV.flatMap((g) => g.items.flatMap(itemHrefs));

export const itemForPath = (pathname: string) =>
  NAV.flatMap((g) => g.items).find((i) => itemHrefs(i).includes(pathname));

export const groupForPath = (pathname: string) => NAV.find((g) => g.items.some((i) => itemHrefs(i).includes(pathname)));

/** Pages that get the "Export PDF" button (main audit pages). */
export const PRINTABLE = ["/", "/transactions", "/report", "/analytics", "/network", "/shap", "/findings", "/investigations"];
