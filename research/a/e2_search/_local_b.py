"""Narrow source-guarded optimization of the frozen local Step3 compiler.

Keep scheduling, allocation, memory dependencies and validation unchanged. Replace
the O(ops) completion scan per event with a retire counter; omit only unconsumed
diagnostic append expressions. This modifies a private fast bundle, never E0.
"""
import ast
import inspect
from src.eval_exact.problem1 import _copy_step3_extended_graph


def install(support):
    module = support['schedule_step3']
    tree = ast.parse(inspect.getsource(module.step3_simulation))
    hits = dict(counter_init=0, counter_update=0, counter_check=0, nonlocal_decl=0, logs=0, result=0)
    kept = {'execution_graph', 'pipe_orders', 'makespan', 'memory_peak', 'memory_dependencies'}

    class Rewrite(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.name == 'retire_step':
                node.body.insert(0, ast.Nonlocal(names=['remaining_ops']))
                hits['nonlocal_decl'] += 1
            return node

        def visit_Assign(self, node):
            self.generic_visit(node)
            text = ast.unparse(node)
            if text == "op_status = {op_id: 'pending' for op_id in op_by_id}":
                hits['counter_init'] += 1
                return [node, ast.parse('remaining_ops = len(op_status)').body[0]]
            if text == "op_status[op_id] = 'done'":
                hits['counter_update'] += 1
                return [node, ast.parse('remaining_ops -= 1').body[0]]
            return node

        def visit_If(self, node):
            self.generic_visit(node)
            if ast.unparse(node.test) == "all((status == 'done' for status in op_status.values()))":
                node.test = ast.parse('remaining_ops == 0', mode='eval').body
                hits['counter_check'] += 1
            return node

        def visit_Expr(self, node):
            value = node.value
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == 'append' and isinstance(value.func.value, ast.Name)
                    and value.func.value.id in ('memory_events', 'ddr_contention_log')):
                hits['logs'] += 1
                return None
            return node

        def visit_Return(self, node):
            if isinstance(node.value, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == 'execution_graph' for k in node.value.keys):
                pairs = [(k, v) for k, v in zip(node.value.keys, node.value.values) if k.value in kept]
                node.value = ast.Dict(keys=[k for k, v in pairs], values=[v for k, v in pairs])
                hits['result'] += 1
            return node

    tree = Rewrite().visit(tree)
    expected = dict(counter_init=1, counter_update=1, counter_check=1, nonlocal_decl=1, logs=3, result=1)
    if hits != expected:
        raise RuntimeError(f'frozen Step3 optimization shape changed: {hits}')
    ast.fix_missing_locations(tree)
    scope = dict(module.__dict__)
    scope['deepcopy'] = _copy_step3_extended_graph
    exec(compile(tree, '<e2_scene_b_local_step3>', 'exec'), scope)
    module.step3_simulation = scope['step3_simulation']
    return hits
