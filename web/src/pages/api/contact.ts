// Contact/feedback endpoint — sends the message to the site owner's inbox via
// Cloudflare's Email Routing send_email binding (no third-party service).
//
// Runtime config (set in the Cloudflare dashboard, Worker → Settings → Variables):
//   CONTACT_TO   the verified destination email (your personal inbox that
//                support@honesttexaselectricity.com forwards to). Required.
//   CONTACT_FROM optional sender on your domain (default noreply@honesttexaselectricity.com)
//
// If the binding/CONTACT_TO aren't configured yet, it returns 503 and the form
// page falls back to a mailto: link, so contact never fully breaks.
import type { APIRoute } from "astro";

export const prerender = false;

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });

// GET is a config check you can open in a browser. It never exposes any value —
// only whether each piece is present — so you can see what still needs setting.
export const GET: APIRoute = async ({ locals }) => {
  const env = (locals as any)?.runtime?.env ?? {};
  const has_CONTACT_TO = Boolean(env.CONTACT_TO);
  const has_SEB = Boolean(env.SEB);
  return json({
    endpoint: "ok",
    has_CONTACT_TO,
    has_send_email_binding: has_SEB,
    configured: has_CONTACT_TO && has_SEB,
    hint: has_CONTACT_TO && has_SEB
      ? "Ready — submit the form at /contact to test delivery."
      : "Set what's false below in the Cloudflare dashboard, then redeploy. " +
        "CONTACT_TO = your verified destination email (Worker → Settings → Variables). " +
        "send_email binding named SEB (Worker → Settings → Bindings, if the wrangler.jsonc one didn't attach).",
  });
};

export const POST: APIRoute = async ({ request, locals }) => {
  const env = (locals as any)?.runtime?.env ?? {};
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return json({ ok: false, error: "Bad request." }, 400);
  }

  // Honeypot: bots fill the hidden "company" field. Pretend success, send nothing.
  if ((form.get("company") as string)?.trim()) return json({ ok: true });

  const name = String(form.get("name") ?? "").trim().slice(0, 120);
  const email = String(form.get("email") ?? "").trim().slice(0, 200);
  const message = String(form.get("message") ?? "").trim().slice(0, 5000);

  if (message.length < 5) return json({ ok: false, error: "Please enter a longer message." }, 400);
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
    return json({ ok: false, error: "That email address looks off." }, 400);

  const to = env.CONTACT_TO as string | undefined;
  const from = (env.CONTACT_FROM as string) || "noreply@honesttexaselectricity.com";
  const seb = env.SEB; // send_email binding

  if (!to || !seb) {
    // Not wired up yet — the form page shows the mailto fallback instead.
    const missing = [!to && "CONTACT_TO", !seb && "SEB (send_email binding)"].filter(Boolean);
    return json({ ok: false, error: "not_configured", missing }, 503);
  }

  try {
    const { EmailMessage } = await import("cloudflare:email");
    const raw = buildMime({ from, to, replyTo: email, name, message });
    await seb.send(new EmailMessage(from, to, raw));
    return json({ ok: true });
  } catch (err) {
    // Log server-side (visible in Worker logs); never return the raw error to the
    // client — it can contain the CONTACT_TO address.
    console.error("contact send_failed:", err);
    return json({ ok: false, error: "send_failed" }, 502);
  }
};

// Minimal RFC 5322 plain-text message. Hand-rolled to avoid a MIME library that
// pulls in Node built-ins the Workers bundler can't handle.
function buildMime(o: { from: string; to: string; replyTo: string; name: string; message: string }) {
  const domain = o.from.split("@")[1] || "honesttexaselectricity.com";
  const id = `<${Date.now()}.${Math.random().toString(36).slice(2)}@${domain}>`;
  const subject = `Site feedback${o.name ? ` from ${o.name}` : ""}`;
  // Strip CR/LF from header-bound values to prevent header injection.
  const clean = (s: string) => s.replace(/[\r\n]+/g, " ").trim();
  const headers = [
    `From: Honest TX Electricity — contact form <${o.from}>`,
    `To: <${o.to}>`,
    o.replyTo ? `Reply-To: <${clean(o.replyTo)}>` : "",
    `Message-ID: ${id}`,
    `Date: ${new Date().toUTCString()}`,
    `Subject: ${clean(subject)}`,
    "MIME-Version: 1.0",
    'Content-Type: text/plain; charset="utf-8"',
    "Content-Transfer-Encoding: 8bit",
  ].filter(Boolean);
  const body =
    `From: ${o.name || "(no name)"} <${o.replyTo || "no email given"}>\r\n\r\n` +
    o.message.replace(/\r?\n/g, "\r\n");
  return headers.join("\r\n") + "\r\n\r\n" + body;
}
