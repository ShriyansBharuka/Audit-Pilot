"use client";

import Link from "next/link";
import { ArrowRight, Check, FileCheck2, Lock, Network, ScanSearch, Shield, Sparkles } from "lucide-react";

// Public marketing page (signed-out visitors on "/"). Numbers are our own measurements (docs/FEASIBILITY.md).

const STATS = [
  { value: "100%", label: "of invoices tested, not a sample" },
  { value: "36 / 36", label: "planted irregularities caught" },
  { value: "0.9 s", label: "from a client entry to an updated risk score" },
  { value: "16", label: "detector families, D0 to D15" },
];

const FEATURES = [
  {
    icon: Network,
    kicker: "Circular trading",
    title: "Find the loops that inflate turnover",
    body: "Goods and cash that leave and come back through accommodation parties show up as a ring, with the value, the parties and the invoices behind it.",
    points: ["Round trips in goods and in cash", "Undisclosed related parties", "Companies Act s.143(12)"],
    img: "/landing/circular.png",
  },
  {
    icon: Sparkles,
    kicker: "Explainable risk",
    title: "Every score shows its working",
    body: "Each invoice's risk splits exactly into the hits that drove it, so a reviewer can see why an item was picked before opening it.",
    points: ["Exact attribution, not an estimate", "Top drivers across the year", "Same view for every invoice"],
    img: "/landing/shap.png",
  },
  {
    icon: FileCheck2,
    kicker: "Findings and memo",
    title: "From a hit to a proposed entry",
    body: "Findings arrive with the evidence, the standard they breach and a proposed adjusting entry. The partner confirms, changes or rejects each one.",
    points: ["Debits and credits always balance", "Draft memo in PDF or Markdown", "Nothing is final without the partner"],
    img: "/landing/findings.png",
  },
];

const TRUST = [
  { icon: Lock, title: "Read-only for auditors", body: "The audit side cannot change the client's books. Proposed entries live apart from the ledger." },
  { icon: Shield, title: "Tamper-evident trail", body: "Every action is hash-chained, so a quiet edit to the record breaks the chain and shows." },
  { icon: ScanSearch, title: "Files kept as sent", body: "Uploads are stored byte for byte with a server-computed SHA-256. Differences become findings, never fixes." },
  { icon: Check, title: "People sign off", body: "Detectors decide what is flagged. AI helps investigate and explain. Only the partner confirms." },
];

const STANDARDS = ["SA 230", "SA 240", "SA 320", "SA 500", "SA 520", "SA 550", "Ind AS 115", "CGST Rule 46", "CGST Rule 138", "Companies Act s.143(12)"];
const INTEGRATIONS = [
  { name: "Power BI", note: "Star-schema export and a live feed" },
  { name: "n8n", note: "Signed webhooks for evidence and reminders" },
  { name: "Claude and MCP agents", note: "Token-bound tools for your own agent" },
  { name: "Excel", note: "Four-sheet workpaper with tick marks" },
  { name: "GST portals", note: "E-invoice, e-way bill and GSTR-1 checks" },
];

function Shot({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-1.5 shadow-[0_30px_80px_-30px_rgba(62,207,142,0.18)]">
      <div className="flex gap-1.5 px-2 py-1.5">
        <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />
        <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />
        <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="w-full rounded-lg border border-slate-800" loading="lazy" />
    </div>
  );
}

export function Landing() {
  return (
    <div className="min-h-screen bg-[var(--background)] text-slate-100">
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-[var(--background)]/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-800">
              <Shield className="h-4 w-4 text-indigo-400" />
            </span>
            <span className="text-[15px] font-medium text-slate-50">AuditPilot</span>
          </Link>
          <nav className="hidden items-center gap-7 text-[13px] text-slate-400 md:flex">
            <a href="#product" className="hover:text-slate-50">Product</a>
            <a href="#how" className="hover:text-slate-50">How it works</a>
            <a href="#trust" className="hover:text-slate-50">Trust</a>
            <a href="#integrations" className="hover:text-slate-50">Integrations</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/signin" className="h-8 px-3 text-[13px] text-slate-300 hover:text-slate-50 flex items-center">Sign in</Link>
            <Link href="/signin" className="h-8 px-3.5 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-[13px] font-medium text-white flex items-center">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-[radial-gradient(ellipse_at_top,rgba(62,207,142,0.10),transparent_60%)]" />
          <div className="relative mx-auto max-w-6xl px-5 pt-20 pb-14 text-center md:pt-28">
            <p className="text-[13px] text-indigo-400">Statutory revenue audit</p>
            <h1 className="mx-auto mt-4 max-w-3xl text-4xl font-medium leading-[1.1] tracking-tight text-slate-50 md:text-6xl">
              Audit every invoice, not a sample.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-[15px] leading-relaxed text-slate-400 md:text-base">
              AuditPilot reconciles the client&apos;s register to the books, tests 100% of revenue against GST and Ind AS
              rules, and hands the partner a draft memo with proposed entries. The software does the testing. People sign off.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link href="/signin" className="h-10 px-5 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-sm font-medium text-white flex items-center gap-2">
                Get started <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#how" className="h-10 px-5 rounded-md border border-slate-700 hover:bg-slate-800 text-sm text-slate-200 flex items-center">
                See how it works
              </a>
            </div>
            <div className="mx-auto mt-16 max-w-5xl text-left">
              <Shot src="/landing/overview.png" alt="AuditPilot overview: revenue tested, findings, circular loops and detector results" />
            </div>
          </div>
        </section>

        {/* Two product areas */}
        <section id="product" className="mx-auto max-w-6xl px-5 py-20">
          <div className="grid gap-5 md:grid-cols-2">
            {[
              { title: "Revenue testing", body: "Every invoice runs through 16 detector families: cut-off, related parties, movement without goods, credit notes, journals, sequence breaks and circular trading.", img: "/landing/circular.png", href: "#how" },
              { title: "Evidence and sign-off", body: "Samples go to the client as evidence requests. Findings, the workpaper and the memo come together for one partner review.", img: "/landing/memo.png", href: "#trust" },
            ].map((c) => (
              <div key={c.title} className="rounded-xl border border-slate-800 bg-slate-900 p-6 flex flex-col">
                <div className="overflow-hidden rounded-lg border border-slate-800">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={c.img} alt={c.title} className="w-full h-56 object-cover object-left-top" loading="lazy" />
                </div>
                <h3 className="mt-6 text-lg font-medium text-slate-50">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400 flex-1">{c.body}</p>
                <a href={c.href} className="mt-5 inline-flex items-center gap-1.5 text-[13px] text-indigo-400 hover:text-indigo-300">
                  Learn more <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </div>
            ))}
          </div>
        </section>

        {/* Stats */}
        <section className="border-y border-slate-800 bg-slate-950/60">
          <div className="mx-auto grid max-w-6xl grid-cols-2 px-5 md:grid-cols-4">
            {STATS.map((s, i) => (
              <div key={s.label} className={`py-10 px-4 border-slate-800 ${i % 2 ? "border-l" : ""} ${i === 2 ? "md:border-l" : ""}`}>
                <div className="text-3xl font-medium tabular-nums text-slate-50 md:text-4xl">{s.value}</div>
                <div className="mt-2 text-[13px] leading-snug text-slate-400">{s.label}</div>
              </div>
            ))}
          </div>
          <p className="mx-auto max-w-6xl px-5 pb-6 text-xs text-slate-500">
            Measured on our synthetic test company (FY 2025-26, 7,000 invoices with planted irregularities), not on client data.
          </p>
        </section>

        {/* Alternating feature rows */}
        <section id="how" className="mx-auto max-w-6xl px-5 py-24 space-y-24">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="grid items-center gap-10 md:grid-cols-2 md:gap-14">
                <div className={i % 2 ? "md:order-2" : ""}>
                  <p className="flex items-center gap-2 text-[13px] text-indigo-400">
                    <Icon className="h-4 w-4" /> {f.kicker}
                  </p>
                  <h2 className="mt-3 text-2xl font-medium tracking-tight text-slate-50 md:text-3xl">{f.title}</h2>
                  <p className="mt-4 text-[15px] leading-relaxed text-slate-400">{f.body}</p>
                  <ul className="mt-6 space-y-2.5">
                    {f.points.map((p) => (
                      <li key={p} className="flex items-start gap-2.5 text-sm text-slate-300">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" /> {p}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className={i % 2 ? "md:order-1" : ""}>
                  <Shot src={f.img} alt={f.title} />
                </div>
              </div>
            );
          })}
        </section>

        {/* Trust + standards */}
        <section id="trust" className="border-t border-slate-800 bg-slate-950/60">
          <div className="mx-auto max-w-6xl px-5 py-24">
            <h2 className="max-w-2xl text-2xl font-medium tracking-tight text-slate-50 md:text-3xl">Built the way an audit file has to be</h2>
            <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800 sm:grid-cols-2 lg:grid-cols-4">
              {TRUST.map((t) => {
                const Icon = t.icon;
                return (
                  <div key={t.title} className="bg-slate-900 p-6">
                    <Icon className="h-5 w-5 text-indigo-400" />
                    <h3 className="mt-4 text-[15px] font-medium text-slate-50">{t.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-400">{t.body}</p>
                  </div>
                );
              })}
            </div>
            <p className="mt-12 text-[13px] text-slate-500">Findings are mapped to the standards they test</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {STANDARDS.map((s) => (
                <span key={s} className="rounded-md border border-slate-800 px-2.5 py-1 text-xs text-slate-300">{s}</span>
              ))}
            </div>
          </div>
        </section>

        {/* Integrations */}
        <section id="integrations" className="mx-auto max-w-6xl px-5 py-24">
          <h2 className="text-2xl font-medium tracking-tight text-slate-50 md:text-3xl">Works with the tools you already use</h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {INTEGRATIONS.map((g) => (
              <div key={g.name} className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                <div className="text-[15px] font-medium text-slate-50">{g.name}</div>
                <div className="mt-1.5 text-[13px] leading-snug text-slate-400">{g.note}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Closing CTA */}
        <section className="px-5 pb-24">
          <div className="mx-auto max-w-6xl rounded-2xl border border-slate-800 bg-[radial-gradient(ellipse_at_bottom,rgba(62,207,142,0.12),transparent_65%)] bg-slate-900 px-6 py-16 text-center">
            <h2 className="text-2xl font-medium tracking-tight text-slate-50 md:text-4xl">Run your next revenue audit on 100% of the books</h2>
            <p className="mx-auto mt-4 max-w-xl text-[15px] text-slate-400">Upload the client&apos;s register and related-party list, and see the first findings in minutes.</p>
            <Link href="/signin" className="mt-8 inline-flex h-10 items-center gap-2 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 px-5 text-sm font-medium text-white">
              Get started <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-800">
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-12 sm:grid-cols-2 md:grid-cols-4">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-indigo-400" />
              <span className="text-sm font-medium text-slate-50">AuditPilot</span>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-slate-500">Statutory revenue audit on the full population.</p>
          </div>
          {[
            { h: "Product", l: [["Overview", "#product"], ["How it works", "#how"], ["Integrations", "#integrations"]] },
            { h: "Trust", l: [["Controls", "#trust"], ["Standards", "#trust"]] },
            { h: "Account", l: [["Sign in", "/signin"], ["Get started", "/signin"]] },
          ].map((c) => (
            <div key={c.h}>
              <div className="text-[13px] font-medium text-slate-300">{c.h}</div>
              <ul className="mt-3 space-y-2">
                {c.l.map(([label, href]) => (
                  <li key={label}>
                    <a href={href} className="text-[13px] text-slate-500 hover:text-slate-50">{label}</a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-slate-800">
          <div className="mx-auto max-w-6xl px-5 py-5 text-xs text-slate-600">© 2026 AuditPilot · ELEVATE 1.0, DJSCE</div>
        </div>
      </footer>
    </div>
  );
}
