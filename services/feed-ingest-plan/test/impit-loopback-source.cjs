/** Serve bounded native transport fixtures and report genuine Node response closure. */
const { createServer } = require("node:http");
const { gzipSync, brotliCompressSync, deflateSync } = require("node:zlib");
const payload = Buffer.from("generated response ".repeat(300));
const encoded = new Map([
  ["gzip", gzipSync(payload)], ["br", brotliCompressSync(payload)], ["deflate", deflateSync(payload)],
]);
let stopping = false;
const server = createServer((request, response) => {
  const path = new URL(request.url, "http://127.0.0.1").pathname.slice(1);
  process.send({ agent: request.headers["user-agent"] ?? "" });
  if (path === "redirect") {
    response.writeHead(302, { location: "/followed" });
    response.end();
    return;
  }
  if (path === "followed") {
    process.send({ followed: true });
    response.end("followed");
    return;
  }
  if (path === "stalled" || path === "cutoff" || path === "reference") {
    response.once("close", () => {
      if (!stopping) process.send({ closed: path });
    });
    response.writeHead(403, { "content-type": "text/html" });
    response.flushHeaders();
    response.write(new Uint8Array(16384));
    return;
  }
  const body = encoded.get(path) ?? payload;
  response.writeHead(403, {
    "content-type": "text/html", "content-length": String(body.byteLength),
    "retry-after": "1".repeat(300),
    ...(encoded.has(path) ? { "content-encoding": path } : {}),
  });
  response.end(body);
});
server.listen(0, "127.0.0.1", () => process.send({ port: server.address().port }));
process.on("message", message => {
  if (message !== "stop") throw new Error("Unexpected generated-source command");
  stopping = true;
  server.close(() => process.disconnect());
  server.closeAllConnections();
});
