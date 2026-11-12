"""Regras de validação do types.xml da Central Economy do DayZ."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from .limits import Limits
from .xmltree import Node, XmlSyntaxError, parse

NUMERIC_TAGS = ("nominal", "lifetime", "restock", "min", "quantmin", "quantmax", "cost")
SINGLE_TAGS = (*NUMERIC_TAGS, "flags", "category")
REPEATABLE_TAGS = ("usage", "value", "tag")
REQUIRED_TAGS = (*NUMERIC_TAGS, "flags")
FLAG_ATTRS = (
    "count_in_cargo",
    "count_in_hoarder",
    "count_in_map",
    "count_in_player",
    "crafted",
    "deloot",
)


class Severity(str, Enum):
    ERROR = "erro"
    WARNING = "aviso"


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str
    message: str
    line: int
    type_name: str | None = None


@dataclass
class Report:
    path: str
    issues: list[Issue] = field(default_factory=list)
    type_count: int = 0
    spawning_count: int = 0
    nominal_by_category: Counter[str] = field(default_factory=Counter)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]


def validate_bytes(data: bytes, path: str = "types.xml", limits: Limits | None = None) -> Report:
    report = _Checker(path, limits).run(data)
    report.issues.sort(key=lambda issue: (issue.line, issue.code))
    return report


class _Checker:
    def __init__(self, path: str, limits: Limits | None) -> None:
        self.report = Report(path)
        self.limits = limits

    def error(self, code: str, message: str, line: int, name: str | None = None) -> None:
        self.report.issues.append(Issue(Severity.ERROR, code, message, line, name))

    def warn(self, code: str, message: str, line: int, name: str | None = None) -> None:
        self.report.issues.append(Issue(Severity.WARNING, code, message, line, name))

    def run(self, data: bytes) -> Report:
        try:
            root = parse(data)
        except XmlSyntaxError as exc:
            self.error("E001", f"XML inválido: {exc.message} (coluna {exc.column})", exc.line)
            return self.report

        if root.tag != "types":
            self.error("E002", f"a raiz do arquivo deve ser <types>, encontrado <{root.tag}>", root.line)
            return self.report

        seen: dict[str, int] = {}
        for node in root.children:
            if node.tag != "type":
                self.warn("W008", f"elemento <{node.tag}> fora de um <type> será ignorado pelo jogo", node.line)
                continue
            self.report.type_count += 1
            name = node.attrs.get("name", "").strip()
            if not name:
                self.error("E003", "<type> sem o atributo name", node.line)
                continue
            key = name.lower()
            if key in seen:
                self.error(
                    "E004",
                    f"tipo duplicado (primeira declaração na linha {seen[key]}); o jogo usa só uma delas",
                    node.line,
                    name,
                )
            else:
                seen[key] = node.line
            self.check_type(node, name)

        return self.report

    def check_type(self, node: Node, name: str) -> None:
        counts = Counter(child.tag for child in node.children)
        for tag in SINGLE_TAGS:
            if counts[tag] > 1:
                self.error("E005", f"<{tag}> declarado {counts[tag]} vezes", node.line, name)
        for tag in REQUIRED_TAGS:
            if counts[tag] == 0:
                self.warn("W002", f"<{tag}> ausente", node.line, name)
        for child in node.children:
            if child.tag not in SINGLE_TAGS and child.tag not in REPEATABLE_TAGS:
                self.warn("W001", f"tag desconhecida <{child.tag}>", child.line, name)

        values = self.check_numbers(node, name)
        self.check_ranges(node, name, values)
        self.check_flags(node, name)
        self.check_named_children(node, name)

        nominal = values.get("nominal") or 0
        if nominal > 0:
            self.report.spawning_count += 1
            category = node.find_all("category")
            label = category[0].attrs.get("name", "?") if category else "(sem categoria)"
            self.report.nominal_by_category[label] += nominal
            if not any(counts[t] for t in ("usage", "value", "category")):
                self.warn(
                    "W003",
                    "nominal > 0 sem <usage>, <value> ou <category>: o item pode não ter onde nascer",
                    node.line,
                    name,
                )

    def check_numbers(self, node: Node, name: str) -> dict[str, int]:
        values: dict[str, int] = {}
        for tag in NUMERIC_TAGS:
            found = node.find_all(tag)
            if not found:
                continue
            child = found[0]
            try:
                values[tag] = int(child.text)
            except ValueError:
                self.error("E006", f"<{tag}> deve ser um número inteiro, encontrado {child.text!r}", child.line, name)
        return values

    def check_ranges(self, node: Node, name: str, values: dict[str, int]) -> None:
        line_of = {tag: node.find_all(tag)[0].line for tag in values}

        for tag in ("nominal", "lifetime", "restock", "min", "cost"):
            if tag in values and values[tag] < 0:
                self.error("E007", f"<{tag}> não pode ser negativo ({values[tag]})", line_of[tag], name)

        # com nominal 0 o item não nasce, então o min não faz diferença
        # (no types.xml do meu servidor eram 172 casos assim, todos de propósito)
        if "min" in values and values.get("nominal", 0) > 0 and values["min"] > values["nominal"]:
            self.error(
                "E008",
                f"min ({values['min']}) maior que nominal ({values['nominal']})",
                line_of["min"],
                name,
            )

        for tag in ("quantmin", "quantmax"):
            value = values.get(tag)
            if value is not None and value != -1 and not 0 <= value <= 100:
                self.error("E009", f"<{tag}> deve ser -1 ou ficar entre 0 e 100 ({value})", line_of[tag], name)

        qmin, qmax = values.get("quantmin"), values.get("quantmax")
        if qmin is not None and qmax is not None:
            if (qmin == -1) != (qmax == -1):
                self.warn("W004", "só um entre quantmin e quantmax é -1; use -1 nos dois ou em nenhum", line_of["quantmin"], name)
            elif qmin > qmax:
                self.error("E010", f"quantmin ({qmin}) maior que quantmax ({qmax})", line_of["quantmin"], name)

    def check_flags(self, node: Node, name: str) -> None:
        for flags in node.find_all("flags")[:1]:
            for attr, value in flags.attrs.items():
                if attr not in FLAG_ATTRS:
                    self.warn("W006", f"atributo desconhecido em <flags>: {attr}", flags.line, name)
                elif value not in ("0", "1"):
                    self.error("E011", f"{attr} deve ser 0 ou 1, encontrado {value!r}", flags.line, name)
            missing = [attr for attr in FLAG_ATTRS if attr not in flags.attrs]
            if missing:
                self.warn("W007", f"<flags> sem: {', '.join(missing)}", flags.line, name)

    def check_named_children(self, node: Node, name: str) -> None:
        for tag in ("category", *REPEATABLE_TAGS):
            seen: set[str] = set()
            unknown: list[tuple[str, bool, int]] = []
            known = 0
            for child in node.find_all(tag):
                ref = child.attrs.get("name") or child.attrs.get("user")
                is_user = "name" not in child.attrs and "user" in child.attrs
                if not ref:
                    self.error("E012", f"<{tag}> sem o atributo name", child.line, name)
                    continue
                key = ref.lower()
                if key in seen:
                    self.warn("W005", f"<{tag} name=\"{ref}\"> repetido", child.line, name)
                seen.add(key)
                if self.exists_in_limits(tag, ref, is_user):
                    known += 1
                else:
                    unknown.append((ref, is_user, child.line))

            for ref, is_user, line in unknown:
                attr = "user" if is_user else "name"
                file = "cfglimitsdefinitionuser.xml" if is_user else "cfglimitsdefinition.xml"
                # usage e value podem ter vários: se sobrou algum que existe, o item ainda nasce por ele
                if tag in ("usage", "value") and known > 0:
                    self.warn("W009", f"<{tag} {attr}=\"{ref}\"> não existe no {file} e é ignorado", line, name)
                else:
                    self.error("E013", f"<{tag} {attr}=\"{ref}\"> não existe no {file}", line, name)

    def exists_in_limits(self, kind: str, ref: str, is_user: bool) -> bool:
        if self.limits is None:
            return True
        if is_user:
            return not self.limits.knows_user(kind) or ref.lower() in self.limits.user_names[kind]
        return not self.limits.knows(kind) or ref.lower() in self.limits.names[kind]
