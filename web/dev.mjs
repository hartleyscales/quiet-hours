#!/usr/bin/env node
// Development server for the Quiet Hours web app. No dependencies.
// Serves web/ as static files and proxies /v1 and /admin to the API, so the
// app is same-origin in development.
//
//   node web/dev.mjs                       http://127.0.0.1:8788, API at http://127.0.0.1:8790
//   PORT=8798 QH_API=http://127.0.0.1:8797 node web/dev.mjs
//
// Flags work too: --port 8798 --api http://127.0.0.1:8797
//
// The page runs on its built-in sample campus by default. Open http://127.0.0.1:8788/?api= to use the API
// through this proxy instead (add &demo=<admin secret> for the phase strip).

import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL(".", import.meta.url));

function flag(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
}

const PORT = Number(flag("port") ?? process.env.PORT ?? 8788);
const HOST = flag("host") ?? process.env.HOST ?? "127.0.0.1";
const API = new URL(flag("api") ?? process.env.QH_API ?? "http://127.0.0.1:8790");

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".webmanifest": "application/manifest+json",
};

function proxy(req, res) {
  const target = new URL(req.url, API);
  const send = target.protocol === "https:" ? httpsRequest : httpRequest;
  const headers = { ...req.headers, host: target.host };
  delete headers.connection;
  const up = send(target, { method: req.method, headers }, (upRes) => {
    res.writeHead(upRes.statusCode ?? 502, upRes.headers);
    upRes.pipe(res);
  });
  up.on("error", (err) => {
    if (res.headersSent) return res.destroy();
    res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: { code: "api_unreachable", message: `dev.mjs could not reach ${API.origin}: ${err.message}` } }));
  });
  req.pipe(up);
}

async function serveFile(req, res) {
  let path;
  try {
    path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  } catch {
    res.writeHead(400).end();
    return;
  }
  if (path.endsWith("/")) path += "index.html";
  const file = normalize(join(ROOT, path));
  if (!file.startsWith(ROOT.endsWith(sep) ? ROOT : ROOT + sep) || file.endsWith("dev.mjs")) {
    res.writeHead(404).end();
    return;
  }
  try {
    const info = await stat(file);
    if (!info.isFile()) throw new Error("not a file");
    const body = await readFile(file);
    res.writeHead(200, { "content-type": TYPES[extname(file)] ?? "application/octet-stream", "cache-control": "no-store" });
    res.end(req.method === "HEAD" ? undefined : body);
  } catch {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" }).end("Not found");
  }
}

createServer((req, res) => {
  const path = (req.url ?? "/").split("?")[0];
  if (path === "/v1" || path.startsWith("/v1/") || path === "/admin" || path.startsWith("/admin/")) return proxy(req, res);
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405).end();
    return;
  }
  serveFile(req, res);
}).listen(PORT, HOST, () => {
  console.log(`Quiet Hours web: http://${HOST}:${PORT}  (API proxied to ${API.origin})`);
});
