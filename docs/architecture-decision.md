# Architecture decision and Orange-skills record

## Problem

The system must show residents acting in a 3D food economy while supporting reproducible policy comparisons. The expensive choice is where authoritative economic state lives. The destination repository was a clean greenfield repository containing its licence and attributes file.

## Orange skills used

The installed skills are junctions into `C:/Users/roylu/orange-skills/global`. The source repository revision checked during planning was `7514dfc905c1069047a69feb4dd577bbaf0e32f2`.

Applied `architect` for caller-first interfaces and ownership, `arena` for two distinct designs and an independent cross-judge, and `swarm` for bounded parallel work. Applied `principle-build-the-lever` through a shared delegate contract and rerunnable package checker, `principle-prove-it-works` through artifact inspection, `show-me-your-work` through the TSV trail, and `technical-writing` with `unslop` for the documents.

Two architecture workers and one evidence worker ran in parallel. They wrote isolated scratch artifacts outside this repository. The parent alone wrote destination files. A separate read-only judge compared the complete architecture candidates after they finished. A final read-only reviewer checked the delivered package.

## Alternatives compared

| Criterion, scored 0 to 2 | A: Python authority and browser 3D | B: Godot authority and native 3D |
| --- | --- | --- |
| Economic validity | 2, ledgers, counterfactuals, calibration, uncertainty | 2, ledgers, headless comparisons, calibration |
| Agent control | 2, bounded offers, receipts, budget, no uncertain retry | 2, bounded offers, gateway, budget, fallbacks |
| 3D coherence | 2, committed projections determine movement | 2, scene reads deterministic C# economy |
| Build feasibility | 2, module map, interfaces, recovery, proposed gates | 2, session interface, native and headless build, proposed gates |
| Evidence discipline | 2, hypothetical and observed inputs distinguished | 2, same distinctions with technical source checking |
| Total | 10 | 10 |

The independent judge and parent reached the same choice. These scores indicate planning completeness against the rubric. They are not benchmark results, implementation proof, or evidence of policy efficacy.

Candidate A gives analysts direct access to the simulation and data workflows while supporting a shareable browser demonstration. Candidate B concentrates a native application behind a deep session interface and gives stronger language-level encapsulation. It is a credible choice if detailed game interaction becomes the main product.

Godot's versioned documentation supports headless export and describes C# platform limits, including lack of web export for the documented Godot 4 C# configuration. [Dedicated server export](https://docs.godotengine.org/en/4.5/tutorials/export/exporting_for_dedicated_servers.html), [C# support](https://docs.godotengine.org/en/4.5/tutorials/scripting/c_sharp/).

## Synthesis decision

Choose Candidate A as the base. Keep one Python kernel and one browser projection. Its public `run`, `compare`, and `replay` capabilities hide the difficult scheduling and accounting decisions without exposing an engine lifecycle to research callers.

Adapt these ideas from Candidate B and the judge:

- Separate economic ownership from custody at a place or in a journey.
- Use integer seconds and an explicit Toronto calendar for short flights and queues.
- Fork only at committed boundaries and make replay read-only.
- Fix the focal LLM population before the run. Camera selection cannot change it.
- Enforce module access rules and document the model with ODD.

Reject a parallel C# model, Godot authority, mandatory native delivery, and a service per actor. Adding them would introduce a second implementation path or competing state ownership. Keep the provider gateway as a module initially, with an independent service only if deployment requires it.

## Specification repairs made

The judge found that Candidate A's illustrative event union omitted reservations, cancellations, and consumption. The final architecture requires a complete transition reducer covering every authoritative change. It also distinguishes a single paired-run difference from uncertainty over replicated experiments.

Both candidates needed a concrete child-school relationship and explicit rounding. The final simulation specification includes household members, school assignment, eligibility, attendance, meal substitution, cent allocation, gram remainders, and minimum service duration.

Both candidates proposed a 12-week prototype. The final delivery plan uses 16 weeks to make room for data provenance, four workstreams, failure behavior, and review. It still distinguishes the prototype from a validated policy instrument.

## Tradeoffs accepted

We accept two languages and a versioned scene protocol in exchange for direct Python research workflows and browser access. We accept schematic movement and a small first district in exchange for inspectable accounting. We accept one writer per world in exchange for clear ordering and reliable replay.

Python cannot enforce all ownership through access modifiers. Import-boundary checks, immutable views, and tests must enforce the contract. Neither candidate's performance targets have been measured. Operating data and calibration remain the larger uncertainty.

## Verification and remaining scrutiny

The package checker verifies document links, required artifacts, source IDs, dates, scenario coverage, call arithmetic, budget arithmetic, and evidence metadata. The [review record](../planning/review.md) preserves findings and corrections. It does not claim the future simulator passes its acceptance gates.

All delegated workstreams returned artifacts. There were no dropouts. Remaining scrutiny concerns real operating data, observed program rollout, behavioral validation, route permissions, and measured software performance.
