import { mkdir, writeFile, chmod } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { networkInterfaces } from 'node:os';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../.local/', import.meta.url));
await mkdir(root, { recursive: true, mode: 0o700 });
const run = args => execFileSync('openssl', args, { cwd: root, stdio: 'ignore' });
if (!existsSync(`${root}/ca.key`)) {
  run(['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.crt', '-days', '3650', '-subj', '/CN=NOVA Local CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign']);
}
const addresses = [...new Set(['127.0.0.1', ...Object.values(networkInterfaces()).flat().filter(n => n?.family === 'IPv4').map(n => n.address)])];
await writeFile(`${root}/server.ext`, `subjectAltName=DNS:localhost,DNS:synapse.local,${addresses.map(ip => `IP:${ip}`).join(',')}\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n`);
run(['req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key', '-out', 'server.csr', '-subj', '/CN=synapse.local']);
run(['x509', '-req', '-in', 'server.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial', '-out', 'server.crt', '-days', '365', '-sha256', '-extfile', 'server.ext']);
await chmod(`${root}/ca.key`, 0o600); await chmod(`${root}/server.key`, 0o600);
console.log('Created project-local HTTPS certificates. Nothing was installed in the system trust store.');
console.log('iPhone: install .local/ca.crt, then enable it in Settings > General > About > Certificate Trust Settings.');
console.log(`Certificate includes: localhost, synapse.local, ${addresses.join(', ')}`);
