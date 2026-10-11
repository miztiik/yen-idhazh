/** Render private Voices inputs with the verified production Server, then serve its real static page. */
import { createServer } from 'node:http';
import { cpSync, createReadStream, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createInterface } from 'node:readline';
import sirv from 'sirv';

const frontend = process.cwd();
const compiled = join(frontend, 'server');
const output = join(frontend, 'build');
cpSync(join(frontend, 'static'), output, { recursive: true });
const { Server } = await import(pathToFileURL(join(compiled, 'index.js')).href);
const { manifest } = await import(pathToFileURL(join(compiled, 'manifest-full.js')).href);
const server = new Server(manifest);
await server.init({ env: process.env, read: (file) => createReadStream(join(compiled, file)) });
const dependencies = new Map();
const response = await server.respond(new Request('http://localhost/console/voices/'), {
	getClientAddress() { throw new Error('Cannot read clientAddress during prerendering'); },
	prerendering: { dependencies, remote_responses: new Map() },
	read: (file) => readFileSync(join(output, file))
});
if (response.status !== 200) throw new Error(`Private Voices render returned ${response.status}: ${await response.text()}`);
const page = join(output, 'console', 'voices', 'index.html');
mkdirSync(dirname(page), { recursive: true });
writeFileSync(page, await response.text(), 'utf8');
for (const [path, dependency] of dependencies) {
	if (dependency.response.status !== 200) throw new Error(`Private Voices dependency ${path} returned ${dependency.response.status}`);
	const file = resolve(output, `.${new URL(path, 'http://localhost').pathname}`);
	mkdirSync(dirname(file), { recursive: true });
	writeFileSync(file, dependency.body ?? new Uint8Array(await dependency.response.arrayBuffer()));
}

let held = process.argv[2] === 'true';
const pending = new Set();
const serve = sirv(output, { dev: true });
const http = createServer((request, response) => {
	const next = () => serve(request, response, () => { response.writeHead(404); response.end(); });
	if (held && request.url?.includes('/state/compact/item-health/index/')) {
		pending.add(next);
		response.once('close', () => pending.delete(next));
	} else next();
});
await new Promise((done) => http.listen(0, '127.0.0.1', done));
console.log(`JUDGEMENT_ORIGIN=http://127.0.0.1:${http.address().port}/`);
createInterface({ input: process.stdin }).on('line', (command) => {
	if (command === 'hold') held = true;
	else if (command === 'release') {
		held = false;
		for (const next of pending) next();
		pending.clear();
	} else {
		for (const next of pending) next();
		pending.clear();
		http.close(() => process.exit(0));
	}
});
