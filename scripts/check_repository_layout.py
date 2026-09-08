"""Enforce game-scoped results, the Markdown allow-list and one-line comments and docstrings."""

import ast
import io
import os
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


ROOT_DOCUMENTS = {"README.md", "AGENTS.md", "VALIDATION.md"}


def allowed_markdown(name):
    parts = Path(name).parts
    if len(parts) == 1:
        return name in ROOT_DOCUMENTS
    if parts[0] == "snapshots":
        return name == "snapshots/README.md" or (len(parts) == 4 and parts[3] == "README.md")
    return (
        len(parts) == 4
        and parts[:2] == ("gamecua", "games")
        and parts[3] in ("README.md", "VALIDATION.md")
    ) or parts[0] == "experiments"


def validate_layout(root, branch):
    errors = []
    results = root / "experiments"
    for game in results.iterdir() if results.is_dir() else ():
        if not game.is_dir():
            errors.append(f"Results must be inside a game directory: {game}")
            continue
        for entry in game.iterdir():
            if entry.name == ".gitkeep":
                continue
            if not entry.is_dir():
                errors.append(f"Results must be inside a bundle directory: {entry}")
            elif branch != "experiments" and entry.name != "demo":
                errors.append(f"Only demos belong in experiments/ on main: {entry}")
    paths = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root, text=True
    ).splitlines()
    for name in paths:
        path = root / name
        if path.suffix == ".md" and not allowed_markdown(name):
            errors.append(f"Markdown is limited to the root documents and game guides: {name}")
        if path.suffix != ".py" or not path.exists():
            continue
        source = path.read_text()
        tree = ast.parse(source)
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and token.start[0] > 1:
                errors.append(
                    f"Only a one-line file header comment is allowed: {name}:{token.start[0]}"
                )
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and "\n" in (ast.get_docstring(node) or ""):
                errors.append(f"Docstrings are one line: {name}:{getattr(node, 'lineno', 1)}")
    return errors


def main():
    branch = (
        os.getenv("GITHUB_BASE_REF")
        or os.getenv("GITHUB_HEAD_REF")
        or os.getenv("GITHUB_REF_NAME")
        or subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    )
    errors = validate_layout(ROOT, branch)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Repository layout valid for {branch}")


if __name__ == "__main__":
    main()
