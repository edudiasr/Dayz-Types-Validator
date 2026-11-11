"""Formatação do relatório em texto (terminal) e em JSON."""

from __future__ import annotations

import json

from .validator import Report, Severity

_RED = "\033[31m"
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def to_text(report: Report, color: bool = True) -> str:
    def paint(text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if color else text

    lines = [paint(report.path, _BOLD)]
    for issue in report.issues:
        is_error = issue.severity is Severity.ERROR
        label = paint(f"{issue.severity.value.upper():5}", _RED if is_error else _YELLOW)
        where = f" [{issue.type_name}]" if issue.type_name else ""
        lines.append(f"  linha {issue.line:>5}  {label} {issue.code}{where} {issue.message}")

    errors, warnings = len(report.errors), len(report.warnings)
    if not report.issues:
        lines.append(paint("  nenhum problema encontrado", _GREEN))

    lines.append("")
    lines.append(
        f"  {report.type_count} tipos, {report.spawning_count} com nominal > 0 · "
        f"{paint(f'{errors} erro(s)', _RED if errors else _GREEN)}, "
        f"{paint(f'{warnings} aviso(s)', _YELLOW if warnings else _GREEN)}"
    )

    if report.nominal_by_category:
        lines.append("")
        lines.append("  Nominal total por categoria:")
        width = max(len(name) for name in report.nominal_by_category)
        for name, total in report.nominal_by_category.most_common():
            lines.append(f"    {name:<{width}}  {total:>6}")

    return "\n".join(lines)


def to_json(reports: list[Report]) -> str:
    payload = [
        {
            "file": report.path,
            "types": report.type_count,
            "spawning": report.spawning_count,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "nominal_by_category": dict(report.nominal_by_category.most_common()),
            "issues": [
                {
                    "severity": issue.severity.value,
                    "code": issue.code,
                    "line": issue.line,
                    "type": issue.type_name,
                    "message": issue.message,
                }
                for issue in report.issues
            ],
        }
        for report in reports
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)
