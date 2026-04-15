import ast
from typing import Set


class NameCollector(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            self.names.add(node.value.id)
        self.generic_visit(node)


def split_focus(focus: str):
    if "." in focus:
        cls, meth = focus.split(".", 1)
        return cls, meth
    else:
        return focus, None


def find_class_method(defs, class_name, method_name):
    cls = defs.get(class_name)
    if not isinstance(cls, ast.ClassDef):
        return None
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            return node
    return None


def analyze_dependencies(tree: ast.Module):
    defs = {}
    imports = []
    direct_deps = {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[node.name] = node
            collector = NameCollector()
            collector.visit(node)
            direct_deps[node.name] = collector.names

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)

    return defs, imports, direct_deps


def compute_needed(defs, direct_deps, focus: str) -> Set[str]:
    needed = set()
    stack = [focus]

    while stack:
        name = stack.pop()
        if name in needed:
            continue
        needed.add(name)

        for dep in direct_deps.get(name, []):
            if dep in defs and dep not in needed:
                stack.append(dep)

    return needed


class PrintStripper(ast.NodeTransformer):
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            node.args = []
            node.keywords = []
        return self.generic_visit(node)


def is_print_call(node):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "print"
    )


def normalize(program: str, focus: str, rm_print_args: bool = True) -> str:
    tree = ast.parse(program)

    defs, imports, direct_deps = analyze_dependencies(tree)

    cls, meth = split_focus(focus)

    if meth is None:
        if focus not in defs:
            raise ValueError(f"Focus `{focus}` not found.")
        focus_name = focus
    else:
        method_node = find_class_method(defs, cls, meth)
        if method_node is None:
            raise ValueError(f"Method `{focus}` not found.")
        focus_name = cls

    needed = compute_needed(defs, direct_deps, focus_name)

    kept_nodes = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in needed:
                kept_nodes.append(node)

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names_used = set().union(*(direct_deps.get(n, set()) for n in needed))
            imported_names = set()

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split('.')[0])
            else:
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

            if names_used & imported_names:
                kept_nodes.append(node)

        elif is_print_call(node):
            kept_nodes.append(node)

    new_tree = ast.Module(body=kept_nodes, type_ignores=[])

    if rm_print_args:
        new_tree = PrintStripper().visit(new_tree)
        ast.fix_missing_locations(new_tree)

    return ast.unparse(new_tree)

