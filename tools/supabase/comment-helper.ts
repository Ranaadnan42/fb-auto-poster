// comment-helper — roz Facebook par woh public posts/groups dhoondta hai jahan log POS, website, app,
// social media ya video automation ka poochh rahe hon; har post ke liye insaani comment likh kar Rana ko email karta hai.
// Rana khud link khol kar comment paste karta hai (bot khud comment NAHI karta — account safe rehta hai).
// Search: GitHub Actions (tools/fb_search.py -> comment_hits.json). Ye function us file ko parhta hai.
// Trigger: pg_cron POST + header x-run-key (app_settings.fb_comment_run_key). ?test=1 -> email nahi, sirf JSON.
// Secrets: GROQ_API_KEY, GEMINI_API_KEY (backup), BREVO_API_KEY
// KHUD-ILAAJ: AI fallback (Groq 120b -> 20b -> Gemini, 429 par ruk kar dobara), email 3 dafa koshish (fail ho to posts
// agle run ke liye bachi rehti hain), hits file purani ho to khud thori search, 45 min baad retry cron (?retry=1 -
// agar pichhla run kamyab tha to kuch nahi karta), aur lagatar 2 dafa fail ho to Rana ko chhota alert.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const GROQ = Deno.env.get("GROQ_API_KEY") ?? "";
const GEMINI = Deno.env.get("GEMINI_API_KEY") ?? "";
const BREVO = Deno.env.get("BREVO_API_KEY") ?? "";
const TO_EMAIL = "ranaadnan320@gmail.com";
const SENDER = "snapcomputer420@gmail.com";
const MAX_SEND = 15;
const db = createClient(SUPABASE_URL, SERVICE_ROLE);
const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });

// sirf post/group wale link — page ka home link comment ke kaam ka nahi
const POST_URL = /facebook\.com\/(groups\/|.*\/posts\/|.*\/permalink|permalink\.php|story\.php|.*\/videos\/|reel\/|share\/p\/|photo|.*\/photos\/)/i;

type Hit = { id: string; url: string; title: string; snippet: string };
type Good = { url: string; title: string; why: string; lang: string; comment: string };

async function timed(url: string, init: RequestInit = {}, ms = 15000) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  try { return await fetch(url, { ...init, signal: c.signal }); } finally { clearTimeout(t); }
}

// Search GitHub Actions par hoti hai (tools/fb_search.py) — DuckDuckGo Supabase ke IP ko block karta hai.
const HITS_URL = "https://raw.githubusercontent.com/Ranaadnan42/fb-auto-poster/main/comment_hits.json";

let HITS_AGE_H = 999;
async function loadHits(debug: string[]): Promise<Omit<Hit, "id">[]> {
  try {
    const r = await timed(HITS_URL + "?t=" + Date.now(), {}, 20000);
    const j = await r.json();
    HITS_AGE_H = (Date.now() - Date.parse(String(j.updated).replace(/Z$/, ":00Z"))) / 3600e3;
    debug.push(`hits file: updated ${j.updated} (${HITS_AGE_H.toFixed(1)}h old), new ${j.new}, total ${(j.hits ?? []).length}`);
    return (j.hits ?? []).map((h: any) => ({ url: String(h.url).replace(/\/members$/, ""), title: String(h.title ?? ""), snippet: String(h.snippet ?? "") }));
  } catch (e) { debug.push(`hits file err ${(e as Error).message}`); return []; }
}

async function ai(prompt: string, debug: string[]): Promise<string> {
  if (GROQ) {
    for (const model of ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]) {
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const r = await timed("https://api.groq.com/openai/v1/chat/completions", {
            method: "POST", headers: { Authorization: `Bearer ${GROQ}`, "Content-Type": "application/json" },
            body: JSON.stringify({ model, temperature: 0.4, max_tokens: 4000, reasoning_effort: "low",
              response_format: { type: "json_object" }, messages: [{ role: "user", content: prompt }] }),
          }, 60000);
          if (r.status === 429) { debug.push(`groq ${model} 429`); await new Promise((s) => setTimeout(s, 8000)); continue; }
          if (!r.ok) { debug.push(`groq ${model} ${r.status}`); break; }
          const out = (await r.json())?.choices?.[0]?.message?.content?.trim();
          if (out) return out;
        } catch (e) { debug.push(`groq ${model}: ${(e as Error).message}`); break; }
      }
    }
  }
  if (GEMINI) {
    try {
      const r = await timed("https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent", {
        method: "POST", headers: { "x-goog-api-key": GEMINI, "Content-Type": "application/json" },
        body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.4, maxOutputTokens: 4000, responseMimeType: "application/json" } }),
      }, 60000);
      const out = (await r.json())?.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
      if (out) return out;
    } catch (e) { debug.push(`gemini: ${(e as Error).message}`); }
  }
  throw new Error("AI failed");
}

// Sirf yehi sach facts — comment in se bahar koi feature claim na kare.
const ABOUT = `We are "Web Builder" (Rana, Pakistan; WhatsApp +92 307 5267349). EXACT facts (do not add anything else):
- Rana POS: Windows billing/cashier software for shops, restaurants, supermarkets, pharmacies. Works OFFLINE. Fast billing,
  barcode scanning, stock/inventory, daily sales & profit reports, receipt printing. One-time license, no monthly fee.
  Saudi version has ZATCA Phase-2 e-invoicing. Sold in Pakistan, Saudi Arabia and UAE. Free live demo on WhatsApp.
  It does NOT have: cloud sync, live multi-branch sync, mobile/Android POS app, machine/vending integration, multi-currency,
  web dashboard, API. Never claim those.
- Websites & online stores (worldwide; we can even make a free sample website for their business first), custom Android apps
  (worldwide), social media page management (posts/reels/replies), AutoPilot Media (AI makes and uploads daily YouTube/Facebook videos).`;

async function judgeBatch(batch: Hit[], debug: string[]): Promise<Good[]> {
  const list = batch.map((h) => `[${h.id}] ${h.url}\n${h.title}\n${h.snippet}`).join("\n\n");
  const prompt = `${ABOUT}\n\nBelow are public Facebook posts/groups found by search, each with an id in [brackets], then url, title, snippet.\n` +
    `For EACH item, decide "ok": true ONLY if the snippet/title CLEARLY shows a real person or business who WANTS TO BUY / is LOOKING FOR / ` +
    `asking recommendations about something we sell, AND our product truly fits: POS only for shops in Pakistan, Saudi Arabia, ` +
    `UAE or other Gulf countries, and only if their need is covered by the EXACT facts; websites, apps, social media management ` +
    `and AutoPilot Media for anyone worldwide. When unsure, ok=false.\n` +
    `ok=false for: anyone OFFERING/SELLING the same service or devices (developers/agencies advertising, "contact me", "we build", ` +
    `"starting at $", buy/sell groups for devices, portfolios), competitors' release notes, job vacancies for employees, news, ` +
    `tutorials/courses, unrelated topics, needs we can't meet (cloud/multi-branch/machine integration), or unclear text.\n` +
    `If the URL is a GROUP home (no /posts/ or /permalink/ in it), ok=true only if the group name shows it is for BUYERS ` +
    `(e.g. "I need a website", shop owners, restaurant owners) — not developer/seller groups; then the "comment" is a short ` +
    `friendly group POST offering our help (same rules).\n` +
    `The comment MUST be about THAT item's own topic (a YouTube automation post gets an AutoPilot Media comment, a website request ` +
    `gets a website comment, etc.). For ok=true write "comment": a short, natural, helpful reply (2-3 sentences) like a real ` +
    `person — first one genuinely useful, honest tip for their exact need, then say Web Builder makes this and they can WhatsApp ` +
    `+92 307 5267349 for a free demo. Mention ONLY features from the EXACT facts. Language = the language of THAT item's ` +
    `title/snippet: Arabic -> Arabic, Urdu or Roman Urdu -> Roman Urdu, otherwise English. No links, no hashtags, no prices, ` +
    `max 1 emoji, never pushy.\n` +
    `"why": one short line in Roman Urdu: what exactly this person asked.\n` +
    `Return ONLY JSON {"r":[{"id":"<the id>","ok":true,"why":"...","lang":"en|ar|ur","comment":"..."}]} with one entry per item.\n\n${list}`;
  const res: Good[] = [];
  try {
    const d = JSON.parse(await ai(prompt, debug));
    const byId = new Map(batch.map((h) => [h.id, h]));
    for (const x of d.r ?? []) {
      const h = byId.get(String(x.id ?? "").replace(/[\[\]]/g, ""));
      if (h && x.ok === true && x.comment) res.push({ url: h.url, title: h.title, why: String(x.why ?? ""), lang: String(x.lang ?? ""), comment: String(x.comment) });
    }
  } catch (e) { debug.push(`batch fail ${(e as Error).message}`); }
  return res;
}

async function judge(hits: Hit[], debug: string[]): Promise<Good[]> {
  const out: Good[] = [];
  for (let i = 0; i < hits.length; i += 10) out.push(...await judgeBatch(hits.slice(i, i + 10), debug)); // ek ek karke: Groq limit
  return out;
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

async function email(items: Good[], stats: string): Promise<boolean> {
  if (!BREVO) return false;
  const cards = items.map((x, i) => `
  <div style="border:1px solid #ddd;border-radius:10px;padding:14px;margin:0 0 16px">
    <div style="font-size:16px;font-weight:bold;margin:0 0 6px">${i + 1}. <a href="${x.url}">${esc(x.title || "Facebook post")}</a></div>
    <div style="font-size:13px;color:#444;margin-bottom:8px">${esc(x.why)}</div>
    <div style="font-size:12px;color:#888">Comment (copy karke post par paste karein):</div>
    <pre dir="auto" style="white-space:pre-wrap;font-family:Arial,sans-serif;font-size:14px;background:#f6f8fa;padding:10px;border-radius:8px">${esc(x.comment)}</pre>
    <a href="${x.url}" style="display:inline-block;background:#1877f2;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none">Post kholein</a>
  </div>`).join("");
  const body = JSON.stringify({
      sender: { email: SENDER, name: "Comment Helper Bot" },
      to: [{ email: TO_EMAIL }],
      subject: `💬 ${items.length} Facebook posts jahan log software/website poochh rahe hain — comments tayyar`,
      htmlContent: `<div style="font-family:Arial,sans-serif;max-width:680px">
        <p>Assalam o Alaikum Adnan bhai, ye log POS / website / app / social media ka poochh rahe hain.
        "Post kholein" dabayein, comment copy karke paste karein. Ek din mein 10-15 se zyada comment na karein.</p>
        ${cards}<p style="font-size:12px;color:#888">${esc(stats)}</p></div>`,
    });
  return await sendMail(body);
}

async function sendMail(body: string): Promise<boolean> {
  for (let i = 0; i < 3; i++) {
    try {
      const r = await timed("https://api.brevo.com/v3/smtp/email", {
        method: "POST", headers: { "api-key": BREVO, "Content-Type": "application/json", accept: "application/json" }, body,
      }, 20000);
      if (r.ok) return true;
    } catch (_) { /* dobara */ }
    await new Promise((s) => setTimeout(s, 4000));
  }
  return false;
}

// ---- Khud-ilaaj: hits file purani ho to khud DuckDuckGo se thori search ----
const FALLBACK_Q = ['site:facebook.com/groups "POS software" chahiye', 'site:facebook.com/groups "need a website" for my business',
  'site:facebook.com/groups "برنامج كاشير"', 'site:facebook.com/groups "website banwani"'];
async function selfSearch(debug: string[]): Promise<Omit<Hit, "id">[]> {
  const out: Omit<Hit, "id">[] = [];
  for (const q of FALLBACK_Q) {
    try {
      const html = await (await timed(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(q)}`, {
        headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36" } })).text();
      for (const b of html.split('class="result results_links').slice(1)) {
        const a = b.match(/class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/);
        if (!a) continue;
        let url = a[1].replace(/&amp;/g, "&");
        const u = url.match(/uddg=([^&]+)/);
        if (u) url = decodeURIComponent(u[1]);
        url = url.split("?")[0].replace(/\/$/, "");
        const sn = b.match(/class="result__snippet"[^>]*>([\s\S]*?)<\/a>/);
        const strip = (x: string) => x.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&#x27;/g, "'").replace(/\s+/g, " ").trim();
        out.push({ url, title: strip(a[2]), snippet: strip(sn?.[1] ?? "") });
      }
    } catch (_) { /* skip */ }
    await new Promise((s) => setTimeout(s, 2500));
  }
  debug.push(`self-search: ${out.length}`);
  return out;
}

async function saveHealth(h: Record<string, unknown>) {
  await db.from("app_settings").upsert({ key: "comment_helper_health", value: JSON.stringify(h), updated_at: new Date().toISOString() });
}
async function getHealth(): Promise<any> {
  try { return JSON.parse(await setting("comment_helper_health") || "{}"); } catch (_) { return {}; }
}

async function run(test: boolean, reset: boolean) {
  const all = new Map<string, Omit<Hit, "id">>();
  const debug: string[] = [];
  const loaded = await loadHits(debug);
  const extra = HITS_AGE_H > 30 ? await selfSearch(debug) : [];   // GitHub search ruk gayi ho to khud dhoondo
  for (const h of [...loaded, ...extra]) if (POST_URL.test(h.url) && !all.has(h.url)) all.set(h.url, h);
  let pool = [...all.values()];
  if (!reset) {
    const { data: seen } = await db.from("comment_seen").select("url").in("url", pool.map((h) => h.url).slice(0, 900));
    const seenSet = new Set((seen ?? []).map((s) => s.url));
    pool = pool.filter((h) => !seenSet.has(h.url));
  }
  const hits: Hit[] = pool.slice(0, 40).map((h, i) => ({ ...h, id: `p${i}` }));
  const good = hits.length ? (await judge(hits, debug)).slice(0, MAX_SEND) : [];
  const stats = `Post links mile: ${all.size} · naye: ${hits.length} · bheje: ${good.length}`;
  const aiDown = hits.length > 0 && debug.filter((d) => d.startsWith("batch fail")).length >= Math.ceil(hits.length / 10);
  let mailed = true;
  if (!test) {
    if (good.length) mailed = await email(good, stats);
    // email na gayi ya AI band tha -> posts ko "dekha hua" mark NA karo, agla run dobara koshish kare
    if (hits.length && mailed && !aiDown) {
      await db.from("comment_seen").upsert(hits.map((h) => ({ url: h.url, title: h.title.slice(0, 200),
        relevant: good.some((g) => g.url === h.url), sent: good.some((g) => g.url === h.url) })));
    }
  }
  const ok = mailed && !aiDown && HITS_AGE_H < 30;
  return { ok, stats, items: test ? good : good.length, debug, problem: ok ? undefined :
    [!mailed && "email nahi gayi", aiDown && "AI jawab nahi de raha", HITS_AGE_H >= 30 && "GitHub search purani"].filter(Boolean).join(", ") };
}

async function setting(key: string) {
  const { data } = await db.from("app_settings").select("value").eq("key", key).maybeSingle();
  return data?.value ?? "";
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  try {
    const runKey = req.headers.get("x-run-key");
    if (!runKey || runKey !== (await setting("fb_comment_run_key"))) return json({ error: "unauthorized" }, 401);
    const p = new URL(req.url).searchParams;
    const test = p.get("test") === "1";
    const health = await getHealth();
    // retry cron: pichhla run 3 ghante ke andar kamyab tha to kuch na karo
    if (p.get("retry") === "1" && health.ok && Date.now() - Date.parse(health.at ?? 0) < 3 * 3600e3) return json({ skipped: "last run ok" });
    let res: any;
    try { res = await run(test, p.get("reset") === "1"); }
    catch (e) { res = { ok: false, problem: (e as Error).message, debug: [] }; }
    if (!test) {
      const fails = res.ok ? 0 : (health.fails ?? 0) + 1;
      await saveHealth({ at: new Date().toISOString(), ok: res.ok, fails, stats: res.stats, problem: res.problem ?? "" });
      if (fails === 2 && BREVO) {   // lagatar 2 dafa masla -> ek dafa chhota alert (har baar nahi)
        await sendMail(JSON.stringify({ sender: { email: SENDER, name: "Comment Helper Bot" }, to: [{ email: TO_EMAIL }],
          subject: "⚠️ Comment Helper: masla aa raha hai (bot khud dobara koshish kar raha hai)",
          textContent: `Masla: ${res.problem}\nBot har run par khud dobara koshish karta rahega. Agar 2 din tak email na aaye to Claude ko batayein:\n"Comment Helper bot theek karo (Supabase comment-helper + GitHub tools/fb_search.py)".` }));
      }
    }
    return json(res);
  } catch (e) {
    return json({ error: (e as Error).message }, 500);
  }
});
