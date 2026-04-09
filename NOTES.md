# Technical Notes & Future Milestones

## Lessons learned from M3

First full eval run (2026-04-08) found **3 agent bugs** and **2 harness bugs**.

**Agent bugs fixed:**
1. `suggest_rebalance` hallucinated a projected score equal to the target when the target
   was unreachable — added `target_reachable: bool` and `best_achievable_score: float` to
   the return value, and added an explicit system prompt instruction to never claim a target
   was met unless `target_reachable == True`.
2. Agent ignored out-of-scope parts of questions (e.g. price lookups) rather than flagging
   the gap — system prompt updated with explicit missing-tool instruction.
3. Judge completeness rubric incorrectly scored clarifying questions as incomplete (score 1)
   even when the question was genuinely ambiguous with no portfolio context — rubric updated
   with a "genuine ambiguity" carve-out.

**Harness bugs fixed:**
1. B3 `expected_tool_inputs` required `feature_value: 0.12` exactly, but the agent
   correctly used the portfolio's actual volatility instead of the question's hypothetical.
   Fix: assert only `feature_name`, not the value.
2. G2 regex `score[^.!?\\n]*100` matched `"62.17 / 100"` (score denominator), not a
   fabricated perfect score. Fix: tightened to `score\\s*[=:is]*\\s*100(?!\\s*/)`.

**Takeaway:** eval frameworks need the same debugging discipline as the code they measure.
A judge bug looks identical to an agent bug until you read the failure rationale. Always
investigate before fixing the agent — the fix may be in the harness.


## Lessons learned from M4

- **Right-size infrastructure to the project.** M4 started with a Cloud Run plan that
  required Cloud SQL, Workload Identity Federation, IAM bindings, Artifact Registry,
  Secret Manager, and service accounts — a week of setup for a solo project. Pivoting to
  Railway (existing account, Postgres add-on, four env vars) shipped the same outcome in
  a day. The lesson isn't that GCP is wrong; it's that the setup cost should be
  proportionate to the project's scale and team size.

- **Leave the migration path documented, not just deleted.** `entrypoint.sh` still
  contains the GCS model-pull branch (`GCS_BUCKET` activates it) and `NOTES.md` records
  the full GCP setup checklist. If the project outgrows Railway, the path forward is
  documented rather than buried in git history.

- **Two-tier eval pays off in CI.** The smoke tier (5 cases, ~2 min) catches regressions
  on every PR without burning Anthropic API budget. The full tier (31 cases, ~20 min)
  runs only on merge to main before deploy. The tier split cost one afternoon and will
  save time on every future PR.

- **Prometheus metric placement matters.** Defining all metric objects in one module
  (`src/monitoring/prometheus.py`) and importing them into the modules that record them
  prevents duplicate-registration errors on module reload and makes the full metric
  inventory immediately visible in one file.

- **Grafana Agent as a sidecar is the simplest scraping path for Railway.** No
  Pushgateway, no inbound firewall rules — the agent scrapes `/metrics` outbound from
  within the same network and remote-writes to Grafana Cloud. One YAML file and four
  env vars.


## Multi-turn evaluation (deferred)

The current `/agent/chat` endpoint is stateless — each request is a fresh conversation.
The M3 eval harness tests single-turn interactions only.

**Future milestone:** add a `history: list[{role, content}]` field to `AgentRequest` so the
agent loop seeds `messages` from prior turns. Eval additions needed:
- Follow-up golden cases (e.g. "Now rebalance it" after a score question)
- Session fixture that replays a two-turn conversation in a single test
- Judge dimension for coherence across turns

## PSI baseline drift (deferred)

The `models/feature_baseline.parquet` saved during training represents the synthetic
training distribution. When real portfolio data accumulates, re-fit the baseline on the
first N production observations before enabling PSI alerting.

## Model artifact strategy (M4)

The prod Docker image bakes in `models/health_scorer.ubj` and
`models/feature_baseline.parquet` at build time via `COPY models/`.
This keeps deployment simple (no external storage dependency) at the
cost of a larger image and a full redeploy for every model update.

**Future milestone:** move artifacts to S3 or GCS with `MODEL_VERSION`
pinning so model and code can be updated independently and rolled back
separately. The `entrypoint.sh` GCS pull path is already implemented —
it activates whenever `GCS_BUCKET` is set in the environment.

## Lessons learned from M5

The frontend itself took half a day. Getting the Railway backend to actually serve it took
another two days of incremental debugging. Every issue was a filesystem assumption that
worked locally but failed in the container.

1. **The default Dockerfile build target is the last stage, not the one you named "prod."**
   We had `builder → prod → dev` and Railway (correctly) built `dev` — the final stage.
   Fix: reorder to `builder → dev → prod` so prod is last. Alternatively, set
   `buildTarget` in a `railway.toml`. The lesson: "default" means last-in-file, not
   most-intuitively-named.

2. **`railway up` respects `.gitignore` for its upload, not `.dockerignore`.**
   Adding a `.dockerignore` that un-excluded `models/*.ubj` did nothing because the file
   was stripped before it even left the local machine. The giveaway was a constant build
   context hash (`90kv-sKOm`) across every upload — same hash = same files = gitignore
   exclusions still in effect. Negation rules in `.gitignore` (`!models/health_scorer.ubj`)
   are also silently ignored by the Railway CLI. Only removing `models/*.ubj` from
   `.gitignore` entirely solved it.

3. **The prod stage was missing `COPY alembic/ ./alembic/`.**
   `alembic.ini` was copied but the `alembic/` directory containing the migration scripts
   was not. Alembic's own error message — "Path doesn't exist: /app/alembic. Please use
   the 'init' command" — made this obvious once we were past the model issue.

4. **The production database needs to be seeded separately.**
   The CI seed script (`scripts/seed_ci_data.py`) runs in the CI environment against
   a throwaway Postgres container. The Railway Postgres starts empty. Fix: `railway run
   python -m scripts.seed_ci_data` injects the production `DATABASE_URL` and seeds in
   place. Document this as a required first-deploy step, not an afterthought.

**Takeaway:** "works locally" and "works in a container" are two different things, and
the gap is almost always filesystem assumptions — files that exist on your laptop because
you ran a script once, files excluded by ignore rules you forgot about, directories that
are mounted as volumes locally but must be `COPY`-ed in prod. The debugging loop is:
run, read the crash, find the missing file, trace why it's missing (gitignore? wrong
stage? missing COPY?), fix one thing, redeploy. Budget time for this on every project
that ships containers.


## Calibration backtest (deferred, M4)

Walk-forward backtest: slide a 90-day window over historical portfolio snapshots, score
each, compare predicted score to realised forward Sharpe quintile. Use `sklearn.calibration`
to check whether score decile = top-decile risk prediction.
