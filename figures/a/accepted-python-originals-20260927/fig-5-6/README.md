# Figure 5-6 delivery

This package joins the pinned global-bound certificate to the accepted 500-cell official result by case, core count, and graph SHA-256. The certificate is compute-only and necessary; it does not include an exact optimality proof.

- Source certificate SHA-256: `fe25f7b7737dbd3d841284bc5939242982613f64e0cffa9bd3d25df1f4a0c96b`
- Source accepted summary SHA-256: `083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2`
- Solver commit: `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`
- Reproduce: `python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 5-6`
- Outputs: `fig56_p2_global_bound_gap.png`, `.svg`, `.pdf`, `bounds.csv`, `ecdf.csv`, `summary.csv`
- Budget: read-only parsing and plotting; no new solver or evaluator calls.

Workbench local-format-v1: only audit role/table bindings and normalized machine-readable tables are added. Original bounds/ecdf, all three figures, and author source bytes are retained unchanged. The applicability phrase is preserved in a separate column; domain=global follows the verified compute-only global certificate. Equal ECDF x values are coalesced to their right-continuous mass; the underlying distribution is unchanged. Run python normalize_tables.py after the author figure export. Author script was read but not executed by workbench.
