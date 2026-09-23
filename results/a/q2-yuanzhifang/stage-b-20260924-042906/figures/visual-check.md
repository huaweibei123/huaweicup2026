# Figure visual check

Developer checked the actual exported PNGs from `src/q2/plot_stage_b.py` at
177.8 mm nominal width (2100 px at 300 dpi); PDF/SVG share the same figure canvas.
This is a layout/data check, not final scientific acceptance or a claim about
the competition's final print specification.

- `quality_cost`: zero-based bars, consistent D/M1/M2 colors and hatch/edge
  distinctions, readable axis units and [E0 call] labels, legend outside data.
  The first render crowded three identical case008 value labels; the final
  source uses one centered `123.1 (all)` annotation. Final PNG was viewed again:
  no remaining overlap/clipping; exact integers remain in metrics.csv.
- `candidate_regressions`: all 104 official exploration points across six
  pools are plotted (duplicates are not evaluations), with D reference at 1,
  all regressions visible through the common 0–3.35 ratio axis, and incumbent
  diamonds including fallback to D. Text and marker explanations are readable.
- No error bars or stochastic uncertainty claims. Tables provide full numeric
  values and the input/output hashes are in provenance.json.

The output location is within the authorized Q2 result directory, rather than
adding a new shared figure tree. Style attribution and CC BY-NC 4.0 source are
retained in the plotting script, report and provenance.
