# 本轮机器可重算的结果摘要

所有主表均来自本轮新运行；不是找回295份历史结果。池最好值不是未知全局最优。

## pilot_v1

|case|旧三构造最好|串行包矩阵|小张量块矩阵|新二构造最好|时间下降|
|---|---:|---:|---:|---:|---:|
|case_001|58984|58984|58984|58984|0.00%|
|case_002|111212|71904|261945|71904|35.35%|
|case_010|24566|26176|23569|23569|4.06%|
|case_044|70260|74838|124268|74838|-6.52%|
|case_048|110334|105597|222220|105597|4.29%|
|case_051|188224|178884|178884|178884|4.96%|
|case_094|24640|41614|23245|23245|5.66%|

## validation_v1

|case|旧三构造最好|串行包矩阵|小张量块矩阵|新二构造最好|时间下降|
|---|---:|---:|---:|---:|---:|
|case_019|23219|24396|23219|23219|0.00%|
|case_026|28637|46781|29824|29824|-4.14%|
|case_037|53320|86131|53320|53320|0.00%|
|case_064|15035|14900|19116|14900|0.90%|
|case_069|20835|17707|25144|17707|15.01%|
|case_071|15328|13443|18919|13443|12.30%|
|case_080|107695|141957|111314|111314|-3.36%|
|case_096|24913|28559|23073|23073|7.39%|

## q3_transfer_v1

|case|旧三构造最好|串行包矩阵|小张量块矩阵|新二构造最好|时间下降|
|---|---:|---:|---:|---:|---:|
|case_002|111173|71904|261945|71904|35.32%|
|case_010|24554|25017|23557|23557|4.06%|
|case_026|28293|40493|27929|27929|1.29%|
|case_044|63765|71199|89039|71199|-11.66%|
|case_051|188224|178876|178876|178876|4.97%|
|case_069|19163|16673|25144|16673|12.99%|
|case_094|24640|38529|23245|23245|5.66%|
|case_096|24912|25921|23073|23073|7.38%|

## n2_transfer_v1

|case|旧三构造最好|串行包矩阵|小张量块矩阵|新二构造最好|时间下降|
|---|---:|---:|---:|---:|---:|
|case_002|138426|137730|261945|137730|0.50%|
|case_010|45071|40794|44737|40794|9.49%|
|case_044|62625|62070|131105|62070|0.89%|
|case_051|318212|318212|318212|318212|0.00%|
|case_094|47042|51661|46982|46982|0.13%|

## n5_transfer_v1

|case|旧三构造最好|串行包矩阵|小张量块矩阵|新二构造最好|时间下降|
|---|---:|---:|---:|---:|---:|
|case_002|117925|59762|261945|59762|49.32%|
|case_010|21316|28145|20383|20383|4.38%|
|case_044|82031|86988|132892|86988|-6.04%|
|case_051|169820|167276|167276|167276|1.50%|
|case_094|21149|46854|19310|19310|8.70%|

## FAST 新P1诊断

{
  "scope": "new P1 5x8 diagnostic pools; NOT >=64 release pools",
  "e1_full_object_equal": 40,
  "event_error_median": 0.1682339589991504,
  "event_error_p95_nearest_rank": 0.5978333870875941,
  "event_max_error": 0.6888338107960215,
  "pools": [
    {
      "case": "case_002",
      "pool_size": 8,
      "best_e0": 93126,
      "rank_top1": "cover16_guard0",
      "rank_top1_regret": 0.06523419882739523,
      "event_top1": "cover16_guard0",
      "event_top1_regret": 0.06523419882739523
    },
    {
      "case": "case_010",
      "pool_size": 8,
      "best_e0": 29918,
      "rank_top1": "component",
      "rank_top1_regret": 0.0,
      "event_top1": "cut2",
      "event_top1_regret": 0.2626846714352564
    },
    {
      "case": "case_026",
      "pool_size": 8,
      "best_e0": 42208,
      "rank_top1": "component",
      "rank_top1_regret": 0.0,
      "event_top1": "cut2",
      "event_top1_regret": 0.21299279757391965
    },
    {
      "case": "case_044",
      "pool_size": 8,
      "best_e0": 124268,
      "rank_top1": "component",
      "rank_top1_regret": 0.0,
      "event_top1": "component",
      "event_top1_regret": 0.0
    },
    {
      "case": "case_051",
      "pool_size": 8,
      "best_e0": 338092,
      "rank_top1": "chain",
      "rank_top1_regret": 0.0,
      "event_top1": "chain",
      "event_top1_regret": 0.0
    }
  ]
}

## 各构造完整运行表

|suite|case|q|n|method|Makespan|构造s|E0函数s|含存档s|
|---|---|---:|---:|---|---:|---:|---:|---:|
|n2_transfer_v1|case_002|2|2|component|261945|0.0102|0.3850|0.4028|
|n2_transfer_v1|case_002|2|2|cut2|261945|0.0079|0.3436|0.3591|
|n2_transfer_v1|case_002|2|2|unit|138426|0.0222|0.9921|1.0545|
|n2_transfer_v1|case_002|2|2|chain_response|137730|0.0832|0.4823|0.5794|
|n2_transfer_v1|case_002|2|2|cut2_response|261945|0.0573|0.3745|0.4381|
|n2_transfer_v1|case_002|2|2|refine_response|129548|0.0783|0.4342|0.5261|
|n2_transfer_v1|case_002|2|2|nr_response|140055|0.0889|0.7277|0.8530|
|n2_transfer_v1|case_010|2|2|component|46568|0.0025|0.0975|0.1039|
|n2_transfer_v1|case_010|2|2|cut2|45071|0.0094|0.0839|0.0973|
|n2_transfer_v1|case_010|2|2|unit|56782|0.0062|0.1675|0.1913|
|n2_transfer_v1|case_010|2|2|chain_response|40794|0.0333|0.1594|0.1997|
|n2_transfer_v1|case_010|2|2|cut2_response|44737|0.0116|0.0809|0.0966|
|n2_transfer_v1|case_010|2|2|refine_response|43682|0.0289|0.2507|0.2887|
|n2_transfer_v1|case_010|2|2|nr_response|42003|0.0359|0.1275|0.1797|
|n2_transfer_v1|case_044|2|2|component|131105|0.0094|0.2628|0.2787|
|n2_transfer_v1|case_044|2|2|cut2|149967|0.0055|0.2177|0.2311|
|n2_transfer_v1|case_044|2|2|unit|62625|0.0827|0.3385|0.4426|
|n2_transfer_v1|case_044|2|2|chain_response|62070|0.0928|0.3467|0.4566|
|n2_transfer_v1|case_044|2|2|cut2_response|131105|0.0252|0.2060|0.2366|
|n2_transfer_v1|case_044|2|2|refine_response|62339|0.0650|0.3790|0.4563|
|n2_transfer_v1|case_044|2|2|nr_response|59103|0.0535|0.3552|0.4361|
|n2_transfer_v1|case_051|2|2|component|607628|0.0053|0.1686|0.1789|
|n2_transfer_v1|case_051|2|2|cut2|318212|0.0106|0.2628|0.2839|
|n2_transfer_v1|case_051|2|2|unit|732959|0.0179|0.3442|0.3813|
|n2_transfer_v1|case_051|2|2|chain_response|318212|0.0292|0.2212|0.2623|
|n2_transfer_v1|case_051|2|2|cut2_response|318212|0.0292|0.1902|0.2299|
|n2_transfer_v1|case_051|2|2|refine_response|318212|0.1086|0.1857|0.3048|
|n2_transfer_v1|case_051|2|2|nr_response|318212|0.0343|0.2372|0.2823|
|n2_transfer_v1|case_094|2|2|component|48073|0.0021|0.0749|0.0803|
|n2_transfer_v1|case_094|2|2|cut2|47042|0.0034|0.0805|0.0874|
|n2_transfer_v1|case_094|2|2|unit|63547|0.0064|0.1890|0.2055|
|n2_transfer_v1|case_094|2|2|chain_response|51661|0.0224|0.1267|0.1568|
|n2_transfer_v1|case_094|2|2|cut2_response|46982|0.0127|0.0749|0.0911|
|n2_transfer_v1|case_094|2|2|refine_response|51778|0.0703|0.1338|0.2111|
|n2_transfer_v1|case_094|2|2|nr_response|50233|0.0177|0.1195|0.1521|
|n5_transfer_v1|case_002|2|5|component|261945|0.0651|0.3146|0.3873|
|n5_transfer_v1|case_002|2|5|cut2|261945|0.0066|0.3197|0.3335|
|n5_transfer_v1|case_002|2|5|unit|117925|0.0248|1.0613|1.1659|
|n5_transfer_v1|case_002|2|5|chain_response|59762|0.0804|0.6883|0.7853|
|n5_transfer_v1|case_002|2|5|cut2_response|261945|0.0266|0.2778|0.3114|
|n5_transfer_v1|case_002|2|5|refine_response|63637|0.0954|0.3001|0.4091|
|n5_transfer_v1|case_002|2|5|nr_response|111373|0.0544|0.5343|0.6125|
|n5_transfer_v1|case_010|2|5|component|31019|0.0026|0.0770|0.0828|
|n5_transfer_v1|case_010|2|5|cut2|21316|0.0044|0.0843|0.0936|
|n5_transfer_v1|case_010|2|5|unit|67042|0.0111|0.2626|0.2897|
|n5_transfer_v1|case_010|2|5|chain_response|28145|0.0278|0.2660|0.3025|
|n5_transfer_v1|case_010|2|5|cut2_response|20383|0.0154|0.0899|0.1101|
|n5_transfer_v1|case_010|2|5|refine_response|28464|0.0354|0.1713|0.2145|
|n5_transfer_v1|case_010|2|5|nr_response|27286|0.0215|0.1250|0.1541|
|n5_transfer_v1|case_044|2|5|component|132892|0.0037|0.1560|0.1652|
|n5_transfer_v1|case_044|2|5|cut2|172053|0.0063|0.2026|0.2152|
|n5_transfer_v1|case_044|2|5|unit|82031|0.0271|0.2114|0.2512|
|n5_transfer_v1|case_044|2|5|chain_response|86988|0.0334|0.2438|0.2882|
|n5_transfer_v1|case_044|2|5|cut2_response|132892|0.0190|0.1514|0.1762|
|n5_transfer_v1|case_044|2|5|refine_response|89774|0.1086|0.2007|0.3280|
|n5_transfer_v1|case_044|2|5|nr_response|78341|0.0465|0.2217|0.2776|
|n5_transfer_v1|case_051|2|5|component|607628|0.0040|0.1465|0.1553|
|n5_transfer_v1|case_051|2|5|cut2|169820|0.0108|0.2778|0.3030|
|n5_transfer_v1|case_051|2|5|unit|201061|0.0194|0.3119|0.3499|
|n5_transfer_v1|case_051|2|5|chain_response|167276|0.0398|0.2591|0.3131|
|n5_transfer_v1|case_051|2|5|cut2_response|167276|0.0718|0.2259|0.3116|
|n5_transfer_v1|case_051|2|5|refine_response|167276|0.0763|0.2938|0.3858|
|n5_transfer_v1|case_051|2|5|nr_response|167276|0.0439|0.2736|0.3313|
|n5_transfer_v1|case_094|2|5|component|21573|0.0025|0.0798|0.0858|
|n5_transfer_v1|case_094|2|5|cut2|21149|0.0036|0.0787|0.0863|
|n5_transfer_v1|case_094|2|5|unit|57585|0.0087|0.1929|0.2160|
|n5_transfer_v1|case_094|2|5|chain_response|46854|0.0188|0.2677|0.2962|
|n5_transfer_v1|case_094|2|5|cut2_response|19310|0.0162|0.0807|0.1004|
|n5_transfer_v1|case_094|2|5|refine_response|47466|0.0339|0.2167|0.2657|
|n5_transfer_v1|case_094|2|5|nr_response|45723|0.0228|0.2245|0.2625|
|phase_refinement_v1|case_002|2|4|phasefix_response|72227|0.1342|0.3020|0.4517|
|phase_refinement_v1|case_002|2|4|phase_response|104109|0.0735|0.5246|0.6290|
|phase_refinement_v1|case_010|2|4|phasefix_response|27648|0.0330|0.1281|0.1696|
|phase_refinement_v1|case_010|2|4|phase_response|29016|0.0239|0.1634|0.1961|
|phase_refinement_v1|case_044|2|4|phasefix_response|78647|0.0750|0.2772|0.3678|
|phase_refinement_v1|case_044|2|4|phase_response|70970|0.0551|0.1764|0.2447|
|phase_refinement_v1|case_048|2|4|phasefix_response|105597|0.1701|0.3750|0.5693|
|phase_refinement_v1|case_048|2|4|phase_response|105597|0.0851|0.3960|0.4999|
|phase_refinement_v1|case_051|2|4|phasefix_response|178884|0.0649|0.2123|0.2917|
|phase_refinement_v1|case_051|2|4|phase_response|178884|0.0988|0.2260|0.3370|
|phase_refinement_v1|case_094|2|4|phasefix_response|41720|0.0377|0.1830|0.2288|
|phase_refinement_v1|case_094|2|4|phase_response|43887|0.0191|0.1629|0.1898|
|phase_refinement_v1|case_069|2|4|phasefix_response|17413|0.0656|0.2275|0.3051|
|phase_refinement_v1|case_069|2|4|phase_response|19467|0.0873|0.2122|0.3335|
|pilot_v1|case_001|2|4|component|58984|0.0051|0.1293|0.1392|
|pilot_v1|case_001|2|4|cut2|58984|0.0037|0.0713|0.0792|
|pilot_v1|case_001|2|4|unit|78028|0.0070|0.0859|0.0996|
|pilot_v1|case_001|2|4|chain_scalar|58984|0.0111|0.0761|0.0926|
|pilot_v1|case_001|2|4|chain_response|58984|0.0102|0.0858|0.1005|
|pilot_v1|case_001|2|4|cut2_response|58984|0.0111|0.1391|0.1553|
|pilot_v1|case_001|2|4|ideal_response|58984|0.0151|0.0813|0.1027|
|pilot_v1|case_002|2|4|component|261945|0.0054|0.3331|0.3513|
|pilot_v1|case_002|2|4|cut2|261945|0.0079|0.2323|0.2480|
|pilot_v1|case_002|2|4|unit|111212|0.0217|0.7486|0.8029|
|pilot_v1|case_002|2|4|chain_scalar|72650|0.0259|0.3123|0.3521|
|pilot_v1|case_002|2|4|chain_response|71904|0.0305|0.3144|0.3613|
|pilot_v1|case_002|2|4|cut2_response|261945|0.0218|0.2604|0.2886|
|pilot_v1|case_002|2|4|ideal_response|115746|5.7500|0.1988|5.9579|
|pilot_v1|case_010|2|4|component|29918|0.0019|0.0961|0.1021|
|pilot_v1|case_010|2|4|cut2|24566|0.0053|0.1944|0.2117|
|pilot_v1|case_010|2|4|unit|64978|0.0166|0.2281|0.2580|
|pilot_v1|case_010|2|4|chain_scalar|26338|0.0207|0.2016|0.2297|
|pilot_v1|case_010|2|4|chain_response|26176|0.0191|0.1440|0.1713|
|pilot_v1|case_010|2|4|cut2_response|23569|0.0138|0.1783|0.1976|
|pilot_v1|case_010|2|4|ideal_response|29916|0.0243|0.1052|0.1328|
|pilot_v1|case_044|2|4|component|124268|0.0063|0.2003|0.2145|
|pilot_v1|case_044|2|4|cut2|156394|0.0055|0.2695|0.2810|
|pilot_v1|case_044|2|4|unit|70260|0.0321|0.2112|0.2567|
|pilot_v1|case_044|2|4|chain_scalar|73593|0.0247|0.2920|0.3285|
|pilot_v1|case_044|2|4|chain_response|74838|0.0311|0.3164|0.3745|
|pilot_v1|case_044|2|4|cut2_response|124268|0.0286|0.2166|0.2513|
|pilot_v1|case_044|2|4|ideal_response|124268|0.0224|0.2492|0.2778|
|pilot_v1|case_048|2|4|component|222220|0.0063|0.3279|0.3424|
|pilot_v1|case_048|2|4|cut2|222220|0.1521|0.3885|0.5508|
|pilot_v1|case_048|2|4|unit|110334|0.0344|0.4350|0.5011|
|pilot_v1|case_048|2|4|chain_scalar|109672|0.0527|0.3824|0.4549|
|pilot_v1|case_048|2|4|chain_response|105597|0.0577|0.3536|0.4305|
|pilot_v1|case_048|2|4|cut2_response|222220|0.0293|0.2813|0.3176|
|pilot_v1|case_048|2|4|ideal_response|222533|3.9403|0.2440|4.1904|
|pilot_v1|case_051|2|4|component|607628|0.0043|0.1848|0.1936|
|pilot_v1|case_051|2|4|cut2|188224|0.0109|0.2680|0.2927|
|pilot_v1|case_051|2|4|unit|188732|0.0170|0.2244|0.2562|
|pilot_v1|case_051|2|4|chain_scalar|178884|0.0250|0.2582|0.2969|
|pilot_v1|case_051|2|4|chain_response|178884|0.0282|0.2574|0.2983|
|pilot_v1|case_051|2|4|cut2_response|178884|0.0266|0.2026|0.2417|
|pilot_v1|case_051|2|4|ideal_response|607628|1.7020|0.1409|1.8485|
|pilot_v1|case_094|2|4|component|24640|0.0021|0.1088|0.1147|
|pilot_v1|case_094|2|4|cut2|25350|0.0040|0.0775|0.0851|
|pilot_v1|case_094|2|4|unit|57192|0.0091|0.1706|0.1901|
|pilot_v1|case_094|2|4|chain_scalar|45284|0.0151|0.1431|0.1689|
|pilot_v1|case_094|2|4|chain_response|41614|0.0194|0.1952|0.2225|
|pilot_v1|case_094|2|4|cut2_response|23245|0.0117|0.0736|0.0892|
|pilot_v1|case_094|2|4|ideal_response|23527|0.0102|0.0707|0.0839|
|q3_transfer_v1|case_002|3|4|component|261945|0.0094|0.2851|0.3049|
|q3_transfer_v1|case_002|3|4|cut2|261945|0.0072|0.2885|0.3052|
|q3_transfer_v1|case_002|3|4|unit|111173|0.0286|0.7498|0.8310|
|q3_transfer_v1|case_002|3|4|chain_response|71904|0.0473|0.3244|0.3906|
|q3_transfer_v1|case_002|3|4|cut2_response|261945|0.0266|0.2922|0.3288|
|q3_transfer_v1|case_002|3|4|refine_response|71108|0.0907|0.3277|0.4380|
|q3_transfer_v1|case_002|3|4|nr_response|110417|0.0554|0.5654|0.6671|
|q3_transfer_v1|case_010|3|4|component|29858|0.0023|0.0733|0.0796|
|q3_transfer_v1|case_010|3|4|cut2|24554|0.0047|0.1311|0.1431|
|q3_transfer_v1|case_010|3|4|unit|59454|0.0078|0.1695|0.1923|
|q3_transfer_v1|case_010|3|4|chain_response|25017|0.0394|0.1367|0.1883|
|q3_transfer_v1|case_010|3|4|cut2_response|23557|0.0159|0.1823|0.2039|
|q3_transfer_v1|case_010|3|4|refine_response|25024|0.0394|0.1393|0.1894|
|q3_transfer_v1|case_010|3|4|nr_response|26243|0.0196|0.1448|0.1784|
|q3_transfer_v1|case_026|3|4|component|42208|0.0019|0.0820|0.0883|
|q3_transfer_v1|case_026|3|4|cut2|28293|0.0048|0.2823|0.3040|
|q3_transfer_v1|case_026|3|4|unit|84424|0.0096|0.3547|0.4109|
|q3_transfer_v1|case_026|3|4|chain_response|40493|0.0465|0.1776|0.2451|
|q3_transfer_v1|case_026|3|4|cut2_response|27929|0.0142|0.0984|0.1217|
|q3_transfer_v1|case_026|3|4|refine_response|42665|0.0901|0.1451|0.2518|
|q3_transfer_v1|case_026|3|4|nr_response|42762|0.0395|0.1585|0.2119|
|q3_transfer_v1|case_044|3|4|component|89039|0.0074|0.2506|0.2665|
|q3_transfer_v1|case_044|3|4|cut2|100591|0.0070|0.1877|0.2019|
|q3_transfer_v1|case_044|3|4|unit|63765|0.0203|0.3061|0.3433|
|q3_transfer_v1|case_044|3|4|chain_response|71199|0.0470|0.3224|0.3922|
|q3_transfer_v1|case_044|3|4|cut2_response|89039|0.0662|0.2100|0.2850|
|q3_transfer_v1|case_044|3|4|refine_response|75335|0.0917|0.3504|0.4608|
|q3_transfer_v1|case_044|3|4|nr_response|64945|0.0553|0.2113|0.2789|
|q3_transfer_v1|case_051|3|4|component|607628|0.0398|0.1736|0.2191|
|q3_transfer_v1|case_051|3|4|cut2|188224|0.0125|0.3028|0.3328|
|q3_transfer_v1|case_051|3|4|unit|188732|0.0228|0.2529|0.2934|
|q3_transfer_v1|case_051|3|4|chain_response|178876|0.0852|0.2533|0.3554|
|q3_transfer_v1|case_051|3|4|cut2_response|178876|0.0747|0.2969|0.3899|
|q3_transfer_v1|case_051|3|4|refine_response|178876|0.0702|0.3117|0.4036|
|q3_transfer_v1|case_051|3|4|nr_response|178876|0.0374|0.2373|0.2984|
|q3_transfer_v1|case_069|3|4|component|25144|0.0033|0.1702|0.1780|
|q3_transfer_v1|case_069|3|4|cut2|25144|0.0075|0.0886|0.1004|
|q3_transfer_v1|case_069|3|4|unit|19163|0.0160|0.3013|0.3423|
|q3_transfer_v1|case_069|3|4|chain_response|16673|0.0339|0.2530|0.3027|
|q3_transfer_v1|case_069|3|4|cut2_response|25144|0.0178|0.1564|0.1793|
|q3_transfer_v1|case_069|3|4|refine_response|16673|0.0693|0.2027|0.2927|
|q3_transfer_v1|case_069|3|4|nr_response|16673|0.0344|0.2647|0.3151|
|q3_transfer_v1|case_094|3|4|component|24640|0.0023|0.0823|0.0907|
|q3_transfer_v1|case_094|3|4|cut2|25160|0.0042|0.0909|0.1009|
|q3_transfer_v1|case_094|3|4|unit|54004|0.0093|0.2034|0.2357|
|q3_transfer_v1|case_094|3|4|chain_response|38529|0.0178|0.1948|0.2243|
|q3_transfer_v1|case_094|3|4|cut2_response|23245|0.0149|0.0730|0.0933|
|q3_transfer_v1|case_094|3|4|refine_response|38624|0.0448|0.1468|0.2037|
|q3_transfer_v1|case_094|3|4|nr_response|39343|0.0225|0.2017|0.2367|
|q3_transfer_v1|case_096|3|4|component|26984|0.0041|0.2410|0.2573|
|q3_transfer_v1|case_096|3|4|cut2|24912|0.0142|0.2268|0.2628|
|q3_transfer_v1|case_096|3|4|unit|45286|0.0208|0.4657|0.5159|
|q3_transfer_v1|case_096|3|4|chain_response|25921|0.0374|0.3044|0.3651|
|q3_transfer_v1|case_096|3|4|cut2_response|23073|0.0355|0.1568|0.2019|
|q3_transfer_v1|case_096|3|4|refine_response|25897|0.0660|0.3088|0.3920|
|q3_transfer_v1|case_096|3|4|nr_response|24207|0.0327|0.2205|0.2684|
|refinement_v1|case_002|2|4|nr_response|110545|0.0980|0.5985|0.7240|
|refinement_v1|case_002|2|4|refine_response|71108|0.0953|0.2973|0.4076|
|refinement_v1|case_002|2|4|unit_scalar|104473|0.0482|0.5891|0.6737|
|refinement_v1|case_002|2|4|unit_response|104109|0.0669|0.4905|0.5834|
|refinement_v1|case_010|2|4|nr_response|28307|0.0221|0.1669|0.1964|
|refinement_v1|case_010|2|4|refine_response|26268|0.0359|0.1238|0.1668|
|refinement_v1|case_010|2|4|unit_scalar|67629|0.0236|0.1678|0.2023|
|refinement_v1|case_010|2|4|unit_response|54864|0.0229|0.1852|0.2179|
|refinement_v1|case_044|2|4|nr_response|68466|0.0417|0.1783|0.2299|
|refinement_v1|case_044|2|4|refine_response|79001|0.1041|0.2867|0.4084|
|refinement_v1|case_044|2|4|unit_scalar|70281|0.0429|0.2714|0.3277|
|refinement_v1|case_044|2|4|unit_response|68510|0.0710|0.2553|0.3385|
|refinement_v1|case_048|2|4|nr_response|105597|0.0697|0.4246|0.5174|
|refinement_v1|case_048|2|4|refine_response|105597|0.1241|0.3629|0.5146|
|refinement_v1|case_048|2|4|unit_scalar|107643|0.0618|0.4446|0.5312|
|refinement_v1|case_048|2|4|unit_response|107477|0.0748|0.3804|0.4813|
|refinement_v1|case_051|2|4|nr_response|178884|0.0390|0.3015|0.3536|
|refinement_v1|case_051|2|4|refine_response|178884|0.0685|0.2261|0.3078|
|refinement_v1|case_051|2|4|unit_scalar|185255|0.0917|0.2404|0.3499|
|refinement_v1|case_051|2|4|unit_response|185255|0.0717|0.3355|0.4270|
|refinement_v1|case_094|2|4|nr_response|41122|0.0320|0.1620|0.2023|
|refinement_v1|case_094|2|4|refine_response|41738|0.0360|0.2321|0.2761|
|refinement_v1|case_094|2|4|unit_scalar|55844|0.0190|0.1637|0.1930|
|refinement_v1|case_094|2|4|unit_response|51312|0.0234|0.1627|0.1957|
|refinement_v1|case_069|2|4|nr_response|17707|0.0763|0.2599|0.3516|
|refinement_v1|case_069|2|4|refine_response|17707|0.0633|0.2324|0.3098|
|refinement_v1|case_069|2|4|unit_scalar|21199|0.0851|0.2473|0.3481|
|refinement_v1|case_069|2|4|unit_response|17422|0.0422|0.2619|0.3175|
|validation_v1|case_019|2|4|component|24099|0.0061|0.1475|0.1574|
|validation_v1|case_019|2|4|cut2|23219|0.0034|0.0929|0.0997|
|validation_v1|case_019|2|4|unit|33579|0.0081|0.1741|0.1946|
|validation_v1|case_019|2|4|chain_response|24396|0.0153|0.1671|0.1904|
|validation_v1|case_019|2|4|cut2_response|23219|0.0152|0.0684|0.0880|
|validation_v1|case_026|2|4|component|42208|0.0386|0.0754|0.1184|
|validation_v1|case_026|2|4|cut2|28637|0.0038|0.1278|0.1369|
|validation_v1|case_026|2|4|unit|87759|0.0307|0.3152|0.3745|
|validation_v1|case_026|2|4|chain_response|46781|0.0185|0.3114|0.3415|
|validation_v1|case_026|2|4|cut2_response|29824|0.0188|0.1184|0.1424|
|validation_v1|case_037|2|4|component|53320|0.0039|0.1602|0.1723|
|validation_v1|case_037|2|4|cut2|58564|0.0055|0.1607|0.1720|
|validation_v1|case_037|2|4|unit|95035|0.0118|0.3503|0.3889|
|validation_v1|case_037|2|4|chain_response|86131|0.0599|0.2826|0.3620|
|validation_v1|case_037|2|4|cut2_response|53320|0.0529|0.1099|0.1683|
|validation_v1|case_064|2|4|component|19116|0.0030|0.1270|0.1331|
|validation_v1|case_064|2|4|cut2|19116|0.0036|0.1044|0.1114|
|validation_v1|case_064|2|4|unit|15035|0.0182|0.3160|0.3457|
|validation_v1|case_064|2|4|chain_response|14900|0.0316|0.1497|0.1960|
|validation_v1|case_064|2|4|cut2_response|19116|0.0202|0.1160|0.1407|
|validation_v1|case_069|2|4|component|25144|0.0033|0.2263|0.2345|
|validation_v1|case_069|2|4|cut2|25144|0.0081|0.1410|0.1525|
|validation_v1|case_069|2|4|unit|20835|0.0213|0.3382|0.3768|
|validation_v1|case_069|2|4|chain_response|17707|0.1199|0.2966|0.4341|
|validation_v1|case_069|2|4|cut2_response|25144|0.0238|0.1559|0.1862|
|validation_v1|case_071|2|4|component|18919|0.0045|0.2621|0.2701|
|validation_v1|case_071|2|4|cut2|18919|0.0057|0.0988|0.1096|
|validation_v1|case_071|2|4|unit|15328|0.0130|0.2368|0.2632|
|validation_v1|case_071|2|4|chain_response|13443|0.0375|0.2095|0.2608|
|validation_v1|case_071|2|4|cut2_response|18919|0.0173|0.1616|0.1832|
|validation_v1|case_080|2|4|component|111314|0.0049|0.3124|0.3277|
|validation_v1|case_080|2|4|cut2|107695|0.0099|0.3811|0.3990|
|validation_v1|case_080|2|4|unit|148009|0.0201|0.5694|0.6133|
|validation_v1|case_080|2|4|chain_response|141957|0.0691|0.5341|0.6314|
|validation_v1|case_080|2|4|cut2_response|111314|0.0267|0.2230|0.2563|
|validation_v1|case_096|2|4|component|26984|0.0041|0.1190|0.1283|
|validation_v1|case_096|2|4|cut2|24913|0.0086|0.1990|0.2150|
|validation_v1|case_096|2|4|unit|48304|0.0147|0.3362|0.3675|
|validation_v1|case_096|2|4|chain_response|28559|0.0335|0.2646|0.3124|
|validation_v1|case_096|2|4|cut2_response|23073|0.0300|0.2143|0.2517|
|window_n2_v1|case_002|2|2|window8_response|126586|0.1215|0.3685|0.5044|
|window_n2_v1|case_044|2|2|window8_response|61687|0.0573|0.2714|0.3401|
|window_n2_v1|case_094|2|2|window8_response|52249|0.0314|0.1187|0.1578|
|window_n5_v1|case_002|2|5|window8_response|57102|0.1303|0.3030|0.4634|
|window_n5_v1|case_044|2|5|window8_response|99827|0.1145|0.2203|0.3481|
|window_n5_v1|case_094|2|5|window8_response|46832|0.0358|0.2180|0.2628|
|window_q3_v1|case_002|3|4|window8_response|66376|0.1268|0.3568|0.5079|
|window_q3_v1|case_010|3|4|window8_response|23909|0.0315|0.1374|0.1805|
|window_q3_v1|case_044|3|4|window8_response|84126|0.0661|0.3104|0.3954|
|window_q3_v1|case_069|3|4|window8_response|15711|0.0584|0.1948|0.2710|
|window_q3_v1|case_094|3|4|window8_response|39409|0.0328|0.2084|0.2544|
|window_refinement_v1|case_002|2|4|window2_response|66670|0.1272|0.3555|0.4976|
|window_refinement_v1|case_002|2|4|window8_response|66376|0.0734|0.3978|0.4912|
|window_refinement_v1|case_002|2|4|window32_response|68598|0.0784|0.3536|0.4518|
|window_refinement_v1|case_010|2|4|window2_response|25942|0.0417|0.1226|0.1711|
|window_refinement_v1|case_010|2|4|window8_response|25179|0.0310|0.1366|0.1774|
|window_refinement_v1|case_010|2|4|window32_response|35695|0.0941|0.1233|0.2244|
|window_refinement_v1|case_044|2|4|window2_response|76410|0.0757|0.2917|0.3806|
|window_refinement_v1|case_044|2|4|window8_response|89524|0.0755|0.2788|0.3704|
|window_refinement_v1|case_044|2|4|window32_response|105715|0.0741|0.2440|0.3333|
|window_refinement_v1|case_051|2|4|window2_response|178884|0.1194|0.2069|0.3388|
|window_refinement_v1|case_051|2|4|window8_response|178884|0.1125|0.2166|0.3416|
|window_refinement_v1|case_051|2|4|window32_response|178884|0.0768|0.2667|0.3582|
|window_refinement_v1|case_094|2|4|window2_response|41611|0.0342|0.1468|0.1894|
|window_refinement_v1|case_094|2|4|window8_response|41666|0.0422|0.1914|0.2417|
|window_refinement_v1|case_094|2|4|window32_response|41851|0.0303|0.1354|0.1770|
|window_refinement_v1|case_069|2|4|window2_response|17676|0.0695|0.3244|0.4144|
|window_refinement_v1|case_069|2|4|window8_response|17070|0.0867|0.2587|0.3628|
|window_refinement_v1|case_069|2|4|window32_response|21513|0.0691|0.2787|0.3624|
|window_validation_v1|case_019|2|4|window8_response|38451|0.0368|0.1575|0.2015|
|window_validation_v1|case_026|2|4|window8_response|46326|0.0364|0.1234|0.1672|
|window_validation_v1|case_037|2|4|window8_response|86131|0.0561|0.2384|0.3104|
|window_validation_v1|case_064|2|4|window8_response|16474|0.0563|0.1299|0.1958|
|window_validation_v1|case_071|2|4|window8_response|14182|0.0434|0.1795|0.2333|
|window_validation_v1|case_080|2|4|window8_response|141957|0.0728|0.3745|0.4645|
|window_validation_v1|case_096|2|4|window8_response|31047|0.0626|0.2037|0.2767|