import inspect

from itertools import zip_longest
from concurrent.futures import ThreadPoolExecutor

from .parsefile import parse


def same_signature(sig1: inspect.Signature, sig2: inspect.Signature):
    _EMPTY = inspect._empty

    if sig1.return_annotation != sig2.return_annotation:
        return False

    params1 = list(sig1.parameters.values())
    params2 = list(sig2.parameters.values())

    if len(params1) != len(params2):
        return False

    for p1, p2 in zip_longest(params1, params2):
        if p1.kind != p2.kind or p1.default != p2.default or p1.annotation != p2.annotation:
            return False

        if p1.name != p2.name:
            if (p1.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            inspect.Parameter.KEYWORD_ONLY,
                            inspect.Parameter.POSITIONAL_ONLY} and p1.annotation is _EMPTY
            ):
                return False

    return True


def cmp(src1: str, src2: str, target_function: str):
    with ThreadPoolExecutor() as executor:
        future1 = executor.submit(parse, src1)
        future2 = executor.submit(parse, src2)
        data_old = future1.result()
        data_new = future2.result()

    count_other_ctx_changes = 0
    if data_old['docstring'] != data_new['docstring']:
        print("Program docstring changed")
        count_other_ctx_changes += 1

    count_other_ctx_changes += len(data_old['imports'] - data_new['imports'])
    if count_other_ctx_changes > 0:
        print("Missing imports", set(data_old['imports']) - set(data_new['imports']))

    _old_cls = data_old['cls']
    _new_cls = data_new['cls']
    common_cls = _old_cls.keys() & _new_cls.keys()

    count_other_ctx_changes += len(_old_cls) - len(common_cls)
    count_other_ctx_changes += sum(1 for k in common_cls if _old_cls[k]["docstring"] != _new_cls[k]["docstring"])
    if count_other_ctx_changes > 0:
        print("Docstring of some old cls changed")

    _old_fns = data_old['fns']
    _new_fns = data_new['fns']
    common_fns = _old_fns.keys() & _new_fns.keys()
    count_other_ctx_changes += len(_old_fns) - len(common_fns)

    _old_vars = data_old['vars']
    _new_vars = data_new['vars']
    common_vars = _old_vars.keys() & _new_vars.keys()
    count_other_ctx_changes += len(_old_vars) - len(common_vars)
    if count_other_ctx_changes > 0:
        print("Missing some old vars")

    count_other_ctx_changes += sum(_old_vars[k]['val'] != _new_vars[k]['val'] for k in common_vars)
    if count_other_ctx_changes > 0:
        print("val of some variables changed")
    count_other_ctx_changes += sum(_old_vars[k]['ann'] != _new_vars[k]['ann'] for k in common_vars)
    if count_other_ctx_changes > 0:
        print("ann of some variables changed")

    implemented_fn_signature_changed = False
    implemented_fn_docstring_changed = False

    for cls in common_cls:
        cur_old_cls = _old_cls[cls]
        cur_new_cls = _new_cls[cls]
        if cur_old_cls['bases'] != cur_new_cls['bases'] or cur_old_cls['decorator_list'] != cur_new_cls[
            'decorator_list']:
            print("Ctx Bases or decorators changed", cls)
            count_other_ctx_changes += 1

    for fn in common_fns:
        _old_fn = _old_fns[fn]
        _new_fn = _new_fns[fn]

        if _old_fn['decorator_list'] != _new_fn['decorator_list'] or _old_fn['async'] != _new_fn['async']:
            print("Decor or async changed", fn)
            count_other_ctx_changes += 1

        if not same_signature(_old_fn['signature'], _new_fn['signature']):
            if fn != target_function:
                count_other_ctx_changes += 1
                print("Ctx signatures changed", fn)
            else:
                implemented_fn_signature_changed = True

        if _old_fn['body'] != _new_fn['body']:
            if fn != target_function:
                count_other_ctx_changes += 1
                print("Ctx body changed", fn)

        if _old_fn['docstring'] != _new_fn['docstring']:
            if fn != target_function:
                count_other_ctx_changes += 1
                print("Ctx docstring changed", fn)
            else:
                implemented_fn_docstring_changed = True

    if len(data_old['others']) != len(data_new['others']):
        count_other_ctx_changes += 1
    else:
        for i in range(len(data_old['others'])):
            if data_old['others'][i] != data_new['others'][i]:
                count_other_ctx_changes += 1
                print("Other ctx changed")

    return {
        "context_changed": count_other_ctx_changes,
        "signature_changed": implemented_fn_signature_changed,
        "body_changed": implemented_fn_docstring_changed,
    }