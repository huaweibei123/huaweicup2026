"""Workbench table adapter. Reads existing rows; does not run experiments."""
import csv
import math
import statistics
from pathlib import Path
p = Path(__file__).resolve().parent
with (p / 'metrics.csv').open(encoding='utf-8', newline='') as stream:
    rows = list(csv.DictReader(stream))
groups = {}
for row in rows:
    key = (int(row['cores']), row['platform'], row['workers'], row['timing_scope'])
    groups.setdefault(key, []).append(float(row['solver_wall']))
out = []
for (cores, platform, workers, scope), values in sorted(groups.items()):
    values.sort()
    position = .95 * (len(values) - 1)
    index = int(position)
    out.append(dict(cores=cores, platform=platform, workers=workers,
        timing_scope=scope, n=len(values), median=statistics.median(values),
        p95=values[index] + (values[min(index+1,len(values)-1)] - values[index]) * (position-index),
        max=max(values), p95_nearest_rank=values[math.ceil(.95*len(values))-1]))
with (p/'summary.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(out[0]))
    writer.writeheader()
    writer.writerows(out)
