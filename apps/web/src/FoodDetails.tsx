import type { FoodView, Household, InteractionEvent } from './interactables.ts';

export const dollars = (cents: number) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(cents / 100);
export const grams = (value: number) => value >= 1000 ? (value / 1000).toFixed(1) + ' kg' : value.toLocaleString() + ' g';
export const words = (value: string) => value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase());
export const at = (seconds: number) => {
  const time = (8 * 3600 + 30 * 60 + Math.floor(seconds)) % (24 * 3600);
  return String(Math.floor(time / 3600)).padStart(2, '0') + ':' + String(Math.floor(time / 60) % 60).padStart(2, '0');
};
export const duration = (seconds: number) => seconds < 60 ? Math.round(seconds) + ' s' : (seconds / 60).toFixed(1) + ' min';

function EventLine({ event }: { event: InteractionEvent }) {
  return <li><time>{at(event.simulation_time)}</time><span>{words(event.action)} <b>{event.household_id ?? event.site_id ?? 'City'}</b>
    {event.quantity_grams > 0 && <> / {grams(event.quantity_grams)}</>}
    {event.payment_cents > 0 && <> / {dollars(event.payment_cents)}</>}
    {event.denial_or_failure_reason && <em>{words(event.denial_or_failure_reason)}</em>}</span></li>;
}

export function HouseholdDetails({ household, view }: { household: Household; view: FoodView }) {
  const state = view.households[household.id]!;
  const events = view.events.filter(event => event.household_id === household.id);
  const offer = events.filter(event => event.action === 'offered').at(-1);
  const chosen = events.filter(event => event.action === 'chosen').at(-1);
  return <div className="household-details">
    <h3>Home and pantry <small>{household.id}</small></h3>
    <p>{household.size} people / {household.income_band} income / {household.mobility} mobility<br />
      {household.children} school-eligible / {Math.round(household.time_budget_seconds / 60)} min trip budget</p>
    <dl><div><dt>Household cash</dt><dd>{dollars(state.cash_cents)}</dd></div>
      <div><dt>Pantry / carried</dt><dd>{grams(state.pantry_grams)} / {grams(state.carrying_grams)}</dd></div>
      <div><dt>Produce used / need</dt><dd>{grams(state.consumed_grams)} / {grams(household.need_grams)}</dd></div>
      <div><dt>Food spending</dt><dd>{dollars(state.expenditure_cents)}</dd></div></dl>
    <p className="assumption-note">Households own their cash and food. Need uses 300 g of produce per person in this illustrative day.</p>
    {chosen && <p>Rule choice: <b>{words(chosen.option_id ?? 'none')}</b>{chosen.reduced_basket ? ' / smaller basket' : ''}{chosen.substitution ? ' / substitute store' : ''}</p>}
    {offer && <details><summary>Feasible choices at {at(offer.simulation_time)}</summary>
      <ul>{offer.options?.map(option => <li key={option.option_id}>{words(option.option_id)}{option.quantity_grams ? ' / ' + grams(option.quantity_grams) + ' / ' + dollars(option.payment_cents ?? 0) : ''}</li>)}</ul>
      {offer.excluded?.map(item => <p key={item.site_id}>{words(item.site_id)}: {words(item.reason)}</p>)}
    </details>}
    <details><summary>Interaction history ({events.length})</summary><ol className="food-events">{events.map(event => <EventLine key={event.event_id} event={event} />)}</ol></details>
  </div>;
}
