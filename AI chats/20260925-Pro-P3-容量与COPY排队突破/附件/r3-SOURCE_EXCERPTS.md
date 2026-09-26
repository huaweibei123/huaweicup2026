# 冻结来源摘录
行号针对用户原附件，未改写源码；本文件便于交叉查阅，不是执行或修改官方代码。

## `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py`
SHA256 `eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0`
### L51–L74
```text
0051: def _prioritize_task_seq(graph, raw_seq, op_subgraph, subgraph_order):
0052:     """依照核内子图调度序分桶，桶内保留 Step1 顺序。
0053: 
0054:     Step1保证raw_seq覆盖完整且拓扑正确，稳定排序不改变覆盖。
0055:     选手的子图顺序是新约束，可能破坏拓扑，故只检查重排后的依赖顺序。
0056:     """
0057:     rank = {subgraph_id: index
0058:             for index, subgraph_id in enumerate(subgraph_order)}
0059:     fallback = len(rank)
0060:     seq = sorted(
0061:         raw_seq,
0062:         key=lambda op_id: rank.get(op_subgraph.get(op_id), fallback),
0063:     )
0064:     if not _check_topo(graph, seq):
0065:         raise SceneBEvaluationError(
0066:             'subgraph priority order violates an intra-core dependency')
0067:     return seq
0068: 
0069: def _build_scene_b_tasks(graph_json, plan, bandwidth, capacity):
0070:     """每核合并为一个 Task，仅对跨核边插入 DDR COPY 对。
0071: 
0072:     原图/方案由derive_multicore_plan校验，参数由evaluate_problem_3校验。
0073:     保留局部依赖、插入源/汇COPY不引入局部环；_prioritize_task_seq检查
0074:     子图重排新增的顺序约束，然后交给不重复校验输入的Step2/3。
```
### L141–L215
```text
0141:     for tensor_id in sorted(tensor_by_id):
0142:         tensor = tensor_by_id[tensor_id]
0143:         eligible_producers = sorted(op for op in producers.get(tensor_id, ())
0144:                                     if op in mapping)
0145:         eligible_consumers = sorted(op for op in consumers.get(tensor_id, ())
0146:                                     if op in mapping)
0147:         producer_cores = sorted({core_by_op[op] for op in eligible_producers})
0148:         consumer_cores = sorted({core_by_op[op] for op in eligible_consumers})
0149:         touched_cores = sorted(set(producer_cores) | set(consumer_cores))
0150:         if not touched_cores:
0151:             continue
0152:         local_tensor = dict(tensor)
0153:         if local_tensor.get('pos') == 'DDR':
0154:             local_tensor['pos'] = 'UB'
0155:         for core_id in touched_cores:
0156:             _append_tensor(tasks_data[core_id], local_tensor)
0157:             for op_id in eligible_producers:
0158:                 if core_by_op[op_id] == core_id:
0159:                     tasks_data[core_id]['edges'].append(
0160:                         {'source': op_id, 'target': tensor_id})
0161:             for op_id in eligible_consumers:
0162:                 if core_by_op[op_id] == core_id:
0163:                     tasks_data[core_id]['edges'].append(
0164:                         {'source': tensor_id, 'target': op_id})
0165: 
0166:         # 图输入：每个消费核各自从 DDR 读入一次。
0167:         if eligible_consumers and not eligible_producers:
0168:             for dst_core in consumer_cores:
0169:                 dst_ops = [op for op in eligible_consumers
0170:                            if core_by_op[op] == dst_core]
0171:                 dst_subgraph = min(
0172:                     (mapping[op] for op in dst_ops),
0173:                     key=lambda sg: core_orders[dst_core].index(sg))
0174:                 add_copy_in(dst_core, tensor_id, tensor['size'], dst_subgraph)
0175: 
0176:         # 图输出：保留对 DDR 的最终写回。
0177:         has_original_copy_out = any(
0178:             op_by_id[op_id].get('op') == 'COPY_OUT'
0179:             for op_id in consumers.get(tensor_id, ()) if op_id in op_by_id)
0180:         if eligible_producers and (has_original_copy_out or not eligible_consumers):
0181:             for src_core in producer_cores:
0182:                 src_ops = [op for op in eligible_producers
0183:                            if core_by_op[op] == src_core]
0184:                 src_subgraph = max(
0185:                     (mapping[op] for op in src_ops),
0186:                     key=lambda sg: core_orders[src_core].index(sg))
0187:                 add_copy_out(src_core, tensor_id, tensor['size'], src_subgraph)
0188: 
0189:         # 跨核 tensor：每个实际 source-core -> target-core 连接一对 COPY。
0190:         for src_core in producer_cores:
0191:             src_ops = [op for op in eligible_producers
0192:                        if core_by_op[op] == src_core]
0193:             src_subgraph = max(
0194:                 (mapping[op] for op in src_ops),
0195:                 key=lambda sg: core_orders[src_core].index(sg))
0196:             for dst_core in consumer_cores:
0197:                 if src_core == dst_core:
0198:                     continue
0199:                 dst_ops = [op for op in eligible_consumers
0200:                            if core_by_op[op] == dst_core]
0201:                 dst_subgraph = min(
0202:                     (mapping[op] for op in dst_ops),
0203:                     key=lambda sg: core_orders[dst_core].index(sg))
0204:                 ddr_tid = new_id()
0205:                 out_id, _ = add_copy_out(
0206:                     src_core, tensor_id, tensor['size'], src_subgraph, ddr_tid)
0207:                 in_id, _ = add_copy_in(
0208:                     dst_core, tensor_id, tensor['size'], dst_subgraph, ddr_tid)
0209:                 cross_links.append({
0210:                     'tensor_id': tensor_id, 'size': tensor['size'],
0211:                     'source_core': src_core, 'target_core': dst_core,
0212:                     'source_copy_out_id': out_id,
0213:                     'target_copy_in_id': in_id,
0214:                 })
0215:                 cross_task_traffic += tensor['size']
```
### L244–L289
```text
0244:     tasks = {}
0245:     for core_id in range(num_cores):
0246:         data = tasks_data[core_id]
0247:         graph = {
0248:             'ops': data['ops'],
0249:             'tensors': list(data['tensors'].values()),
0250:             'edges': data['edges'],
0251:         }
0252:         task_graph_copy_traffic += _copy_traffic_bytes(graph)
0253:         raw_seq = step1_schedule(graph) if graph['ops'] else []
0254:         seq = _prioritize_task_seq(
0255:             graph, raw_seq, data['op_subgraph'], data['subgraph_order'])
0256:         result2 = step2_spill_insertion(
0257:             graph, seq, capacity=capacity) if seq else {
0258:                 'new_ops': [], 'new_tensors': [], 'new_edges': [],
0259:                 'spill_records': [], 'seq_ext': []}
0260:         spill_copy_traffic += sum(
0261:             spill['size'] * (1 + int(spill['spill_out_copies_data']))
0262:             for spill in result2.get('spill_records', []))
0263:         ext_op_subgraph = dict(data['op_subgraph'])
0264:         for spill in result2.get('spill_records', []):
0265:             next_subgraph = ext_op_subgraph.get(spill.get('next_use_op'))
0266:             previous_subgraph = ext_op_subgraph.get(spill.get('prev_use_op'))
0267:             if spill['spill_out_id'] is not None:
0268:                 ext_op_subgraph[spill['spill_out_id']] = (
0269:                     previous_subgraph if previous_subgraph is not None
0270:                     else next_subgraph)
0271:             ext_op_subgraph[spill['spill_in_id']] = next_subgraph
0272:         ext_graph = _build_extended_graph(graph, result2)
0273:         prepared = prepare_step3_execution(
0274:             ext_graph, capacity=capacity, bandwidth=bandwidth)
0275:         prepared.update({
0276:             'task_id': core_id, 'core_id': core_id,
0277:             'subgraph_ids': data['subgraph_order'],
0278:             'op_subgraph': ext_op_subgraph,
0279:         })
0280:         tasks[core_id] = prepared
0281:     original_copy_traffic = _copy_traffic_bytes(graph_json)
0282:     partition_added_traffic = task_graph_copy_traffic - original_copy_traffic
0283:     traffic = {
0284:         'original_graph_copy_bytes': original_copy_traffic,
0285:         'scheduled_copy_bytes': task_graph_copy_traffic + spill_copy_traffic,
0286:         'added_copy_bytes': partition_added_traffic + spill_copy_traffic,
0287:         'partition_added_copy_bytes': partition_added_traffic,
0288:         'spill_added_copy_bytes': spill_copy_traffic,
0289:     }
```
### L352–L396
```text
0352:     def advance_pool_work(pool_name, now):
0353:         pool = bandwidth_pools[pool_name]
0354:         elapsed = now - pool['last_update']
0355:         while elapsed > 1e-9:
0356:             active = [item for item, work in pool['remaining'].items()
0357:                       if work > 1e-9]
0358:             if not active:
0359:                 break
0360:             min_work = min(pool['remaining'][item] for item in active)
0361:             finish_delta = min_work * len(active)
0362:             if finish_delta >= elapsed - 1e-9:
0363:                 share = elapsed / len(active)
0364:                 for item in active:
0365:                     pool['remaining'][item] = max(
0366:                         0.0, pool['remaining'][item] - share)
0367:                 break
0368:             for item in active:
0369:                 pool['remaining'][item] = max(
0370:                     0.0, pool['remaining'][item] - min_work)
0371:             elapsed -= finish_delta
0372:         pool['last_update'] = now
0373: 
0374:     def reschedule_pool(pool_name, now):
0375:         remaining = bandwidth_pools[pool_name]['remaining']
0376:         if not remaining:
0377:             return {}
0378:         ordered = sorted((max(0.0, work), item)
0379:                          for item, work in remaining.items())
0380:         projected, cursor, previous = {}, float(now), 0.0
0381:         active_count, i = len(ordered), 0
0382:         while i < len(ordered):
0383:             work = ordered[i][0]
0384:             cursor += (work - previous) * active_count
0385:             j = i
0386:             while j < len(ordered) and abs(ordered[j][0] - work) <= 1e-9:
0387:                 projected[ordered[j][1]] = int(math.ceil(cursor - 1e-9))
0388:                 j += 1
0389:             active_count -= j - i
0390:             previous, i = work, j
0391:         for item, end in projected.items():
0392:             op_end[item] = end
0393:         for executor_key, running in executors.items():
0394:             executors[executor_key] = [
0395:                 (item, projected.get(item, end)) for item, end in running]
0396:         return projected
```
### L416–L474
```text
0416:     def insert_cache(key_value, size, now, item):
0417:         nonlocal cache_used_bytes
0418:         if key_value is None or size > cache_capacity_bytes:
0419:             return
0420:         if key_value in cache_entries:
0421:             return
0422:         evicted = []
0423:         while cache_entries and cache_used_bytes + size > cache_capacity_bytes:
0424:             old_key, old_size = cache_entries.popitem(last=False)
0425:             cache_used_bytes -= old_size
0426:             evicted.append(old_key)
0427:         cache_entries[key_value] = size
0428:         cache_used_bytes += size
0429:         cache_events.append({
0430:             'time': now, 'event': 'insert', 'tensor_id': key_value,
0431:             'size_bytes': size, 'used_bytes': cache_used_bytes,
0432:             'evicted_tensor_ids': evicted,
0433:             'core_id': item[0], 'op_id': item[1],
0434:         })
0435: 
0436:     def external_release(item):
0437:         preds = external_preds.get(item, ())
0438:         if any(op_status.get(pred) != 'done' for pred in preds):
0439:             return None
0440:         return max((op_end[pred] + cross_core_copy_delay for pred in preds),
0441:                    default=0)
0442: 
0443:     def queue_if_ready(item, now):
0444:         if op_status[item] != 'pending' or pred_remaining[item] != 0:
0445:             return
0446:         core_id, op_id = item
0447:         task = tasks[core_id]
0448:         pipe = op_pipe(task['op_by_id'][op_id])
0449:         order = task['pipe_ops'][pipe]
0450:         cursor = task['pipe_cursor'][pipe]
0451:         if cursor >= len(order) or order[cursor] != op_id:
0452:             return
0453:         release = external_release(item)
0454:         if release is None:
0455:             return
0456:         if release > now:
0457:             if item not in release_scheduled:
0458:                 heapq.heappush(external_release_heap, (release, item))
0459:                 release_scheduled.add(item)
0460:             return
0461:         release_scheduled.discard(item)
0462:         op_status[item] = 'ready'
0463:         heapq.heappush(issue_queues[(core_id, pipe)],
0464:                        (task['seq_pos'][op_id], item))
0465: 
0466:     def advance_pipe(core_id, op_id, now):
0467:         """完成 Pipe 队首操作，然后尝试唤醒下一操作。"""
0468:         task = tasks[core_id]
0469:         pipe = op_pipe(task['op_by_id'][op_id])
0470:         cursor = task['pipe_cursor'][pipe]
0471:         order = task['pipe_ops'][pipe]
0472:         task['pipe_cursor'][pipe] += 1
0473:         if cursor + 1 < len(order):
0474:             queue_if_ready(key(core_id, order[cursor + 1]), now)
```
### L539–L581
```text
0539:                         cache_key, transfer_bytes = copy_tensor_info(task, op_id)
0540:                         eligible = (cache_eligible(op['op'])
0541:                                     and cache_key is not None
0542:                                     and transfer_bytes > 0)
0543:                         cache_hit = eligible and cache_key in cache_entries
0544:                         effective_bandwidth = (
0545:                             cache_bandwidth_bytes_per_cycle
0546:                             if cache_hit else bandwidth)
0547:                         duration = _op_duration(
0548:                             op, task['in_tids'], task['out_tids'],
0549:                             task['tensor_by_id'], effective_bandwidth)
0550:                         op_status[item] = 'running'
0551:                         op_start[item] = now
0552:                         op_end[item] = now + duration
0553:                         executors[executor_key].append((item, op_end[item]))
0554:                         if eligible:
0555:                             cache_stats['copy_in_{}'.format(
0556:                                 'hits' if cache_hit else 'misses')] += 1
0557:                             cache_stats['{}_bytes'.format(
0558:                                 'hit' if cache_hit else 'miss')] += transfer_bytes
0559:                             op_cache_key[item] = cache_key
0560:                             op_memory_path[item] = (
0561:                                 'CACHE_READ' if cache_hit else 'DDR')
0562:                             cache_events.append({
0563:                                 'time': now,
0564:                                 'event': 'hit' if cache_hit else 'miss',
0565:                                 'tensor_id': cache_key,
0566:                                 'size_bytes': transfer_bytes,
0567:                                 'core_id': core_id, 'op_id': op_id,
0568:                                 'op': op['op'],
0569:                             })
0570:                         if cache_hit:
0571:                             pool_name = 'CACHE_READ'
0572:                             advance_pool_work(pool_name, now)
0573:                             bandwidth_pools[pool_name]['remaining'][item] = float(duration)
0574:                             reschedule_pool(pool_name, now)
0575:                         elif _uses_ddr_bandwidth(
0576:                                 op, task['in_tids'], task['out_tids'],
0577:                                 task['tensor_by_id']):
0578:                             op_memory_path.setdefault(item, 'DDR')
0579:                             advance_pool_work('DDR', now)
0580:                             bandwidth_pools['DDR']['remaining'][item] = float(duration)
0581:                             reschedule_pool('DDR', now)
```
### L675–L714
```text
0675: 
0676:     total_hits = cache_stats['copy_in_hits']
0677:     total_accesses = total_hits + cache_stats['copy_in_misses']
0678:     cache_stats['hits'] = total_hits
0679:     cache_stats['accesses'] = total_accesses
0680:     total_bytes = cache_stats['hit_bytes'] + cache_stats['miss_bytes']
0681:     cache_stats['hit_rate'] = (
0682:         cache_stats['hit_bytes'] / total_bytes if total_bytes else 0.0)
0683: 
0684:     result = {
0685:         'scene': 'B',
0686:         'problem': 3,
0687:         'cache_mode': 'read_only',
0688:         'makespan': max(op_end.values(), default=0),
0689:         'num_cores': num_cores,
0690:         'bandwidth_bytes_per_cycle': bandwidth,
0691:         'cache_capacity_bytes': cache_capacity_bytes,
0692:         'cache_bandwidth_bytes_per_cycle': cache_bandwidth_bytes_per_cycle,
0693:         'cache_stats': cache_stats,
0694:         'cache_events': cache_events,
0695:         'cache_final_entries': [
0696:             {'tensor_id': cache_key, 'size_bytes': size}
0697:             for cache_key, size in cache_entries.items()
0698:         ],
0699:         'cache_used_bytes_final': cache_used_bytes,
0700:         'capacity_bytes': dict(capacity),
0701:         'memory_peak_by_core': {
0702:             core_id: dict(task['step3']['memory_peak'])
0703:             for core_id, task in tasks.items()
0704:         },
0705:         'step3_by_core': {
0706:             core_id: {
0707:                 'local_makespan': task['step3']['makespan'],
0708:                 'memory_dependency_count': len(
0709:                     task['step3']['memory_dependencies']),
0710:                 'pipe_op_counts': {
0711:                     pipe: len(order) for pipe, order in task['pipe_ops'].items()
0712:                 },
0713:             }
0714:             for core_id, task in tasks.items()
```

## `data/raw/a/official/code/schedule_step2.py`
SHA256 `2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3`
### L157–L202
```text
0157:     def trigger_one_spill(t, T, current_step_tids):
0158:         """在 step t 触发一次 Belady SPILL, 返回 (victim_tid, freed_size) 或 None.
0159:         排除当前 step t 正在使用的 buffer (即 victim.uses 含 step t 的 use) —
0160:         否则 victim 仍在被 op 读, SPILL_OUT 只能排在 op 之后, 造成 op 自身瞬时超 capacity.
0161:         """
0162:         # 只在 next_use 不是 None (即还有 future use) 的 candidate 中选
0163:         finite = [
0164:             (nu, ui, tid)
0165:             for tid, (nu, ui) in type_active[T].items()
0166:             if nu is not None
0167:         ]
0168:         # 排除当前 step 正在使用的 buffer (uses 列表里有 use 的 step == t)
0169:         finite = [item for item in finite if item[2] not in current_step_tids]
0170:         if not finite:
0171:             return None
0172:         finite.sort(key=lambda x: -x[0])  # max next_use first
0173:         nu, ui, victim_tid = finite[0]
0174:         info = tensor_lifecycle[victim_tid]
0175:         v_size = info['size']
0176: 
0177:         # prev_use / next_use 的取值依据:
0178:         #   active[T] 里存的是 (next_use, use_index)，use_index 表示 victim
0179:         #   已经被 use 过的次数。溢出检查发生在 step t 的 use 处理之后，因此
0180:         #   ui 已是包含 step t 在内的已处理次数。
0181:         #   于是: 下一次 use = uses[ui] (存在且非 None，见上面的过滤)，
0182:         #         上一次 use = uses[ui-1] (ui > 0 时)，否则退回到首次 alloc 的 step。
0183:         prev_use_step = info['uses'][ui - 1][0] if ui > 0 else info['first']
0184:         next_use_step = nu  # next use, guaranteed not None
0185:         prev_use_op = info['uses'][ui - 1][1] if ui > 0 else None
0186:         next_use_op = info['uses'][ui][1]  # uses[ui] is next use, op is index 1
0187: 
0188:         # 从 active 移除 victim
0189:         type_active[T].pop(victim_tid)
0190:         type_resid[T] -= v_size
0191: 
0192:         pending_spills.append({
0193:             'out_after_step': prev_use_step,
0194:             'in_before_step': next_use_step,
0195:             'tid': victim_tid,
0196:             'pos': T,
0197:             'size': v_size,
0198:             'prev_use_op': prev_use_op,
0199:             'next_use_op': next_use_op,
0200:         })
0201:         spill_in_at_step[next_use_step].append((victim_tid, ui))
0202:         return victim_tid, v_size
```
### L224–L289
```text
0224:         # 1. 处理本步 use 的 alloc / next_use 更新，但延迟 last-use free。
0225:         #    物理语义必须是 alloc -> 容量检查/SPILL -> execute -> free；否则会漏掉
0226:         #    “输出已经申请、末次输入尚未释放”的瞬态峰值。
0227:         release_after_execute = []
0228:         for tid, idx in uses_at_step[t]:
0229:             info = tensor_lifecycle[tid]
0230:             uses = info['uses']
0231:             T = info['pos']
0232:             if idx == 0:
0233:                 # First use (producer) = 申请内存
0234:                 next_nu = uses[1][0] if 1 < len(uses) else None
0235:                 type_active[T][tid] = (next_nu, 1)
0236:                 type_resid[T] += info['size']
0237:             elif idx < len(uses) - 1:
0238:                 # Mid use: update next_use。对已有 key 赋值不改变 dict 插入顺序。
0239:                 new_nu = uses[idx + 1][0]
0240:                 active_item = type_active[T].get(tid)
0241:                 if active_item is not None:
0242:                     _, used_count = active_item
0243:                     type_active[T][tid] = (new_nu, used_count + 1)
0244:             # k=1 的 tensor 同时是 first use 和 last use：先 alloc 参与瞬态容量
0245:             # 检查，执行完成后再释放。普通末次输入同理延迟到容量检查之后释放。
0246:             if idx == len(uses) - 1:
0247:                 release_after_execute.append((T, tid))
0248: 
0249:         # 1.5 alloc 后、execute/free 前统一 Belady SPILL。
0250:         #     trigger_one_spill 会排除当前 op 使用的所有 tensor，因此只会换出当前
0251:         #     op 不需要的驻留项。最终生成的 SPILL_OUT 锚定在 victim 上次 use 之后，
0252:         #     在扩展序列中物理发生于当前 op 之前。
0253:         for T, C in capacity.items():
0254:             while get_resid(T) > C:
0255:                 resid_now = get_resid(T)
0256:                 overflow_log.append({'step': t, 'type': T, 'resid': resid_now, 'capacity': C})
0257:                 result = trigger_one_spill(t, T, current_step_tids[T])
0258:                 if result is None:
0259:                     current_tids = sorted(current_step_tids[T].intersection(type_active[T]))
0260:                     active_desc = sorted(
0261:                         (tid, tensor_lifecycle[tid]['size'], nu)
0262:                         for tid, (nu, _) in type_active[T].items()
0263:                     )
0264:                     message = (
0265:                         '[STEP2 ERROR] no spill victim: step={step} op={op} type={type_} '
0266:                         'alloc_resid={resid} capacity={capacity} current_tids={current} '
0267:                         'active(tid,size,next_use)={active}'
0268:                     ).format(
0269:                         step=t, op=op, type_=T, resid=resid_now, capacity=C,
0270:                         current=current_tids, active=active_desc,
0271:                     )
0272:                     emit_error(message)
0273:                     raise Step2SchedulingError(message)
0274: 
0275:             # 这是当前 op 真正的 alloc 后峰值；此时输入和输出都仍然驻留。
0276:             resid_after_alloc = get_resid(T)
0277:             if resid_after_alloc > C:
0278:                 # while 的后置断言，防止未来修改重新引入静默超限。
0279:                 message = (
0280:                     '[STEP2 ERROR] alloc peak still exceeds capacity after spill: '
0281:                     'step={step} op={op} type={type_} resid={resid} capacity={capacity}'
0282:                 ).format(step=t, op=op, type_=T, resid=resid_after_alloc, capacity=C)
0283:                 emit_error(message)
0284:                 raise Step2SchedulingError(message)
0285: 
0286:         # 2. 当前 op 执行完成后，释放本步末次使用的输入/输出。
0287:         for T, tid in release_after_execute:
0288:             if type_active[T].pop(tid, None) is not None:
0289:                 type_resid[T] -= tensor_lifecycle[tid]['size']
```
### L304–L383
```text
0304:     backing_by_tid = dict(original_copy_in_backing)
0305:     backing_origin = {
0306:         tid: 'original_copy_in' for tid in original_copy_in_backing
0307:     }
0308:     current_incarnation = {
0309:         tid: tid for tid in tensor_lifecycle
0310:     }
0311:     incarnation_version = defaultdict(int)
0312:     spill_records_by_tid = defaultdict(list)
0313: 
0314:     for sp in pending_spills:
0315:         logical_tid = sp['tid']
0316:         from_tid = current_incarnation[logical_tid]
0317:         spill_out_copies_data = sp['tid'] not in backing_by_tid
0318:         spill_out_id = None
0319:         if spill_out_copies_data:
0320:             spill_out_id = next_id
0321:             next_id += 1
0322:         spill_in_id = next_id
0323:         next_id += 1
0324:         if spill_out_copies_data:
0325:             backing_tid = next_id
0326:             next_id += 1
0327:             backing_by_tid[sp['tid']] = backing_tid
0328:             backing_origin[sp['tid']] = 'spill_out'
0329:             new_tensors_list.append({
0330:                 'id': backing_tid,
0331:                 'pos': 'DDR',
0332:                 'size': sp['size'],
0333:             })
0334:             backing_source = 'new_spill_out'
0335:         else:
0336:             backing_tid = backing_by_tid[sp['tid']]
0337:             backing_source = (
0338:                 'original_copy_in'
0339:                 if backing_origin[sp['tid']] == 'original_copy_in'
0340:                 else 'reused_spill_out'
0341:             )
0342: 
0343:         incarnation_version[logical_tid] += 1
0344:         to_tid = next_id
0345:         next_id += 1
0346:         current_incarnation[logical_tid] = to_tid
0347:         new_tensors_list.append({
0348:             'id': to_tid,
0349:             'logical_tid': logical_tid,
0350:             'version': incarnation_version[logical_tid],
0351:             'pos': sp['pos'],
0352:             'size': sp['size'],
0353:         })
0354: 
0355:         if spill_out_copies_data:
0356:             new_ops_list.append({
0357:                 'id': spill_out_id,
0358:                 'op': 'COPY_OUT',
0359:                 'pipe': 'PIPE_MTE3',
0360:                 'cycles': max(1, sp['size'] // 64),
0361:                 'transfer_bytes': sp['size'],
0362:                 'spill_logical_tid': logical_tid,
0363:             })
0364:         new_ops_list.append({
0365:             'id': spill_in_id,
0366:             'op': 'COPY_IN',
0367:             'pipe': 'PIPE_MTE2',
0368:             'cycles': max(1, sp['size'] // 64),
0369:             'transfer_bytes': sp['size'],
0370:             'spill_logical_tid': logical_tid,
0371:         })
0372: 
0373:         # 数据边直接表达物理 incarnation 的生产与消费。COPY_OUT 也是 from_tid
0374:         # 的一个消费者；Step3 的引用计数会等所有消费者结束后再释放 from_tid。
0375:         if spill_out_copies_data:
0376:             new_edges.append((from_tid, spill_out_id))
0377:             new_edges.append((spill_out_id, backing_tid))
0378:         new_edges.append((backing_tid, spill_in_id))
0379:         new_edges.append((spill_in_id, to_tid))
0380: 
0381:         if spill_out_id is not None:
0382:             insert_after[sp['out_after_step']].append(spill_out_id)
0383:         insert_before[sp['in_before_step']].append(spill_in_id)
```
### L443–L456
```text
0443:     # Build seq_ext
0444:     seq_ext = []
0445:     for i, op in enumerate(seq):
0446:         # 'after (i-1)' 事件
0447:         if i > 0:
0448:             for sid in insert_after[i - 1]:
0449:                 seq_ext.append(sid)
0450:         # 'before i' 事件
0451:         for sid in insert_before[i]:
0452:             seq_ext.append(sid)
0453:         seq_ext.append(op)
0454:     # 'after (n-1)' 事件 (loop 结束后)
0455:     for sid in insert_after[n - 1]:
0456:         seq_ext.append(sid)
```

## `data/raw/a/official/code/schedule_step3.py`
SHA256 `50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a`
### L74–L92
```text
0074: def _op_duration(op, in_tids, out_tids, tensor_by_id, bandwidth):
0075:     """普通 op 使用 cycles；COPY op 优先按搬运 tensor 大小换算。"""
0076:     op_type = op['op']
0077:     if op_type in ('COPY_IN', 'COPY_OUT'):
0078:         tids = out_tids[op['id']] if op_type == 'COPY_IN' else in_tids[op['id']]
0079:         sizes = [tensor_by_id[tid]['size'] for tid in tids if tid in tensor_by_id]
0080:         if sizes:
0081:             return max(1, math.ceil(sum(sizes) / bandwidth))
0082:     return max(1, op.get('cycles', 1))
0083: 
0084: def _uses_ddr_bandwidth(op, in_tids, out_tids, tensor_by_id):
0085:     """只有端点包含 DDR 的 COPY 才进入共享 DDR 带宽池。"""
0086:     if op['op'] not in ('COPY_IN', 'COPY_OUT'):
0087:         return False
0088:     tids = in_tids[op['id']] + out_tids[op['id']]
0089:     return any(
0090:         tid in tensor_by_id and tensor_by_id[tid].get('pos') == 'DDR'
0091:         for tid in tids
0092:     )
```
### L144–L178
```text
0144:     def add_free_credit(tid):
0145:         tensor = tensor_by_id[tid]
0146:         consumers = sorted(tensor_consumers.get(tid, ()))
0147:         producers = sorted(tensor_producers.get(tid, ()))
0148:         # 有读者时必须等全部读者结束（WAR）；无读者的死输出至少要等旧写完成
0149:         # 才能复用同一额度（WAW）。
0150:         sources = consumers if consumers else producers
0151:         free_credits[tensor['pos']].append({
0152:             'bytes': tensor['size'],
0153:             'sources': tuple(sources),
0154:             'tid': tid,
0155:             'kind': 'WAR' if consumers else 'WAW',
0156:         })
0157: 
0158:     def consume_free_credit(tid, producer_op):
0159:         tensor = tensor_by_id[tid]
0160:         pos = tensor['pos']
0161:         remaining = tensor['size']
0162:         credits = free_credits[pos]
0163:         while remaining > 0 and credits:
0164:             credit = credits[0]
0165:             taken = min(remaining, credit['bytes'])
0166:             if credit['sources']:
0167:                 for source_op in credit['sources']:
0168:                     if source_op == producer_op:
0169:                         continue
0170:                     part = memory_dependency_parts[(source_op, producer_op)]
0171:                     part['bytes'] += taken
0172:                     part['tensor_ids'].add(credit['tid'])
0173:                     part['kinds'].add(credit['kind'])
0174:                     part['positions'].add(pos)
0175:             credit['bytes'] -= taken
0176:             remaining -= taken
0177:             if credit['bytes'] == 0:
0178:                 credits.pop(0)
```
### L217–L237
```text
0217:     # 没有片上 producer 的 tensor 视为图开始前已驻留。
0218:     for tid in sorted(managed_tensors):
0219:         if not tensor_producers.get(tid) and tensor_consumers.get(tid):
0220:             allocate_tensor(tid, 0, kind='initial_alloc')
0221:     initial_overflow = {
0222:         pos: memory_used[pos] for pos in capacity
0223:         if memory_used[pos] > capacity[pos]
0224:     }
0225:     if initial_overflow:
0226:         message = (
0227:             '[STEP3 ERROR] initial resident tensors exceed capacity: used={} capacity={}'
0228:         ).format(initial_overflow, capacity)
0229:         emit_error(message)
0230:         raise Step3SchedulingError(message)
0231:     for pos in capacity:
0232:         unused = capacity[pos] - memory_used[pos]
0233:         if unused:
0234:             free_credits[pos].append({
0235:                 'bytes': unused, 'sources': (), 'tid': None,
0236:                 'kind': 'VIRGIN',
0237:             })
```
### L281–L296
```text
0281:     seq_pos = {op_id: i for i, op_id in enumerate(seq)}
0282:     # seq_ext 是 Step2 已验证的确定性拓扑序。Step3 在每条 Pipe 上使用它的
0283:     # 投影作为固定发射顺序；这样多核阶段加入跨核 COPY 等待后，仍与核内
0284:     # 调度结果保持同序，不会因局部 ready 时刻不同而重新排列 Pipe。
0285:     planned_pipe_orders = {pipe: [] for pipe in PIPES}
0286:     for op_id in seq:
0287:         planned_pipe_orders[op_pipe(op_by_id[op_id])].append(op_id)
0288:     pipe_cursor = {pipe: 0 for pipe in PIPES}
0289:     allocation_order = [
0290:         op_id for op_id in seq
0291:         if any(tid in managed_tensors for tid in out_tids[op_id])
0292:     ]
0293:     allocation_rank = {
0294:         op_id: rank for rank, op_id in enumerate(allocation_order)
0295:     }
0296:     next_allocation_rank = 0
```
### L595–L609
```text
0595:     # 多核模拟只认图依赖。把虚拟额度复用关系写成直接 op->op 边，并保留
0596:     # metadata 便于复核；_build_graph_views 会与普通数据依赖统一解析。
0597:     execution_graph = deepcopy(ext_graph)
0598:     existing_edges = {
0599:         (edge['source'], edge['target']) for edge in execution_graph['edges']
0600:     }
0601:     for dep in memory_dependencies:
0602:         pair = (dep['source'], dep['target'])
0603:         if pair in existing_edges:
0604:             continue
0605:         execution_graph['edges'].append({
0606:             'source': dep['source'], 'target': dep['target'],
0607:             'dependency': 'MEMORY_REUSE',
0608:         })
0609:         existing_edges.add(pair)
```

## `data/raw/a/official/code/multicore_cut_evaluate_problem_1.py`
SHA256 `2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f`
### L123–L175
```text
0123:             local_consumers = consumers.get(tensor_id, set()) & task_op_ids
0124:             eligible_producers = {op for op in producers.get(tensor_id, ()) if op in mapping}
0125:             eligible_consumers = {op for op in consumers.get(tensor_id, ()) if op in mapping}
0126:             has_original_copy_out = any(
0127:                 op_by_id[op_id].get('op') == 'COPY_OUT'
0128:                 for op_id in consumers.get(tensor_id, ())
0129:                 if op_id in op_by_id)
0130:             input_boundary = bool(local_consumers) and not bool(local_producers)
0131:             output_boundary = bool(local_producers) and (
0132:                 has_original_copy_out or not eligible_consumers
0133:                 or bool(eligible_consumers - task_op_ids))
0134: 
0135:             # Task 内 Tensor 必须在私有缓存；原 DDR Tensor 仅作为边界副本。
0136:             if tensor.get('pos') == 'DDR':
0137:                 tensor['pos'] = 'UB'
0138:             tensors.append(tensor)
0139:             local_tensor_ids.add(tensor_id)
0140:             for producer_id in sorted(local_producers):
0141:                 edges.append({'source': producer_id, 'target': tensor_id})
0142:             for consumer_id in sorted(local_consumers):
0143:                 edges.append({'source': tensor_id, 'target': consumer_id})
0144: 
0145:             if input_boundary:
0146:                 ddr_id, copy_id = new_boundary_ids()
0147:                 tensors.append({'id': ddr_id, 'pos': 'DDR', 'size': tensor['size']})
0148:                 ops.append({'id': copy_id, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2',
0149:                             'cycles': max(1, math.ceil(tensor['size'] / bandwidth))})
0150:                 edges.extend([
0151:                     {'source': ddr_id, 'target': copy_id},
0152:                     {'source': copy_id, 'target': tensor_id},
0153:                 ])
0154:             if output_boundary:
0155:                 ddr_id, copy_id = new_boundary_ids()
0156:                 tensors.append({'id': ddr_id, 'pos': 'DDR', 'size': tensor['size']})
0157:                 ops.append({'id': copy_id, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3',
0158:                             'cycles': max(1, math.ceil(tensor['size'] / bandwidth))})
0159:                 edges.extend([
0160:                     {'source': tensor_id, 'target': copy_id},
0161:                     {'source': copy_id, 'target': ddr_id},
0162:                 ])
0163:                 remote_consumer_tasks = {
0164:                     mapping[op_id] for op_id in eligible_consumers
0165:                     if mapping[op_id] != task_id
0166:                 }
0167:                 cross_task_traffic += tensor['size'] * len(remote_consumer_tasks)
0168: 
0169:         for edge in direct_edges:
0170:             if edge['source'] in task_op_ids and edge['target'] in task_op_ids:
0171:                 edges.append(dict(edge))
0172: 
0173:         graph = {'ops': ops, 'tensors': tensors, 'edges': edges}
0174:         task_graph_copy_traffic += _copy_traffic_bytes(graph)
0175:         seq = step1_schedule(graph)
```
### L317–L347
```text
0317: 
0318:     def task_release_time(task_id):
0319:         task = tasks[task_id]
0320:         core_id = task['core_id']
0321:         if any(task_status[pred] != 'done' for pred in task['pred_tasks']):
0322:             return None
0323:         release = 0
0324:         if core_previous_end[core_id] is not None:
0325:             release = core_previous_end[core_id] + same_core_wait
0326:         for pred in task['pred_tasks']:
0327:             if tasks[pred]['core_id'] != core_id:
0328:                 release = max(release, task_end[pred] + cross_core_wait)
0329:         return release
0330: 
0331:     def activate_ready_tasks(now):
0332:         changed = False
0333:         for core_id in range(num_cores):
0334:             if core_active_task[core_id] is not None:
0335:                 continue
0336:             order = core_orders.get(core_id, [])
0337:             if core_index[core_id] >= len(order):
0338:                 continue
0339:             task_id = order[core_index[core_id]]
0340:             release = task_release_time(task_id)
0341:             if release is not None and release <= now:
0342:                 activate_task(task_id, now)
0343:                 changed = True
0344:         return changed
0345: 
0346:     def retire(now):
0347:         advance_ddr_work(now)
```

## `results/a/q3-nikolastarx/pro-r08-independent-20260925/REVIEW.md`
SHA256 `d3b0a213b7d6d44f668b517bf131442e4d4da0a4035fdc93d8cd5c6c657bbf99`
### L1–L25
```text
0001: # R8 两条条件命题的独立静态审阅（2026-09-25）
0002: 
0003: 范围：只读 `FINAL-r08-bc5e4db8.rendered.txt`、其 `supplement.json`、冻结 P3/Step2/Step3 源码及 `config.txt`。没有运行构造器、求解器、官方评价函数或附件；071/069 的数值均是 Pro 报告，**不是本机复现**。
0004: 
0005: ## 1. 计算增强 DAG 的两次跨核界：**需收紧后成立**
0006: 
0007: 在同一固定 owner、同一原计算图和同一逐 M/V pipe FIFO 上，令 `L0` 为跨核边权设零的最长路，`Lδ` 为每条跨核原计算依赖增加同一个非负 `δ` 后的最长路。若每条**原计算边和 FIFO 边**都不降低 `S < P < A < O` 阶段，所有私有流完整同核，S 的每个原计算弱连通分量完整同核，且仅有 `S → 私有` 与跨流 `P(K/V) → A` 两类跨核原计算边，那么路径至多经过一次 `S → 私有`、一次 `P → A`；故跨核边数 ≤2，逐路径加权并取最大值得 `Lδ ≤ L0 + 2δ`。同阶段 S 内边因弱连通分量同核而不跨核，私有流内部边也不跨核。这是严格的**计算图**界。
0008: 
0009: R8 的“四阶段 FIFO 单调”只约束排出的 M/V 顺序；还必须静态检查**每条原计算依赖**也阶段不回退、无未分类原计算 op、无额外跨流/跨核直接 op-op 边，并且加入两条 pipe FIFO 后全图仍是 DAG。缺少原边阶段检查时，可有 `S₀→P₁→A₂→P₂→A₃` 路径，其中三个跨核边依次是 `S₀→P₁`、`P₁→A₂`、`P₂→A₃`，`A₂→P₂` 为同流同核的阶段回退边。让 `A₂` 与 `P₂` 分属 M/V pipe 即可避免单 pipe FIFO 自动封住这个例子。若“单次共享前沿”已被实现为严格的全原边阶段检查，则此反例会被拒绝；仅凭文字中的跨流边型不能拒绝。
0010: 
0011: 还应限定 `L0` 与 `Lδ` 取**同一增强 DAG**；原图 FIFO/owner 改变后不能把旧方案的 `L0` 代入。P3 实际在 `_build_scene_b_tasks` 建每核 Task 与跨核 COPY（`multicore_cut_evaluate_problem_3.py:69-74,189-215,217-241`），再在 `evaluate_problem_3` 加 COPY 外部前驱和 Cache/DDR 资源（同文件 `:307-349`）。所以该界不约束官方 Makespan，不能把 δ 简单当成 COPY 完整耗时。
0012: 
0013: ## 2. 全支持容量证书：**按 Task 物理支持集收紧后成立；按“原计算 touched tensor”字面不成立**
0014: 
0015: Step2 对每个 Task 的**全部非 DDR tensor ID**从所有 op-tensor 边生成 lifecycle（`schedule_step2.py:39-67,109-129`）；先分配本步输出、暂不释放末次输入，然后检查超容才 spill（`:224-257`），因此若该 Task 每池所有会出现于 lifecycle 的不同物理 ID 大小总和 ≤ 对应容量，任一瞬间驻留量都是此全集的子集，Step2 无 spill。这也覆盖 alloc-before-free 瞬态。无 spill 时，Step2 不生成新的片上 incarnation（`:314-353`）。
0016: 
0017: “原计算 touched”必须在**P3 重建之后**转成上述全集：P3 每核建一个 Task，原 DDR tensor 的本地视图改为 UB（`multicore_cut_evaluate_problem_3.py:69-94,141-156`）；图输入、跨核 tensor 边和图输出会添 COPY 与 DDR backing（`:166-215`）；跨核直接 op-op 边另造一个新的 UB 桥 tensor（`:217-241`）。若只累计原图 tensor，这个桥不在集合里：例如原 UB touched 总量恰等于容量，另有一条正大小跨核直接边，P3 加桥后即超容。故 guard 要求无这种直接跨核边，或把桥也逐 Task/逐池计入。原图 COPY op 所接的本地片上 tensor、图输入/输出与每核副本也需计入；“compute”若仅指 M/V op，不能保证覆盖它们。DDR backing 不占 L1/UB，但原 DDR 视图改成的 UB 要计。每个 Task 及同名 logical tensor 的每份物理副本分别计，不能跨 Task 以 logical ID 去重。当前固定配置为 `L1=524288, UB=131072` B（`data/raw/a/official/data/config.txt`）；R8 报的静态数值仍需按此映射独立核对。
0018: 
0019: Step3 的无 `MEMORY_REUSE` 结论还需要：每个片上物理 ID 在本 Task 最多分配一次（唯一 producer，且不由重复写/再生导致二次分配），Step2 确实无 spill，以及总支持集覆盖 Step3 管理的全部会分配 ID。Step3 先把无 producer 的已消费 tensor 作为初始驻留（`schedule_step3.py:217-230`），把剩余容量作为队首 `VIRGIN` credit（`:231-237`）；释放的 WAR/WAW credit 只追加队尾（`:144-156`），分配从队首取，只有取到带 source 的 credit 才记录依赖（`:158-178`）。在“所有物理 ID 首次分配大小总和 ≤ 容量”下，初始 `VIRGIN` 足以覆盖其余 ID 的全部首次分配，所以不会读到回收 credit；`memory_dependencies` 为空，因而不会添 `MEMORY_REUSE` 边（`:583-609`）。若仅以同 logical ID 去重，或 spill 产生多个 incarnation，这一推论失效。Step3 本身以 `tid`/`pos` 管理容量，不按 logical ID 合并（`:124-133,185-215`）。
0020: 
0021: ## 下一最小零 E0 guard
0022: 
0023: 1. 对每条原计算边与 M/V FIFO 边核对阶段不下降；校验全部原 op/边只落入四阶段和准许的跨流类型、S 分量及每条私有流 owner 一致、计算增强图无环。用同一图独立计算最长路与逐路径跨核边上界。
0024: 2. 只运行 P3 的 Task 构造前静态映射或等价纯构造检查：逐 Task 枚举**实际**本地非 DDR tensor ID、池与大小，包括 UB 桥、原 DDR→UB、本地 COPY 端点；按 ID 去重求和并核对容量。不得把 `logical_tid` 当物理去重键。
0025: 3. 核对每个被分配 ID 唯一 producer/一次分配，且无 Step2 spill/重命名；若以后做正式验证，再比对 `spill_records`、`memory_dependencies` 和准备后的 Task tensor 清单。静态 guard 通过仅支持进入有界机制验证，不代表官方 Makespan 改善。
```

## `results/a/q3-nikolastarx/query-flow-static-repair-20260925/REPORT.md`
SHA256 `6a5e5b2b2124392ac76a0e340642d75ac8a847f747583cf1af8fb99f9241a804`
### L1–L12
```text
0001: # R8 修正后静态结果
0002: 
0003: 冻结构造源码 `b1eb32aca82436b20cc82da8c86d4301ef00cfb1`；原始071、069/config/全部q3源哈希见run/summary.json。两次construct、两次独立pipe_bound，全部完成；0 Task/Step/E0/E1/E2/VM，0重试，诊断墙钟0.198227秒（非完整solver时延）。
0004: 
0005: |5核图|旧官方计划的计算FIFO+500下界|新候选同口径下界|新候选同词零延迟界|最大L1/UB支持B|
0006: |---|---:|---:|---:|---:|
0007: |071|5441|4538|4215|108672 / 83718|
0008: |069|6232|5846|5846|131968 / 124806|
0009: 
0010: 新旧下界不同并不证明官方M下降。新计划每条增强路径≤2跨核，原计算singleton完整覆盖；原max/sum树不改，K/V producer恰一次。071 5流10row/1状态，069 6流12row/15规范配对中14容量证书拒绝，只有一个状态通过。强容量拒绝不等于其余配对官方非法。与Pro模型数值和全支持最大量相同；本地P/O分类为071 85/90、069 102/108，与作者80/95和96/114不同：本实现把不依赖row、只供该流输出的上游计算归P。原边均阶段不回退，两次跨核证明仍适用。Pro附件代码/计划字节未取得，不宣称逐字复现作者实现。
0011: 
0012: 原071候选plan SHA `b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136`。本轮仅此计划申请一次P3，严格官方M改善且所有准备guard通过后一次同计划P2；069不申请评分。此前失败首阶段账仍单独保留，合计3真实construct、2bound、0官方，未重置旧预算。
```

## `results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/REPORT.md`
SHA256 `e4b0cbae7da64928f075c6d7d0ed7380beb8f9413cbce4a67a1c41e36febf90e`
### L1–L15
```text
0001: # Q3 partial-preload Linux mechanism receipt
0002: 
0003: This receipt contains exactly three new official E0 attempts for case 044, five cores: candidate P3, same-plan candidate P2, and control-plan P2. It is a mechanism experiment, not a full-500 result.
0004: 
0005: - Candidate P3 Makespan: **37060** cycles; reused full-prefix P3: **38024** cycles, a reduction of **964 (2.5352%)**. Candidate G = 37060/37060 = **1.0**; control G = 38024/38024 = **1.0**. The prior P3 is exact reused evidence (SHA `d4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1`) and is not represented as a new attempt.
0006: - All three new results report 140800 added bytes and 0 spill bytes. Candidate P3 has 11 hits / 182 accesses, 11264 hit bytes, 1012064 miss bytes, byte hit rate 0.0110072235; same-plan P2 provides the paired non-cache result.
0007: - `solver_wall_seconds` is `null`/unknown. The 7.9257 s prepare diagnostic and score/host diagnostics are not solver wall time. `full500=false`.
0008: - One prepare plus three E0 calls were made; no E1/E2, retry, or new full-prefix P3 call. Phase and per-core evidence remain in raw receipts.
0009: - Candidate plan SHA: `0a75e3613ad5f69e293e45e6c1cfc1545b3b1036245ebc7bf0af75b3321df0fd`. Control plan SHA: `13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508`. The retained old P3 result uses the same control plan. Official single-core baseline SHA: `73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c`. Source commit: `817e9e399f5efaf66cea6ddc495fe444950e43f2`; controller commit: `f4bc0b983f247e3395394e9b4ac25b25fd210d0b`; host checkout HEAD was `ff6e16ea8fbc2af90417aa045c457f37f6e167d7`.
0010: - T0/guard READY was observed at `2026-09-25T06:08:27Z`; exact UTC start is not recorded by the controller (its deadline is monotonic). Preflight receipt was captured at `2026-09-25T06:08:16.647041+00:00`. Controller wall 57.15144412498921 s; stop `confirmed_empty`, watchdog `disarmed_by_confirmed_parent`, and fresh sessions-after exact empty rc 0.
0011: - Evidence archive SHA: `02fa71024fcc6fe35071c7dd9e8a5516caa55609bcbb8fa930bcc661aa114898`; transport package SHA: `5b293299544502de4c5aa2569d55ebd768262d5462ea54f4f68092749445c6f7`. Original result gzip bytes were copied without recompression and verified against each worker `result_sha256`.
0012: - Independent identity/FIFO audit: `results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/INDEPENDENT_AUDIT.json`. It reports timing deltas consistent with earlier downstream starts; it does not prove complete causal decomposition.
0013: - Protocol preflight: exit `0`, eligible `3`. See `protocol-preflight.json` for the actual command and output.
0014: 
0015: The exporter copies exact source bytes, verifies archive/member safety and hashes, generates public run projections without the local admission path, runs the read-only submission preflight, and records its real result. It does not execute a solver or evaluator.
```
