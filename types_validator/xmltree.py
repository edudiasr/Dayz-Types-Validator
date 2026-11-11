"""Leitor de XML que guarda o número da linha de cada elemento.

O ElementTree da biblioteca padrão não informa linhas, e um relatório de
erros sem linha não ajuda quem está editando um types.xml com milhares de
entradas. Por isso a árvore é montada direto com o expat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.parsers import expat


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    line: int
    children: list[Node] = field(default_factory=list)
    text: str = ""

    def find_all(self, tag: str) -> list[Node]:
        return [child for child in self.children if child.tag == tag]


class XmlSyntaxError(Exception):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def parse(data: bytes) -> Node:
    parser = expat.ParserCreate()
    stack: list[Node] = []
    texts: list[list[str]] = []
    root: Node | None = None

    def start(tag: str, attrs: dict[str, str]) -> None:
        nonlocal root
        node = Node(tag, dict(attrs), parser.CurrentLineNumber)
        if stack:
            stack[-1].children.append(node)
        else:
            root = node
        stack.append(node)
        texts.append([])

    def end(_tag: str) -> None:
        node = stack.pop()
        node.text = "".join(texts.pop()).strip()

    def chars(data: str) -> None:
        if texts:
            texts[-1].append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars

    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise XmlSyntaxError(expat.ErrorString(exc.code), exc.lineno, exc.offset + 1) from None

    if root is None:
        raise XmlSyntaxError("arquivo vazio", 1, 1)
    return root
