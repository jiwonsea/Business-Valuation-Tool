# Earnings Forecast Engine — Project Memory

<!-- This file is auto-loaded every session. Keep it English and tight: each line must prevent a likely mistake. User-facing report/terminal output stays Korean; everything else (code, comments, config, this file) is English for token economy. -->

## Purpose
Quarterly/annual forward-EPS model + consensus gap + backtest. Started as follow-up to the Midas Asset Management research interview (2026-05-18) — backs the stated 6-month goal ("find gaps between consensus and intrinsic value") with a concrete artifact. Built to be reusable for other buy-side / sell-side roles.

## Sibling Repos
- `F:\dev\Portfolio\business-valuation-tool` (BVT) — static valuation, 7 engines; growth is CAGR-fade only.
- `F:\dev\Portfolio\fx-reserves-analyzer` — macro VAR / FEVD.
- This repo supplies the forward-earnings layer BVT's growth/DCF lacks.

## Structure
```
earnings-forecast-engine/
├── cli.py                    # entry point
├── profiles/sk_hynix.yaml    # per-company assumptions (BVT profiles/ pattern)
├── engine/                   # pure functions (no IO)
├── pipeline/                 # IO only (Yahoo, DART)
├── schemas/models.py         # Pydantic v2 (BVT single-file pattern)
├── output/                   # HTML (primary) + MD + xlsx + charts
├── tests/                    # pytest
└── docs/                     # methodology, thesis, AI collaboration
```

## Conventions
- Code, docstrings, comments, config, and this file: English. User-facing output only (reports, terminal): Korean.
- Pydantic v2; engine returns Pydantic models, never DataFrames.
- All assumptions live in `profiles/*.yaml` — never hardcode numbers in code.
- Explicit `encoding='utf-8'` on every file IO (Windows cp949 guard).

## Data Sources
- **Yahoo Finance** (yfinance) — consensus, actuals, price. KS tickers e.g. `000660.KS`.
- **DART OpenAPI** — quarterly financials. corp_code cache: SK Hynix = `00164779`.
- **Manual IR assumptions** — `assumptions:` section of `profiles/{company}.yaml`.

## Open Problems (active workstreams)

Updated 2026-07-03 (post opex fix + 2026Q1 window extension + seed-implied shares + forward-window roll to 2026Q2). Offline 9Q baseline (DART cache, verified this date): rev MAPE 8.99% · EPS MAPE 10.39% · EPS bias −3.58% (inside ±5%) · MASE EPS 0.28 / Theil 0.28 · consensus skill +0.54, surprise 4/4 (N=4). 2026Q1 (supercycle: rev +60% QoQ, GP 79%) added with research-sourced drivers; its −16.3% EPS error is mostly below-OP block (−23.7% lever) → risk-band layer, per design.

- **`valuation.fair_value_elasticity` 1.2 — still DRAFT.** Confirming needs BVT DCF fixed to a positive fair value + a measured (%FV)/(%EPS) on the host (`HANDOFF_valuation_bridge.md` #3). All other formerly-draft values were CONFIRMED 2026-07-03 under user delegation: opex split (LOO/Theil-Sen robustness in profile comment), tax anchors, risk_band mad/k=1.5, overlay entries, overlay_weight.
- **Consensus vintage N=4 → expand further.** N=3→4 done 2026-07-03 by extending the backtest window to 2026Q1 (DART cache + yahoo vintage). Further N needs KR broker consensus (Naver Finance / FnGuide, README P1 — Naver is blocked in the Cowork sandbox; host workstream) or accumulating live vintages over time.
- **Backtest↔forward coupling (structural).** `run_backtest` consumes the BASE scenario's `bit_growth_qoq[0]` / `other[0]` / margins / finance as methodology assumptions — future forward-assumption changes to those fields silently move the backtest. This roll kept them pinned (base dram 0.05 / nand 0.04 / other 0.01) to preserve the 9Q baseline; the clean fix is a separate `backtest_methodology` assumptions block (NOTICED BUT NOT TOUCHING).
- **Git hygiene — committing (host).** 7+ sessions of work uncommitted on top of the initial commit. Commit per-session with `git add -p` on the host. Fixed 2026-07-02: stray literal-named `C:\temp\...cacert.pem` removed and its cause patched (`_ssl_setup` now returns early on POSIX); `.gitattributes` added (LF normalization — first commit after adding it may show a one-time renormalization diff); `*cacert.pem` gitignored.

### Resolved (see HANDOFF_*.md for details)
- ~~Forward `forecast_window` started 2026Q1 (already realized)~~ → rolled to 2026Q2 (2026-07-03, user-delegated): seed = 2026Q1 actual (rev 52,576bn / EPS 57,175, DART cache); 2026Q2~2027Q1 bear/base/bull vectors research-sourced (TrendForce 2Q26 conventional DRAM +58~63% / NAND +70~75% QoQ, 3Q26 double→single-digit deceleration; HBM3E 2026 +~20%, HBM4 ~70% premium ramp; supply tight through late 2027, 2027–28 oversupply risk → bear = correction scenario). Overlays refreshed: +2026Q3 consumer demand-destruction, +2027Q1 supply-inflection (as_of 2026-07-03); prior entries kept as ex-ante records. Verified: 9Q backtest bit-identical (full BacktestResult JSON diff), 98 tests green, dry-run OK, forward chain sanity-checked on real seed.
- ~~Opex systematic bias −4.2%~~ → diagnosed (level: constant 15% vs realized 12.5%; shape: operating leverage, corr(rev, opex%) −0.77) and fixed via optional fixed+variable opex split (`opex = 990 bn + var% × revenue`, DRAFT values). Opex lever −4.2%→+0.3%; EPS bias −6.41%→−1.61%; MASE EPS 0.37→0.28. Legacy constant-% path bit-identical when the split is absent. `PLAN_opex_model.md` §5, `scripts/diagnose_opex.py`.
- ~~Backtest not meaningful~~ → skill metrics vs naive RW (`engine/skill_metrics.py`): MASE/Theil both <1 for revenue & EPS; direction hit-rate shown to be no edge (model 87.5% = RW 87.5%). `HANDOFF_backtest_diag.md` session C.
- ~~Output diverges from actuals & consensus~~ → attributed and fixed: gross-margin anchor off-by-one (`backtest.py`) + tax anchor 0.20→0.164; bias −10.55%→−6.41%. Consensus-side divergence was yfinance `.KS` data quality, gated via `quality_notes`. Remaining below-OP block is structural → risk band.
- ~~Point-in-time overlays~~ → implemented: `Overlay` schema with lookahead guard, `engine/risk_band.py` (±band, annotation-only), `engine/valuation_bridge.py` consumer with 2-layer separation (EPS gap → fair-value delta; overlays → separate macro risk score). `HANDOFF_block_overlay.md`, `HANDOFF_valuation_bridge.md`.

## Workflow
- One session = one workstream. Plan mode → save `PLAN_*.md` to repo → implement in a fresh focused session → self-verify with pytest / `--dry-run`.
- Cross-session continuity via Cowork memory + repo `HANDOFF_*.md` (keep the latter for git / portfolio narrative).
- Human: methodology, assumption values, scenario probabilities, result interpretation, thesis, interview answers.
- AI (Codex CLI on host, or Cowork here): code, refactor, tests, Pydantic schemas, report/template boilerplate, dry-run verification.
- Do not delete CLAUDE.md / AGENTS.md / `.codex/` meta dirs (2026-04-27 user policy).

## Engineering Rules (Cowork-relevant subset of global CLAUDE.md)
- Think before coding: state assumptions; if multiple readings exist, surface them instead of picking silently. Plan mode for 3+ file or hard-to-reverse changes; execute single-file edits directly.
- Simplicity first: minimum code for the asked problem; legibility over cleverness; no unrequested abstractions.
- Surgical changes: every changed line traces to the request; don't refactor what isn't broken; log `NOTICED BUT NOT TOUCHING: file:line symptom` instead of fixing adjacent code.
- Goal-driven: turn vague tasks into failing-test → pass; run pytest / dry-run after changes and fix failures before reporting done; measure baseline before structural change; on regression, stop and isolate before new work.
- Security: never commit `.env`; never print API keys / secrets in chat.

## Runtime Gotchas
- Cowork sandbox mounts the repo at an ASCII path, so the old Codex 한글-path silent-fail does NOT apply here. (Still required when running Codex / Claude Code on the Windows host.)
- Sandbox network is allowlisted: Yahoo direct returned 403 — live Yahoo / DART calls may fail in Cowork. Use `--dry-run` (fixtures) in Cowork; run live data pulls on the Windows host.
- Sandbox resets per session — reinstall deps with `pip install -r requirements.txt --break-system-packages`.
- Yahoo `.KS` tickers: some fields sparse → null-handle + "consensus unavailable" warning.
- Keep single-file Plotly HTML < 5MB — no Malgun.ttf embed, system fonts only.
- DART API rate limit 1000/min — httpx retry / backoff.

## Device Bridge Limits (measured 2026-08-12) — the "bridge keeps dropping" cause
Every `device_bash` call is a **fresh bwrap sandbox** (`--unshare-pid --die-with-parent`). So:
- **Hard 45 s wall per call.** At 45 s the whole PID namespace is torn down. Budget ~35 s.
- **`nohup` / `&` do NOT survive the call** — verified: a backgrounded loop stops the instant the call returns. No daemons, no long pytest, no shell/cwd/env carry-over.
- **A killed git leaves `.git/index.lock`, and the mount forbids unlink** (`rm` → "Operation not permitted"), so the lock is permanent → every later git command fails. This cascade is what looks like a dropped bridge. (One such lock sat stale from 2026-08-09 to 2026-08-12.)
- Removal on the mount = `mv` into `_to_delete/` only. Overwrites work; deletes never do.
- The VM's own disk (`/sessions`, ~9.8 G) is the tight one — tars + `pip install` fill it; the mount itself has ~800 G.
- FUSE cost ≈ 3.5 ms/file: `du -sh` of the repo 5.8 s, `tar` incl. `.git` 15 s (of the 45 s budget).

**Always run first, and after every git command:**
```bash
python scripts/bridge_ops.py preflight
python scripts/bridge_ops.py git commit -m ...
python scripts/bridge_ops.py run --budget 35 -- <cmd>
python scripts/bridge_ops.py chunk --list <list> --state <state> -- <cmd with {}>
python scripts/bridge_ops.py chunk --list <list> --state <state> --shell --command '<template using BRIDGE_ITEM>'
```

Git commands that touch the index leave a lock after every run on the mount, so cleanup must run after git. On the host, locks are preserved by default; `locks --stale-after 600` is explicit because age-based deletion can break a long-running git operation. For chunk resumes, `--assume-idempotent` approves retrying previously failed items only after confirming duplicate side effects are impossible; the tool cannot detect partial success.
**Second, distinct failure — the MCP transport itself drops** (observed live 2026-08-12 07:22 KST+): all `mcp__remote-devices__*` tools vanish, `device_bash` → "No such tool available". The device VM keeps running (uptime continuous, mount and files intact). **Recovery is `RefreshMcpTools(server="remote-devices")`, not a new session** — tools came back in one call with no state loss. Only if `ls $HOME/mnt/<repo>` fails after that is the desktop app actually down.

## Verification

```powershell
python -m pytest tests/test_bridge_ops.py -q
```
- `pytest -q` — per-engine unit tests.
- `python scripts/verify_anchor.py` — offline G1 gate: reproduce active forward anchors with zero network calls, then verify the canonical 9Q SHA.
- `python -m pytest tests/test_frozen_integrity.py -q -s` — FROZEN Git/blob/profile-SHA gate; must run on the Windows host from a Git checkout.
- `python cli.py --company sk_hynix --dry-run` — offline report from fixtures.
- `python cli.py --company sk_hynix` — live pull, inspect HTML (run on host if sandbox network is blocked).
- 9Q backtest MAPE: revisit assumptions if revenue > 10% or EPS > 25%.
- Model must beat naive-baseline error, not just hit direction. Gap < 5% every quarter = "no view" → rewrite thesis; gap large vs BOTH actual and consensus = bug → diagnose.

## Plan Reference
Original: `C:\Users\김지원\.claude\plans\glittery-juggling-candle.md`
