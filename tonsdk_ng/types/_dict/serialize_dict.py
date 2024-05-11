from collections.abc import Callable
from math import ceil, log2
from typing import Literal

from typing_extensions import NamedTuple

from .._bit_string import BitString
from .._cell import Cell
from .find_common_prefix import find_common_prefix

Serializer = Callable[[Cell, Cell], None]
Source = dict[str, Cell]
SourceInt = dict[int, Cell]


class Node(NamedTuple):
    kind: Literal["fork", "leaf"]
    value: Cell | None = None
    left: "Edge" | None = None
    right: "Edge" | None = None


class Edge(NamedTuple):
    label: str
    node: Node


def pad(src: str, size: int) -> str:
    return f"{src:0>{size}}"


def remove_prefix_map(src: Source, length: int) -> Source:
    if length == 0:
        return src
    else:
        return {k[length:]: v for k, v in src.items()}


def fork_map(src: Source) -> tuple[Source, Source]:
    assert len(src) > 0, "Internal inconsistency"
    left = {}
    right = {}
    for k, v in src.items():
        if k.startswith("0"):
            left[k[1:]] = v
        else:
            right[k[1:]] = v

    assert len(left) > 0, "Internal inconsistency. Left empty."
    assert len(right) > 0, "Internal inconsistency. Left empty."
    return left, right


def build_node(src: Source) -> Node:
    assert len(src) > 0, "Internal inconsistency"
    if len(src) == 1:
        value: Cell = next(iter(src.values()))
        return Node(kind="leaf", value=value)

    left, right = fork_map(src)
    return Node(
        kind="fork",
        left=build_edge(left),
        right=build_edge(right),
    )


def build_edge(src: Source) -> Edge:
    assert len(src) > 0, "Internal inconsistency"
    label = find_common_prefix(list(src.keys()))
    return Edge(
        label=label,
        node=build_node(remove_prefix_map(src, len(label))),
    )


def build_tree(src: SourceInt, key_size: int) -> Edge:
    # Convert map keys
    tree = {pad(bin(k)[2:], key_size): v for k, v in src.items()}
    # Calculate root label
    return build_edge(tree)


# Serialization
def write_label_short(src: str, to: BitString) -> BitString:
    # Header
    to.write_bit(0)

    # Unary length
    for e in src:
        to.write_bit(1)
    to.write_bit(0)

    # Value
    for e in src:
        to.write_bit(e == "1")

    return to


def label_short_length(src: str) -> int:
    return 1 + len(src) + 1 + len(src)


def write_label_long(src: str, key_length: int, to: BitString) -> BitString:
    # Header
    to.write_bit(1)
    to.write_bit(0)

    # Length
    length = ceil(log2(key_length + 1))
    to.write_uint(len(src), length)

    # Value
    for e in src:
        to.write_bit(e == "1")

    return to


def label_long_length(src: str, key_length: int) -> int:
    return 1 + 1 + ceil(log2(key_length + 1)) + len(src)


def write_label_same(
    value: bool, length: int, key_length: int, to: BitString
) -> None:
    to.write_bit(1)
    to.write_bit(1)

    to.write_bit(value)

    len_len = ceil(log2(key_length + 1))
    to.write_uint(length, len_len)


def label_same_length(key_size: int) -> int:
    return 1 + 1 + 1 + ceil(log2(key_size + 1))


def is_same(src: str) -> bool:
    if len(src) == 0 or len(src) == 1:
        return True

    return all(e == src[0] for e in src[1:])


def detect_label_type(src: str, key_size: int) -> str:
    kind = "short"
    kind_length = label_short_length(src)

    long_length = label_long_length(src, key_size)
    if long_length < kind_length:
        kind_length = long_length
        kind = "long"

    if is_same(src):
        same_length = label_same_length(key_size)
        if same_length < kind_length:
            kind_length = same_length
            kind = "same"

    return kind


def write_label(src: str, key_size: int, to: BitString) -> None:
    match detect_label_type(src, key_size):
        case "short":
            write_label_short(src, to)
        case "long":
            write_label_long(src, key_size, to)
        case "same":
            write_label_same(src[0] == "1", len(src), key_size, to)


def write_node(
    src: Node, key_size: int, serializer: Serializer, to: Cell
) -> None:
    match src.kind:
        case "leaf":
            assert src.value is not None
            serializer(src.value, to)
        case "fork":
            left_cell = Cell()
            right_cell = Cell()
            assert src.left is not None and src.right is not None
            write_edge(src.left, key_size - 1, serializer, left_cell)
            write_edge(src.right, key_size - 1, serializer, right_cell)
            to.refs.append(left_cell)
            to.refs.append(right_cell)


def write_edge(
    src: Edge, key_size: int, serializer: Serializer, to: Cell
) -> None:
    write_label(src.label, key_size, to.bits)
    write_node(src.node, key_size - len(src.label), serializer, to)


def serialize_dict(
    src: SourceInt, key_size: int, serializer: Serializer
) -> Cell:
    tree = build_tree(src, key_size)
    dest = Cell()
    write_edge(tree, key_size, serializer, dest)
    return dest


__all__ = [
    "serialize_dict",
]
