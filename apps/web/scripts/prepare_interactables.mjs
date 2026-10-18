// Cache Python-authoritative traces by the exact map, generator and kernel inputs.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const out = resolve(root, 'apps/web/public/data/interactables');
const inputs = ['apps/web/public/data/toronto.json', 'sim/core/data/catalog.json'];
for (const directory of ['sim/interactables', 'sim/core']) {
  for (const file of readdirSync(resolve(root, directory)).sort()) {
    if (file.endsWith('.py')) inputs.push(`${directory}/${file}`);
  }
}
const hash = createHash('sha256');
for (const path of inputs) hash.update(path).update(readFileSync(resolve(root, path)));
const digest = hash.digest('hex');
const outputs = [200, 600, 1200].flatMap(n => ['baseline', 'emergency'].map(p => `${out}/${n}-${p}.json`));
if (!existsSync(`${out}/input.sha256`) || readFileSync(`${out}/input.sha256`, 'utf8') !== digest || !outputs.every(existsSync)) {
  const result = spawnSync(process.env.PYTHON || 'python', ['-m', 'sim.interactables'], { cwd: root, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
  mkdirSync(out, { recursive: true });
  writeFileSync(`${out}/input.sha256`, digest);
}
