import ast

from conftest import ROOT

FORBIDDEN_IMPORTS = ("src.alpha", "src.portfolio", "src.backtest", "src.preprocessing",
                     "src.data.providers", "src.data.quality", "src.data.validation",
                     "src.data.cli", "src.data.io")
FORBIDDEN_CALLS = {"read_csv", "read_parquet", "read_json", "read_excel", "loadtxt",
                   "read_text", "read_bytes", "fit", "fit_transform", "fillna",
                   "open", "__import__", "eval", "exec"}


def import_names(node, package):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        base = package[:len(package) - node.level + 1] if node.level else []
        if node.module:
            base += node.module.split(".")
        prefix = ".".join(base)
        return [prefix] + [prefix + "." + alias.name for alias in node.names]
    return []


def test_feature_modules_do_not_bypass_pit_or_import_targets():
    for path in (ROOT / "src/features").rglob("*.py"):
        tree = ast.parse(path.read_text())
        package = list(path.relative_to(ROOT).parts[:-1])
        for node in ast.walk(tree):
            names = import_names(node, package)
            assert not any(name == prefix or name.startswith(prefix + ".")
                           for name in names for prefix in FORBIDDEN_IMPORTS), path
            if isinstance(node, ast.Call):
                call = (node.func.attr if isinstance(node.func, ast.Attribute)
                        else node.func.id if isinstance(node.func, ast.Name) else "")
                assert call not in FORBIDDEN_CALLS, (path, call)
            if isinstance(node, ast.Attribute):
                assert node.attr != "_bundle", path


def test_architecture_audit_resolves_relative_and_from_imports():
    for code, package in [("from ...alpha import labels", ["src", "features", "nested"]),
                          ("from src import alpha", ["src", "features"]),
                          ("from src.data import providers", ["src", "features"])]:
        names = import_names(ast.parse(code).body[0], package)
        assert any(name == prefix or name.startswith(prefix + ".")
                   for name in names for prefix in FORBIDDEN_IMPORTS)
