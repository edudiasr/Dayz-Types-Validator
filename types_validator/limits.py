"""Leitura do cfglimitsdefinition.xml e do cfglimitsdefinitionuser.xml.

Esses arquivos definem quais nomes de category, tag, usage e value existem.
Um types.xml que usa um nome fora dessas listas faz o item não nascer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .xmltree import Node, parse

# elemento-pai no arquivo de limites -> (tipo usado no types.xml, filho com nome)
_SECTIONS = {
    "categories": ("category", "category"),
    "tags": ("tag", "tag"),
    "usageflags": ("usage", "usage"),
    "valueflags": ("value", "value"),
}


@dataclass
class Limits:
    names: dict[str, set[str]] = field(default_factory=dict)
    user_names: dict[str, set[str]] = field(default_factory=dict)

    def knows(self, kind: str) -> bool:
        return bool(self.names.get(kind))

    def knows_user(self, kind: str) -> bool:
        return bool(self.user_names.get(kind))

    def merge_file(self, data: bytes) -> None:
        self._walk(parse(data))

    def _walk(self, node: Node) -> None:
        section = _SECTIONS.get(node.tag)
        if section:
            kind, child_tag = section
            for child in node.children:
                name = child.attrs.get("name")
                if not name:
                    continue
                if child.tag == child_tag:
                    self.names.setdefault(kind, set()).add(name.lower())
                elif child.tag == "user":
                    self.user_names.setdefault(kind, set()).add(name.lower())
            return
        for child in node.children:
            self._walk(child)
