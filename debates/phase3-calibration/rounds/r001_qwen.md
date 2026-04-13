**Q1: (d) Hierarchical tuning**
Reasoning: Beta as sector priors provides regularization; per-name prob/weight fine-tuning captures idiosyncratic signals without overfitting 10–100 samples.
Failure mode: If hierarchy isn't penalized (e.g., no shrinkage), fine-tune layer absorbs all variance → betas become unidentifiable noise.

**Q2: MAPE + Hit-rate**
Reasoning: MAPE quantifies calibration error magnitude for the human reviewer; hit-rate validates directional signal usefulness across T+3/6/12m horizons.
Failure mode: MAPE alone rewards conservative (low-variance) outputs that miss big moves; hit-rate alone ignores magnitude of misses.

**Q3: 10+ for T+3/6m, 30+ for 12m**
Reasoning: Shorter horizons need fewer samples due to lower variance; 12m requires more to separate signal from noise. Always output with uncertainty bands regardless.
Failure mode: No threshold → garbage outputs with wide CIs that erode user trust; hard cutoff → useless silence on new sectors.

**Q4: Exclude ML models + driver catalog auto-discovery**
Reasoning: Both are scope explosions for a 1–2 week phase; manual driver catalog + parametric calibration ships fast and builds trust. Walk-forward CV can be stubbed; real-time recompute is post-calibration.
Failure mode: Including ML → weeks of feature engineering, uninterpretable outputs, no shipping.