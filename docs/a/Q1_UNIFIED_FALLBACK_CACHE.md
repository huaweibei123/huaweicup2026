# Unified fallback construction cache

The v3 constructor keeps the v2 candidate order, plan serialization, structural
routes, distinct-plan limit, and online E1 selection. For a multicore input,
bounded (B), sink peel (S), and heavy suffix (H) each need at most one successful
construction: S receives B, H receives S, and overload receives H. Only successful
results are cached. A failed H construction is retried inside overload, preserving
the original independent candidate failure boundary.

H accepts a lazy fallback factory in the unified controller, so its fallback
is built only when H actually runs. This keeps constructor substitutions in
synthetic routing tests isolated as well.

Each constructor retains its standalone default and deep-copies an injected
fallback before using it. The cache does not reuse plans across graphs or core
counts. Diagnostics keep the same meaningful fields; construction timings and
the solver variant differ. This is a call-count optimization, not a measured
solver speedup or an E0 quality claim. Synthetic unit checks compare plan bytes,
fallback details, success counts, failure retry, and alias isolation. Full
official results require a separate fixed-version run.
