import ast


_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _parse_module(source: str) -> ast.Module:
    try:
        return ast.parse(source or "")
    except SyntaxError as exc:
        raise ValueError(f"Invalid Python syntax: {exc.msg}") from exc


def _normalize_code(code: str) -> str:
    normalized = (code or "").rstrip() + "\n"
    _parse_module(normalized)
    return normalized


def _parse_target(target: str) -> tuple[str | None, str]:
    raw = (target or "").strip()
    if not raw:
        raise ValueError("ast_patch target is required")
    if "." in raw:
        parts = raw.split(".")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid method target format; use ClassName.method_name")
        return parts[0], parts[1]
    return None, raw


def _extract_single_function(code: str) -> ast.AST:
    code_module = _parse_module(code)
    funcs = [n for n in code_module.body if isinstance(n, _DEF_NODES)]
    if len(funcs) != 1:
        raise ValueError("ast_patch code must define exactly one function")
    return funcs[0]


def _replace_in_lines(original: str, node: ast.AST, replacement: str) -> str:
    col = int(getattr(node, "col_offset", 0) or 0)
    if col > 0:
        indented: list[str] = []
        for line in replacement.splitlines(keepends=True):
            if line.strip():
                indented.append((" " * col) + line)
            else:
                indented.append(line)
        replacement = "".join(indented)
    lines = original.splitlines(keepends=True)
    start = node.lineno - 1
    end = node.end_lineno
    new_lines = lines[:start] + [replacement] + lines[end:]
    return "".join(new_lines)


def apply_ast_patch_text(old_content: str, operation: str, target: str, code: str) -> str:
    if operation not in {"replace_function", "add_function"}:
        raise ValueError("Unsupported ast_patch operation")

    original = old_content or ""
    module = _parse_module(original)
    replacement = _normalize_code(code)

    if operation == "replace_function":
        class_name, func_name = _parse_target(target)
        new_func = _extract_single_function(replacement)
        if getattr(new_func, "name", "") != func_name:
            raise ValueError("ast_patch code function name must match target")

        if class_name is None:
            top_matches = [n for n in module.body if isinstance(n, _DEF_NODES) and n.name == func_name]
            class_matches: list[ast.AST] = []
            for node in module.body:
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, _DEF_NODES) and item.name == func_name:
                            class_matches.append(item)
            if top_matches:
                if len(top_matches) > 1:
                    raise ValueError("Multiple top-level functions found; use explicit target")
                return _replace_in_lines(original, top_matches[0], replacement)
            if class_matches:
                raise ValueError("Ambiguous method target; use ClassName.method_name")
            raise ValueError(f"Function not found: {target}")

        class_nodes = [n for n in module.body if isinstance(n, ast.ClassDef) and n.name == class_name]
        if not class_nodes:
            raise ValueError(f"Class not found: {class_name}")
        if len(class_nodes) > 1:
            raise ValueError(f"Multiple classes found: {class_name}")

        methods = [n for n in class_nodes[0].body if isinstance(n, _DEF_NODES) and n.name == func_name]
        if not methods:
            raise ValueError(f"Method not found: {class_name}.{func_name}")
        if len(methods) > 1:
            raise ValueError(f"Multiple methods found: {class_name}.{func_name}")
        return _replace_in_lines(original, methods[0], replacement)

    # add_function
    class_name, func_name = _parse_target(target)
    if class_name is not None:
        raise ValueError("add_function supports top-level target names only")
    new_func = _extract_single_function(replacement)
    if getattr(new_func, "name", "") != func_name:
        raise ValueError("ast_patch code function name must match target")

    if original and not original.endswith("\n"):
        original += "\n"
    separator = "\n" if original and not original.endswith("\n\n") else ""
    return f"{original}{separator}{replacement}"
