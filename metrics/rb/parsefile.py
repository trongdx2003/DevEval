import ast
import inspect


def get_docstr(node):
    docstr = ast.get_docstring(node)
    if docstr:
        splitter = docstr.split()
        return [line.strip() for line in splitter if line]
    return docstr


def parse(source: str) -> dict:
    tree = ast.parse(source)

    result = {
        "docstring": get_docstr(tree),
        "imports": set(),
        "vars": {},
        "fns": {},
        "cls": {},
        "others": [],
    }

    def eval_node(node):
        try:
            return ast.literal_eval(node)
        except Exception:
            return ast.dump(node, include_attributes=False)

    def get_annotation(node):
        return ast.dump(node, include_attributes=False) if node else ""

    def get_name(node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{get_name(node.value)}.{node.attr}"
        else:
            return ast.dump(node, include_attributes=False)

    def get_decorators(node):
        return [get_name(d) for d in node.decorator_list]

    def flatten_targets(target):
        if isinstance(target, ast.Name):
            return [(target.id, False)]
        elif isinstance(target, ast.Starred):
            if isinstance(target.value, ast.Name):
                return [(target.value.id, True)]
        elif isinstance(target, (ast.Tuple, ast.List)):
            res = []
            for elt in target.elts:
                res.extend(flatten_targets(elt))
            return res
        return []

    def extract_values(value_node, targets):
        try:
            value = ast.literal_eval(value_node)
        except Exception:
            src = ast.dump(value_node, include_attributes=False)
            return [src] * len(targets)

        if not isinstance(value, (list, tuple)):
            return [value] * len(targets)

        n = len(targets)
        star_idx = [i for i, (_, s) in enumerate(targets) if s]

        if len(star_idx) > 1:
            return [value] * n

        if not star_idx:
            if len(value) == n:
                return list(value)
            return [value] * n

        star_i = star_idx[0]
        before = star_i
        after = n - star_i - 1

        if len(value) < before + after:
            return [value] * n

        res = []
        for i in range(before):
            res.append(value[i])
        res.append(list(value[before: len(value) - after]))
        for i in range(after):
            res.append(value[len(value) - after + i])

        return res

    def build_signature(fn):
        params = []

        def make_param(arg, default=inspect._empty, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD):
            return inspect.Parameter(arg.arg, kind, default=default)

        args = fn.args
        pos_args = args.args
        defaults = [inspect._empty] * (len(pos_args) - len(args.defaults)) + [
            eval_node(d) for d in args.defaults
        ]

        for a, d in zip(pos_args, defaults):
            params.append(make_param(a, d))

        if args.vararg:
            params.append(make_param(args.vararg, kind=inspect.Parameter.VAR_POSITIONAL))

        for a, d in zip(args.kwonlyargs, args.kw_defaults):
            default = eval_node(d) if d else inspect._empty
            params.append(make_param(a, default, inspect.Parameter.KEYWORD_ONLY))

        if args.kwarg:
            params.append(make_param(args.kwarg, kind=inspect.Parameter.VAR_KEYWORD))

        return inspect.Signature(params)

    def extract_body(fn):
        body = fn.body[:]

        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]

        if not body:
            return ""

        return ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)

    queue = [(node, "") for node in tree.body]

    for node, prefix in queue:

        if isinstance(node, ast.Import) and not prefix:
            for alias in node.names:
                result["imports"].add(alias.name)

        elif isinstance(node, ast.ImportFrom) and not prefix:
            module = node.module or ""
            for alias in node.names:
                result["imports"].add(f"{module}.{alias.name}" if module else alias.name)

        elif isinstance(node, ast.Assign):
            targets = []
            for t in node.targets:
                targets.extend(flatten_targets(t))
            values = extract_values(node.value, targets)

            for (name, _), val in zip(targets, values):
                q_name = f"{prefix}.{name}" if prefix else name
                result["vars"][q_name] = {"val": val, "ann": None}

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                q_name = f"{prefix}.{node.target.id}" if prefix else node.target.id
                result["vars"][q_name] = {
                    "val": eval_node(node.value) if node.value else None,
                    "ann": get_annotation(node.annotation)
                }

        elif isinstance(node, ast.ClassDef):
            q_name = f"{prefix}.{node.name}" if prefix else node.name
            result["cls"][q_name] = {
                "docstring": get_docstr(node),
                "bases": [get_name(b) for b in node.bases],
                "decorator_list": get_decorators(node),
            }
            queue.extend((stmt, q_name) for stmt in node.body)

        elif isinstance(node, ast.FunctionDef):
            q_name = f"{prefix}.{node.name}" if prefix else node.name
            result["fns"][q_name] = {
                "async": False,
                "decorator_list": get_decorators(node),
                "signature": build_signature(node),
                "docstring": get_docstr(node),
                "body": extract_body(node),
            }

        elif isinstance(node, ast.AsyncFunctionDef):
            q_name = f"{prefix}.{node.name}" if prefix else node.name
            result["fns"][q_name] = {
                "async": True,
                "signature": build_signature(node),
                "docstring": get_docstr(node),
                "body": extract_body(node),
                "decorator_list": get_decorators(node),
            }

        elif not prefix:
            result["others"].append(ast.dump(node, include_attributes=False))

    return result
