"use client";

import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AssistantEvent, AssistantStatus, api, streamAssistant } from "@/lib/api";
import { Check, ChevronDown, Loader2, MessageSquare, Play, RotateCcw, Send, Sparkles, X } from "lucide-react";

type Proposal = {
  tool: string;
  args: Record<string, unknown>;
  why: string;
  state: "pending" | "running" | "done" | "failed" | "dismissed";
  result?: string;
};
type Msg = { role: "user" | "assistant"; content: string; tools: { name: string; status: string }[]; proposals: Proposal[]; error?: string };

const CLIENT_ROLES = ["sales", "warehouse", "accounts", "client_admin"];

function starters(path: string, role: string): string[] {
  const client = CLIENT_ROLES.includes(role);
  if (client) {
    if (path.startsWith("/upload") || path.startsWith("/evidence")) return ["What do I need to send?", "Which requests are overdue?", "Show my last 5 invoices"];
    return ["What do I need to send?", "Show my last 5 invoices", "Which requests are overdue?"];
  }
  if (path === "/") return ["Summarise the risk", "Which case has the highest risk?", "What should I do next?"];
  if (path.startsWith("/findings")) return ["Explain F-001", "Which findings have adjusting entries?", "Summarise the risk"];
  if (path.startsWith("/evidence")) return ["What's still open?", "Which samples have no evidence yet?"];
  if (path.startsWith("/network")) return ["Explain the largest circular flow", "Which parties are related?"];
  return ["Summarise the risk", "Which case has the highest risk?", "What should I do next?"];
}

function pageKey(path: string) {
  if (path === "/") return "overview";
  return path.split("/")[1] || "overview";
}

// "get_engagement_status" -> "engagement status"
const humanTool = (name: string) => name.replace(/^(get|list|run)_/, "").replace(/_/g, " ");

/** Minimal, safe formatting for answers: **bold**, `code`, "- " bullets and paragraphs (no HTML injection). */
function inline(text: string, key: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={`${key}-${i}`} className="font-semibold text-slate-50">{p.slice(2, -2)}</strong>
    ) : p.startsWith("`") && p.endsWith("`") ? (
      <code key={`${key}-${i}`} className="rounded bg-slate-950 px-1 py-0.5 font-mono text-[12px] text-slate-200">{p.slice(1, -1)}</code>
    ) : (
      <React.Fragment key={`${key}-${i}`}>{p}</React.Fragment>
    ),
  );
}

function Formatted({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = (k: number) => {
    if (bullets.length) {
      blocks.push(
        <ul key={`ul${k}`} className="list-disc space-y-1 pl-4">
          {bullets.map((b, i) => <li key={i}>{inline(b, `b${k}-${i}`)}</li>)}
        </ul>,
      );
      bullets = [];
    }
  };
  text.split("\n").forEach((line, i) => {
    const m = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (m) bullets.push(m[1]);
    else {
      flush(i);
      if (line.trim()) blocks.push(<p key={`p${i}`}>{inline(line, `p${i}`)}</p>);
    }
  });
  flush(-1);
  return <div className="space-y-2">{blocks}</div>;
}

function Typing() {
  return (
    <span className="inline-flex items-center gap-1 py-1" aria-label="Thinking">
      {[0, 150, 300].map((d) => (
        <span key={d} className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: `${d}ms` }} />
      ))}
    </span>
  );
}

export function AssistantPanel() {
  const { user } = useAuth();
  const pathname = usePathname();
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [details, setDetails] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setStatus(null);
    setMsgs([]);
    if (user) api.getAssistantStatus().then(setStatus).catch(() => setStatus(null));
  }, [user?.token, user?.role]); // eslint-disable-line react-hooks/exhaustive-deps

  // braces matter: newer browsers return a Promise from scrollIntoView, and an effect may only return a cleanup function
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [msgs, open]);

  useEffect(() => {
    if (!open) return;
    box.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!user || !status?.enabled || !status.supported) return null; // hidden when off or unsupported

  const patchLast = (fn: (m: Msg) => Msg) => setMsgs((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)));

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    const history = [...msgs, { role: "user" as const, content: q, tools: [], proposals: [] }];
    setMsgs([...history, { role: "assistant", content: "", tools: [], proposals: [] }]);
    setInput("");
    setBusy(true);
    abort.current = new AbortController();
    // partner: read-only over the data this page already shows (the MCP gateway refuses the partner token)
    let context: unknown = undefined;
    if (status.mode === "page_data") {
      const [ov, fs] = await Promise.all([api.getOverview().catch(() => null), api.getFindings().catch(() => [])]);
      context = { page: pathname, overview: ov, findings: fs };
    }
    try {
      await streamAssistant(
        { messages: history.map((m) => ({ role: m.role, content: m.content })), page: pageKey(pathname), context },
        (e: AssistantEvent) => {
          if (e.type === "delta") patchLast((m) => ({ ...m, content: m.content + e.text }));
          else if (e.type === "tool")
            patchLast((m) => {
              const tools = [...m.tools];
              const i = tools.map((t) => t.name).lastIndexOf(e.name);
              if (e.status === "done" && i >= 0) tools[i] = { name: e.name, status: "done" };
              else tools.push({ name: e.name, status: e.status });
              return { ...m, tools };
            });
          else if (e.type === "proposal")
            patchLast((m) => ({ ...m, proposals: [...m.proposals, { tool: e.tool, args: e.args, why: e.why, state: "pending" }] }));
          else if (e.type === "error") patchLast((m) => ({ ...m, error: e.message }));
        },
        abort.current.signal,
      );
    } catch (err) {
      patchLast((m) => ({ ...m, error: err instanceof Error ? err.message : "Assistant failed" }));
    } finally {
      setBusy(false);
    }
  };

  const run = async (mi: number, pi: number) => {
    const p = msgs[mi].proposals[pi];
    const set = (patch: Partial<Proposal>) =>
      setMsgs((ms) => ms.map((m, i) => (i !== mi ? m : { ...m, proposals: m.proposals.map((x, j) => (j === pi ? { ...x, ...patch } : x)) })));
    set({ state: "running" });
    try {
      const r = await api.runAssistantAction(p.tool, p.args);
      set({ state: r.ok ? "done" : "failed", result: r.text.slice(0, 400) });
    } catch (err) {
      set({ state: "failed", result: err instanceof Error ? err.message : "Failed" });
    }
  };

  const dismiss = (mi: number, pi: number) =>
    setMsgs((ms) => ms.map((m, i) => (i !== mi ? m : { ...m, proposals: m.proposals.map((x, j) => (j === pi ? { ...x, state: "dismissed" } : x)) })));

  const reset = () => {
    abort.current?.abort();
    setBusy(false);
    setMsgs([]);
  };

  const first = (user.name || "").split(/[\s,@]/)[0];
  const readOnly = status.mode === "page_data";

  // portal to <body>: the header uses backdrop-filter, which would make it the containing block of "fixed" children
  return createPortal(
    <div className="no-print">
      {/* launcher: bottom-left of the page content (clear of the sidebar) */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close assistant" : "Open assistant"}
        aria-expanded={open}
        className={`fixed bottom-6 left-4 md:left-[280px] z-40 h-12 rounded-full border border-indigo-500/40 bg-indigo-600 hover:bg-indigo-700 text-white shadow-[0_10px_30px_-8px_rgba(62,207,142,0.45)] flex items-center gap-2 transition-all ${
          open ? "w-12 justify-center" : "pl-4 pr-5"
        }`}
      >
        {open ? <ChevronDown className="h-5 w-5" /> : <><Sparkles className="h-4 w-4" /><span className="text-sm font-medium">Ask AuditPilot</span></>}
      </button>

      {open && (
        <section
          role="dialog"
          aria-label="AuditPilot assistant"
          className="fixed z-40 bottom-0 left-0 right-0 h-[85vh] md:bottom-24 md:left-[280px] md:right-auto md:w-[400px] md:h-[600px] md:max-h-[calc(100vh-8rem)] flex flex-col overflow-hidden rounded-t-2xl md:rounded-2xl border border-slate-700/80 bg-slate-900 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.6)]"
        >
          {/* header */}
          <header className="flex items-center gap-3 px-4 h-16 border-b border-slate-800 shrink-0">
            <span className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-white" />
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-slate-50">AuditPilot Assistant</div>
              <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                {readOnly ? "Read-only · answers from this page" : "Live data · your permissions"}
              </div>
            </div>
            {msgs.length > 0 && (
              <button onClick={reset} aria-label="New chat" title="New chat" className="h-8 w-8 rounded-md text-slate-400 hover:text-slate-50 hover:bg-slate-800 flex items-center justify-center">
                <RotateCcw className="h-4 w-4" />
              </button>
            )}
            <button onClick={() => setOpen(false)} aria-label="Close" className="h-8 w-8 rounded-md text-slate-400 hover:text-slate-50 hover:bg-slate-800 flex items-center justify-center">
              <X className="h-4 w-4" />
            </button>
          </header>

          {/* messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 text-sm">
            {msgs.length === 0 && (
              <div className="space-y-4 pt-2">
                <div className="flex gap-2.5">
                  <span className="h-7 w-7 shrink-0 rounded-full bg-slate-800 flex items-center justify-center"><Sparkles className="h-3.5 w-3.5 text-indigo-400" /></span>
                  <div className="rounded-2xl rounded-tl-sm bg-slate-800 px-3.5 py-2.5 text-slate-200 leading-relaxed">
                    Hi{first ? ` ${first}` : ""}! I look things up in this engagement for you, with your own permissions.
                    {readOnly ? " I can explain what this page shows." : " If you want something changed, I'll suggest it and you decide."}
                  </div>
                </div>
                <div className="space-y-2 pl-9">
                  <div className="text-[11px] text-slate-500">Try asking</div>
                  <div className="flex flex-wrap gap-2">
                    {starters(pathname, user.role || "").map((s) => (
                      <button key={s} onClick={() => send(s)} className="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:border-indigo-500/60 hover:bg-slate-800 transition">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {msgs.map((m, mi) =>
              m.role === "user" ? (
                <div key={mi} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-3.5 py-2.5 text-white whitespace-pre-wrap leading-relaxed">{m.content}</div>
                </div>
              ) : (
                <div key={mi} className="flex gap-2.5">
                  <span className="h-7 w-7 shrink-0 rounded-full bg-slate-800 flex items-center justify-center"><Sparkles className="h-3.5 w-3.5 text-indigo-400" /></span>
                  <div className="min-w-0 flex-1 space-y-2">
                    {m.tools.length > 0 && (
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-500">
                        <span>Checked</span>
                        {m.tools.map((t, ti) => (
                          <span key={ti} className="inline-flex items-center gap-1 text-slate-400">
                            {t.status === "done" ? <Check className="h-3 w-3 text-indigo-400" /> : <Loader2 className="h-3 w-3 animate-spin" />}
                            {humanTool(t.name)}
                          </span>
                        ))}
                      </div>
                    )}
                    {(m.content || (busy && mi === msgs.length - 1 && !m.error)) && (
                      <div className="rounded-2xl rounded-tl-sm bg-slate-800 px-3.5 py-2.5 text-slate-200 leading-relaxed">
                        {m.content ? <Formatted text={m.content} /> : <Typing />}
                      </div>
                    )}
                    {m.proposals.map((p, pi) => {
                      const key = `${mi}-${pi}`;
                      return (
                        <div key={pi} className="rounded-xl border border-slate-700 bg-slate-950 p-3 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] uppercase tracking-wide text-slate-500">Suggested action</span>
                            <span className={`text-[11px] ${p.state === "done" ? "text-indigo-400" : p.state === "failed" ? "text-rose-300" : "text-slate-400"}`}>
                              {p.state === "pending" ? "needs your OK" : p.state === "running" ? "running…" : p.state}
                            </span>
                          </div>
                          <div className="text-sm text-slate-100 capitalize">{humanTool(p.tool)}</div>
                          <div className="text-xs text-slate-400">{p.why}</div>
                          <button onClick={() => setDetails(details === key ? null : key)} className="text-[11px] text-slate-500 hover:text-slate-300">
                            {details === key ? "Hide details" : "Show details"}
                          </button>
                          {details === key && (
                            <pre className="text-[11px] text-slate-400 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto rounded-md bg-slate-900 p-2">
                              {p.tool}
                              {"\n"}
                              {JSON.stringify(p.args, null, 1)}
                            </pre>
                          )}
                          {p.state === "pending" && (
                            <div className="flex gap-2 pt-1">
                              <button onClick={() => run(mi, pi)} className="h-8 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium flex items-center gap-1.5">
                                <Play className="h-3 w-3" /> Run
                              </button>
                              <button onClick={() => dismiss(mi, pi)} className="h-8 px-3 rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs">
                                Dismiss
                              </button>
                            </div>
                          )}
                          {p.result && (
                            <div className={`text-[11px] font-mono whitespace-pre-wrap break-all max-h-28 overflow-y-auto ${p.state === "failed" ? "text-rose-300" : "text-slate-400"}`}>
                              {p.result}
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {m.error && <div className="rounded-lg border border-rose-500/30 px-3 py-2 text-xs text-rose-300">{m.error}</div>}
                  </div>
                </div>
              ),
            )}
            <div ref={end} />
          </div>

          {/* composer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="border-t border-slate-800 p-3 shrink-0"
          >
            <div className="flex items-end gap-2 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 focus-within:border-indigo-500/60">
              <MessageSquare className="h-4 w-4 mb-1.5 shrink-0 text-slate-600" />
              <textarea
                ref={box}
                rows={1}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                placeholder="Ask about this engagement…"
                className="flex-1 resize-none bg-transparent text-sm text-slate-50 placeholder-slate-600 outline-none focus-visible:outline-none leading-6 max-h-[120px]"
              />
              <button
                type="submit"
                disabled={busy || !input.trim()}
                className="h-8 w-8 shrink-0 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white flex items-center justify-center disabled:opacity-40"
                aria-label="Send"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-slate-600">Uses live data · changes run only when you press Run</p>
          </form>
        </section>
      )}
    </div>,
    document.body,
  );
}
