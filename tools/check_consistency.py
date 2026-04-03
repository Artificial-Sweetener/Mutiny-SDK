#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SECTION_IMPL = "impl"
SECTION_DEMO = "demo"
SECTION_DOCS = "docs"
ALL_SECTIONS = (SECTION_IMPL, SECTION_DEMO, SECTION_DOCS)

RULE_IMPL_CLASS_MISSING = "IMPL_CLASS_MISSING"
RULE_IMPL_MEMBER_MISSING = "IMPL_MEMBER_MISSING"
RULE_IMPL_EXPORT_MISSING = "IMPL_EXPORT_MISSING"
RULE_IMPL_EXPORT_MISMATCH = "IMPL_EXPORT_MISMATCH"

RULE_DEMO_INTERNAL_IMPORT = "DEMO_INTERNAL_IMPORT"
RULE_DEMO_PRIVATE_ACCESS = "DEMO_PRIVATE_ACCESS"
RULE_DEMO_UNKNOWN_METHOD = "DEMO_UNKNOWN_METHOD"
RULE_DEMO_ROOT_IMPORT = "DEMO_ROOT_IMPORT"

RULE_DOCS_DIR_MISSING = "DOCS_DIR_MISSING"
RULE_DOCS_API_REFERENCE_MISSING = "DOCS_API_REFERENCE_MISSING"
RULE_DOCS_SYMBOL_MISSING = "DOCS_SYMBOL_MISSING"
RULE_DOCS_GHOST_SYMBOL = "DOCS_GHOST_SYMBOL"
RULE_DOCS_INTERNAL_REFERENCE = "DOCS_INTERNAL_REFERENCE"
RULE_DOCS_BAD_IMPORT = "DOCS_BAD_IMPORT"

FORBIDDEN_DOC_MODULES = (
    "mutiny.types",
    "mutiny.domain",
    "mutiny.engine",
    "mutiny.services",
    "mutiny.discord",
    "mutiny.config",
)

ROOT_EXPORT_ALIASES = {"JobStatus"}


@dataclass(frozen=True)
class Issue:
    section: str
    rule_id: str
    symbol: str
    location: str
    hint: str


@dataclass(frozen=True)
class StubContract:
    mutiny_classes: set[str]
    config_classes: set[str]
    model_classes: set[str]
    mutiny_members: set[str]
    config_members: set[str]
    model_fields: dict[str, set[str]]
    model_aliases: set[str]
    public_exports: set[str]
    top_level_contract_names: set[str]


@dataclass(frozen=True)
class ModuleClassMap:
    classes: set[str]
    members_by_class: dict[str, set[str]]
    fields_by_class: dict[str, set[str]]
    top_level_assignments: set[str]


@dataclass(frozen=True)
class InitExportInfo:
    lazy_symbols: dict[str, str]
    all_exports: set[str]


def _read_ast(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _format_location(path: Path, line: int | None = None, root: Path | None = None) -> str:
    if root:
        try:
            path_text = path.relative_to(root).as_posix()
        except ValueError:
            path_text = path.as_posix()
    else:
        path_text = path.as_posix()
    if line is None:
        return path_text
    return f"{path_text}:{line}"


def _collect_stub_contract(repo_root: Path) -> StubContract:
    mutiny_stub = repo_root / "mutiny" / "mutiny.pyi"
    config_stub = repo_root / "mutiny" / "config.pyi"
    public_models_stub = repo_root / "mutiny" / "public_models.pyi"
    mutiny_map = _collect_module_classes(mutiny_stub)
    config_map = _collect_module_classes(config_stub)
    public_models_map = _collect_module_classes(public_models_stub)
    public_exports = (
        mutiny_map.classes
        | config_map.classes
        | public_models_map.classes
        | ROOT_EXPORT_ALIASES
        | {"__version__"}
    )
    top_level_contract_names = public_exports - {"__version__"}
    return StubContract(
        mutiny_classes=mutiny_map.classes,
        config_classes=config_map.classes,
        model_classes=public_models_map.classes,
        mutiny_members=mutiny_map.members_by_class.get("Mutiny", set()),
        config_members=config_map.members_by_class.get("Config", set()),
        model_fields=public_models_map.fields_by_class,
        model_aliases=public_models_map.top_level_assignments - public_models_map.classes,
        public_exports=public_exports,
        top_level_contract_names=top_level_contract_names,
    )


def _collect_module_classes(module_path: Path) -> ModuleClassMap:
    tree = _read_ast(module_path)
    classes: set[str] = set()
    members_by_class: dict[str, set[str]] = {}
    fields_by_class: dict[str, set[str]] = {}
    top_level_assignments: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    top_level_assignments.add(target.id)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            top_level_assignments.add(node.target.id)
        if not isinstance(node, ast.ClassDef):
            continue
        classes.add(node.name)
        members: set[str] = set()
        fields: set[str] = set()
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                members.add(member.name)
            if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                fields.add(member.target.id)
            if isinstance(member, ast.Assign):
                for target in member.targets:
                    if isinstance(target, ast.Name):
                        fields.add(target.id)
        members_by_class[node.name] = members
        fields_by_class[node.name] = fields
    return ModuleClassMap(
        classes=classes,
        members_by_class=members_by_class,
        fields_by_class=fields_by_class,
        top_level_assignments=top_level_assignments,
    )


def _collect_init_exports(repo_root: Path) -> InitExportInfo:
    init_path = repo_root / "mutiny" / "__init__.py"
    tree = _read_ast(init_path)
    lazy_symbols: dict[str, str] = {}
    all_exports: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "_LAZY_SYMBOLS" and isinstance(node.value, ast.Dict):
                lazy_symbols = _dict_str_to_str(node.value)
            if target.id == "__all__":
                exports = _extract_export_list(node.value, lazy_symbols)
                if exports:
                    all_exports = exports

    if not all_exports and lazy_symbols:
        all_exports = set(lazy_symbols.keys())
    return InitExportInfo(lazy_symbols=lazy_symbols, all_exports=all_exports)


def _dict_str_to_str(node: ast.Dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in zip(node.keys, node.values, strict=False):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            result[key.value] = value.value
    return result


def _extract_export_list(node: ast.AST, lazy_symbols: dict[str, str]) -> set[str]:
    if isinstance(node, ast.List):
        return {
            element.value
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "list":
        if node.args:
            arg = node.args[0]
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Attribute)
                and isinstance(arg.func.value, ast.Name)
                and arg.func.value.id == "_LAZY_SYMBOLS"
                and arg.func.attr == "keys"
            ):
                return set(lazy_symbols.keys())
    return set()


def check_implementation(repo_root: Path, contract: StubContract) -> list[Issue]:
    issues: list[Issue] = []
    mutiny_impl = _collect_module_classes(repo_root / "mutiny" / "mutiny.py")
    config_impl = _collect_module_classes(repo_root / "mutiny" / "config.py")
    models_impl = _collect_module_classes(repo_root / "mutiny" / "public_models.py")
    init_info = _collect_init_exports(repo_root)

    for class_name in sorted(contract.mutiny_classes):
        if class_name not in mutiny_impl.classes:
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_CLASS_MISSING,
                    symbol=class_name,
                    location="mutiny/mutiny.py",
                    hint=(
                        f"Add `{class_name}` to mutiny/mutiny.py "
                        "or remove it from mutiny/mutiny.pyi."
                    ),
                )
            )

    for class_name in sorted(contract.config_classes):
        if class_name not in config_impl.classes:
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_CLASS_MISSING,
                    symbol=class_name,
                    location="mutiny/config.py",
                    hint=(
                        f"Add `{class_name}` to mutiny/config.py "
                        "or remove it from mutiny/config.pyi."
                    ),
                )
            )

    for class_name in sorted(contract.model_classes):
        if class_name not in models_impl.classes:
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_CLASS_MISSING,
                    symbol=class_name,
                    location="mutiny/public_models.py",
                    hint=(
                        f"Add `{class_name}` to mutiny/public_models.py "
                        "or remove it from mutiny/public_models.pyi."
                    ),
                )
            )

    issues.extend(
        _missing_member_issues(
            class_name="Mutiny",
            expected_members=contract.mutiny_members,
            members_by_class=mutiny_impl.members_by_class,
            module_path="mutiny/mutiny.py",
        )
    )
    issues.extend(
        _missing_field_issues(
            expected_fields=contract.model_fields,
            fields_by_class=models_impl.fields_by_class,
            module_path="mutiny/public_models.py",
        )
    )

    for alias_name in sorted(contract.model_aliases):
        if alias_name not in models_impl.top_level_assignments:
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_EXPORT_MISSING,
                    symbol=alias_name,
                    location="mutiny/public_models.py",
                    hint=f"Define `{alias_name}` in mutiny/public_models.py.",
                )
            )
    issues.extend(
        _missing_member_issues(
            class_name="Config",
            expected_members=contract.config_members,
            members_by_class=config_impl.members_by_class,
            module_path="mutiny/config.py",
        )
    )

    for required in sorted(contract.public_exports):
        if required not in init_info.all_exports:
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_EXPORT_MISSING,
                    symbol=required,
                    location="mutiny/__init__.py",
                    hint=f"Export `{required}` from mutiny/__init__.py.",
                )
            )

    for exported in sorted(init_info.all_exports - contract.public_exports):
        issues.append(
            Issue(
                section=SECTION_IMPL,
                rule_id=RULE_IMPL_EXPORT_MISMATCH,
                symbol=exported,
                location="mutiny/__init__.py",
                hint="Remove unsupported root exports or add them to the canonical public stubs.",
            )
        )

    lazy_keys = set(init_info.lazy_symbols.keys())
    if init_info.all_exports and lazy_keys and init_info.all_exports - {"__version__"} != lazy_keys:
        mismatch = sorted((init_info.all_exports - {"__version__"}) ^ lazy_keys)
        for symbol in mismatch:
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_EXPORT_MISMATCH,
                    symbol=symbol,
                    location="mutiny/__init__.py",
                    hint="Keep __all__ and _LAZY_SYMBOLS in sync.",
                )
            )

    return issues


def _missing_member_issues(
    *,
    class_name: str,
    expected_members: set[str],
    members_by_class: dict[str, set[str]],
    module_path: str,
) -> list[Issue]:
    actual = members_by_class.get(class_name, set())
    return [
        Issue(
            section=SECTION_IMPL,
            rule_id=RULE_IMPL_MEMBER_MISSING,
            symbol=f"{class_name}.{member}",
            location=module_path,
            hint=f"Implement `{member}` on `{class_name}` or remove it from the stub.",
        )
        for member in sorted(expected_members - actual)
    ]


def _missing_field_issues(
    *,
    expected_fields: dict[str, set[str]],
    fields_by_class: dict[str, set[str]],
    module_path: str,
) -> list[Issue]:
    issues: list[Issue] = []
    for class_name, fields in expected_fields.items():
        actual = fields_by_class.get(class_name, set())
        for field_name in sorted(fields - actual):
            issues.append(
                Issue(
                    section=SECTION_IMPL,
                    rule_id=RULE_IMPL_MEMBER_MISSING,
                    symbol=f"{class_name}.{field_name}",
                    location=module_path,
                    hint=f"Add `{field_name}` to `{class_name}` or remove it from the stub.",
                )
            )
    return issues


class _DemoAnalyzer(ast.NodeVisitor):
    def __init__(self, path: Path, root: Path, contract: StubContract) -> None:
        self.path = path
        self.root = root
        self.contract = contract
        self.issues: list[Issue] = []
        self._mutiny_aliases: set[str] = set()
        self._module_aliases: set[str] = set()
        self._mutiny_vars: set[str] = set()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = node.module or ""
        if module_name.startswith("mutiny."):
            self.issues.append(
                Issue(
                    section=SECTION_DEMO,
                    rule_id=RULE_DEMO_INTERNAL_IMPORT,
                    symbol=module_name,
                    location=_format_location(self.path, node.lineno, self.root),
                    hint="Examples must import from the `mutiny` package root only.",
                )
            )
        if module_name == "mutiny":
            for alias in node.names:
                imported = alias.name
                if imported not in self.contract.public_exports:
                    self.issues.append(
                        Issue(
                            section=SECTION_DEMO,
                            rule_id=RULE_DEMO_ROOT_IMPORT,
                            symbol=imported,
                            location=_format_location(self.path, node.lineno, self.root),
                            hint="Examples may import only supported root symbols.",
                        )
                    )
                if imported == "Mutiny":
                    self._mutiny_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith("mutiny."):
                self.issues.append(
                    Issue(
                        section=SECTION_DEMO,
                        rule_id=RULE_DEMO_INTERNAL_IMPORT,
                        symbol=alias.name,
                        location=_format_location(self.path, node.lineno, self.root),
                        hint="Examples must import from the `mutiny` package root only.",
                    )
                )
            if alias.name == "mutiny":
                self._module_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._is_mutiny_constructor_call(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._mutiny_vars.add(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            if self._annotation_mentions_mutiny(node.annotation) or (
                node.value is not None and self._is_mutiny_constructor_call(node.value)
            ):
                self._mutiny_vars.add(node.target.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id in self._mutiny_vars:
            if node.attr.startswith("_"):
                self.issues.append(
                    Issue(
                        section=SECTION_DEMO,
                        rule_id=RULE_DEMO_PRIVATE_ACCESS,
                        symbol=f"{node.value.id}.{node.attr}",
                        location=_format_location(self.path, node.lineno, self.root),
                        hint="Examples must avoid private facade internals.",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id in self._mutiny_vars:
                method_name = node.func.attr
                if method_name not in self.contract.mutiny_members:
                    self.issues.append(
                        Issue(
                            section=SECTION_DEMO,
                            rule_id=RULE_DEMO_UNKNOWN_METHOD,
                            symbol=f"Mutiny.{method_name}",
                            location=_format_location(self.path, node.lineno, self.root),
                            hint="Examples must call methods defined by mutiny/mutiny.pyi.",
                        )
                    )
        self.generic_visit(node)

    def _is_mutiny_constructor_call(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if isinstance(node.func, ast.Name) and node.func.id in self._mutiny_aliases:
            return True
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            return node.func.value.id in self._module_aliases and node.func.attr == "Mutiny"
        return False

    def _annotation_mentions_mutiny(self, annotation: ast.AST) -> bool:
        if isinstance(annotation, ast.Name):
            return annotation.id in self._mutiny_aliases or annotation.id == "Mutiny"
        if isinstance(annotation, ast.Attribute) and isinstance(annotation.value, ast.Name):
            return annotation.value.id in self._module_aliases and annotation.attr == "Mutiny"
        if isinstance(annotation, ast.Subscript):
            return self._annotation_mentions_mutiny(
                annotation.value
            ) or self._annotation_mentions_mutiny(annotation.slice)
        if isinstance(annotation, ast.BinOp):
            return self._annotation_mentions_mutiny(
                annotation.left
            ) or self._annotation_mentions_mutiny(annotation.right)
        return False


def check_demo_compliance(repo_root: Path, contract: StubContract) -> list[Issue]:
    issues: list[Issue] = []
    examples_root = repo_root / "examples"
    if not examples_root.exists():
        return issues

    for path in sorted(examples_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        analyzer = _DemoAnalyzer(path=path, root=repo_root, contract=contract)
        analyzer.visit(_read_ast(path))
        issues.extend(analyzer.issues)

    return issues


def check_docs(repo_root: Path, contract: StubContract) -> list[Issue]:
    issues: list[Issue] = []
    docs_root = repo_root / "docs"
    api_reference = docs_root / "api-reference.md"

    if not docs_root.exists():
        issues.append(
            Issue(
                section=SECTION_DOCS,
                rule_id=RULE_DOCS_DIR_MISSING,
                symbol="docs/",
                location="docs",
                hint="Create docs/ and document the public API.",
            )
        )
        issues.append(
            Issue(
                section=SECTION_DOCS,
                rule_id=RULE_DOCS_API_REFERENCE_MISSING,
                symbol="docs/api-reference.md",
                location="docs/api-reference.md",
                hint="Add docs/api-reference.md for the public API contract.",
            )
        )
        return issues

    if not api_reference.exists():
        issues.append(
            Issue(
                section=SECTION_DOCS,
                rule_id=RULE_DOCS_API_REFERENCE_MISSING,
                symbol="docs/api-reference.md",
                location="docs/api-reference.md",
                hint="Add docs/api-reference.md for the public API contract.",
            )
        )

    markdown_files = sorted(docs_root.rglob("*.md"))
    docs_text = "\n".join(path.read_text(encoding="utf-8") for path in markdown_files)

    for symbol in sorted(_doc_contract_symbols(contract)):
        if not _symbol_present(symbol, docs_text):
            issues.append(
                Issue(
                    section=SECTION_DOCS,
                    rule_id=RULE_DOCS_SYMBOL_MISSING,
                    symbol=symbol,
                    location="docs/api-reference.md",
                    hint=f"Document `{symbol}` in the docs.",
                )
            )

    known_mutiny = contract.mutiny_members | {"Mutiny"}
    known_config = contract.config_members | {"Config"}

    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_DOC_MODULES:
            if re.search(rf"\b{re.escape(forbidden)}\b", text):
                issues.append(
                    Issue(
                        section=SECTION_DOCS,
                        rule_id=RULE_DOCS_INTERNAL_REFERENCE,
                        symbol=forbidden,
                        location=_format_location(path, root=repo_root),
                        hint="Docs must not present internal modules as supported API.",
                    )
                )
        for token, line in _extract_backtick_tokens(text):
            normalized = _normalize_doc_member_token(token)
            if normalized.startswith("Mutiny."):
                member = normalized.split(".", 1)[1]
                if member not in known_mutiny:
                    issues.append(
                        Issue(
                            section=SECTION_DOCS,
                            rule_id=RULE_DOCS_GHOST_SYMBOL,
                            symbol=token,
                            location=_format_location(path, line, repo_root),
                            hint="Remove or correct this Mutiny method reference.",
                        )
                    )
            if normalized.startswith("Config."):
                member = normalized.split(".", 1)[1]
                if member not in known_config:
                    issues.append(
                        Issue(
                            section=SECTION_DOCS,
                            rule_id=RULE_DOCS_GHOST_SYMBOL,
                            symbol=token,
                            location=_format_location(path, line, repo_root),
                            hint="Remove or correct this Config method reference.",
                        )
                    )
        for symbol, line in _extract_invalid_root_imports(text, contract.public_exports):
            issues.append(
                Issue(
                    section=SECTION_DOCS,
                    rule_id=RULE_DOCS_BAD_IMPORT,
                    symbol=symbol,
                    location=_format_location(path, line, repo_root),
                    hint="Docs code examples may import only supported root symbols.",
                )
            )

    return issues


def _doc_contract_symbols(contract: StubContract) -> set[str]:
    symbols: set[str] = set(contract.top_level_contract_names)
    for member in contract.mutiny_members:
        if not member.startswith("__"):
            symbols.add(f"Mutiny.{member}")
    for member in contract.config_members:
        if not member.startswith("__"):
            symbols.add(f"Config.{member}")
    return symbols


def _symbol_present(symbol: str, docs_text: str) -> bool:
    return any(
        re.search(pattern, docs_text)
        for pattern in (rf"\b{re.escape(symbol)}\b", rf"`{re.escape(symbol)}`")
    )


def _extract_backtick_tokens(text: str) -> Iterable[tuple[str, int]]:
    for match in re.finditer(r"`([^`]+)`", text):
        token = match.group(1).strip()
        line = text.count("\n", 0, match.start()) + 1
        if token:
            yield token, line


def _normalize_doc_member_token(token: str) -> str:
    return re.sub(r"\([^`]*\)$", "", token.strip())


def _extract_invalid_root_imports(text: str, public_exports: set[str]) -> Iterable[tuple[str, int]]:
    pattern = re.compile(r"from\s+mutiny\s+import\s+([^\n]+)")
    for match in pattern.finditer(text):
        imported_symbols = [part.strip() for part in match.group(1).split(",")]
        line = text.count("\n", 0, match.start()) + 1
        for imported in imported_symbols:
            if imported and imported not in public_exports:
                yield imported, line


def run_checks(repo_root: Path, section_filter: str | None = None) -> list[Issue]:
    selected = {section_filter} if section_filter else set(ALL_SECTIONS)
    contract = _collect_stub_contract(repo_root)
    issues: list[Issue] = []

    if SECTION_IMPL in selected:
        issues.extend(check_implementation(repo_root, contract))
    if SECTION_DEMO in selected:
        issues.extend(check_demo_compliance(repo_root, contract))
    if SECTION_DOCS in selected:
        issues.extend(check_docs(repo_root, contract))

    return sorted(issues, key=lambda item: (item.section, item.rule_id, item.location, item.symbol))


def render_report(issues: list[Issue], section_filter: str | None = None) -> str:
    section_titles = {
        SECTION_IMPL: "Implementation Gaps",
        SECTION_DEMO: "Demo Compliance Gaps",
        SECTION_DOCS: "Docs Gaps",
    }
    sections = [section_filter] if section_filter else list(ALL_SECTIONS)
    lines: list[str] = []
    total = 0
    for section in sections:
        lines.append(section_titles[section])
        current = [issue for issue in issues if issue.section == section]
        if not current:
            lines.append("- none")
        else:
            total += len(current)
            for issue in current:
                lines.append(
                    f"- [{issue.rule_id}] {issue.symbol} @ {issue.location} :: {issue.hint}"
                )
        lines.append("")
    lines.append(f"Total gaps: {total}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Mutiny public API consistency across stubs, exports, docs, and examples."
    )
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when gaps exist.")
    parser.add_argument("--section", choices=ALL_SECTIONS, help="Run only one section.")
    parser.add_argument("--json-out", type=Path, help="Optional JSON report output path.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root to analyze (defaults to current directory).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    issues = run_checks(repo_root=repo_root, section_filter=args.section)
    print(render_report(issues=issues, section_filter=args.section))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(issue) for issue in issues]
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
