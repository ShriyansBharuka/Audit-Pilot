"use client";

import React, { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AssistantEvent, AssistantStatus, api, streamAssistant } from "@/lib/api";
import { Check, Loader2, Play, Send, Sparkles, Wrench, X } from "lucide-react";

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
    if (path.startsWith("/upload") || path.startsWith("/evidence")) return ["What do I need to send?", "Which requests are overdue?"];
    return ["What do I need to send?", "Show my last 5 invoices"];
  }
  if (path === "/") return ["Summarise the risk", "Which case has the highest risk?"];
  if (path.startsWith("/findings")) return ["Explain F-001", "Which findings have adjusting entries?"];
  if (path.startsWith("/evidence")) return ["What's still open?", "Which samples have no evidence yet?"];
  if (path.startsWith("/network")) return ["Explain the largest circular flow"];
  return ["Summarise the risk", "What should I do next?"];
}

function pageKey(path: string) {
  if (path === "/") return "overview";
  return path.split("/")[1] || "overview";
}

export function AssistantPanel() {
  const { user } = useAuth();
  const pathname = usePathname();
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setStatus(null);
    setMsgs([]);
    if (user) api.getAssistantStatus().then(setStatus).catch(() => setStatus(null));
  }, [user?.token, user?.role]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [msgs]);

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

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="h-8 text-xs px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white flex items-center gap-1.5 transition"
      >
        <Sparkles className="h-3.5 w-3.5" />
        <span>Ask AuditPilot</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="relative w-full max-w-md h-full bg-slate-900 border-l border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 h-14 border-b border-slate-800 shrink-0">
              <div>
                <div className="text-sm font-medium text-slate-50">AuditPilot assistant</div>
                <div className="text-[11px] text-slate-500">
                  {status.mode === "page_data" ? "Read-only · this page's data" : "Your role's tools · every call is logged"}
                </div>
              </div>
              <button onClick={() => setOpen(false)} aria-label="Close" className="text-slate-400 hover:text-slate-50">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 text-sm">
              {msgs.length === 0 && (
                <div className="space-y-2">
                  <div className="text-xs text-slate-500">Try</div>
                  {starters(pathname, user.role || "").map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="block w-full text-left px-3 py-2 rounded-md border border-slate-800 hover:bg-slate-800/60 text-slate-300 text-xs"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {msgs.map((m, mi) => (
                <div key={mi} className={m.role === "user" ? "flex justify-end" : ""}>
                  {m.role === "user" ? (
                    <div className="max-w-[85%] rounded-lg bg-slate-800 px-3 py-2 text-slate-100 whitespace-pre-wrap">{m.content}</div>
                  ) : (
                    <div className="space-y-2">
                      {m.tools.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {m.tools.map((t, ti) => (
                            <span key={ti} className="inline-flex items-center gap-1 rounded border border-slate-700 px-1.5 py-0.5 text-[11px] font-mono text-slate-400">
                              {t.status === "done" ? <Check className="h-3 w-3 text-indigo-400" /> : <Wrench className="h-3 w-3" />}
                              {t.name}
                            </span>
                          ))}
                        </div>
                      )}
                      {(m.content || (busy && mi === msgs.length - 1)) && (
                        <div className="text-slate-200 whitespace-pre-wrap leading-relaxed">
                          {m.content.replace(/\*\*/g, "") || <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
                        </div>
                      )}
                      {m.proposals.map((p, pi) => (
                        <div key={pi} className="rounded-md border border-slate-700 bg-slate-950 p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs text-slate-200">{p.tool}</span>
                            <span className="text-[11px] text-slate-500">
                              {p.state === "pending" ? "needs your OK" : p.state === "running" ? "running…" : p.state}
                            </span>
                          </div>
                          <div className="text-xs text-slate-400">{p.why}</div>
                          <pre className="text-[11px] text-slate-500 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                            {JSON.stringify(p.args, null, 1)}
                          </pre>
                          {p.state === "pending" && (
                            <div className="flex gap-2">
                              <button
                                onClick={() => run(mi, pi)}
                                className="h-7 px-2.5 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-xs flex items-center gap-1"
                              >
                                <Play className="h-3 w-3" /> Run
                              </button>
                              <button
                                onClick={() => dismiss(mi, pi)}
                                className="h-7 px-2.5 rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs"
                              >
                                Dismiss
                              </button>
                            </div>
                          )}
                          {p.result && (
                            <div className={`text-[11px] font-mono whitespace-pre-wrap break-all ${p.state === "failed" ? "text-rose-300" : "text-slate-400"}`}>
                              {p.result}
                            </div>
                          )}
                        </div>
                      ))}
                      {m.error && <div className="text-xs text-rose-300">{m.error}</div>}
                    </div>
                  )}
                </div>
              ))}
              <div ref={end} />
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
              className="border-t border-slate-800 p-3 flex gap-2 shrink-0"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about this engagement…"
                className="flex-1 h-9 px-3 rounded-md bg-slate-950 border border-slate-700 text-sm text-slate-50 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                disabled={busy || !input.trim()}
                className="h-9 w-9 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white flex items-center justify-center disabled:opacity-50"
                aria-label="Send"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </form>
          </aside>
        </div>
      )}
    </>
  );
}
