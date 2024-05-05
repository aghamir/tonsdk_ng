import copy
import math
import typing
from hashlib import sha256
from typing import NamedTuple

from typing_extensions import Self

from tonsdk_ng.utils import (
    bytes_to_b64str,
    crc32c,
    read_n_bytes_uint_from_array,
    tree_walk,
)

from ._bit_string import BitString

if typing.TYPE_CHECKING:
    from ._slice import Slice


class Cell:
    REACH_BOC_MAGIC_PREFIX = bytes.fromhex("B5EE9C72")
    LEAN_BOC_MAGIC_PREFIX = bytes.fromhex("68ff65f3")
    LEAN_BOC_MAGIC_PREFIX_CRC = bytes.fromhex("acc3a728")

    def __init__(self) -> None:
        self.bits = BitString(1023)
        self.refs: list[Cell] = []
        self.is_exotic = False

    def __repr__(self) -> str:
        return "<Cell refs_num: %d, %s>" % (len(self.refs), repr(self.bits))

    def __bool__(self) -> bool:
        return bool(self.bits.cursor) or bool(self.refs)

    def bytes_hash(self) -> bytes:
        return sha256(self.bytes_repr()).digest()

    def bytes_repr(self) -> bytes:
        repr_array = list()
        repr_array.append(self.get_data_with_descriptors())
        for ref in self.refs:
            repr_array.append(ref.get_max_depth_as_array())
        for ref in self.refs:
            repr_array.append(ref.bytes_hash())
        return b"".join(repr_array)

    def write_cell(self, another_cell: Self) -> None:
        self.bits.write_bit_string(another_cell.bits)
        self.refs += another_cell.refs

    def get_data_with_descriptors(self) -> bytes:
        d1 = self.get_refs_descriptor()
        d2 = self.get_bits_descriptor()
        tuBits = self.bits.get_top_upped_array()
        return d1 + d2 + tuBits

    def get_bits_descriptor(self) -> bytearray:
        d2 = bytearray([0])
        d2[0] = math.ceil(self.bits.cursor / 8) + math.floor(
            self.bits.cursor / 8
        )
        return d2

    def get_refs_descriptor(self) -> bytearray:
        d1 = bytearray([0])
        d1[0] = len(self.refs) + self.is_exotic * 8 + self.get_max_level() * 32
        return d1

    def get_max_level(self) -> int:
        if self.is_exotic:
            raise NotImplementedError(
                "Calculating max level for exotic cells is not implemented"
            )
        max_level = 0
        for r in self.refs:
            r_max_level = r.get_max_level()
            if r_max_level > max_level:
                max_level = r_max_level
        return max_level

    def get_max_depth_as_array(self) -> bytearray:
        max_depth = self.get_max_depth()
        return bytearray([max_depth // 256, max_depth % 256])

    def get_max_depth(self) -> int:
        max_depth = 0
        if len(self.refs) > 0:
            for r in self.refs:
                r_max_depth = r.get_max_depth()
                if r_max_depth > max_depth:
                    max_depth = r_max_depth
            max_depth += 1
        return max_depth

    def tree_walk(self) -> tuple[list[tuple[bytes, "Cell"]], dict[bytes, int]]:
        return tree_walk(self, [], {})

    def is_explicitly_stored_hashes(self) -> int:
        return 0

    def serialize_for_boc(
        self, cells_index: dict[bytes, int], ref_size: int
    ) -> bytes:
        repr_arr = []

        repr_arr.append(self.get_data_with_descriptors())
        if self.is_explicitly_stored_hashes():
            raise NotImplementedError(
                "Cell hashes explicit storing is not implemented"
            )

        for ref in self.refs:
            ref_hash = ref.bytes_hash()
            ref_index_int = cells_index[ref_hash]
            ref_index_hex = format(ref_index_int, "x")
            if len(ref_index_hex) % 2:
                ref_index_hex = "0" + ref_index_hex
            reference = bytes.fromhex(ref_index_hex)
            repr_arr.append(reference)

        return b"".join(repr_arr)

    def boc_serialization_size(
        self, cells_index: dict[bytes, int], ref_size: int
    ) -> int:
        return len(self.serialize_for_boc(cells_index, ref_size))

    def to_boc(
        self,
        has_idx: bool = True,
        hash_crc32: bool = True,
        has_cache_bits: bool = False,
        flags: int = 0,
    ) -> bytes:
        root_cell = copy.deepcopy(self)

        all_cells = root_cell.tree_walk()
        topological_order = all_cells[0]
        cells_index = all_cells[1]

        cells_num = len(topological_order)
        # Minimal number of bits to represent reference (unused?)
        s = len(f"{cells_num:b}")
        s_bytes = max(math.ceil(s / 8), 1)
        full_size = 0
        cell_sizes = {}
        for _hash, subcell in topological_order:
            cell_sizes[_hash] = subcell.boc_serialization_size(
                cells_index, s_bytes
            )
            full_size += cell_sizes[_hash]

        offset_bits = len(f"{full_size:b}")
        offset_bytes = max(math.ceil(offset_bits / 8), 1)

        serialization = BitString(
            (1023 + 32 * 4 + 32 * 3) * len(topological_order)
        )
        serialization.write_bytes(Cell.REACH_BOC_MAGIC_PREFIX)
        settings = bytes(
            "".join(
                [
                    "1" if i else "0"
                    for i in [has_idx, hash_crc32, has_cache_bits]
                ]
            ),
            "utf-8",
        )
        serialization.write_bit_array(settings)
        serialization.write_uint(flags, 2)
        serialization.write_uint(s_bytes, 3)
        serialization.write_uint8(offset_bytes)
        serialization.write_uint(cells_num, s_bytes * 8)
        serialization.write_uint(1, s_bytes * 8)  # One root for now
        serialization.write_uint(0, s_bytes * 8)  # Complete BOCs only
        serialization.write_uint(full_size, offset_bytes * 8)
        serialization.write_uint(0, s_bytes * 8)  # Root shoulh have index 0

        if has_idx:
            for _hash, subcell in topological_order:
                serialization.write_uint(cell_sizes[_hash], offset_bytes * 8)

        for cell_info in topological_order:
            ref_cell_ser = cell_info[1].serialize_for_boc(cells_index, s_bytes)
            serialization.write_bytes(ref_cell_ser)

        ser_arr = serialization.get_top_upped_array()
        if hash_crc32:
            ser_arr += crc32c(ser_arr)

        return ser_arr

    def to_boc_b64str(
        self,
        has_idx: bool = True,
        hash_crc32: bool = True,
        has_cache_bits: bool = False,
        flags: int = 0,
    ) -> str:
        return bytes_to_b64str(
            self.to_boc(
                has_idx=has_idx,
                hash_crc32=hash_crc32,
                has_cache_bits=has_cache_bits,
                flags=flags,
            )
        )

    def begin_parse(self) -> Slice:
        from ._slice import Slice

        return Slice(self)

    @staticmethod
    def one_from_boc(serialized_boc: str | bytes) -> "Cell":
        cells = deserialize_boc(serialized_boc)

        if len(cells) != 1:
            raise Exception("Expected 1 root cell")

        return cells[0]


def deserialize_cell_data(
    cell_data: bytes, reference_index_size: int
) -> dict[str, Cell | bytes]:
    if len(cell_data) < 2:
        raise Exception("Not enough bytes to encode cell descriptors")

    d1, d2 = cell_data[0], cell_data[1]
    cell_data = cell_data[2:]
    math.floor(d1 / 32)
    is_exotic = d1 & 8
    ref_num = d1 % 8
    data_bytes_size = math.ceil(d2 / 2)
    fullfilled_bytes = not (d2 % 2)

    cell = Cell()
    cell.is_exotic = bool(is_exotic)

    if len(cell_data) < data_bytes_size + reference_index_size * ref_num:
        raise Exception("Not enough bytes to encode cell data")

    cell.bits.set_top_upped_array(
        bytearray(cell_data[:data_bytes_size]), fullfilled_bytes
    )
    cell_data = cell_data[data_bytes_size:]
    for r in range(ref_num):
        cell.refs.append(
            read_n_bytes_uint_from_array(reference_index_size, cell_data)
        )
        cell_data = cell_data[reference_index_size:]

    return {"cell": cell, "residue": cell_data}


class ParsedBocHeader(NamedTuple):
    has_idx: bool
    hash_crc32: bool
    has_cache_bits: bool
    flags: int
    size_bytes: int
    off_bytes: int
    cells_num: int
    roots_num: int
    absent_num: int
    tot_cells_size: int
    root_list: list[int]
    index_: list[int]
    cells_data: bytes


def parse_boc_header(serialized_boc: bytes) -> ParsedBocHeader:
    if len(serialized_boc) < 4 + 1:
        raise Exception("Not enough bytes for magic prefix")

    input_data = serialized_boc
    prefix = serialized_boc[:4]
    serialized_boc = serialized_boc[4:]

    match prefix:
        case Cell.REACH_BOC_MAGIC_PREFIX:
            flags_byte = serialized_boc[0]
            has_idx = bool(flags_byte & 128)
            hash_crc32 = bool(flags_byte & 64)
            has_cache_bits = bool(flags_byte & 32)
            flags = (flags_byte & 16) * 2 + (flags_byte & 8)
            size_bytes = flags_byte % 8
        case Cell.LEAN_BOC_MAGIC_PREFIX:
            has_idx = True
            hash_crc32 = False
            has_cache_bits = False
            flags = 0
            size_bytes = serialized_boc[0]
        case Cell.LEAN_BOC_MAGIC_PREFIX_CRC:
            has_idx = True
            hash_crc32 = True
            has_cache_bits = False
            flags = 0
            size_bytes = serialized_boc[0]

    serialized_boc = serialized_boc[1:]

    if len(serialized_boc) < 1 + 5 * size_bytes:
        raise Exception("Not enough bytes for encoding cells counters")

    offset_bytes = serialized_boc[0]
    serialized_boc = serialized_boc[1:]
    cells_num = read_n_bytes_uint_from_array(size_bytes, serialized_boc)
    serialized_boc = serialized_boc[size_bytes:]
    roots_num = read_n_bytes_uint_from_array(size_bytes, serialized_boc)
    serialized_boc = serialized_boc[size_bytes:]
    absent_num = read_n_bytes_uint_from_array(size_bytes, serialized_boc)
    serialized_boc = serialized_boc[size_bytes:]
    tot_cells_size = read_n_bytes_uint_from_array(offset_bytes, serialized_boc)
    serialized_boc = serialized_boc[offset_bytes:]

    if len(serialized_boc) < roots_num * size_bytes:
        raise Exception("Not enough bytes for encoding root cells hashes")

    root_list = []
    for c in range(roots_num):
        root_list.append(
            read_n_bytes_uint_from_array(size_bytes, serialized_boc)
        )
        serialized_boc = serialized_boc[size_bytes:]

    index = []
    if has_idx:
        if len(serialized_boc) < offset_bytes * cells_num:
            raise Exception("Not enough bytes for index encoding")
        for c in range(cells_num):
            index.append(
                read_n_bytes_uint_from_array(offset_bytes, serialized_boc)
            )
            serialized_boc = serialized_boc[offset_bytes:]

    if len(serialized_boc) < tot_cells_size:
        raise Exception("Not enough bytes for cells data")
    cells_data = serialized_boc[:tot_cells_size]
    serialized_boc = serialized_boc[tot_cells_size:]

    if hash_crc32:
        if len(serialized_boc) < 4:
            raise Exception("Not enough bytes for crc32c hashsum")

        length = len(input_data)
        if crc32c(input_data[: length - 4]) != serialized_boc[:4]:
            raise Exception("Crc32c hashsum mismatch")

        serialized_boc = serialized_boc[4:]

    if len(serialized_boc):
        raise Exception("Too much bytes in BoC serialization")

    return ParsedBocHeader(
        has_idx=has_idx,
        hash_crc32=hash_crc32,
        has_cache_bits=has_cache_bits,
        flags=flags,
        size_bytes=size_bytes,
        off_bytes=offset_bytes,
        cells_num=cells_num,
        roots_num=roots_num,
        absent_num=absent_num,
        tot_cells_size=tot_cells_size,
        root_list=root_list,
        index_=index,
        cells_data=cells_data,
    )


def deserialize_boc(serialized_boc: str | bytes) -> list[Cell]:
    if isinstance(serialized_boc, str):
        serialized_boc = bytes.fromhex(serialized_boc)

    header = parse_boc_header(serialized_boc)
    cells_data = header.cells_data
    cells_array: list[Cell] = []

    for ci in range(header.cells_num):
        dd = deserialize_cell_data(cells_data, header.size_bytes)
        cells_data = dd["residue"]
        cells_array.append(dd["cell"])

    for ci in reversed(range(header.cells_num)):
        c = cells_array[ci]
        for ri in range(len(c.refs)):
            r = c.refs[ri]
            if r < ci:
                raise Exception("Topological order is broken")
            c.refs[ri] = cells_array[r]

    root_cells = []
    for ri in header.root_list:
        root_cells.append(cells_array[ri])

    return root_cells
