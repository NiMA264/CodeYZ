import ast
import re


_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


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


def _validate_module_name(module: str) -> None:
    if not _MODULE_RE.match(module):
        raise ValueError("Invalid module target")


def _validate_name(name: str) -> None:
    if not _IDENT_RE.match(name):
        raise ValueError("Invalid import name target")


def _extract_single_import(operation: str, target: str, code: str) -> tuple[str, str | None]:
    code_module = _parse_module(code)
    if len(code_module.body) != 1:
        raise ValueError("Import patch code must contain exactly one import statement")
    stmt = code_module.body[0]

    if operation == "add_import":
        _validate_module_name(target)
        if not isinstance(stmt, ast.Import) or len(stmt.names) != 1:
            raise ValueError("add_import requires code in the form: import module")
        alias = stmt.names[0]
        if alias.asname is not None or alias.name != target:
            raise ValueError("add_import code must exactly match target")
        return target, None

    if operation == "add_from_import":
        module, sep, name = target.rpartition(".")
        if not sep:
            raise ValueError("add_from_import target must be module.name")
        _validate_module_name(module)
        _validate_name(name)
        if not isinstance(stmt, ast.ImportFrom) or len(stmt.names) != 1:
            raise ValueError("add_from_import requires code in the form: from module import name")
        if stmt.level != 0:
            raise ValueError("Relative imports are not supported")
        alias = stmt.names[0]
        if alias.name == "*":
            raise ValueError("Wildcard imports are not supported")
        if alias.asname is not None or stmt.module != module or alias.name != name:
            raise ValueError("add_from_import code must exactly match target")
        return module, name

    raise ValueError("Unsupported ast_patch operation")


def _is_docstring_expr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(getattr(node, "value", None), ast.Constant)
        and isinstance(node.value.value, str)
    )


def _import_insert_line(original: str, module: ast.Module) -> int:
    lines = original.splitlines(keepends=True)
    insert_line = 0
    if lines and lines[0].startswith("#!"):
        insert_line = 1
    if len(lines) > insert_line and re.match(r"^#.*coding[:=]\s*[-\w.]+", lines[insert_line]):
        insert_line += 1

    if module.body and _is_docstring_expr(module.body[0]):
        insert_line = max(insert_line, module.body[0].end_lineno)

    for node in module.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insert_line = max(insert_line, node.end_lineno)

    return insert_line


def _insert_line(original: str, line_no: int, line: str) -> str:
    lines = original.splitlines(keepends=True)
    out = lines[:line_no] + [line] + lines[line_no:]
    return "".join(out)


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
    if operation not in {"replace_function", "add_function", "add_import", "add_from_import"}:
        raise ValueError("Unsupported ast_patch operation")

    original = old_content or ""
    module = _parse_module(original)
    replacement = _normalize_code(code)

    if operation in {"add_import", "add_from_import"}:
        module_name, import_name = _extract_single_import(operation, target, replacement)

        if operation == "add_import":
            for node in module.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == module_name:
                            return original
        else:
            assert import_name is not None
            for node in module.body:
                if isinstance(node, ast.ImportFrom):
                    if node.level != 0:
                        raise ValueError("Relative imports are not supported")
                    for alias in node.names:
                        if alias.name == "*":
                            raise ValueError("Wildcard imports are not supported")
                    if node.module == module_name:
                        names = [alias.name for alias in node.names]
                        if import_name in names:
                            return original
                        merged = f"from {module_name} import {', '.join(names + [import_name])}\n"
                        return _replace_in_lines(original, node, merged)

        insert_line = _import_insert_line(original, module)
        return _insert_line(original, insert_line, replacement)

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
