# Workshop — Next Steps

Open follow-ups after wiring up the cross-agent answer-validation pipeline
(published submission schema in `ssd-speckit-workshop/specs/submission_schema.json`,
hybrid scorer in `sdd-workshop-leaderboard/server/score.mjs`, Copilot-backed
LLM judge verified end-to-end against `claude-sonnet-4.6`). Listed in
priority order — pick whichever closes the next gap.

## 1. Tune alias dictionaries to drop free LLM calls ✅

Every label that hits the alias list short-circuits the LLM round-trip and
becomes deterministic. Run a few representative student submissions through
the judge, see which novel phrasings the model says YES to, and promote the
common ones into the per-pattern alias arrays.

- Edit: `sdd-workshop-leaderboard/server/expectations.mjs` (the `aliases`
  array on each pattern) and mirror in `sdd-workshop-leaderboard/worker/expectations.js`.
- Verify: rerun `node --test sdd-workshop-leaderboard/server/score.test.mjs`
  plus `LLM_JUDGE_MODEL=claude-sonnet-4.6 ./scripts/run-llm-test.sh` —
  the smoke test's "novel-label" cache size should shrink to 1 (only the
  rejected `"a chessboard"` remains).

## 2. Cloudflare Worker judge parity ✅

The Node server reaches Copilot through the local Python proxy. The Worker
can't host Python, so the worker path needs a different provider's bearer
token directly.

- Pick a non-Copilot OpenAI-compatible endpoint (Anthropic API, Azure
  OpenAI, OpenAI, etc.).
- Set as Worker secrets:
  ```
  cd sdd-workshop-leaderboard
  wrangler secret put LLM_JUDGE_URL
  wrangler secret put LLM_JUDGE_TOKEN
  wrangler secret put LLM_JUDGE_MODEL
  ```
- Verify with `wrangler dev` and replay the three fixtures from
  `scripts/fixtures/` against the local worker URL.

## 3. Judge log visibility

The judge silently grants/denies — only LLM transport errors log. Day-of,
the operator should be able to tail the server and watch verdicts as they
happen.

- Edit: `sdd-workshop-leaderboard/server/judge.mjs` — add one
  `console.log` inside the LLM branch with shape
  `[judge] <patternId> <normalizedLabel> -> YES|NO (llm)`.
- Mirror in `sdd-workshop-leaderboard/worker/judge.js`.

## 4. Index page — link schema and surface per-pattern breakdowns ✅

Right now `index.html` shows only the final score. Students who lose 4
points can't tell which pattern bled them. Surface per-pattern points from
the scorer (it already computes them internally).

- Extend `score()` in `server/score.mjs` to return both the rounded total
  and a `breakdown: { pattern_1: 20, pattern_2: 16, ... }` map (callers
  that only want the number can keep using `score(...)` via a thin wrapper).
- Update `/submit` in `server/server.mjs` to include the breakdown on the
  201 response.
- Update `index.html` to render the breakdown inline under each row and
  link to `ssd-speckit-workshop/specs/submission_schema.json`.

## 5. Anti-cheat — bind submissions to recent telemetry ✅

A hand-typed "perfect" answer that never ran the sim still scores 100. To
raise the floor, require a SHA of a recent telemetry window in the
submission and have the scorer reject submissions whose SHA doesn't match
any window the sim has actually emitted.

- Add a `telemetry_window_sha256` field to
  `ssd-speckit-workshop/specs/submission_schema.json` (required on
  `answer`).
- Have the sim log emitted-window SHAs (rolling, last N) somewhere the
  scorer can read.
- In `score.mjs`, fail the submission with a clear error when the SHA is
  missing or doesn't match any logged window.

## 6. Commit the work ✅

None of the three workshop repos are git-clean. Concrete groupings:

- `ssd-speckit-workshop/`: new `specs/submission_schema.json`, README
  "Submission contract" section.
- `sdd-workshop-leaderboard/`: new `server/expectations.mjs`,
  `server/judge.mjs`, rewritten `server/score.mjs`, patched
  `server/server.mjs`, mirrored `worker/{expectations,judge,score}.js`,
  patched `worker/worker.js`, new `server/score.test.mjs`, new
  `scripts/judge_proxy.py`, `scripts/with-judge.sh`, `scripts/run-llm-test.sh`,
  `scripts/test-llm-judge.mjs`, `scripts/fixtures/*.json`, README updates.
- `ssd-workshop-sim-drone/`: this file.

Suggest one commit per repo with a message that points at the design
choice ("hybrid scoring: structural deterministic + LLM-judged labels").
