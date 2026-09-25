import ast

from conftest import ROOT


def test_preprocessing_does_not_read_qa_or_fit_other_splits():
    forbidden = ("artifacts", "src.features.quality", "src.data.providers", "src.alpha",
                 "src.portfolio", "src.backtest")
    for path in (ROOT / "src/preprocessing").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            assert not any(name == item or name.startswith(item + ".")
                           for name in names for item in forbidden), path
        source = path.read_text()
        assert "fit_transform" not in source
        assert "StandardScaler" not in source
        assert "PCA" not in source
