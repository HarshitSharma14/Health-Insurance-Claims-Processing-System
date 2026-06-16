/**
 * Generate matching sample document images (JPG) for every dev-panel case,
 * rendered from HTML via Playwright/Chromium. Output → frontend/public/casedocs/.
 *
 * Run:  node scripts/gen_docs.mjs   (from frontend/)
 *
 * Each case gets a document set whose extracted content drives its expected
 * outcome. Patient names are kept consistent within a case so the live
 * patient-identity check does not false-trigger (except TC003, which is
 * intentionally mismatched).
 */
import { chromium } from "@playwright/test";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { mkdirSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "public", "casedocs");
mkdirSync(OUT, { recursive: true });

// ── HTML templates ──────────────────────────────────────────────────────────

const css = `
  *{margin:0;padding:0;box-sizing:border-box;font-family:Arial,Helvetica,sans-serif}
  body{width:760px;background:#fff;color:#111}
  .doc{padding:0}
  .hdr{padding:14px 20px;border-bottom:3px solid var(--c)}
  .hdr.fill{background:var(--c);color:#fff;border:none}
  .org{font-size:21px;font-weight:bold}
  .sub{font-size:11px;opacity:.85;margin-top:2px}
  .addr{font-size:11px;opacity:.8;margin-top:4px}
  .band{background:#f2f4fb;padding:7px 20px;display:flex;justify-content:space-between;
        border-bottom:1px solid #d4dcf0}
  .band .t{font-weight:bold;color:var(--c);font-size:14px}
  .band .m{font-size:11px;color:#555;text-align:right}
  .pg{display:flex;flex-wrap:wrap;border-bottom:1px solid #ddd}
  .pg .c{padding:8px 14px;border-right:1px solid #ddd;min-width:33%}
  .pg label{font-size:10px;text-transform:uppercase;color:#888;display:block;letter-spacing:.4px}
  .pg span{font-size:14px;font-weight:bold}
  .body{padding:14px 20px}
  .row{margin-bottom:10px;font-size:14px}
  .row b{color:#444}
  .diag{font-weight:bold;color:#b3261e;font-size:15px}
  table{width:100%;border-collapse:collapse;margin-top:6px}
  th{background:#eef2ff;text-align:left;padding:8px 14px;font-size:11px;text-transform:uppercase;
     color:var(--c);border-bottom:2px solid #d4dcf0}
  th.r,td.r{text-align:right}
  td{padding:8px 14px;border-bottom:1px solid #eee;font-size:13px}
  td.n{font-family:monospace;text-align:right}
  .tot{display:flex;justify-content:space-between;padding:7px 14px;border-top:2px solid var(--c);
       font-weight:bold;font-size:15px}
  ul{margin:6px 0 0 18px}.ul li{font-size:13px}
  .ftr{padding:12px 20px;border-top:1px dashed #bbb;font-size:11px;color:#666;display:flex;
       justify-content:space-between;align-items:flex-end}
  .sig{text-align:right}.sigl{border-top:1px solid #333;width:150px;margin:0 0 4px auto}
`;

function shell(color, inner) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head>
    <body><div class="doc" style="--c:${color}">${inner}</div></body></html>`;
}

function patientGrid(d) {
  const cells = [
    ["Patient Name", d.patient],
    ["Member ID", d.member || "—"],
    ["Date", d.date || "—"],
    d.doctor ? ["Ref. Doctor", d.doctor] : null,
    d.hospital ? ["Provider", d.hospital] : null,
  ].filter(Boolean);
  return `<div class="pg">${cells.map(([l, v]) =>
    `<div class="c"><label>${l}</label><span>${v}</span></div>`).join("")}</div>`;
}

function prescription(d) {
  const meds = (d.meds || []).map((m, i) => `<tr><td>${i + 1}</td><td>${m}</td></tr>`).join("");
  return shell("#1a3a6b", `
    <div class="hdr">
      <div class="org">${d.doctor}</div>
      <div class="sub">${d.quals || "MBBS, MD"} &nbsp;|&nbsp; Reg. No: ${d.reg || "KA/00000/2015"}</div>
      <div class="addr">${d.clinic || "City Medical Centre"}, Bengaluru &nbsp;|&nbsp; Ph: +91-80-22001234</div>
    </div>
    <div class="band"><div class="t">PRESCRIPTION (Rx)</div>
      <div class="m"><div>Rx No: ${d.no || "RX/2024/0001"}</div><div>Date: ${d.date}</div></div></div>
    ${patientGrid(d)}
    <div class="body">
      ${d.complaint ? `<div class="row"><b>Chief Complaint:</b> ${d.complaint}</div>` : ""}
      <div class="row"><b>Diagnosis:</b> <span class="diag">${d.diagnosis}</span></div>
      ${d.treatment ? `<div class="row"><b>Advised Treatment:</b> ${d.treatment}</div>` : ""}
      ${meds ? `<div class="row"><b>Rx:</b><table><tbody>${meds}</tbody></table></div>` : ""}
      ${d.tests ? `<div class="row"><b>Investigations Advised:</b><ul class="ul">${
        d.tests.map(t => `<li>${t}</li>`).join("")}</ul></div>` : ""}
    </div>
    <div class="ftr"><div>Computer-generated prescription.</div>
      <div class="sig"><div class="sigl"></div><div><b>${d.doctor}</b></div><div>${d.reg || ""}</div></div></div>`);
}

function bill(d) {
  const rows = (d.items || []).map((it, i) =>
    `<tr><td>${i + 1}</td><td>${it.desc}</td><td class="n">${it.amt.toLocaleString("en-IN")}.00</td></tr>`).join("");
  return shell("#1a3a6b", `
    <div class="hdr fill"><div class="org">${d.hospital}</div>
      <div class="sub">${d.sub || "Multi-Specialty OPD & Diagnostic Centre"}</div>
      <div class="addr">Bengaluru &nbsp;|&nbsp; GSTIN: 29AXXXX1234X1ZX</div></div>
    <div class="band"><div class="t">${d.title || "RECEIPT / TAX INVOICE"}</div>
      <div class="m"><div>Bill No: ${d.no || "BILL/2024/0001"}</div><div>Date: ${d.date}</div></div></div>
    ${patientGrid(d)}
    <table><thead><tr><th style="width:30px">#</th><th>Description</th>
      <th class="r" style="width:120px">Amount (₹)</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="tot"><div>TOTAL</div><div>₹ ${d.total.toLocaleString("en-IN")}.00</div></div>
    <div class="ftr"><div>Mode of Payment: Insurance (Plum GHI 2024)</div>
      <div class="sig"><div class="sigl"></div><div><b>Authorised Signatory</b></div></div></div>`);
}

function lab(d) {
  return shell("#6a1b9a", `
    <div class="hdr"><div class="org">${d.lab || "Apollo Diagnostics"}</div>
      <div class="sub">Advanced Imaging & Pathology — NABL Accredited</div>
      <div class="addr">Bengaluru &nbsp;|&nbsp; ISO 15189:2012</div></div>
    <div class="band"><div class="t">${d.title || "LAB / RADIOLOGY REPORT"}</div>
      <div class="m"><div>Report No: ${d.no || "LAB/2024/0001"}</div><div>Date: ${d.date}</div></div></div>
    ${patientGrid(d)}
    <div class="body">
      <div class="row"><b>Test:</b> <span class="diag">${d.test}</span></div>
      ${d.findings ? `<div class="row"><b>Findings:</b> ${d.findings}</div>` : ""}
      ${d.impression ? `<div class="row"><b>Impression:</b> ${d.impression}</div>` : ""}
      ${d.amount ? `<div class="row"><b>Amount Charged:</b> ₹ ${d.amount.toLocaleString("en-IN")}.00</div>` : ""}
    </div>
    <div class="ftr"><div>Clinical correlation advised.</div>
      <div class="sig"><div class="sigl"></div><div><b>Dr. P. Kulkarni, MD (Radiology)</b></div></div></div>`);
}

function pharmacy(d) {
  const rows = (d.items || []).map((it, i) =>
    `<tr><td>${i + 1}</td><td>${it.desc}</td><td class="n">${it.amt.toFixed(2)}</td></tr>`).join("");
  return shell("#2e7d32", `
    <div class="hdr"><div class="org">${d.shop || "MedPlus Pharmacy"}</div>
      <div class="sub">Authorised Retail Chemist</div>
      <div class="addr">Bengaluru &nbsp;|&nbsp; Drug Licence: KA-BLR-2019-DL-04521</div></div>
    <div class="band"><div class="t">PHARMACY BILL / CASH MEMO</div>
      <div class="m"><div>Bill No: ${d.no || "MP/2024/0001"}</div><div>Date: ${d.date}</div></div></div>
    ${patientGrid(d)}
    <table><thead><tr><th style="width:30px">#</th><th>Medicine / Product</th>
      <th class="r" style="width:110px">Amount (₹)</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="tot"><div>NET PAYABLE</div><div>₹ ${d.total.toFixed(2)}</div></div>
    <div class="ftr"><div>Dispensed against valid prescription.</div>
      <div class="sig"><div class="sigl"></div><div><b>Pharmacist</b></div></div></div>`);
}

// ── Per-case document manifest ───────────────────────────────────────────────
// Each entry: { file, kind, data, blur? }. Patient names are consistent within
// a case (except tc003, intentionally mismatched).

const TEMPLATES = { prescription, bill, lab, pharmacy };

const RX = (d) => ({ kind: "prescription", ...d });
const BILL = (d) => ({ kind: "bill", ...d });
const LAB = (d) => ({ kind: "lab", ...d });
const PHARM = (d) => ({ kind: "pharmacy", ...d });

const DOCS = {
  // TC004 — clean consultation
  "tc004_rx":   RX({ patient: "Rajesh Kumar", member: "EMP001", date: "01-Nov-2024", doctor: "Dr. Arun Sharma", reg: "KA/45678/2015", complaint: "Fever 3 days", diagnosis: "Viral Fever", meds: ["Tab Paracetamol 650mg 1-1-1 x5d", "Tab Vitamin C 500mg 0-0-1 x7d"], tests: ["CBC", "Dengue NS1"] }),
  "tc004_bill": BILL({ hospital: "City Medical Centre", patient: "Rajesh Kumar", member: "EMP001", date: "01-Nov-2024", doctor: "Dr. Arun Sharma", items: [{ desc: "Consultation Fee (OPD)", amt: 1000 }, { desc: "CBC Test", amt: 300 }, { desc: "Dengue NS1 Test", amt: 200 }], total: 1500 }),
  // TC005 — diabetes (waiting period)
  "tc005_rx":   RX({ patient: "Vikram Joshi", member: "EMP005", date: "15-Oct-2024", doctor: "Dr. Sunil Mehta", reg: "GJ/56789/2014", diagnosis: "Type 2 Diabetes Mellitus", meds: ["Tab Metformin 500mg", "Tab Glimepiride 1mg"] }),
  "tc005_bill": BILL({ hospital: "City Diabetes Care", patient: "Vikram Joshi", member: "EMP005", date: "15-Oct-2024", items: [{ desc: "Diabetology Consultation", amt: 3000 }], total: 3000 }),
  // TC007 — MRI pre-auth
  "tc007_rx":   RX({ patient: "Suresh Patil", member: "EMP007", date: "02-Nov-2024", doctor: "Dr. Venkat Rao", reg: "AP/67890/2017", diagnosis: "Suspected Lumbar Disc Herniation", tests: ["MRI Lumbar Spine"] }),
  "tc007_lab":  LAB({ patient: "Suresh Patil", member: "EMP007", date: "02-Nov-2024", title: "RADIOLOGY REPORT — MRI LUMBAR SPINE", test: "MRI Lumbar Spine", impression: "L5-S1 broad-based posterior disc herniation with left S1 nerve root compression.", amount: 15000 }),
  "tc007_bill": BILL({ hospital: "Apollo Diagnostics", patient: "Suresh Patil", member: "EMP007", date: "02-Nov-2024", items: [{ desc: "MRI Lumbar Spine (without contrast)", amt: 15000 }], total: 15000 }),
  // TC008 — per-claim limit exceeded
  "tc008_rx":   RX({ patient: "Amit Verma", member: "EMP003", date: "20-Oct-2024", doctor: "Dr. R. Gupta", reg: "DL/34567/2016", diagnosis: "Gastroenteritis", meds: ["Antibiotics", "Probiotics", "ORS"] }),
  "tc008_bill": BILL({ hospital: "City Medical Centre", patient: "Amit Verma", member: "EMP003", date: "20-Oct-2024", items: [{ desc: "Consultation Fee", amt: 2000 }, { desc: "Medicines", amt: 5500 }], total: 7500 }),
  // TC009 — fraud same-day
  "tc009_rx":   RX({ patient: "Ravi Menon", member: "EMP008", date: "30-Oct-2024", doctor: "Dr. S. Khan", reg: "KA/22334/2016", diagnosis: "Migraine" }),
  "tc009_bill": BILL({ hospital: "City Medical Centre", patient: "Ravi Menon", member: "EMP008", date: "30-Oct-2024", items: [{ desc: "Neurology Consultation", amt: 4800 }], total: 4800 }),
  // TC010 — network discount (Apollo)
  "tc010_rx":   RX({ patient: "Deepak Shah", member: "EMP010", date: "03-Nov-2024", doctor: "Dr. S. Iyer", reg: "TN/56789/2013", diagnosis: "Acute Bronchitis", meds: ["Amoxicillin 500mg", "Salbutamol Inhaler"] }),
  "tc010_bill": BILL({ hospital: "Apollo Hospitals", patient: "Deepak Shah", member: "EMP010", date: "03-Nov-2024", items: [{ desc: "Consultation Fee", amt: 1500 }, { desc: "Medicines", amt: 3000 }], total: 4500 }),
  // TC011 — alt medicine (component failure)
  "tc011_rx":   RX({ patient: "Kavita Nair", member: "EMP006", date: "28-Oct-2024", doctor: "Vaidya T. Krishnan", reg: "AYUR/KL/2345/2019", diagnosis: "Chronic Joint Pain", treatment: "Panchakarma Therapy" }),
  "tc011_bill": BILL({ hospital: "Ayur Wellness Centre", patient: "Kavita Nair", member: "EMP006", date: "28-Oct-2024", items: [{ desc: "Panchakarma Therapy (5 sessions)", amt: 3000 }, { desc: "Consultation", amt: 1000 }], total: 4000 }),
  // TC012 — bariatric exclusion
  "tc012_rx":   RX({ patient: "Anita Desai", member: "EMP009", date: "18-Oct-2024", doctor: "Dr. P. Banerjee", reg: "WB/34567/2015", diagnosis: "Morbid Obesity (BMI 37)", treatment: "Bariatric Consultation and Customised Diet Plan" }),
  "tc012_bill": BILL({ hospital: "City Medical Centre", patient: "Anita Desai", member: "EMP009", date: "18-Oct-2024", items: [{ desc: "Bariatric Consultation", amt: 3000 }, { desc: "Personalised Diet and Nutrition Program", amt: 5000 }], total: 8000 }),
  // TC003 — patient mismatch (rx Rajesh, bill Arjun)
  "tc003_rx":   RX({ patient: "Rajesh Kumar", member: "EMP001", date: "01-Nov-2024", doctor: "Dr. Arun Sharma", reg: "KA/45678/2015", diagnosis: "Viral Fever", meds: ["Paracetamol 650mg"] }),
  "tc003_bill": BILL({ hospital: "City Medical Centre", patient: "Arjun Mehta", member: "EMP001", date: "01-Nov-2024", items: [{ desc: "Consultation Fee", amt: 1500 }], total: 1500 }),
  // TC002 — unreadable pharmacy bill (good rx + blurred bill)
  "tc002_rx":   RX({ patient: "Sneha Reddy", member: "EMP004", date: "25-Oct-2024", doctor: "Dr. R. Nair", reg: "KA/98765/2018", diagnosis: "Acute Pharyngitis", meds: ["Amoxicillin 500mg"] }),
  "tc002_blurry": { ...PHARM({ shop: "MedPlus Pharmacy", patient: "Sneha Reddy", member: "EMP004", date: "25-Oct-2024", items: [{ desc: "Amoxicillin 500mg", amt: 300 }, { desc: "Paracetamol 650mg", amt: 200 }, { desc: "Cough Syrup", amt: 300 }], total: 800 }), blur: 14 },
  // EX001 — vision partial (glasses covered, LASIK excluded)
  "ex001_rx":   RX({ patient: "Rajesh Kumar", member: "EMP001", date: "10-Nov-2024", doctor: "Dr. Anand Rao", reg: "KA/77001/2016", diagnosis: "Myopia + Astigmatism", treatment: "Corrective Glasses" }),
  "ex001_bill": BILL({ hospital: "Eye Care Centre", patient: "Rajesh Kumar", member: "EMP001", date: "10-Nov-2024", items: [{ desc: "Eye Examination", amt: 500 }, { desc: "Glasses (single-vision lenses + frame)", amt: 2500 }, { desc: "LASIK Surgery Consultation", amt: 4500 }], total: 7500 }),
  // EX002 — pharmacy below minimum
  "ex002_rx":   RX({ patient: "Sneha Reddy", member: "EMP004", date: "05-Nov-2024", doctor: "Dr. R. Nair", reg: "KA/98765/2018", diagnosis: "Acute Pharyngitis", meds: ["Amoxicillin 500mg", "Paracetamol 650mg"] }),
  "ex002_pharm": PHARM({ shop: "MedPlus Pharmacy", patient: "Sneha Reddy", member: "EMP004", date: "05-Nov-2024", items: [{ desc: "Amoxicillin 500mg (generic)", amt: 108 }, { desc: "Azithromycin 500mg (generic)", amt: 77 }, { desc: "Paracetamol 650mg", amt: 25 }, { desc: "Vitamin C + Zinc", amt: 114 }, { desc: "ORS Sachets", amt: 48 }, { desc: "Gargle 100ml", amt: 90 }], total: 462 }),
  // EX003 — dental sub-limit cap (all covered, total > 10000)
  "ex003_bill": BILL({ hospital: "Smile Dental Clinic", title: "DENTAL TREATMENT BILL", patient: "Kavita Nair", member: "EMP006", date: "12-Nov-2024", items: [{ desc: "Root Canal Treatment", amt: 8000 }, { desc: "Crown Placement", amt: 5000 }], total: 13000 }),
  // EX004 — hypertension waiting period
  "ex004_rx":   RX({ patient: "Vikram Joshi", member: "EMP005", date: "20-Oct-2024", doctor: "Dr. Priya Mehta", reg: "GJ/44321/2016", diagnosis: "Essential Hypertension (HTN)", meds: ["Amlodipine 5mg", "Telmisartan 40mg"] }),
  "ex004_bill": BILL({ hospital: "City Heart Clinic", patient: "Vikram Joshi", member: "EMP005", date: "20-Oct-2024", items: [{ desc: "Cardiology Consultation", amt: 2500 }], total: 2500 }),
  // EX005 — cataract waiting period (vision)
  "ex005_rx":   RX({ patient: "Vikram Joshi", member: "EMP005", date: "01-Dec-2024", doctor: "Dr. Kavitha Iyer", reg: "GJ/55678/2014", diagnosis: "Senile Cataract - right eye", treatment: "Phacoemulsification Cataract Surgery" }),
  "ex005_bill": BILL({ hospital: "Vision Eye Hospital", patient: "Vikram Joshi", member: "EMP005", date: "01-Dec-2024", items: [{ desc: "Cataract Surgery (phaco) RE", amt: 4500 }], total: 4500 }),
  // EX006 — infertility exclusion
  "ex006_rx":   RX({ patient: "Priya Singh", member: "EMP002", date: "25-Oct-2024", doctor: "Dr. Shalini Roy", reg: "KA/33445/2015", diagnosis: "Primary Infertility - IVF Consultation", treatment: "IVF Protocol Assessment and Hormonal Stimulation Plan" }),
  "ex006_bill": BILL({ hospital: "Fertility Care Centre", patient: "Priya Singh", member: "EMP002", date: "25-Oct-2024", items: [{ desc: "IVF Consultation", amt: 1500 }, { desc: "Hormonal Workup (FSH, LH, AMH)", amt: 2000 }], total: 3500 }),
  // EX007 — member not found
  "ex007_rx":   RX({ patient: "Unknown Member", member: "EMP999", date: "01-Nov-2024", doctor: "Dr. A. Kumar", diagnosis: "Viral Fever", meds: ["Paracetamol"] }),
  "ex007_bill": BILL({ hospital: "City Medical Centre", patient: "Unknown Member", member: "EMP999", date: "01-Nov-2024", items: [{ desc: "Consultation", amt: 1200 }], total: 1200 }),
  // EX008 — diagnostic network (Fortis)
  "ex008_rx":   RX({ patient: "Amit Verma", member: "EMP003", date: "15-Nov-2024", doctor: "Dr. Suresh Rao", reg: "KA/12345/2013", diagnosis: "Suspected Liver Function Abnormality", tests: ["LFT", "Ultrasound Abdomen", "CBC"] }),
  "ex008_lab":  LAB({ patient: "Amit Verma", member: "EMP003", date: "15-Nov-2024", title: "PATHOLOGY REPORT", test: "LFT + USG Abdomen + CBC", findings: "Mildly elevated ALT/AST; USG shows grade I fatty liver.", amount: 4800 }),
  "ex008_bill": BILL({ hospital: "Fortis Healthcare", patient: "Amit Verma", member: "EMP003", date: "15-Nov-2024", items: [{ desc: "Liver Function Tests (LFT)", amt: 1800 }, { desc: "Ultrasound Abdomen", amt: 2000 }, { desc: "CBC", amt: 1000 }], total: 4800 }),
  // TC001 — wrong docs (single prescription, reused twice in frontend)
  "tc001_rx":   RX({ patient: "Rajesh Kumar", member: "EMP001", date: "01-Nov-2024", doctor: "Dr. Arun Sharma", reg: "KA/45678/2015", diagnosis: "Viral Fever", meds: ["Paracetamol 650mg", "Vitamin C 500mg"] }),
};

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 760, height: 1200 }, deviceScaleFactor: 2 });
  let n = 0;
  for (const [file, d] of Object.entries(DOCS)) {
    const html = TEMPLATES[d.kind](d);
    const wrapped = d.blur
      ? html.replace("<body>", `<body><div style="filter:blur(${d.blur}px)">`).replace("</body>", "</div></body>")
      : html;
    await page.setContent(wrapped, { waitUntil: "networkidle" });
    const el = await page.$(".doc");
    await el.screenshot({ path: join(OUT, `${file}.jpg`), type: "jpeg", quality: 90 });
    n++;
    process.stdout.write(`  ${file}.jpg\n`);
  }
  await browser.close();
  console.log(`\nGenerated ${n} document images → public/casedocs/\n`);
}

main();
