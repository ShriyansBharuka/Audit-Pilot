"use client";

import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Check, Copy, Eye, EyeOff, KeyRound, Plus, Trash2 } from "lucide-react";

const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL || "http://localhost:8000/mcp";
const PUBLIC_KEY = "auditpilot_public_mcp";
const PLACEHOLDER = "YOUR_TOKEN";

type AgentToken = { id: string; role: string; label: string; hint: string; created_at: string };
type App = {
  id: string;
  name: string;
  where: "local" | "cloud";
  needs?: string;
  steps: (c: Ctx) => React.ReactNode[];
};
type Ctx = { url: string; pathUrl: string; publicPathUrl: string; token: string; hasPublic: boolean };

// ------------------------------------------------------------------ small pieces

function CopyBlock({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950">
      {label && <div className="px-3 pt-2 text-[11px] text-slate-500">{label}</div>}
      <div className="flex items-start gap-2 p-3">
        <pre className="flex-1 overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-slate-200">{text}</pre>
        <button
          onClick={() => {
            navigator.clipboard.writeText(text);
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          }}
          aria-label="Copy"
          className="shrink-0 h-7 px-2 rounded border border-slate-700 hover:bg-slate-800 text-[11px] text-slate-300 flex items-center gap-1"
        >
          {done ? <Check className="h-3.5 w-3.5 text-indigo-400" /> : <Copy className="h-3.5 w-3.5" />} {done ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="flex items-center gap-3 px-5 h-12 border-b border-slate-800">
        <span className="h-6 w-6 rounded-full bg-slate-800 text-xs text-slate-200 flex items-center justify-center">{n}</span>
        <h2 className="text-sm font-medium text-slate-50">{title}</h2>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </section>
  );
}

const B = ({ children }: { children: React.ReactNode }) => <span className="text-slate-100">{children}</span>;

// ------------------------------------------------------------------ per-app instructions

const json = (o: unknown) => JSON.stringify(o, null, 2);

const APPS: App[] = [
  {
    id: "claude-code",
    name: "Claude Code",
    where: "local",
    steps: (c) => [
      <>Install Claude Code if you don&apos;t have it (needs Node.js 18+).<CopyBlock text="npm install -g @anthropic-ai/claude-code" /></>,
      <>Add AuditPilot with your token. Run this once in any terminal:<CopyBlock text={`claude mcp add --transport http auditpilot ${c.url} --header "Authorization: Bearer ${c.token}"`} /></>,
      <>Start <B>claude</B> and type <B>/mcp</B>. You should see <B>auditpilot · connected</B>.</>,
      <>Ask in plain English, for example <B>&quot;Use auditpilot: who am I and what can I do?&quot;</B> To remove it later: <code className="text-slate-300">claude mcp remove auditpilot</code></>,
    ],
  },
  {
    id: "claude-desktop",
    name: "Claude Desktop",
    where: "local",
    needs: "Node.js on this computer",
    steps: (c) => [
      <>Install <B>Node.js</B> (nodejs.org) if you don&apos;t have it. Claude Desktop uses it to run the small <B>mcp-remote</B> bridge.</>,
      <>In Claude Desktop open <B>Settings → Developer → Edit Config</B>. This opens <code className="text-slate-300">claude_desktop_config.json</code>.</>,
      <>Replace its contents with this (or add the <B>auditpilot</B> entry to your existing <B>mcpServers</B>) and save:<CopyBlock text={json({ mcpServers: { auditpilot: { command: "npx", args: ["-y", "mcp-remote", c.pathUrl] } } })} /></>,
      <>Quit Claude Desktop completely (also from the system tray) and open it again. Click the <B>tools</B> icon in the chat box: the AuditPilot tools are listed.</>,
    ],
  },
  {
    id: "claude-ai",
    name: "Claude.ai (web)",
    where: "cloud",
    needs: "a Pro, Max, Team or Enterprise plan, and a public HTTPS address",
    steps: (c) => [
      <>Claude.ai runs in the cloud, so it needs AuditPilot&apos;s <B>public</B> address (step 3 below). {c.hasPublic ? "It's filled in below." : "Add it in step 3 first."}</>,
      <>Open <B>claude.ai → Settings → Connectors → Add custom connector</B>.</>,
      <>Name it <B>AuditPilot</B> and paste this as the <B>Remote MCP server URL</B> (your token is inside it, so keep it private). Click <B>Add</B>.<CopyBlock text={c.publicPathUrl} /></>,
      <>In a new chat, open the <B>tools</B> menu (the <B>+</B> / search-and-tools button) and switch <B>AuditPilot</B> on.</>,
    ],
  },
  {
    id: "chatgpt",
    name: "ChatGPT",
    where: "cloud",
    needs: "a plan with Developer mode (Plus, Pro, Business), and a public HTTPS address",
    steps: (c) => [
      <>ChatGPT runs in the cloud, so it needs AuditPilot&apos;s <B>public</B> address (step 3 below). {c.hasPublic ? "It's filled in below." : "Add it in step 3 first."}</>,
      <>Open <B>Settings → Apps &amp; Connectors → Advanced settings</B> and turn on <B>Developer mode</B>.</>,
      <>Back in <B>Apps &amp; Connectors</B>, click <B>Create</B>. Name: <B>AuditPilot</B>. MCP server URL:<CopyBlock text={c.publicPathUrl} />Authentication: <B>No authentication</B> (the token is in the URL). Tick <B>I trust this application</B> and click <B>Create</B>.</>,
      <>In a new chat, click <B>+</B> → <B>Developer mode</B> and select <B>AuditPilot</B>. ChatGPT asks before running tools that change data.</>,
    ],
  },
  {
    id: "cursor",
    name: "Cursor",
    where: "local",
    steps: (c) => [
      <>Open <B>Cursor Settings → Tools &amp; Integrations → New MCP server</B>. This opens <code className="text-slate-300">mcp.json</code> (global: <code className="text-slate-300">~/.cursor/mcp.json</code>).</>,
      <>Paste this and save:<CopyBlock text={json({ mcpServers: { auditpilot: { url: c.url, headers: { Authorization: `Bearer ${c.token}` } } } })} /></>,
      <>Back in settings, AuditPilot shows a green dot and its tools. Use it from the chat in <B>Agent</B> mode.</>,
    ],
  },
  {
    id: "vscode",
    name: "VS Code (Copilot)",
    where: "local",
    steps: (c) => [
      <>Press <B>Ctrl+Shift+P</B> → <B>MCP: Open User Configuration</B> (or create <code className="text-slate-300">.vscode/mcp.json</code> in a project).</>,
      <>Paste this and save:<CopyBlock text={json({ servers: { auditpilot: { type: "http", url: c.url, headers: { Authorization: `Bearer ${c.token}` } } } })} /></>,
      <>Click <B>Start</B> above the entry. In <B>Copilot Chat</B> switch to <B>Agent</B> mode and open the tools picker: AuditPilot&apos;s tools are listed.</>,
    ],
  },
  {
    id: "gemini",
    name: "Gemini CLI",
    where: "local",
    steps: (c) => [
      <>Open <code className="text-slate-300">~/.gemini/settings.json</code> (create it if missing) and add:<CopyBlock text={json({ mcpServers: { auditpilot: { httpUrl: c.url, headers: { Authorization: `Bearer ${c.token}` } } } })} /></>,
      <>Run <B>gemini</B> and type <B>/mcp</B>: auditpilot is listed with its tools.</>,
    ],
  },
  {
    id: "n8n",
    name: "n8n",
    where: "local",
    steps: (c) => [
      <>In your workflow, add an <B>AI Agent</B> node, then add the tool <B>MCP Client Tool</B>.</>,
      <>Endpoint: <CopyBlock text={c.url} />Server transport: <B>HTTP Streamable</B>. Authentication: <B>Header Auth</B> with name <B>Authorization</B> and value:<CopyBlock text={`Bearer ${c.token}`} /></>,
      <>Choose which tools to expose (or all). Run the workflow: the agent can now call AuditPilot.</>,
    ],
  },
  {
    id: "python",
    name: "Python / your own agent",
    where: "local",
    steps: (c) => [
      <>Install the official MCP client:<CopyBlock text={'pip install "mcp>=2.3,<3"'} /></>,
      <>
        Connect and call a tool:
        <CopyBlock
          text={`import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

async def main():
    http = create_mcp_http_client(headers={"Authorization": "Bearer ${c.token}"})
    async with streamable_http_client("${c.url}", http_client=http) as (r, w, *_):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print([t.name for t in (await s.list_tools()).tools])
            print(await s.call_tool("whoami", {}))

asyncio.run(main())`}
        />
      </>,
    ],
  },
];

const PROMPTS: Record<string, string[]> = {
  audit_staff: [
    "Who am I and what can I do here?",
    "What's the engagement status and the company risk band?",
    "List the open audit cases, biggest first, and trace the money for the top one.",
    "Select a sales sample and tell me why each item was picked.",
    "Verify the integrity of the books and the audit trail.",
  ],
  client: [
    "Who am I and what can I do here?",
    "Show me my last 5 invoices.",
    "Which evidence requests are still open?",
    "Create a customer Coastal Dredgers Pvt Ltd, GSTIN 27AAACC5123D1Z8.",
  ],
};

// ------------------------------------------------------------------ page

export default function ConnectPage() {
  const { user, identities } = useAuth();
  const web = user?.account === "supabase";
  const isPartnerToken = !web && user?.role === "engagement_partner";

  // the token used in the commands below
  const [token, setToken] = useState<string>("");
  const [show, setShow] = useState(false);
  const [mine, setMine] = useState<AgentToken[]>([]);
  const [org, setOrg] = useState("");
  const [label, setLabel] = useState("My agent");
  const [fresh, setFresh] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [app, setApp] = useState("claude-code");
  const [publicBase, setPublicBase] = useState(process.env.NEXT_PUBLIC_MCP_PUBLIC_URL || "");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(PUBLIC_KEY);
      if (saved) setPublicBase(saved);
    } catch {
      /* private window: keep the default */
    }
    if (!web && user?.token && user.role !== "engagement_partner") setToken(user.token);
    if (web) loadTokens();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [web, user?.token]);

  const loadTokens = () =>
    api
      .getAgentTokens()
      .then((r) => {
        setMine(r.items);
        setOrg(r.organisation);
      })
      .catch((e) => setError(e.message));

  const personas = identities.filter((i: any) => i.token && i.role !== "engagement_partner" && i.role !== "orchestrator");
  const ctx: Ctx = useMemo(() => {
    const t = token || PLACEHOLDER;
    const base = MCP_URL.replace(/\/mcp$/, "");
    const pub = (publicBase || "").trim().replace(/\/+$/, "").replace(/\/mcp$/, "");
    return {
      url: MCP_URL,
      token: t,
      pathUrl: `${base}/c/${t}/mcp`,
      publicPathUrl: pub ? `${pub}/c/${t}/mcp` : `https://YOUR-PUBLIC-HOST/c/${t}/mcp`,
      hasPublic: !!pub,
    };
  }, [token, publicBase]);
  const current = APPS.find((a) => a.id === app)!;
  const role = web ? (user?.role === "engagement_partner" ? "audit_staff" : user?.role) : user?.role;
  const prompts = role === "audit_staff" || role === "engagement_partner" ? PROMPTS.audit_staff : PROMPTS.client;
  const masked = token ? `${token.slice(0, 4)}${"•".repeat(Math.max(0, token.length - 8))}${token.slice(-4)}` : "";

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-medium text-slate-50 tracking-tight">Connect an AI agent</h1>
        <p className="mt-1 text-sm text-slate-400">
          Use AuditPilot from Claude, ChatGPT, Cursor and other assistants over MCP. The agent gets exactly your role&apos;s
          permissions, and everything it does is recorded in the audit trail.
        </p>
      </div>

      {/* 1. token */}
      <Step n={1} title="Get your token">
        {web ? (
          <>
            <p className="text-sm text-slate-400">
              Create a token for an agent in <B>{org || "your organisation"}</B>. It acts as{" "}
              <B>{(role || "").replace("_", " ")}</B>
              {user?.role === "engagement_partner" && " (a partner's agent works as audit staff: confirming findings and sign-off stay with you in this app)"}.
              The token is shown once; revoke it here any time.
            </p>
            <form
              className="flex flex-wrap gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setError(null);
                try {
                  const t = await api.createAgentToken(label);
                  setFresh(t.token);
                  setToken(t.token);
                  setShow(true);
                  loadTokens();
                } catch (ex) {
                  setError(ex instanceof Error ? ex.message : "Could not create the token");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Name, e.g. Claude Code"
                className="flex-1 min-w-[200px] h-9 px-3 rounded-md bg-slate-950 border border-slate-700 text-sm text-slate-50 outline-none focus:border-indigo-500" />
              <button type="submit" disabled={busy} className="h-9 px-3 rounded-md bg-indigo-600 hover:bg-indigo-700 border border-indigo-500/40 text-white text-xs font-medium flex items-center gap-1.5 disabled:opacity-50">
                <Plus className="h-3.5 w-3.5" /> {busy ? "Creating…" : "Create token"}
              </button>
            </form>
            {fresh && (
              <div className="rounded-md border border-amber-500/30 p-3 space-y-2">
                <p className="text-xs text-amber-300">Copy it now: it will not be shown again. The commands below already use it.</p>
                <CopyBlock text={fresh} />
              </div>
            )}
            {mine.length > 0 && (
              <table className="w-full text-sm">
                <tbody className="divide-y divide-slate-800">
                  {mine.map((t) => (
                    <tr key={t.id}>
                      <td className="py-2 text-slate-200">{t.label}</td>
                      <td className="py-2 text-xs text-slate-500">{t.role.replace("_", " ")}</td>
                      <td className="py-2 font-mono text-xs text-slate-500">agt_…{t.hint}</td>
                      <td className="py-2 text-xs text-slate-500">{t.created_at.slice(0, 10)}</td>
                      <td className="py-2 text-right">
                        <button onClick={() => api.revokeAgentToken(t.id).then(loadTokens)} className="text-xs text-slate-400 hover:text-rose-300 inline-flex items-center gap-1">
                          <Trash2 className="h-3.5 w-3.5" /> Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {!fresh && (
              <label className="block space-y-1.5">
                <span className="text-xs text-slate-400">Or paste a token you saved earlier, to fill in the commands</span>
                <input value={token} onChange={(e) => setToken(e.target.value.trim())} placeholder="agt_…"
                  className="w-full h-9 px-3 rounded-md bg-slate-950 border border-slate-700 font-mono text-sm text-slate-50 outline-none focus:border-indigo-500" />
              </label>
            )}
          </>
        ) : isPartnerToken ? (
          <>
            <p className="text-sm text-slate-400">
              The engagement partner&apos;s token is <B>never</B> given to an agent: decisions and sign-off stay human. Give the
              agent an auditor token instead, from the judge card (also in <code className="text-slate-300">identities.json</code>
              on the server), or pick a demo persona:
            </p>
            {personas.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {personas.map((p: any) => (
                  <button key={p.principal} onClick={() => setToken(p.token)}
                    className={`h-8 px-3 rounded-md border text-xs ${token === p.token ? "border-indigo-500/60 text-slate-50" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>
                    {p.name} · {p.role.replace("_", " ")}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <p className="text-sm text-slate-400">
              You signed in with an access token, and the agent can use the same one (role <B>{(user?.role || "").replace("_", " ")}</B>).
              It comes from the judge card printed when the demo was set up, and lives in <code className="text-slate-300">identities.json</code> on the server.
              Treat it like a password.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded-md border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-200">{show ? token : masked}</code>
              <button onClick={() => setShow((v) => !v)} className="h-8 px-2.5 rounded-md border border-slate-700 hover:bg-slate-800 text-xs text-slate-300 flex items-center gap-1">
                {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />} {show ? "Hide" : "Show"}
              </button>
              <button onClick={() => navigator.clipboard.writeText(token)} className="h-8 px-2.5 rounded-md border border-slate-700 hover:bg-slate-800 text-xs text-slate-300 flex items-center gap-1">
                <Copy className="h-3.5 w-3.5" /> Copy
              </button>
            </div>
          </>
        )}
        {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
        {!token && <p className="text-xs text-amber-300 flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5" /> The commands below show {PLACEHOLDER} until you pick or create a token.</p>}
      </Step>

      {/* 2. app */}
      <Step n={2} title="Choose your assistant and follow the steps">
        <div className="flex flex-wrap gap-2" role="tablist">
          {APPS.map((a) => (
            <button key={a.id} role="tab" aria-selected={app === a.id} onClick={() => setApp(a.id)}
              className={`h-8 px-3 rounded-md border text-xs ${app === a.id ? "border-indigo-500/60 bg-slate-800 text-slate-50" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>
              {a.name}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500">
          {current.where === "local" ? "Runs on your computer and talks to " : "Runs in the cloud and needs a public HTTPS address instead of "}
          <code className="text-slate-400">{MCP_URL}</code>
          {current.needs ? ` · Needs ${current.needs}.` : "."}
        </p>
        <ol className="space-y-4">
          {current.steps(ctx).map((s, i) => (
            <li key={i} className="flex gap-3 text-sm leading-relaxed text-slate-300">
              <span className="mt-0.5 h-5 w-5 shrink-0 rounded-full border border-slate-700 text-[11px] text-slate-400 flex items-center justify-center">{i + 1}</span>
              <div className="min-w-0 flex-1 space-y-2">{s}</div>
            </li>
          ))}
        </ol>
      </Step>

      {/* 3. public address */}
      <Step n={3} title="Public address (only for Claude.ai and ChatGPT)">
        <p className="text-sm text-slate-400">
          Cloud assistants can&apos;t reach <code className="text-slate-300">localhost</code>. Once AuditPilot is hosted, use its
          address. Until then, open a free tunnel on the computer running AuditPilot and restart the MCP server with the
          tunnel&apos;s host name:
        </p>
        <CopyBlock label="1. Start a tunnel (prints https://<random>.trycloudflare.com)" text="cloudflared tunnel --url http://localhost:8000" />
        <CopyBlock label="2. Restart the MCP server with that host (PowerShell)" text={'$env:PUBLIC_HOST="<random>.trycloudflare.com"; python -m app.mcp_server'} />
        <label className="block space-y-1.5">
          <span className="text-xs text-slate-400">3. Paste the public address here to fill in the steps</span>
          <input
            value={publicBase}
            onChange={(e) => {
              setPublicBase(e.target.value);
              try {
                localStorage.setItem(PUBLIC_KEY, e.target.value);
              } catch {
                /* ignore */
              }
            }}
            placeholder="https://<random>.trycloudflare.com"
            className="w-full h-9 px-3 rounded-md bg-slate-950 border border-slate-700 font-mono text-sm text-slate-50 outline-none focus:border-indigo-500"
          />
        </label>
      </Step>

      {/* 4. prompts */}
      <Step n={4} title="Try it">
        <p className="text-sm text-slate-400">Ask in plain English. Good first questions:</p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {prompts.map((p) => (
            <li key={p} className="rounded-md border border-slate-800 px-3 py-2 text-sm text-slate-200">&ldquo;{p}&rdquo;</li>
          ))}
        </ul>
        <p className="text-xs leading-relaxed text-slate-500">
          The rules hold whatever the agent tries: a client agent can&apos;t see the audit&apos;s work, an auditor agent can&apos;t
          change the books, and no agent can confirm findings or sign off. Refusals show up in <B>Admin → Audit trail</B>.
        </p>
      </Step>
    </div>
  );
}
