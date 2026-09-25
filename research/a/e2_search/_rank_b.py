"""Private, source-shape-guarded Scene B COPY subgraph rank lookup.

The frozen official builder repeatedly calls ``core_orders[core].index(sg)``
while assigning COPY operations. A valid plan has unique integer subgraph IDs
and each is scheduled exactly once, so one per-core position table gives the
same rank. The error path delegates to the original list.index expression.
Only the fast bundle is patched; the separate full/fallback E0 bundle is not.
"""
import ast
import inspect


def install(runtime):
    original = runtime._build_scene_b_tasks
    tree = ast.parse(inspect.getsource(original))
    hits = dict(core_orders=0, lookups=0)

    class Rewrite(ast.NodeTransformer):
        def visit_Assign(self, node):
            self.generic_visit(node)
            if ast.unparse(node) == "core_orders = plan_view['core_orders']":
                hits['core_orders'] += 1
                helpers = ast.parse('''
core_positions = {core: {sg: rank for rank, sg in enumerate(order)}
                  for core, order in core_orders.items()}
def core_position(core, sg):
    try:
        return core_positions[core][sg]
    except KeyError:
        return core_orders[core].index(sg)
''').body
                return [node, *helpers]
            return node

        def visit_Call(self, node):
            self.generic_visit(node)
            target = node.func
            if (isinstance(target, ast.Attribute) and target.attr == 'index'
                    and isinstance(target.value, ast.Subscript)
                    and isinstance(target.value.value, ast.Name)
                    and target.value.value.id == 'core_orders'
                    and len(node.args) == 1 and not node.keywords
                    and isinstance(node.args[0], ast.Name) and node.args[0].id == 'sg'):
                hits['lookups'] += 1
                return ast.copy_location(ast.Call(
                    func=ast.Name(id='core_position', ctx=ast.Load()),
                    args=[target.value.slice, node.args[0]], keywords=[]), node)
            return node

    tree = Rewrite().visit(tree)
    if hits != dict(core_orders=1, lookups=4):
        raise RuntimeError(f'frozen Scene B rank lookup shape changed: {hits}')
    ast.fix_missing_locations(tree)
    namespace = dict(original.__globals__)
    exec(compile(tree, '<e2_scene_b_rank_index>', 'exec'), namespace)
    runtime._build_scene_b_tasks = namespace[original.__name__]
    return hits
