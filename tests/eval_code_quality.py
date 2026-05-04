#!/usr/bin/env python3
"""
Code Quality Eval — Pre-Commit Quality Checks
===============================================
Validates Python source files for syntax errors, hardcoded secrets,
and broken intra-package imports.

This script is domain-agnostic — use it as-is in any Python project.

Usage:
    python tests/eval_code_quality.py [--src path/to/src]

Exit code 0 = all checks passed, exit code 1 = issues found.
"""

import ast
import re
import sys
from pathlib import Path

# Patterns that suggest hardcoded secrets
SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|secret|password|token|credential)\s*=\s*['\"][^'\"]{8,}", "Possible hardcoded secret"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Possible hardcoded bearer token"),
    (r"(?i)(?:sk|pk)[-_](?:live|test)[-_][a-zA-Z0-9]{20,}", "Possible API key"),
]


def check_syntax(src_dir):
    """Verify all .py files compile without syntax errors."""
    issues = []
    for py_file in sorted(src_dir.glob("*.py")):
        try:
            source = py_file.read_text()
            ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            issues.append(f"{py_file.name}:{e.lineno}: {e.msg}")
    return issues


def check_secrets(src_dir):
    """Scan for hardcoded secret patterns."""
    issues = []
    for py_file in sorted(src_dir.glob("*.py")):
        source = py_file.read_text()
        for pattern, label in SECRET_PATTERNS:
            matches = re.finditer(pattern, source)
            for m in matches:
                line_num = source[:m.start()].count("\n") + 1
                issues.append(f"{py_file.name}:{line_num}: {label}")
    return issues


def check_imports(src_dir):
    """Verify intra-package imports resolve to existing files."""
    issues = []
    module_names = {f.stem for f in src_dir.glob("*.py")}

    for py_file in sorted(src_dir.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError:
            continue  # Already caught by check_syntax

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top_module = node.module.split(".")[0]
                if top_module in module_names and top_module != py_file.stem:
                    target = src_dir / f"{top_module}.py"
                    if not target.exists():
                        issues.append(
                            f"{py_file.name}:{node.lineno}: "
                            f"imports from '{node.module}' but {top_module}.py not found"
                        )
    return issues


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Code Quality Eval")
    parser.add_argument("--src", default=None, help="Path to src/ directory")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_dir = script_dir.parent
    src_dir = Path(args.src) if args.src else repo_dir / "src"

    results = {
        "syntax": check_syntax(src_dir),
        "secrets": check_secrets(src_dir),
        "imports": check_imports(src_dir),
    }

    total_issues = sum(len(v) for v in results.values())
    passed = total_issues == 0

    print(f"Code Quality: {'PASSED' if passed else 'FAILED'} ({total_issues} issues)")
    for category, issues in results.items():
        mark = "+" if not issues else "X"
        print(f"  [{mark}] {category}: {len(issues)} issues")
        for issue in issues:
            print(f"      {issue}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
