# GOOGL Q2 2026 post-print memory

- Pre-print provenance is immutable: commit `aecd9207`, FROZEN report SHA256 `cdbccf30…f2f8`, embedded profile SHA256 `0990edd5…fd2fb`.
- SEC 10-Q accession `0001652044-26-000071` supplies the 2026Q2 same-accession actual: revenue 119,796; NI 112,193; diluted shares 12,309M; GAAP EPS 9.11.
- `profiles/googl.generic.yaml` now has 9 contiguous actual quarters (2024Q2..2026Q2). Seed remains 2026Q1 and forward window remains 2026Q2; no Q3 roll/reseed.
- N=8 backtest: revenue MAPE 4.976%, bias +0.982%, RW MAPE 6.693%; GAAP EPS MAPE 19.157%, bias −18.755%. EPS degradation is expected from Q1/Q2 OI&E and stays labelled structural.
- Frozen one-point score: revenue −3.219%, OP −1.788%, op margin +0.503pp, operating-EPS proxy +6.90%; GAAP EPS excluded from model scoring.
- Surprise direction: revenue miss, adjusted/operating EPS hit, OP unscored because no direct frozen-time consensus, GAAP EPS excluded.
- Q2 ETR 19.1% is elevated by deferred tax on unrealized equity gains. No disclosed ex-gain ETR; 16% forward tax anchor remains human-owned and unchanged.
- Cloud/RPO segment overlay remains a design discussion only. No implementation.
- Actual/profile commit: `9ab839f`. SK Hynix host 9Q canonical remains `b979d79f…f6e7`.
- Verification: GOOGL/EDGAR/skill tests 26 passed; full suite 225 passed and 1 unrelated pre-existing TSLA template-state failure.
