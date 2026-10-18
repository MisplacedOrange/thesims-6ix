# OpenAI Council proposer

The local Council can ask OpenAI for a structured plan draft. Python remains the
authority for supported actions, parameter validation, approval and simulation.
No API request happens at startup, on proposal intake, during replay, or while
loading a saved run. Each click on **Generate draft with OpenAI** authorizes one
Responses API request. There are no automatic provider retries, model fallbacks,
or substitutions of a deterministic plan for a failed model request.

## Local configuration

Open the repository root `.env` in your editor. If missing, copy `.env.example`.
Enter these values locally, never in chat or in browser source:

```dotenv
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=your-chosen-model-id
COUNCIL_OPENAI_ENABLED=true
COUNCIL_OPENAI_TIMEOUT_SECONDS=60
COUNCIL_OPENAI_MAX_OUTPUT_TOKENS=3000
```

Choose a model available to your project that supports Responses structured
outputs. No default model is silently selected. The request/output token limit
does not guarantee a dollar cost; input tokens are also billed. Serialized review
context is capped at 256 KB; output limits must be 512–16000 tokens and the
network timeout 5–180 seconds. A model may consume its limit without producing a
complete draft; that is reported as a failed call.

The loader reads only these five variable names from the root file; process
environment variables take precedence, including empty values. Simple single or
double quoted values are accepted. Shell expansion, multiline values and inline
comments are not supported. No SDK package installation is needed: the Python
standard library sends HTTPS requests directly to the fixed OpenAI Responses
endpoint. Redirects are rejected. Configuration is read on each request, so
refreshing the Council picks up locally edited configuration.

`.env` is ignored by Git, but is plaintext on disk. Keep API keys out of `VITE_*`
variables. The API exposes model/configuration status, never the credential.
The current public Vercel service has no Council user authentication: model
generation is disabled there even if a key is present. Authenticated hosted
model access requires a separate deployment change. Local mode uses the existing
loopback Council server and Vite proxy; do not expose them as a public service.

## Review workflow

1. Start the app with `cd apps/web` then `npm run dev`.
2. Save a proposal and review its organization/stakeholder evidence.
3. Open **Simulation** and save an evaluated scope in **Infrastructure planner**.
4. In **OpenAI plan drafts**, choose population and seed, review sharing limits,
   and confirm sending the listed context to OpenAI. Click **Generate draft**.
5. Review rationale, assumptions, excluded outcomes, uncertainties and exact plan
   parameters. Unsupported infrastructure can remain a non-executable candidate;
   it must not be replaced by an unrelated executable food-site action.
6. Click **Adopt draft for review**. This runs the normal Council plan validation
   and records the immutable draft id on the saved plan. It does not approve it.
7. In **Infrastructure planner**, inspect blockers and advice, record the decision,
   then explicitly run the matched comparison. Non-executable candidates cannot
   be approved for execution. Any changed plan requires a new approval.

The model gets the exact saved proposal and scope, current proposal-linked
organizations and stakeholder-input records, pinned location context, the live
action catalog, and frozen simulation inputs. This can include sensitive text
entered by a reviewer. The confirmation is an explicit review of sharing limits;
the software cannot determine consent from free text. No household microdata,
API keys or future stochastic draws are supplied. The request uses `store:false`;
this does not promise zero provider retention under every account policy.

## Records, failures and concurrent edits

`POST /api/council/planner/drafts` uses schema 1, `If-Match` and `Idempotency-Key`,
like other Council commands. Its body is `population`, `seed`, and the boolean
`consent_to_send`. A durable job reservation is made before the external request,
then the SQLite write lock is released. Successful generations save immutable
`planner_draft` records without changing a current plan or approval. An adopted
plan uses the existing `/plans` command plus `planner_draft_id`; the command must
match the draft exactly. The server compares the entire frozen input hash before
adoption, including evidence, action definitions and simulator source/version.

Calls are recorded in `planner_jobs` in the same Council SQLite database. They
retain the exact request (without Authorization), prompt version, input/request
hashes, configured/resolved model, response/request ids, usage, raw response,
timestamps and outcome. Final job records cannot be updated or deleted. Browser
state exposes a summary of the latest 20 calls; full requests/responses remain in
SQLite. Drafts keep exact context, instructions, structured output and command.
The adopted plan hash includes its draft reference; replay needs no new API call.

If Council changes while OpenAI is working, the response is retained in the call
audit and reported as a revision conflict; no draft or plan replaces newer work.
An idempotency key reserves at most one provider attempt. Successful retries of
the same command use the existing receipt. Failures and interrupted attempts are
never silently retried. A server crash can leave a job marked running, indicating
an unknown provider outcome. Inspect it before explicitly starting another call.
Provider HTTP errors, timeouts, refusals, incomplete output, malformed data,
unknown actions, invalid parameters and stale drafts have explicit error states.
Provider error bodies and credentials are not returned to the browser.

This integration proposes plans within the implemented simulation. It does not
establish policy quality, simulator calibration, representative consultation or
real-world effects. The deterministic planner remains available for comparisons.

API implementation follows OpenAI's [Responses structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
and [server-side authentication guidance](https://developers.openai.com/api/reference/overview#authentication).
