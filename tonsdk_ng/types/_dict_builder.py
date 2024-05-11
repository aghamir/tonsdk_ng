from typing_extensions import Self

from ._cell import Cell
from ._dict import serialize_dict


class DictBuilder:
    def __init__(self, key_size: int):
        self.key_size = key_size
        self.items: dict[int, Cell] = {}
        self.ended = False

    def store_cell(self, index: int | bytes, value: Cell) -> Self:
        assert self.ended is False, "Already ended"
        if isinstance(index, bytes):
            index = int(index.hex(), 16)

        assert isinstance(index, int), "Invalid index type"
        assert index not in self.items, f"Item {index} already exist"
        self.items[index] = value
        return self

    def store_ref(self, index: int | bytes, value: Cell) -> Self:
        assert self.ended is False, "Already ended"

        cell = Cell()
        cell.refs.append(value)
        self.store_cell(index, cell)
        return self

    def end_dict(self) -> Cell:
        assert self.ended is False, "Already ended"
        self.ended = True
        if not self.items:
            return Cell()  # ?

        def default_serializer(src: Cell, dest: Cell) -> None:
            dest.write_cell(src)

        return serialize_dict(self.items, self.key_size, default_serializer)

    def end_cell(self) -> Cell:
        assert self.ended is False, "Already ended"
        assert self.items, "Dict is empty"
        return self.end_dict()


def begin_dict(key_size: int) -> DictBuilder:
    return DictBuilder(key_size)
