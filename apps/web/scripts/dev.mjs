import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repositoryRoot = resolve(appRoot, '../..');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const children = [
  spawn(python, ['-m', 'sim.council', '--port', '8765'], { cwd: repositoryRoot, stdio: 'inherit', windowsHide: true }),
  spawn(process.execPath, [resolve(appRoot, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', ...process.argv.slice(2)], {
    cwd: appRoot,
    stdio: 'inherit',
    windowsHide: true,
  }),
];

let shuttingDown = false;
let remaining = children.length;
let forceStopTimer;

function stop(signal = 'SIGTERM') {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill(signal);
  }
  forceStopTimer = setTimeout(() => {
    for (const child of children) {
      if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
    }
  }, 2500);
  forceStopTimer.unref();
}

for (const child of children) {
  child.on('error', error => {
    console.error(`Could not start ${child.spawnfile}: ${error.message}`);
    process.exitCode = 1;
    stop();
  });
  child.once('exit', (code, signal) => {
    remaining--;
    if (!shuttingDown) {
      process.exitCode = code ?? (signal ? 1 : 0);
      stop();
    }
    if (shuttingDown && remaining === 0) {
      clearTimeout(forceStopTimer);
      process.exit(process.exitCode ?? 0);
    }
  });
}

process.on('SIGINT', () => {
  process.exitCode = 130;
  stop('SIGINT');
});
process.on('SIGTERM', () => {
  process.exitCode = 143;
  stop('SIGTERM');
});
