// AuditPilot AI pitch deck (ELEVATE 1.0 · PS-04).  Build:  cd docs/pitch && node build_deck.js
// Numbers on the results slide come from metrics.json (python -m app.evaluate output); rebuild after re-running it.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const SKILL = process.env.PPTX_SKILL_DIR || "";
const THEME = {
  name: "AuditPilot Ledger",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A2A", lt1: "FFFFFF", dk2: "0B3D3A", lt2: "EEF4F2",
    accent1: "0B7A6F", accent2: "F2A541", accent3: "C0392B", accent4: "5B6B73", accent5: "2E86AB", accent6: "7A9E7E",
    hlink: "0B7A6F", folHlink: "5B6B73",
  },
};
const HEX = THEME.colors;
const metrics = fs.existsSync(path.join(__dirname, "metrics.json"))
  ? JSON.parse(fs.readFileSync(path.join(__dirname, "metrics.json"), "utf8")) : null;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "AuditPilot AI: AI-run statutory revenue audit";
pres.author = "Team ELEV01: Shriyans, Ibrahim, Darshan, Aarav";
pres.company = "ELEVATE 1.0 DJSCE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------- layouts
pres.defineSlideMaster({
  title: "DARK", background: { color: HEX.dk2 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.4, w: 8.8, h: 1.4, fontSize: 40,
    bold: true, color: C.background1, fontFace: THEME.headFontFace, valign: "bottom", align: "left" }, text: "" } },
  { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.9, w: 8.8, h: 1.6, fontSize: 18,
    color: C.background2, fontFace: THEME.bodyFontFace, valign: "top" }, text: "" } }],
});
pres.defineSlideMaster({
  title: "LIGHT", background: { color: HEX.lt1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontSize: 30,
    bold: true, color: C.text2, fontFace: THEME.headFontFace, valign: "middle" }, text: "" } }],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent4 },
});

// ---------- helpers
let objN = 0;
const name = (s) => `${s}-${++objN}`;
function text(slide, t, o) { slide.addText(t, { isTextBox: true, objectName: name("text"), ...o }); }
function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || C.background2 },
    line: { color: fill || C.background2 }, objectName: name("card"),
    shadow: { type: "outer", color: "9AA8A6", blur: 4, offset: 1.5, angle: 90, opacity: 0.25 } });
}
function dot(slide, x, y, d, label, fill, fontSize) { // the motif: an auditor's tick-mark circle
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill || C.accent1 }, line: { color: fill || C.accent1 },
    objectName: name("dot") });
  text(slide, label, { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: fontSize || 14, bold: true,
    color: C.background1, margin: 0 });
}
function bullets(slide, items, o) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { isTextBox: true, objectName: name("list"), fontSize: 15, color: C.text1, paraSpaceAfter: 6, valign: "top", ...o });
}
const SECTIONS = new Set(["Opening"]);
const S = (title, master = "LIGHT", section) => {
  if (!SECTIONS.has(section)) { pres.addSection({ title: section }); SECTIONS.add(section); }
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
};

// ---------- 1 title
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Opening" });
s.addText("AuditPilot AI", { placeholder: "title" });
s.addText([{ text: "Audit the business, not the spreadsheet.", options: { bold: true, color: C.accent2, breakLine: true } },
  { text: "An AI-run statutory revenue audit an engagement partner would sign", options: { breakLine: true } },
  { text: "ELEVATE 1.0 · PS-04 · Team ELEV01: Shriyans · Ibrahim · Darshan · Aarav", options: { fontSize: 13 } }],
  { placeholder: "body" });
s.addNotes("One line: we built the company's system of record and audit 100% of it, through an MCP server any AI agent can use, under strict auditor independence, with a human partner signing off.");

// ---------- 2 problem
s = S("Today's audit tests the spreadsheet", "LIGHT", "Opening");
const stats = [["7,000", "sales a year in a mid-size manufacturer"], ["~30", "of them tested, picked on judgment"],
  ["~4%", "chance 30 random samples catch any of 10 planted sales"]];
stats.forEach(([n, l], i) => {
  const x = 0.5 + i * 3.05;
  card(s, x, 1.3, 2.8, 2.2);
  text(s, n, { x: x + 0.2, y: 1.45, w: 2.4, h: 1.0, fontSize: 44, bold: true, color: i === 2 ? C.accent3 : C.text2,
    fontFace: THEME.headFontFace });
  text(s, l, { x: x + 0.2, y: 2.45, w: 2.4, h: 0.9, fontSize: 14, color: C.text1 });
});
text(s, "The auditor only sees the client's export, never what was promised, what physically moved, or what was reversed after year end. Fake invoices, circular trading, period-end stuffing and hidden related-party sales hide behind paperwork that looks complete.",
  { x: 0.5, y: 3.8, w: 9.0, h: 1.0, fontSize: 14, color: C.text1 });
s.addNotes("The 4% figure is our own calculation: a uniform random sample of 30 from 7,000 contains at least one of 10 planted invoices only about 4% of the time. So sampling cannot be the detector.");

// ---------- 3 answer
s = S("Our answer: four ideas", "LIGHT", "Solution");
const pillars = [["1", "Build the system of record", "Enquiry → order → dispatch → invoice → payment, on a tamper-evident ledger with mock GST portals"],
  ["2", "Test 100%, sample to prove", "15 detectors over every sale; samples only for evidence vouching"],
  ["3", "AuditGraph risk engine", "Transaction + company risk on a temporal graph, incl. circular-trading value"],
  ["4", "MCP under independence", "Any agent with a token runs the business or audits it; the auditor can never write"]];
pillars.forEach(([n, h, d], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 1.25 + Math.floor(i / 2) * 1.95;
  card(s, x, y, 4.35, 1.7);
  dot(s, x + 0.25, y + 0.3, 0.6, n, C.accent1, 18);
  text(s, h, { x: x + 1.05, y: y + 0.2, w: 3.1, h: 0.5, fontSize: 17, bold: true, color: C.text2, margin: 0 });
  text(s, d, { x: x + 1.05, y: y + 0.7, w: 3.1, h: 0.9, fontSize: 13, color: C.text1, margin: 0 });
});
s.addNotes("These map 1:1 to the 'beyond the core' section of the problem statement.");

// ---------- 4 what proves a sale
s = S("What proves a sale really happened", "LIGHT", "Solution");
const stages = [["Enquiry", "lead, contact"], ["Order", "price, terms, scheme"], ["Movement", "dispatch, LR, POD, e-way bill"],
  ["Revenue & tax", "invoice, IRN, GSTR-1, ledger"], ["Cash", "bank receipt, payer a/c"], ["Reversals", "credit notes, returns"]];
stages.forEach(([h, d], i) => {
  const x = 0.45 + i * 1.53;
  card(s, x, 1.45, 1.4, 1.7, i === 2 || i === 3 ? C.background2 : C.background2);
  dot(s, x + 0.45, 1.6, 0.5, String(i + 1), i >= 2 && i <= 3 ? C.accent2 : C.accent1, 14);
  text(s, h, { x: x + 0.05, y: 2.2, w: 1.3, h: 0.4, fontSize: 13, bold: true, color: C.text2, align: "center", margin: 0 });
  text(s, d, { x: x + 0.05, y: 2.6, w: 1.3, h: 0.5, fontSize: 10, color: C.text1, align: "center", margin: 0 });
});
bullets(s, ["Every write posts a balanced journal and appends to a hash-chained edit log (nothing is updated or deleted)",
  "Government copies (IRN, e-way bill, GSTR-1/3B, bank) sit in a separate store the client can't edit",
  "The client's exported register is compared against all of it: every difference is a finding, not a cleaning step"],
  { x: 0.5, y: 3.4, w: 9.0, h: 1.6 });
s.addNotes("The PS says deciding what must exist to prove a sale is part of the problem. This is our answer.");

// ---------- 5 architecture
s = S("One MCP front door, four databases", "LIGHT", "Solution");
const box = (x, y, w, h, t, fill, fc) => { card(s, x, y, w, h, fill);
  text(s, t, { x, y, w, h, fontSize: 12, bold: true, color: fc || C.text2, align: "center", valign: "middle" }); };
box(0.4, 1.2, 2.2, 0.55, "Judges' AI agent", C.background2);
box(0.4, 1.85, 2.2, 0.55, "Our GPT investigator", C.background2);
box(0.4, 2.5, 2.2, 0.55, "n8n · Shopify app", C.background2);
box(0.4, 3.15, 2.2, 0.55, "Web app (Streamlit)", C.background2);
box(3.0, 1.2, 3.0, 1.3, "MCP Gateway\ntoken → role → only that role's tools\nevery call hash-chained in the trail", C.accent1, C.background1);
box(3.0, 2.7, 1.45, 1.0, "Client tools\nrun the business", C.background2);
box(4.55, 2.7, 1.45, 1.0, "Audit tools\nread-only on the books", C.background2);
box(6.4, 1.2, 3.2, 0.55, "erp.db: books, ledger, edit log", C.background2);
box(6.4, 1.85, 3.2, 0.55, "ext.db: IRN, e-way bill, GSTR, bank", C.background2);
box(6.4, 2.5, 3.2, 0.55, "pbc.db: evidence requests ⇄ uploads", C.background2);
box(6.4, 3.15, 3.2, 0.55, "audit.db: workpaper, findings, trail", C.accent2, C.text1);
s.addShape(pres.shapes.LINE, { x: 2.65, y: 2.15, w: 0.3, h: 0, line: { color: HEX.accent4, width: 2, endArrowType: "triangle" }, objectName: name("arrow") });
s.addShape(pres.shapes.LINE, { x: 6.05, y: 2.15, w: 0.3, h: 0, line: { color: HEX.accent4, width: 2, endArrowType: "triangle" }, objectName: name("arrow") });
text(s, "Python 3.11 · SQLite · official MCP SDK 2.3 · networkx · openpyxl · Streamlit · hosted on Voroa (2 vCPU / 4 GB, CPU only)",
  { x: 0.4, y: 4.15, w: 9.2, h: 0.5, fontSize: 12, color: C.accent4 });
s.addNotes("The web app is itself just another MCP client, so it gets exactly the user's permissions and every click is in the audit trail.");

// ---------- 6 independence + tamper evidence
s = S("Independence is enforced, not promised", "LIGHT", "Trust");
const layers = ["Identity comes only from a token: no tool accepts a role argument",
  "An auditor never even sees client tools (role-filtered tool list)",
  "Auditor connections to the books are read-only inside SQLite: a bug can't write",
  "Adjusting entries are proposals; only management posts them",
  "Only a human partner confirms findings and signs off, in the web app; the MCP server refuses the partner token"];
layers.forEach((t, i) => { dot(s, 0.5, 1.2 + i * 0.66, 0.45, String(i + 1), C.accent1, 13);
  text(s, t, { x: 1.1, y: 1.17 + i * 0.66, w: 4.4, h: 0.55, fontSize: 13, color: C.text1, valign: "middle", margin: 0 }); });
card(s, 5.8, 1.2, 3.8, 3.6);
text(s, "Tamper evidence", { x: 6.0, y: 1.3, w: 3.4, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, ["Hash-chained edit log of every business write (before → after)",
  "Hash-chained audit trail of every agent call, including refusals",
  "Each trail row anchors the books' chain head, in a file the client can't open",
  "A rewritten chain fails at the first anchor; a direct DB edit shows as 'changed outside the application'",
  "Client edits after testing name the field, old → new, who, and every affected sample"],
  { x: 6.0, y: 1.7, w: 3.5, h: 3.0, fontSize: 11 });
s.addNotes("Demo this live: an auditor-token call to create_sales_order is refused and logged; editing the SQLite file directly is caught by verify_integrity.");

// ---------- 7 detectors
s = S("100% testing: 15 detectors", "LIGHT", "Detection");
const det = [["D0", "Register ≠ system of record"], ["D1", "Undisclosed related parties (PAN-in-GSTIN, bank, phone, director)"],
  ["D2", "Related party starting mid-year"], ["D3", "Cut-off by transfer of control"], ["D4", "Turnover with no movement"],
  ["D5", "Period-end spikes in sales and discounts"], ["D6", "Invoice ↔ IRN ↔ e-way bill ↔ GSTR-1 ↔ books"],
  ["D7", "Revenue entries not from a sale"], ["D8", "Forged / other-transaction evidence"], ["D9", "Credit notes after year end"],
  ["D10", "Circular trading"], ["D11", "Changes after testing began"], ["D12", "Ledger and trail integrity"],
  ["D13", "Backdating, sequence breaks"], ["D14", "Instructions hidden in evidence"]];
det.forEach(([c, t], i) => {
  const col = Math.floor(i / 5), row = i % 5, x = 0.5 + col * 3.07, y = 1.2 + row * 0.72;
  dot(s, x, y, 0.5, c, col === 0 ? C.accent1 : col === 1 ? C.accent5 : C.accent4, 11);
  text(s, t, { x: x + 0.6, y, w: 2.35, h: 0.5, fontSize: 11, color: C.text1, valign: "middle", margin: 0 });
});
text(s, "Deterministic rules decide every finding (explainable, reproducible). LLMs only investigate and explain.",
  { x: 0.5, y: 4.85, w: 9.0, h: 0.4, fontSize: 12, italic: true, color: C.accent4 });
s.addNotes("Each hit carries a plain-language reason, the standard (SA / Ind AS / GST), the rupee impact and a proposed adjusting entry.");

// ---------- 8 AuditGraph
s = S("AuditGraph: risk that follows the money", "LIGHT", "Detection");
card(s, 0.5, 1.2, 4.4, 3.4);
text(s, "Scores", { x: 0.7, y: 1.3, w: 4.0, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, ["A: the invoice's own anomaly score (its detector hits)",
  "E = 0.35·C + 0.25·F + 0.15·T + 0.15·H + 0.10·N per company: circular exposure, flagged flows, timing, open exceptions, counterparties",
  "R = 0.7·A + 0.3·E, never below High for hard evidence",
  "Updates on every business event; history is never overwritten",
  "Company flag LOW / MODERATE / HIGH sets the sample size (25 / 30 / 35)"],
  { x: 0.7, y: 1.75, w: 4.05, h: 2.8, fontSize: 12 });
card(s, 5.2, 1.2, 4.3, 3.4);
text(s, "Circular flow (minimum-span decomposition)", { x: 5.4, y: 1.3, w: 3.9, h: 0.4, fontSize: 14, bold: true, color: C.text2 });
const node = (x, y, t) => dot(s, x, y, 0.6, t, C.accent3, 16);
node(6.9, 1.85, "A"); node(5.7, 3.15, "B"); node(8.1, 3.15, "C");
const arrow = (x, y, w, h, flipH) => s.addShape(pres.shapes.LINE, { x, y, w, h, flipH,
  line: { color: HEX.accent4, width: 2, endArrowType: "triangle" }, objectName: name("edge") });
arrow(6.0, 2.4, 0.9, 0.75, true); arrow(6.35, 3.45, 1.7, 0); s.addShape(pres.shapes.LINE, { x: 7.5, y: 2.4, w: 0.75, h: 0.75, line: { color: HEX.accent4, width: 2, beginArrowType: "triangle" }, objectName: name("edge") }); // C -> A
text(s, "₹10 L", { x: 5.75, y: 2.45, w: 0.8, h: 0.3, fontSize: 11, color: C.text1 });
text(s, "₹9 L", { x: 6.85, y: 3.5, w: 0.8, h: 0.3, fontSize: 11, color: C.text1 });
text(s, "₹8 L", { x: 7.95, y: 2.45, w: 0.8, h: 0.3, fontSize: 11, color: C.text1 });
text(s, "Circular value = ₹8 L; residuals 2 / 1 / 0. Reciprocal trade with matching goods (job work) is not flagged.",
  { x: 5.4, y: 3.85, w: 3.9, h: 0.65, fontSize: 11, color: C.text1 });
s.addNotes("Algorithm from 'A Graph Theoretical Approach for Identifying Fraudulent Transactions in Circular Trading' (2017). Cycles close only through the audited company, shared identifiers or group companies: we don't invent visibility into third parties' books.");

// ---------- 9 results
s = S("Results on our synthetic company", "LIGHT", "Evidence");
const fam = metrics && metrics.per_family ? metrics.per_family : {};
const FAMILY = { A: "Undisclosed RP", B: "RP mid-period", C: "Cut-off", D: "No movement", E: "Concentration",
  F: "Statutory", G: "Non-sale revenue", H: "Evidence", I: "Credit notes", J: "Circular", K: "Register ≠ books", L: "Live attacks" };
const famKeys = Object.keys(fam);
const clean = fs.existsSync(path.join(__dirname, "clean_run.json"))
  ? JSON.parse(fs.readFileSync(path.join(__dirname, "clean_run.json"), "utf8")) : null;
if (famKeys.length) {
  s.addChart(pres.charts.BAR, [{ name: "Recall", labels: famKeys.map((k) => FAMILY[k] || k), values: famKeys.map((k) => Math.round(fam[k].recall * 100)) }], {
    x: 0.4, y: 1.15, w: 5.6, h: 3.9, barDir: "bar", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0\"%\"", dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt", catAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk1, valAxisHidden: true, valAxisMaxVal: 110, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, showTitle: true, title: "Planted irregularities caught, by family (%)", titleFontSize: 12, titleFontFace: "+mn-lt", titleColor: HEX.dk2,
  });
} else if (clean) {
  const cc = [[String(clean.zero_fp_detectors.length), `detectors with zero false alarms on ${clean.invoices.toLocaleString("en-IN")} clean invoices`],
    [`${clean.cycles} cycles`, `found in the planted trading network: ₹${clean.circular_inr} circular value`],
    [`~${clean.analytics_seconds} s`, "to run all detectors over 100% of the year on a laptop CPU"]];
  cc.forEach(([n, l], i) => {
    card(s, 0.4, 1.15 + i * 1.3, 5.6, 1.15);
    text(s, n, { x: 0.6, y: 1.2 + i * 1.3, w: 1.9, h: 1.05, fontSize: 28, bold: true, color: C.text2, valign: "middle", fontFace: THEME.headFontFace });
    text(s, l, { x: 2.5, y: 1.2 + i * 1.3, w: 3.4, h: 1.05, fontSize: 13, color: C.text1, valign: "middle" });
  });
}
const pct = (v) => (v === undefined || v === null ? "—" : `${Math.round(v * 100)}%`);
const abl = metrics ? metrics.ablation_recall_at_k || {} : {};
const ablVals = Object.values(abl);
const callouts = [[pct(metrics && metrics.recall), "of planted irregularities caught"],
  [pct(metrics && metrics.precision_sev4), "precision of severity-4+ hits"],
  [ablVals.length ? `${pct(ablVals[0])} → ${pct(ablVals[ablVals.length - 1])}` : "—", `planted invoices in the top ${metrics ? metrics.k : 30} by risk: transaction-only → full AuditGraph`]];
if (metrics) callouts.forEach(([n, l], i) => {
  card(s, 6.3, 1.15 + i * 1.3, 3.3, 1.15);
  text(s, n, { x: 6.45, y: 1.2 + i * 1.3, w: 3.0, h: 0.55, fontSize: 26, bold: true, color: C.text2, fontFace: THEME.headFontFace });
  text(s, l, { x: 6.45, y: 1.72 + i * 1.3, w: 3.0, h: 0.5, fontSize: 11, color: C.text1 });
});
if (!metrics && clean) text(s, "Recall per irregularity family and the AuditGraph ablation appear here once the planted set and answer key are complete (python -m app.evaluate).", { x: 6.3, y: 1.15, w: 3.3, h: 3.6, fontSize: 13, italic: true, color: C.accent4, valign: "middle" });
text(s, "Prototype performance on a dataset we designed (7,000 invoices, planted irregularities kept in a held-out answer key the engine never reads). Not a claim of real-world accuracy.",
  { x: 0.4, y: 5.05, w: 8.7, h: 0.45, fontSize: 10, italic: true, color: C.accent4 });
s.addNotes("Numbers from python -m app.evaluate. The ablation compares transaction features only, plus graph features, plus entity risk: the measured benefit of AuditGraph.");

// ---------- 10 demo flow
s = S("Live demo: plant it, catch it, sign it", "LIGHT", "Evidence");
const steps = ["Judge card: the auditor token can't even see client tools",
  "Replay the year: risk scores move as events arrive",
  "As the client: plant a 31-Mar invoice shipped 2-Apr, a director's bank account on a customer, a manual sales journal; upload a doctored register",
  "As the auditor: reconcile → analytics → risk-based samples with seed and reasons → forged evidence caught",
  "Client edits an LR date → the stale sample is named; a direct DB edit → integrity alert",
  "Partner confirms findings and signs off; workpaper + memo + trail verified offline"];
steps.forEach((t, i) => {
  const y = 1.15 + i * 0.66;
  dot(s, 0.5, y, 0.48, String(i + 1), i === 5 ? C.accent2 : C.accent1, 14);
  text(s, t, { x: 1.15, y: y - 0.04, w: 8.3, h: 0.56, fontSize: 13, color: C.text1, valign: "middle", margin: 0 });
});
s.addNotes("About 4 minutes. Backup: the screen recording, in case the venue network fails.");

// ---------- 11 deliverables
s = S("Deliverables a partner would sign", "LIGHT", "Evidence");
const deliv = [["Workpaper (.xlsx)", ["Sales Register pasted exactly as received + auditor columns", "Sales TOD, Sales Cut-off TOD, Credit Note TOD in the PS figure layout", "Objective, work done, tick marks, prepared / reviewed"]],
  ["Findings memo", ["Each finding in plain language with the SA / Ind AS / GST basis", "₹ impact and proposed adjusting entries (GST treated correctly)", "SA 450 summary, s.143(12) consideration"]],
  ["Audit trail", ["Every agent and human action, hash-chained", "Anchored to the books' chain", "Verifiable offline with one script"]]];
deliv.forEach(([h, items], i) => {
  const x = 0.5 + i * 3.05;
  card(s, x, 1.2, 2.85, 3.5);
  dot(s, x + 0.2, 1.35, 0.5, "✓", C.accent2, 16);
  text(s, h, { x: x + 0.8, y: 1.35, w: 1.95, h: 0.5, fontSize: 15, bold: true, color: C.text2, valign: "middle", margin: 0 });
  bullets(s, items, { x: x + 0.15, y: 2.0, w: 2.6, h: 2.6, fontSize: 12 });
});
s.addNotes("The AI proposes; the human partner decides every finding with a mandatory comment, then signs off with the identity on record.");

// ---------- 12 sponsors + limits
s = S("Built with our sponsors, honest about limits", "LIGHT", "Close");
const spons = [["Voroa", "Hosts both services; runs on 2 vCPU / 4 GB, no GPU"], ["n8n", "Upload alerts, evidence emails and reminders, 15-min continuous monitoring via MCP"],
  ["ShipReady", "Shopify connector feeding orders, discounts and refunds into the system of record"], ["OpenAI", "Investigator agent (just another MCP client) and document reading, under a cost cap"]];
spons.forEach(([h, d], i) => {
  const y = 1.15 + i * 0.85;
  card(s, 0.5, y, 4.6, 0.72);
  text(s, h, { x: 0.65, y, w: 1.2, h: 0.72, fontSize: 14, bold: true, color: C.text2, valign: "middle", margin: 0 });
  text(s, d, { x: 1.9, y, w: 3.1, h: 0.72, fontSize: 11, color: C.text1, valign: "middle", margin: 0 });
});
card(s, 5.4, 1.15, 4.2, 3.4);
text(s, "Limitations", { x: 5.6, y: 1.25, w: 3.8, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
bullets(s, ["Government and bank records are simulated: they show how a real portal check works, not real independence",
  "The graph only sees entities we have records for",
  "Weights are provisional; scores rank risk, they are not fraud probabilities",
  "Accuracy is measured on our own synthetic data"], { x: 5.6, y: 1.7, w: 3.85, h: 2.8, fontSize: 12 });
s.addNotes("Say the limitations out loud: judges reward honesty about what a prototype proves.");

// ---------- 13 close
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Close" }); // section declared by slide 12
s.addText("Connect your agent and try to fool it", { placeholder: "title" });
s.addText([{ text: "MCP endpoint on Voroa + a token from the judge card", options: { breakLine: true } },
  { text: "claude mcp add --transport http auditpilot <url>/mcp --header \"Authorization: Bearer aud_…\"", options: { fontFace: "Courier New", fontSize: 11, color: C.accent2, breakLine: true } },
  { text: "Team ELEV01: Shriyans · Ibrahim · Darshan · Aarav", options: { fontSize: 14 } }], { placeholder: "body" });
s.addNotes("Invite judges to plant their own irregularities live with the client token and audit with the auditor token.");

(async () => {
  const out = path.join(__dirname, "AuditPilot_AI_ELEV01.pptx");
  await pres.writeFile({ fileName: out });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(out, THEME);
  }
  console.log("wrote", out, metrics ? "(with metrics)" : "(no metrics.json yet)");
})();
