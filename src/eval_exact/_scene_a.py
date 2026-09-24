"""P1 global simulator derived from the frozen official evaluate_scene_a.

Source SHA256: 2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f.
Only completed-state scans and output grouping are changed. Event ordering,
FIFO, DDR binary64 expressions and ceil operations remain as in the oracle.
Local compilation is supplied by a private, byte-verified runtime instance.
This is ordinary source code; no source rewriting occurs at runtime.
"""
import heapq
import math


def evaluate_scene_a(runtime, graph_json, plan, bandwidth, capacity,
                     cross_core_wait, same_core_wait, max_iter=1000000):
    """执行场景 A 多核事件模拟并返回 makespan 与完整时间线。

    带宽、容量与两类等待周期都由 CLI 从 config.txt 读出后传入，本函数不再
    提供配置默认值；每条 Pipe 同一时刻只有 PIPE_SLOTS 个在飞指令，不对外开放。
    """
    validate_parameters = runtime.validate_parameters
    _build_scene_a_tasks = runtime._build_scene_a_tasks
    PIPES, PIPE_SLOTS = runtime.PIPES, runtime.PIPE_SLOTS
    op_pipe = runtime.op_pipe
    _op_duration, _uses_ddr_bandwidth = runtime._op_duration, runtime._uses_ddr_bandwidth
    SceneAEvaluationError = runtime.SceneAEvaluationError
    capacity = dict(capacity)
    validate_parameters(bandwidth, capacity, max_iter,
                        cross_core_wait=cross_core_wait, same_core_wait=same_core_wait)
    tasks, cross_task_traffic, data_movement, plan_view = _build_scene_a_tasks(
        graph_json, plan, bandwidth, capacity)
    num_cores = plan_view['num_cores']
    core_orders = plan_view['core_orders']
    task_status = {task_id: 'waiting' for task_id in tasks}
    task_start, task_end = {}, {}
    task_rank = {tid: i for i, tid in enumerate(tasks)}
    task_ops_left = {}
    tasks_left = len(tasks)
    core_index = {core_id: 0 for core_id in range(num_cores)}
    core_active_task = {core_id: None for core_id in range(num_cores)}
    core_previous_end = {core_id: None for core_id in range(num_cores)}
    executors = {
        (core_id, pipe): []
        for core_id in range(num_cores) for pipe in PIPES
    }
    issue_queues = {
        (core_id, pipe): []
        for core_id in range(num_cores) for pipe in PIPES
    }
    op_status, pred_remaining, op_start, op_end = {}, {}, {}, {}
    ddr_remaining_work, ddr_contention_log = {}, []
    ddr_last_update = 0

    def key(task_id, op_id):
        return (task_id, op_id)

    def init_pipe_queues(task):
        """装载 Step3 已确定的逐 Pipe 顺序。"""
        task['pipe_cursor'] = {pipe: 0 for pipe in task['pipe_ops']}

    def advance_ddr_work(now):
        nonlocal ddr_last_update
        elapsed = now - ddr_last_update
        while elapsed > 1e-9:
            active = [item for item, work in ddr_remaining_work.items() if work > 1e-9]
            if not active:
                break
            min_work = min(ddr_remaining_work[item] for item in active)
            finish_delta = min_work * len(active)
            if finish_delta >= elapsed - 1e-9:
                share = elapsed / len(active)
                for item in active:
                    ddr_remaining_work[item] = max(0.0, ddr_remaining_work[item] - share)
                break
            for item in active:
                ddr_remaining_work[item] = max(0.0, ddr_remaining_work[item] - min_work)
            elapsed -= finish_delta
        ddr_last_update = now

    def reschedule_ddr(now):
        if not ddr_remaining_work:
            return {}
        ordered = sorted((max(0.0, work), item)
                         for item, work in ddr_remaining_work.items())
        projected, cursor, previous, active_count = {}, float(now), 0.0, len(ordered)
        i = 0
        while i < len(ordered):
            work = ordered[i][0]
            cursor += (work - previous) * active_count
            j = i
            while j < len(ordered) and abs(ordered[j][0] - work) <= 1e-9:
                projected[ordered[j][1]] = int(math.ceil(cursor - 1e-9))
                j += 1
            active_count -= j - i
            previous = work
            i = j
        for item, end in projected.items():
            op_end[item] = end
        for executor_key, running in executors.items():
            executors[executor_key] = [
                (item, projected.get(item, end)) for item, end in running]
        return projected

    def queue_if_ready(task_id, op_id):
        item = key(task_id, op_id)
        if op_status[item] != 'pending' or pred_remaining[item] != 0:
            return
        task = tasks[task_id]
        pipe = op_pipe(task['op_by_id'][op_id])
        order = task['pipe_ops'][pipe]
        cursor = task['pipe_cursor'][pipe]
        if cursor >= len(order) or order[cursor] != op_id:
            return
        op_status[item] = 'ready'
        heapq.heappush(issue_queues[(task['core_id'], pipe)],
                       (task['seq_pos'][op_id], item))

    def activate_task(task_id, now):
        task = tasks[task_id]
        init_pipe_queues(task)
        task_status[task_id] = 'active'
        task_ops_left[task_id] = len(task['seq'])
        task_start[task_id] = now
        core_active_task[task['core_id']] = task_id
        for op_id in task['seq']:
            item = key(task_id, op_id)
            op_status[item] = 'pending'
            pred_remaining[item] = len(task['op_preds'][op_id])
        for op_id in task['seq']:
            queue_if_ready(task_id, op_id)

    def advance_pipe(task_id, op_id):
        """操作完成后推进所在 Pipe，并尝试唤醒下一操作。"""
        task = tasks[task_id]
        pipe = op_pipe(task['op_by_id'][op_id])
        cursor = task['pipe_cursor'][pipe]
        order = task['pipe_ops'][pipe]
        task['pipe_cursor'][pipe] += 1
        if cursor + 1 < len(order):
            queue_if_ready(task_id, order[cursor + 1])

    def task_release_time(task_id):
        task = tasks[task_id]
        core_id = task['core_id']
        if any(task_status[pred] != 'done' for pred in task['pred_tasks']):
            return None
        release = 0
        if core_previous_end[core_id] is not None:
            release = core_previous_end[core_id] + same_core_wait
        for pred in task['pred_tasks']:
            if tasks[pred]['core_id'] != core_id:
                release = max(release, task_end[pred] + cross_core_wait)
        return release

    def activate_ready_tasks(now):
        changed = False
        for core_id in range(num_cores):
            if core_active_task[core_id] is not None:
                continue
            order = core_orders.get(core_id, [])
            if core_index[core_id] >= len(order):
                continue
            task_id = order[core_index[core_id]]
            release = task_release_time(task_id)
            if release is not None and release <= now:
                activate_task(task_id, now)
                changed = True
        return changed

    def retire(now):
        nonlocal tasks_left
        advance_ddr_work(now)
        retired_ddr = False
        for executor_key, running in list(executors.items()):
            keep = []
            for item, end in running:
                if end > now:
                    keep.append((item, end))
                    continue
                task_id, op_id = item
                op_status[item] = 'done'
                task_ops_left[task_id] -= 1
                advance_pipe(task_id, op_id)
                if item in ddr_remaining_work:
                    ddr_remaining_work.pop(item)
                    retired_ddr = True
                for succ_id in tasks[task_id]['op_succs'][op_id]:
                    succ_item = key(task_id, succ_id)
                    pred_remaining[succ_item] -= 1
                    queue_if_ready(task_id, succ_id)
            executors[executor_key] = keep
        if retired_ddr:
            reschedule_ddr(now)

        # Preserve official task insertion order when simultaneous tasks retire.
        active_tasks = (tid for tid in core_active_task.values() if tid is not None)
        for task_id in sorted(active_tasks, key=task_rank.__getitem__):
            if task_ops_left[task_id] == 0:
                core_id = tasks[task_id]['core_id']
                task_status[task_id] = 'done'
                tasks_left -= 1
                task_end[task_id] = now
                core_active_task[core_id] = None
                core_previous_end[core_id] = now
                core_index[core_id] += 1

    def issue(now):
        issued_in_pass = True
        while issued_in_pass:
            issued_in_pass = False
            for core_id in range(num_cores):
                for pipe in PIPES:
                    executor_key = (core_id, pipe)
                    queue = issue_queues[executor_key]
                    while len(executors[executor_key]) < PIPE_SLOTS:
                        if not queue:
                            break
                        _, item = heapq.heappop(queue)
                        issued_in_pass = True
                        task_id, op_id = item
                        task = tasks[task_id]
                        op = task['op_by_id'][op_id]
                        duration = _op_duration(
                            op, task['in_tids'], task['out_tids'],
                            task['tensor_by_id'], bandwidth)
                        op_status[item] = 'running'
                        op_start[item] = now
                        op_end[item] = now + duration
                        executors[executor_key].append((item, op_end[item]))
                        if _uses_ddr_bandwidth(
                                op, task['in_tids'], task['out_tids'],
                                task['tensor_by_id']):
                            advance_ddr_work(now)
                            ddr_remaining_work[item] = float(duration)
                            projected = reschedule_ddr(now)
                            ddr_contention_log.append({
                                'time': now,
                                'issued': {'task_id': task_id, 'op_id': op_id,
                                           'core_id': core_id, 'pipe': pipe},
                                'active_count': len(ddr_remaining_work),
                                'projected_ends': [
                                    {'task_id': active[0], 'op_id': active[1], 'end': end}
                                    for active, end in sorted(projected.items())
                                ],
                            })

    now = 0
    for iteration in range(max_iter):
        retire(now)
        activate_ready_tasks(now)
        issue(now)
        if tasks_left == 0:
            break
        next_times = [end for running in executors.values() for _, end in running]
        for core_id in range(num_cores):
            if core_active_task[core_id] is not None:
                continue
            order = core_orders.get(core_id, [])
            if core_index[core_id] < len(order):
                release = task_release_time(order[core_index[core_id]])
                if release is not None and release > now:
                    next_times.append(release)
        if not next_times:
            waiting = sorted(task_id for task_id, status in task_status.items()
                             if status != 'done')
            raise SceneAEvaluationError(
                'multicore scheduler deadlock at t={}; waiting_tasks={}'.format(
                    now, waiting))
        next_now = min(next_times)
        if next_now <= now:
            raise SceneAEvaluationError(
                'multicore scheduler made no progress at t={}'.format(now))
        now = next_now
    else:
        raise SceneAEvaluationError('max_iter exceeded')

    per_core_timeline = []
    for core_id in range(num_cores):
        task_entries = []
        for task_id in core_orders.get(core_id, []):
            task_entries.append({
                'task_id': task_id, 'subgraph_id': task_id,
                'start': task_start[task_id], 'end': task_end[task_id],
                'duration': task_end[task_id] - task_start[task_id],
            })
        op_entries = []
        for item, start in op_start.items():
            task_id, op_id = item
            if tasks[task_id]['core_id'] != core_id:
                continue
            op = tasks[task_id]['op_by_id'][op_id]
            op_entries.append({
                'task_id': task_id, 'op_id': op_id, 'op': op['op'],
                'pipe': op_pipe(op),
                'start': start, 'end': op_end[item],
                'duration': op_end[item] - start,
            })
        op_entries.sort(key=lambda entry: (entry['start'], entry['task_id'], entry['op_id']))
        subgraph_entries = []
        ops_by_task = {}
        for entry in op_entries:
            ops_by_task.setdefault(entry['task_id'], []).append(entry)
        for task_id in core_orders.get(core_id, []):
            subgraph_ops = ops_by_task.get(task_id, [])
            if not subgraph_ops:
                raise SceneAEvaluationError(
                    'subgraph {} has no scheduled op'.format(task_id))
            start = min(entry['start'] for entry in subgraph_ops)
            end = max(entry['end'] for entry in subgraph_ops)
            subgraph_entries.append({
                'subgraph_id': task_id,
                'start': start, 'end': end, 'duration': end - start,
            })
        per_core_timeline.append({
            'core_id': core_id, 'tasks': task_entries,
            'subgraphs': subgraph_entries, 'ops': op_entries})

    makespan = max(task_end.values(), default=0)
    memory_peak_by_core = {
        core_id: {
            pos: max((tasks[task_id]['step3']['memory_peak'][pos]
                      for task_id in core_orders.get(core_id, [])), default=0)
            for pos in capacity
        }
        for core_id in range(num_cores)
    }
    return {
        'scene': 'A',
        'makespan': makespan,
        'num_cores': num_cores,
        'bandwidth_bytes_per_cycle': bandwidth,
        'capacity_bytes': dict(capacity),
        'memory_peak_by_core': memory_peak_by_core,
        'step3_by_task': {
            task_id: {
                'local_makespan': task['step3']['makespan'],
                'memory_dependency_count': len(
                    task['step3']['memory_dependencies']),
                'pipe_op_counts': {
                    pipe: len(order) for pipe, order in task['pipe_ops'].items()
                },
            }
            for task_id, task in tasks.items()
        },
        'task_cross_core_wait_cycles': cross_core_wait,
        'task_same_core_wait_cycles': same_core_wait,
        'cross_task_traffic': cross_task_traffic,
        'data_movement_bytes': data_movement,
        'task_dependencies': [
            {'source': source, 'target': target}
            for source, target in plan_view['dependency_pairs']
        ],
        'per_core_timeline': per_core_timeline,
        'ddr_contention_log': ddr_contention_log,
    }
