import ast
import difflib
from typing import List, Union


def merge(old_src: str, new_src: str, target_function: str) -> str:
    # -----------------------------
    # Helpers
    # -----------------------------

    def is_import(node: ast.AST) -> bool:
        return isinstance(node, (ast.Import, ast.ImportFrom))

    def is_docstring_node(node: ast.AST) -> bool:
        return (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
        )

    def extract_docstring_node(node: ast.AST):
        return node.body[0] if hasattr(node, "body") and node.body and is_docstring_node(node.body[0]) else None

    def remove_docstring_node(nodes: List[ast.AST]) -> List[ast.AST]:
        return nodes[1:] if nodes and is_docstring_node(nodes[0]) else nodes

    def get_name(node: ast.AST) -> Union[str, None]:
        return getattr(node, "name", None) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                                ast.ClassDef)) else None

    def merge_imports(old_nodes: List[ast.AST], new_nodes: List[ast.AST]) -> List[ast.AST]:
        return list({ast.unparse(n): n for n in old_nodes + new_nodes if is_import(n)}.values())

    def split_nodes(nodes: List[ast.AST]):
        imports, globals_, defs = [], [], []
        for n in nodes:
            if is_import(n):
                imports.append(n)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defs.append(n)
            else:
                globals_.append(n)
        return imports, globals_, defs

    def merge_globals(old_globals: List[ast.AST], new_globals: List[ast.AST]) -> List[ast.AST]:
        old_strs = [ast.unparse(n) for n in old_globals]
        new_strs = [ast.unparse(n) for n in new_globals]

        matcher = difflib.SequenceMatcher(None, old_strs, new_strs)
        merged = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal' or tag == 'delete':
                merged.extend(old_globals[i1:i2])
            elif tag == 'insert':
                merged.extend(new_globals[j1:j2])
            elif tag == 'replace':
                merged.extend(old_globals[i1:i2])
                merged.extend(new_globals[j1:j2])

        return merged

    def merge_class_bodies(old_cls: ast.ClassDef, new_cls: ast.ClassDef):
        clean_new_body = remove_docstring_node(new_cls.body)
        is_pass_only = not clean_new_body or (len(clean_new_body) == 1 and isinstance(clean_new_body[0], ast.Pass))
        new_doc = extract_docstring_node(new_cls)

        # 🔥 ALWAYS strip old docstring to strictly mirror the new class's docstring state
        old_cls.body = remove_docstring_node(old_cls.body)

        if is_pass_only:
            if new_doc:
                old_cls.body.insert(0, new_doc)
            return

        new_named_nodes = {
            n.name: n for n in clean_new_body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

        new_body = []
        for n in old_cls.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name in new_named_nodes:
                new_body.append(new_named_nodes.pop(n.name))
            else:
                new_body.append(n)

        new_body.extend(new_named_nodes.values())

        if new_doc:
            new_body.insert(0, new_doc)

        old_cls.body = new_body

    def replace_or_add_defs(old_defs: List[ast.AST], new_defs: List[ast.AST]) -> List[ast.AST]:
        new_map = {get_name(d): d for d in new_defs if get_name(d)}
        result = []

        for d in old_defs:
            name = get_name(d)
            if name in new_map:
                new_node = new_map.pop(name)
                if isinstance(d, ast.ClassDef) and isinstance(new_node, ast.ClassDef):
                    merge_class_bodies(d, new_node)
                    result.append(d)
                else:
                    result.append(new_node)
            else:
                result.append(d)

        result.extend(new_map.values())
        return result

    def find_class(defs: List[ast.AST], class_name: str) -> Union[ast.ClassDef, None]:
        return next((d for d in defs if isinstance(d, ast.ClassDef) and getattr(d, "name", None) == class_name), None)

    def extract_method_like_functions(nodes: List[ast.AST]) -> List[ast.FunctionDef]:
        return [n for n in nodes if isinstance(n, ast.FunctionDef) and is_method_like(n)]

    def is_method_like(fn: ast.FunctionDef) -> bool:
        has_self = fn.args.args and fn.args.args[0].arg == "self"
        has_decorator = any(getattr(d, "id", "") in {"classmethod", "staticmethod"} for d in fn.decorator_list)
        return bool(has_self or has_decorator)

    def remove_nodes(nodes: List[ast.AST], to_remove: List[ast.AST]) -> List[ast.AST]:
        remove_ids = {id(n) for n in to_remove}
        return [n for n in nodes if id(n) not in remove_ids]

    def merge_methods_into_class(old_cls: ast.ClassDef, new_methods: List[ast.FunctionDef],
                                 new_cls: Union[ast.ClassDef, None] = None):
        new_method_map = {m.name: m for m in new_methods}

        # 🔥 Unconditionally strip old docstring if a new class representation exists
        if new_cls is not None:
            old_cls.body = remove_docstring_node(old_cls.body)
            new_doc = extract_docstring_node(new_cls)
        else:
            new_doc = None

        new_body = [new_method_map.pop(n.name, n) if isinstance(n, ast.FunctionDef) else n for n in old_cls.body]
        new_body.extend(new_method_map.values())

        if new_doc:
            new_body.insert(0, new_doc)

        old_cls.body = new_body

    # -----------------------------
    # Parse ASTs
    # -----------------------------
    old_tree = ast.parse(old_src)
    new_tree = ast.parse(new_src)

    old_doc = extract_docstring_node(old_tree)
    new_doc = extract_docstring_node(new_tree)
    final_doc = new_doc if new_doc is not None else old_doc

    old_body = remove_docstring_node(old_tree.body)
    new_body = remove_docstring_node(new_tree.body)

    old_imports, old_globals, old_defs = split_nodes(old_body)
    new_imports, new_globals, new_defs = split_nodes(new_body)

    merged_imports = merge_imports(old_imports, new_imports)
    merged_globals = merge_globals(old_globals, new_globals)

    # -----------------------------
    # Case 1: standalone function
    # -----------------------------
    if "." not in target_function:
        merged_defs = replace_or_add_defs(old_defs, new_defs)

    # -----------------------------
    # Case 2: class method
    # -----------------------------
    else:
        class_name, _ = target_function.split(".")

        old_cls = find_class(old_defs, class_name)
        new_cls = find_class(new_defs, class_name)

        top_level_methods = extract_method_like_functions(new_defs)
        new_defs = remove_nodes(new_defs, top_level_methods)

        class_methods = [n for n in new_cls.body if isinstance(n, ast.FunctionDef)] if new_cls else []
        all_new_methods = class_methods + top_level_methods

        if old_cls:
            merge_methods_into_class(old_cls, all_new_methods, new_cls)
            if new_cls and not old_cls:
                old_defs.append(new_cls)
        else:
            if new_cls:
                new_cls.body.extend(top_level_methods)
                old_defs.append(new_cls)
            else:
                new_class = ast.ClassDef(
                    name=class_name,
                    bases=[],
                    keywords=[],
                    body=all_new_methods if all_new_methods else [ast.Pass()],
                    decorator_list=[],
                )
                old_defs.append(new_class)

        remaining_new_defs = [d for d in new_defs if get_name(d) != class_name]
        merged_defs = replace_or_add_defs(old_defs, remaining_new_defs)

    # -----------------------------
    # Construct final module
    # -----------------------------
    final_body = []
    if final_doc is not None:
        final_body.append(final_doc)

    final_body.extend(merged_imports + merged_globals + merged_defs)

    final_module = ast.Module(body=final_body, type_ignores=[])
    ast.fix_missing_locations(final_module)

    return ast.unparse(final_module)
