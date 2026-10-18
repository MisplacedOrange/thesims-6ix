const j = require('./scratch-islands.json');
const P = (lon, lat) => [Math.round((lon + 79.385) * 111320 * Math.cos(43.65 * Math.PI / 180)), Math.round((43.65 - lat) * 111320)];
for (const e of j.elements) {
  const t = e.tags || {};
  if (e.type === 'way') console.log('way', e.id, t.name, t.place, t.aeroway, e.geometry.length, P(e.bounds.minlon, e.bounds.maxlat), P(e.bounds.maxlon, e.bounds.minlat));
  else console.log('rel', e.id, t.name, t.place, e.members.length, e.members.map(m => m.role + ':' + (m.geometry ? m.geometry.length : 0)).join(' '));
}
const d = require('./public/data/toronto.json');
const s = d.shores[0];
console.log(s.filter((_, i) => i % 8 === 0).map(p => p.map(Math.round).join(',')).join(' '));
