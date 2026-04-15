import ast
import textwrap
from typing import Optional

def get_definition(src: str, fn: str) -> Optional[str]:
    tree = ast.parse(src)
    lines = src.splitlines()
    path = fn.split(".")

    def extract_node_source(node: ast.AST) -> Optional[str]:
        """Extract full source including decorators."""
        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            return None

        # Include decorators if present
        start_lineno = node.lineno
        if getattr(node, "decorator_list", None):
            start_lineno = min(d.lineno for d in node.decorator_list)

        return textwrap.dedent("\n".join(lines[start_lineno - 1: node.end_lineno]))

    def visit(node: ast.AST, path_idx: int) -> Optional[str]:
        if path_idx >= len(path):
            return None

        target = path[path_idx]

        for child in ast.iter_child_nodes(node):
            # Match class
            if isinstance(child, ast.ClassDef) and child.name == target:
                return visit(child, path_idx + 1)

            # Match function or async function
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == target:
                if path_idx == len(path) - 1:
                    return extract_node_source(child)

        return None

    return visit(tree, 0)

if __name__ == "__main__":
    import sys

    file_path = sys.argv[1]
    target_function = sys.argv[2]

    with open(file_path, "r") as old_file:
        src = old_file.read()

    print(get_definition(src, target_function))