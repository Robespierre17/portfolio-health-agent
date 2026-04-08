# Technical Notes & Future Milestones

## Lesson learned: eval frameworks need debugging too

First eval run (2026-04-08, run `20260408_121257`) flagged F7 as a failure. Investigation
showed the agent was asking for clarification on a genuinely ambiguous question ("What is
the health score?" with no portfolio_id in context) — correct behaviour by design, since
F1/F2/F7 were explicitly built to prevent the agent from guessing or defaulting.

The judge's Completeness rubric incorrectly treated any clarifying question as score 1
(incomplete). Fix: added a "genuine ambiguity" special rule to the judge prompt
distinguishing clarification (correct) from refusal with sufficient context (incorrect).

**Takeaway:** eval frameworks are code. They contain bugs. A failure that doesn't make
sense in context is as likely to be a judge bug as an agent bug — investigate before
fixing the agent.


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

## Calibration backtest (deferred, M4)

Walk-forward backtest: slide a 90-day window over historical portfolio snapshots, score
each, compare predicted score to realised forward Sharpe quintile. Use `sklearn.calibration`
to check whether score decile = top-decile risk prediction.
