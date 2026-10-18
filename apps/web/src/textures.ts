import * as THREE from 'three';

const TAU = Math.PI * 2;

function canvas2d(size: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = size;
  const c = canvas.getContext('2d');
  if (!c) throw new Error('Canvas is unavailable');
  return [canvas, c];
}

function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Seamless fbm over a size×size tile: every octave's lattice period divides the tile, indices wrap.
function tileableFbm(size: number, seed: number, periods: number[]): Float32Array {
  const random = rng(seed);
  const out = new Float32Array(size * size);
  let amp = 1, total = 0;
  for (const p of periods) {
    const grid = Float32Array.from({ length: p * p }, random);
    for (let y = 0; y < size; y++) {
      const gy = (y / size) * p, y0 = Math.floor(gy), ty = gy - y0, sy = ty * ty * (3 - 2 * ty);
      const r0 = (y0 % p) * p, r1 = ((y0 + 1) % p) * p;
      for (let x = 0; x < size; x++) {
        const gx = (x / size) * p, x0 = Math.floor(gx), tx = gx - x0, sx = tx * tx * (3 - 2 * tx);
        const c0 = x0 % p, c1 = (x0 + 1) % p;
        const a = grid[r0 + c0] + (grid[r0 + c1] - grid[r0 + c0]) * sx;
        const b = grid[r1 + c0] + (grid[r1 + c1] - grid[r1 + c0]) * sx;
        out[y * size + x] += (a + (b - a) * sy) * amp;
      }
    }
    total += amp; amp *= 0.5;
  }
  let min = Infinity, max = -Infinity;
  for (let i = 0; i < out.length; i++) { out[i] /= total; min = Math.min(min, out[i]); max = Math.max(max, out[i]); }
  for (let i = 0; i < out.length; i++) out[i] = (out[i] - min) / (max - min || 1);
  return out;
}

function finish(canvas: HTMLCanvasElement, colorSpace: THREE.ColorSpace, anisotropy = 1): THREE.CanvasTexture {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = colorSpace;
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.anisotropy = anisotropy;
  return texture;
}

/** Tileable near-white fbm: sRGB 0.86–1.0, mean ≈ 0.93 sRGB (≈ 0.85 linear), so `color * map` ≈ `color * 0.85`. */
export function noiseTexture(): THREE.CanvasTexture {
  const size = 256, [canvas, c] = canvas2d(size);
  const n = tileableFbm(size, 1337, [4, 8, 16, 32, 64]);
  const img = c.createImageData(size, size);
  for (let i = 0; i < n.length; i++) {
    const v = Math.round((0.86 + n[i] * 0.14) * 255);
    img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = v; img.data[i * 4 + 3] = 255;
  }
  c.putImageData(img, 0, 0);
  return finish(canvas, THREE.SRGBColorSpace, 4);
}

export function waterNormalTexture(): THREE.CanvasTexture {
  const size = 256, [canvas, c] = canvas2d(size);
  // Mostly isotropic noise: a dominant low-frequency wave reads as stripes across the lake.
  const waves: [number, number, number, number][] = [[7, 3, 0.05, 2.6], [-5, 9, 0.04, 5.3], [11, -6, 0.03, 1.1]];
  const noise = tileableFbm(size, 4242, [8, 16, 32, 64]);
  const h = new Float32Array(size * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const u = x / size, v = y / size;
    let s = 0;
    for (const [kx, ky, a, ph] of waves) s += Math.sin(TAU * (kx * u + ky * v) + ph) * a;
    h[y * size + x] = s + noise[y * size + x] * 0.5;
  }
  const strength = 14, img = c.createImageData(size, size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const dx = (h[y * size + (x + 1) % size] - h[y * size + (x + size - 1) % size]) * 0.5;
    const dy = (h[((y + 1) % size) * size + x] - h[((y + size - 1) % size) * size + x]) * 0.5;
    // Canvas rows run top-down while texture v (flipY) runs bottom-up, so the y slope flips sign.
    const nx = -dx * strength, ny = dy * strength, inv = 1 / Math.hypot(nx, ny, 1), i = (y * size + x) * 4;
    img.data[i] = Math.round((nx * inv * 0.5 + 0.5) * 255);
    img.data[i + 1] = Math.round((ny * inv * 0.5 + 0.5) * 255);
    img.data[i + 2] = Math.round((inv * 0.5 + 0.5) * 255);
    img.data[i + 3] = 255;
  }
  c.putImageData(img, 0, 0);
  return finish(canvas, THREE.NoColorSpace);
}

/** 64×64 ballast tile: u (x) runs along the track, one repeat ≈ 1.3 m with two sleepers; v (y) across, rails at v≈0.3/0.7. */
export function sleeperTexture(): THREE.CanvasTexture {
  const size = 64, [canvas, c] = canvas2d(size), random = rng(97);
  c.fillStyle = '#6e655c'; c.fillRect(0, 0, size, size);
  for (let i = 0; i < 700; i++) {
    const l = 70 + random() * 70;
    c.fillStyle = `rgb(${l + 8 | 0},${l + 2 | 0},${l - 6 | 0})`;
    c.fillRect(random() * size | 0, random() * size | 0, 1, 1);
  }
  for (const x of [10, 42]) {
    c.fillStyle = '#3b2c22'; c.fillRect(x, 8, 12, 48);
    c.fillStyle = '#4a3a2e'; c.fillRect(x + 1, 9, 10, 2);
  }
  for (const y of [19, 44]) {
    c.fillStyle = '#5c5f63'; c.fillRect(0, y - 1, size, 3);
    c.fillStyle = '#b9bdc2'; c.fillRect(0, y, size, 1);
  }
  return finish(canvas, THREE.SRGBColorSpace, 4);
}
