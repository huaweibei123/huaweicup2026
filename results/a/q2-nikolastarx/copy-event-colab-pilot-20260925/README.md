# Fixed-owner COPY-event Colab ablation

The same three official graphs 005/009/015 at five cores use their frozen c665 selected plans as controlled seeds. Only eligible execution order changes; original owner and singleton mapping are asserted equal. This is a mechanism ablation, not a cold full solver, a historical best-combination score, or a new full500 result. A production algorithm would have to generate/select the seed online and include all those costs.

Source: copy_event_retime at 978b6f4c86a5c7057f1bc2f98abaed7fdaac2f53. One standard Colab CPU worker; at most three constructions and three official E0 calls, zero E2/retries; 60 seconds per stage, 360 seconds per batch, 4 GiB observed process-tree RSS. New session/capsule/output; no resuming the previous latency pilot. Every source/input/seed byte is checked against the capsule manifest before construction, and seed graph/plan/result identity was checked against the completed c665 audit when packaging.

## Completed controlled result

Three same-owner selected-plan ablations completed on Colab Linux x86_64 / Python 3.13.15 / 2 CPU. Actual counts: three constructions, three unmodified official E0 calls, zero E2 and retries. Batch wall: 8.292 seconds, excluding allocation/upload/download and uninstrumented CU cost. Original source/input/seed/result bytes are preserved in the capsule/results ZIPs; hashes and process receipts were read back and locally audited. The runtime was released after download.

| Case / K5 | c665 official M | Retimed official M | Reduction | Partition-added DDR unchanged | New spill-added DDR |
|---|---:|---:|---:|---:|---:|
| 005 | 33515 | 32849 | +1.987% | 1410582 B | 0 B |
| 009 | 51905 | 44648 | +13.981% | 577996 B | 0 B |
| 015 | 40828 | 57948 | −41.932% | 317952 B | 1376262 B |

The local audit confirmed identical eligible mapping and owner for every cell. Cross-core transfer counts remain 728/751/0, respectively. Thus this contrast holds placement fixed and changes ordering. The three original selected plans had zero spill; 015 now incurs 1376262 bytes of spill. This demonstrates that the event-only retiming is not capacity-safe. It does not prove how much of the increased Makespan is attributable to each spill or ordering effect.

Do not enable this as an unconditional replacement. An online production candidate must include current-input seed selection and exact scoring/fallback in its measured cost; a capacity-aware ordering rule is another research direction. The existing full500 score remains unchanged. These selected mechanism tests do not prove a full-dataset gain or global optimality.

[report.json](report.json), [capsule-manifest.json](capsule-manifest.json), [capsule.zip](capsule.zip), and [results.zip](results.zip) contain evidence. Remote runner commit: b94e57ed1a7a7cda96dd1477324f4fd902d59195; result ZIP SHA-256: 4023d549420384260682141c2fa7053b3b8b6e8e4762a525c4c5b5e166697919. This runner does not invoke native E2; no native/E0 equality claim is made for the new candidates.
