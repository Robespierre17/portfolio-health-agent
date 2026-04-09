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

## Calibration backtest (deferred, M4)

Walk-forward backtest: slide a 90-day window over historical portfolio snapshots, score
each, compare predicted score to realised forward Sharpe quintile. Use `sklearn.calibration`
to check whether score decile = top-decile risk prediction.
