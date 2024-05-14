from ._address import Address
from ._bit_string import BitString
from ._cell import Cell
from ._slice import Slice


class Builder:
    def __init__(self) -> None:
        self.bits = BitString(1023)
        self.refs: list[Cell] = []
        self.is_exotic = False

    def __repr__(self) -> str:
        return "<Builder refs_num: %d, %s>" % (len(self.refs), repr(self.bits))

    def store_cell(self, src: Cell) -> "Builder":
        self.bits.write_bit_string(src.bits)
        self.refs += src.refs
        return self

    def store_ref(self, src: Cell) -> "Builder":
        self.refs.append(src)
        return self

    def store_maybe_ref(self, src: Cell | None) -> "Builder":
        if src:
            self.bits.write_bit(1)
            self.store_ref(src)
        else:
            self.bits.write_bit(0)

        return self

    def store_slice(self, src: Slice) -> "Builder":
        if len(self.refs) + len(src.refs) > 4:
            raise ValueError("refs overflow")
        self.bits.write_bit_array(src.bits)
        for i in range(src.ref_offset, len(src.refs)):
            self.store_ref(src.refs[i])
        return self

    def store_maybe_slice(self, src: Slice | None) -> "Builder":
        if src is not None:
            self.bits.write_bit(1)
            self.store_slice(src)
        else:
            self.bits.write_bit(0)
        return self

    def store_bit(self, value: int) -> "Builder":
        self.bits.write_bit(value)
        return self

    def store_bit_array(self, value: bytes | bytearray) -> "Builder":
        self.bits.write_bit_array(value)
        return self

    def store_uint(self, value: int, bit_length: int) -> "Builder":
        self.bits.write_uint(value, bit_length)
        return self

    def store_uint8(self, value: int) -> "Builder":
        self.bits.write_uint8(value)
        return self

    def store_int(self, value: int, bit_length: int) -> "Builder":
        self.bits.write_int(value, bit_length)
        return self

    def store_string(self, value: str) -> "Builder":
        self.bits.write_string(value)
        return self

    def store_bytes(self, value: bytes) -> "Builder":
        self.bits.write_bytes(value)
        return self

    def store_bit_string(self, value: BitString) -> "Builder":
        self.bits.write_bit_string(value)
        return self

    def store_address(self, value: Address) -> "Builder":
        self.bits.write_address(value)
        return self

    def store_grams(self, value: int) -> "Builder":
        self.bits.write_grams(value)
        return self

    def store_coins(self, value: int) -> "Builder":
        self.bits.write_coins(value)
        return self

    def end_cell(self) -> Cell:
        cell = Cell()
        cell.bits = self.bits
        cell.refs = self.refs
        cell.is_exotic = self.is_exotic
        return cell


def begin_cell() -> Builder:
    return Builder()
