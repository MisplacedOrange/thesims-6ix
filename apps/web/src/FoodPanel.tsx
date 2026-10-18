import { useEffect, useState } from 'react';
import { foodMetrics } from './interactables.ts';
import type { FoodTrace, FoodView, Household, InteractionEvent } from './interactables.ts';

export const dollars = (cents: number) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(cents / 100);
const grams = (value: number) => value >= 1000 ? `${(value / 1000).toFixed(1)} kg` : `${value} g`;
const words = (value: string) => value.replaceAll('_', ' ');
const at = (seconds: number) => `${String(8 + Math.floor((seconds + 1800) / 3600)).padStart(2, '0')}:${String(Math.floor((seconds + 1800) % 3600 / 60)).padStart(2, '0')}`;

function EventLine({ event }: { event: InteractionEvent }) {
  return <li><time>{at(event.simulation_time)}</time><span>{words(event.action)} <b>{event.household_id ?? event.site_id ?? 'City'}</b>
    {event.quantity_grams > 0 && <> · {grams(event.quantity_grams)}</>}
    {event.payment_cents > 0 && <> · {dollars(event.payment_cents)}</>}
    {event.denial_or_failure_reason && <em>{words(event.denial_or_failure_reason)}</em>}</span></li>;
}

export function HouseholdDetails({ household, view }: { household: Household; view: FoodView }) {
  const state = view.households[household.id]!;
  const events = view.events.filter(e => e.household_id === household.id);
  const offer = events.filter(e => e.action === 'offered').at(-1);
  const chosen = events.filter(e => e.action === 'chosen').at(-1);
  return <div className="household-details">
    <h3>Home & pantry <small>{household.id}</small></h3>
    <p>{household.size} people · {household.income_band} income · {household.mobility} mobility<br />
      {household.children} school-eligible · {Math.round(household.time_budget_seconds / 60)} min trip budget</p>
    <dl><div><dt>Household cash</dt><dd>{dollars(state.cash_cents)}</dd></div>
      <div><dt>Pantry / carried</dt><dd>{state.pantry_grams} / {state.carrying_grams} g</dd></div>
      <div><dt>Produce used / need</dt><dd>{state.consumed_grams} / {household.need_grams} g</dd></div>
      <div><dt>Food spending</dt><dd>{dollars(state.expenditure_cents)}</dd></div></dl>
    <p className="assumption-note">Household owns cash and food. Need uses 300 g of produce per person in this illustrative day.</p>
    {chosen && <p>Rule choice: <b>{words(chosen.option_id ?? 'none')}</b>{chosen.reduced_basket ? ' · smaller basket' : ''}{chosen.substitution ? ' · substitute store' : ''}</p>}
    {offer && <details><summary>Legal choices at {at(offer.simulation_time)}</summary>
      <ul>{offer.options?.map(o => <li key={o.option_id}>{words(o.option_id)}{o.quantity_grams ? ` · ${o.quantity_grams} g · ${dollars(o.payment_cents ?? 0)}` : ''}</li>)}</ul>
      {offer.excluded?.map(e => <p key={e.site_id}>{words(e.site_id)}: {words(e.reason)}</p>)}
    </details>}
    <details><summary>Interaction history ({events.length})</summary><ol className="food-events">{events.map(e => <EventLine key={e.event_id} event={e} />)}</ol></details>
  </div>;
}

export function FoodPanel({ trace, view, siteId, policy, busy, residentId, onPolicy, onSite, onCloseSite, onSeek }: {
  trace: FoodTrace; view: FoodView; siteId: string | null; policy: 'baseline' | 'emergency'; busy: boolean;
  onPolicy: (policy: 'baseline' | 'emergency') => void; onSite: (id: string) => void; onCloseSite: () => void;
  onSeek: (seconds: number) => void;
  residentId: number | null;
}) {
  const [collapsed, setCollapsed] = useState(() => window.innerWidth <= 800);
  const [tab, setTab] = useState('outcomes');
  const [grouping, setGrouping] = useState<'area' | 'income_band' | 'size' | 'mobility'>('income_band');
  useEffect(() => { if (siteId) setCollapsed(false); }, [siteId]);
  useEffect(() => { if (residentId !== null && window.innerWidth <= 800) setCollapsed(true); }, [residentId]);
  const metrics = foodMetrics(trace, view);
  const site = trace.sites.find(s => s.id === siteId);
  const state = site ? view.sites[site.id]! : null;
  const done = view.seconds >= trace.horizon_seconds;
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(trace, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = `food-day-${trace.population}-${trace.policy}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className={'food-panel glass' + (collapsed ? ' collapsed' : '')} aria-label="Food access simulation">
    <header><div><span className="eyebrow">ILLUSTRATIVE SCENARIO</span><h2>Food access, in motion</h2></div>
      <button className="small-icon" aria-label={collapsed ? 'Open food dashboard' : 'Collapse food dashboard'} onClick={() => setCollapsed(!collapsed)}>{collapsed ? '+' : '−'}</button></header>
    {!collapsed && <div className="food-panel-body">
      <p className="food-context">Downtown graph · {trace.population} synthetic households<br />Oct 17, 08:30–14:30 · seed {trace.seed} · Python event playback</p>
      <label className="food-policy">Scenario <select aria-label="Food policy scenario" value={policy} disabled={busy} onChange={e => onPolicy(e.target.value as 'baseline' | 'emergency')}>
        <option value="baseline">No-policy baseline</option><option value="emergency">Emergency food site</option></select></label>
      {policy === 'emergency' && <p className="assumption-note">City grant: CAD 300 at 09:30; stock arrives 09:31. Capacity: {trace.sites.find(s => s.id === 'emergency')?.capacity} visits. Closes 13:30. Restarted run.</p>}
      <label className="food-playhead">Day progress <span>{at(view.seconds)}</span><input aria-label="Food simulation timeline" type="range" min="0" max={trace.horizon_seconds} step="1" value={Math.floor(view.seconds)} onChange={e => onSeek(Number(e.target.value))} /></label>
      <nav className="food-tabs" aria-label="Food dashboard sections">{['outcomes', 'sites', 'groups', 'events'].map(t => <button key={t} onClick={() => { setTab(t); onCloseSite(); }} aria-pressed={tab === t}>{t}</button>)}</nav>
      {site && state ? <div className="food-site-details"><button className="food-back" onClick={onCloseSite}>← All {tab}</button>
        <h3>{site.name}</h3><p>{site.type} · {view.seconds < site.active_from ? 'not activated' : view.seconds >= site.opens && view.seconds < site.closes ? 'open' : 'closed'}<br />{at(site.opens)}–{at(site.closes)} · {site.service_seconds} s service<br />Eligibility: {site.eligible}</p>
        <dl><div><dt>Produce stock</dt><dd>{grams(state.stock_grams)}</dd></div>
          <div><dt>Price per 100 g</dt><dd>{dollars(state.price_cents_per_100g)}</dd></div>
          <div><dt>{site.type === 'school' ? 'Portions / capacity' : 'Served / capacity'}</dt><dd>{state.served} / {state.capacity}</dd></div>
          <div><dt>Visits / denials</dt><dd>{state.visits} / {state.denials}</dd></div>
          <div><dt>{site.type === 'retailer' ? 'Sold' : 'Distributed'}</dt><dd>{grams(state.sold_grams)}</dd></div>
          <div><dt>Replenishment received</dt><dd>{grams(state.received_grams)}</dd></div>
          <div><dt>Revenue / procurement</dt><dd>{dollars(state.revenue_cents)} / {dollars(state.spending_cents)}</dd></div></dl>
        <p className="assumption-note">Synthetic location and operating values: {trace.scenario_id}. Site presence is not evidence of real operating capacity.</p>
        <ol className="food-events">{view.events.filter(e => e.site_id === site.id).slice(-12).reverse().map(e => <EventLine key={e.event_id} event={e} />)}</ol>
      </div> : tab === 'outcomes' ? <>
        <div className="food-stats"><div><b>{grams(metrics.purchased + metrics.received)}</b><span>Food obtained</span></div>
          <div><b>{dollars(metrics.spending)}</b><span>Household spending</span></div>
          <div><b>{grams(metrics.pantry)}</b><span>Pantry remaining</span></div>
          <div><b>{grams(metrics.unmet)}</b><span>{done ? 'Unmet produce need' : 'Produce need pending use'}</span></div></div>
        <dl><div><dt>Purchased / program food</dt><dd>{grams(metrics.purchased)} / {grams(metrics.received)}</dd></div>
          <div><dt>Produce used / 300 g portions</dt><dd>{grams(metrics.consumed)} / {metrics.portions}</dd></div>
          <div><dt>Trips home / food collected</dt><dd>{metrics.completed} / {metrics.successful}</dd></div>
          <div><dt>Denied attempts</dt><dd>{metrics.failures}</dd></div>
          <div><dt>Latest offer: feasible sites</dt><dd>{metrics.legalSites}</dd></div>
          <div><dt>Completed-trip travel</dt><dd>{Math.round(metrics.travel / 60)} min</dd></div>
          <div><dt>Settled-attempt queue / service</dt><dd>{Math.round(metrics.queue / 60)} / {Math.round(metrics.service / 60)} min</dd></div>
          <div><dt>Supplier delivery shortfall</dt><dd>{grams(metrics.shortfall)}</dd></div>
          <div><dt>Supplier deliveries / revenue</dt><dd>{grams(view.events.filter(e => e.action === 'delivery').reduce((n, e) => n + e.quantity_grams, 0))} / {dollars(view.events.filter(e => e.action === 'delivery').reduce((n, e) => n + e.payment_cents, 0))}</dd></div>
          <div><dt>Retail revenue</dt><dd>{dollars(trace.sites.filter(s => s.type === 'retailer').reduce((n, s) => n + view.sites[s.id]!.revenue_cents, 0))}</dd></div>
          <div><dt>Program procurement spending</dt><dd>{dollars(trace.sites.filter(s => s.type !== 'retailer').reduce((n, s) => n + view.sites[s.id]!.spending_cents, 0))}</dd></div>
          <div><dt>Public grant outlay</dt><dd>{dollars(view.publicSpending)}</dd></div></dl>
        {Object.entries(metrics.failureReasons).map(([reason, count]) => <p className="food-failure" key={reason}>{words(reason)} <b>{count}</b></p>)}
        <p className="assumption-note">Unmet need is finalized after pantry use at 14:30. Portions cover one produce component. No complete-diet, hunger-prevalence, or business-margin measure is modeled.</p>
      </> : tab === 'sites' ? <div className="food-site-list">{trace.sites.map(s => <button key={s.id} onClick={() => onSite(s.id)} disabled={view.seconds < s.active_from}>
        <span><b>{s.name}</b><small>{s.type} · {view.seconds < s.active_from ? 'activates 09:30' : view.seconds >= s.opens && view.seconds < s.closes ? 'open' : 'closed'}</small></span>
        <span>{grams(view.sites[s.id]!.stock_grams)} →</span></button>)}</div>
        : tab === 'groups' ? <><label className="food-policy">Group by <select aria-label="Outcome grouping" value={grouping} onChange={e => setGrouping(e.target.value as typeof grouping)}>
          {['income_band', 'area', 'size', 'mobility'].map(g => <option value={g} key={g}>{words(g)}</option>)}</select></label>
          <table className="food-groups"><thead><tr><th>Group</th><th>HH</th><th>Obtained g</th><th>{done ? 'Unmet g' : 'Pending g'}</th><th>CAD</th></tr></thead><tbody>
            {Object.entries(metrics.strata(grouping)).map(([name, group]) => <tr key={name}><th>{name}</th><td>{group.count}</td><td>{group.obtained.toLocaleString()}</td><td>{group.unmet.toLocaleString()}</td><td>{(group.spending / 100).toFixed(2)}</td></tr>)}</tbody></table>
          <p className="assumption-note">Unweighted synthetic households. Group counts are households; grams are totals in the displayed run window.</p></>
          : <ol className="food-events">{view.events.slice(-30).reverse().map(e => <EventLine key={e.event_id} event={e} />)}</ol>}
      <details className="food-assumptions"><summary>Units, sources & assumptions</summary><p>{trace.assumptions.food_use}. Crossing waits: {trace.assumptions.crossing_delay_seconds} s. {trace.assumptions.scope}.</p>
        <p>Operations and households: illustrative, parameter {trace.assumptions.parameter_id}. Map: attributed OpenStreetMap geometry. Unknown: {trace.assumptions.unknown_inputs.join(', ')}.</p>
        <p>Money: integer CAD cents; food: grams; time: seconds. Dashboard window: 08:30 to playhead. Arrival does not guarantee service; cash, price, opening hours, stock and capacity are rechecked at settlement.</p></details>
      <button className="food-export" onClick={download}>Download full run & event records ↓</button>
    </div>}
  </section>;
}
