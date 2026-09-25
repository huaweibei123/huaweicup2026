# Hypergap timeline diagnostic

Source reference: `run-20260924T233302Z`; result paths are relative. This script only reads existing `result.json`; no solver, constructor or evaluator is invoked.

## 005 · K5

E0 M 33,515 cycles; added DDR 1,410,582 B (partition 1,410,582, spill 0); dependencies/transfers 728/728; configured cross-core delay 500 cycles.
Transfer fields identify 728 release lags; 728 equal configured delay; 0 missing. Observed copy-in start-minus-release gap range: 0–28918 cycles. This gap alone is not evidence of critical stall.
Independent compute Pipe balance: M max/min 1.317948717948718; V max/min 1.2485892196925472.

|core|Pipe|busy|leading idle|internal idle|trailing idle|ops|
|---:|---|---:|---:|---:|---:|---:|
|0|PIPE_M|10,530|395|18,803|3,787|118|
|0|PIPE_V|10,278|598|19,008|3,631|522|
|0|PIPE_MTE2|12,782|0|16,210|4,523|154|
|0|PIPE_MTE3|6,798|410|22,708|3,599|116|
|1|PIPE_M|13,827|395|18,293|1,000|182|
|1|PIPE_V|12,704|533|19,326|952|692|
|1|PIPE_MTE2|15,193|0|16,015|2,307|209|
|1|PIPE_MTE3|7,239|1,518|23,851|907|140|
|2|PIPE_M|12,879|395|19,921|320|173|
|2|PIPE_V|12,743|1,150|19,338|284|721|
|2|PIPE_MTE2|13,245|0|18,670|1,600|175|
|2|PIPE_MTE3|8,962|410|23,885|258|149|
|3|PIPE_M|12,768|598|17,338|2,811|182|
|3|PIPE_V|12,372|195|20,922|26|682|
|3|PIPE_MTE2|16,162|0|17,291|62|208|
|3|PIPE_MTE3|7,653|613|25,249|0|162|
|4|PIPE_M|13,878|395|18,275|967|161|
|4|PIPE_V|12,833|598|19,165|919|680|
|4|PIPE_MTE2|12,336|0|18,784|2,395|158|
|4|PIPE_MTE3|10,013|1,000|21,628|874|168|

## 009 · K5

E0 M 51,905 cycles; added DDR 577,996 B (partition 577,996, spill 0); dependencies/transfers 751/751; configured cross-core delay 500 cycles.
Transfer fields identify 751 release lags; 751 equal configured delay; 0 missing. Observed copy-in start-minus-release gap range: 0–43719 cycles. This gap alone is not evidence of critical stall.
Independent compute Pipe balance: M max/min 1.3730655858511422; V max/min 1.537525466659325.

|core|Pipe|busy|leading idle|internal idle|trailing idle|ops|
|---:|---|---:|---:|---:|---:|---:|
|0|PIPE_M|10,856|50|40,925|74|281|
|0|PIPE_V|27,923|64|23,917|1|1,218|
|0|PIPE_MTE2|4,558|0|46,715|632|259|
|0|PIPE_MTE3|1,475|112|50,318|0|199|
|1|PIPE_M|11,170|50|38,038|2,647|216|
|1|PIPE_V|26,450|103|24,200|1,152|1,089|
|1|PIPE_MTE2|8,233|0|42,507|1,165|287|
|1|PIPE_MTE3|2,045|112|48,597|1,151|175|
|2|PIPE_M|13,448|50|37,412|995|244|
|2|PIPE_V|24,701|98|26,184|922|999|
|2|PIPE_MTE2|7,488|0|42,896|1,521|247|
|2|PIPE_MTE3|2,620|64|48,300|921|189|
|3|PIPE_M|14,780|98|35,911|1,116|153|
|3|PIPE_V|22,757|45|28,048|1,055|911|
|3|PIPE_MTE2|7,964|0|42,444|1,497|226|
|3|PIPE_MTE3|1,487|209|49,155|1,054|150|
|4|PIPE_M|14,906|50|26,605|10,344|72|
|4|PIPE_V|18,161|98|23,290|10,356|488|
|4|PIPE_MTE2|8,968|0|32,531|10,406|155|
|4|PIPE_MTE3|1,039|64|40,467|10,335|107|

## 015 · K5

E0 M 40,828 cycles; added DDR 317,952 B (partition 317,952, spill 0); dependencies/transfers 0/0; configured cross-core delay 500 cycles.
Transfer fields identify 0 release lags; 0 equal configured delay; 0 missing. Observed copy-in start-minus-release gap range: None–None cycles. This gap alone is not evidence of critical stall.
Independent compute Pipe balance: M max/min None; V max/min 5.6421663442940035.

|core|Pipe|busy|leading idle|internal idle|trailing idle|ops|
|---:|---|---:|---:|---:|---:|---:|
|0|PIPE_M|0|n/a|n/a|n/a|0|
|0|PIPE_V|29,170|1,370|3,856|6,432|145|
|0|PIPE_MTE2|13,791|0|0|27,037|15|
|0|PIPE_MTE3|1|34,396|0|6,431|1|
|1|PIPE_M|21,552|2,995|15,831|450|32|
|1|PIPE_V|24,204|6,079|10,236|309|230|
|1|PIPE_MTE2|14,966|0|23,050|2,812|60|
|1|PIPE_MTE3|26|24,942|15,552|308|19|
|2|PIPE_M|22,824|2,995|6,573|8,436|45|
|2|PIPE_V|21,660|9,487|9,680|1|242|
|2|PIPE_MTE2|15,426|0|19,338|6,064|80|
|2|PIPE_MTE3|23|17,720|23,085|0|22|
|3|PIPE_M|22,848|2,995|4,642|10,343|44|
|3|PIPE_V|21,293|9,223|8,894|1,418|244|
|3|PIPE_MTE2|14,207|0|21,154|5,467|73|
|3|PIPE_MTE3|29|16,786|22,596|1,417|21|
|4|PIPE_M|27,756|2,995|0|10,077|9|
|4|PIPE_V|5,170|6,079|19,636|9,943|22|
|4|PIPE_MTE2|8,985|0|0|31,843|6|
|4|PIPE_MTE3|5|24,756|6,125|9,942|3|

## Evidence limits and next hypothesis

Confirmed: per-core/per-Pipe busy and idle spans, separate M/V balance, MTE2/MTE3 activity, spill bytes, transfer/dependency counts, and configured 500-cycle release lag where fields expose it. These results do not identify why an idle interval occurred or whether a transfer is critical.

A testable algorithm hypothesis—not an established minimal effective change—is adding per-core PIPE_MTE2/PIPE_MTE3 availability calendars and honoring transfer release timestamps during candidate placement. First compare predicted copy release-to-start timing against these existing results; do not infer benefit from utilization alone.
