from __future__ import annotations

import copy
import io
import math
from hashlib import sha256
from typing import NamedTuple, TYPE_CHECKING

from tonsdk_ng.utils import bytes_to_b64str, crc32c, tree_walk
from ._bit_string import BitString

if TYPE_CHECKING:
    from ._slice import Slice


class Cell:
    REACH_BOC_MAGIC_PREFIX = bytes.fromhex("b5ee9c72")
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

    def write_cell(self, another_cell: "Cell") -> None:
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
        cells = from_boc_multi_root(serialized_boc)

        if len(cells) != 1:
            raise ValueError("Expected 1 root cell")

        return cells[0]


class Flags(NamedTuple):
    has_index: bool
    has_crc32c: bool
    has_cache_bits: bool

    @staticmethod
    def parse(byte: int) -> "Flags":
        # has_idx:(## 1) has_crc32c:(## 1)  has_cache_bits:(## 1) flags:...
        return Flags(
            has_index=bool(byte & (1 << 7)),
            has_crc32c=bool(byte & (1 << 6)),
            has_cache_bits=bool(byte & (1 << 5)),
        )


def from_boc_multi_root(data: bytes | bytearray | str) -> list[Cell]:
    if isinstance(data, str):
        data = bytes.fromhex(data)

    if len(data) < 10:
        raise ValueError("invalid boc")

    r = io.BytesIO(data)
    match r.read(4):
        case Cell.REACH_BOC_MAGIC_PREFIX:
            byte = big_int(r.read(1))
            cell_num_size_bytes = byte & 0b00000111
            flags = Flags.parse(byte)
        case Cell.LEAN_BOC_MAGIC_PREFIX:
            flags = Flags(
                has_index=True, has_crc32c=False, has_cache_bits=False
            )
            cell_num_size_bytes = big_int(r.read(1))
        case Cell.LEAN_BOC_MAGIC_PREFIX_CRC:
            flags = Flags(has_index=True, has_crc32c=True, has_cache_bits=False)
            cell_num_size_bytes = big_int(r.read(1))
        case _:
            raise ValueError("Invalid BOC magic header")
    # off_bytes:(## 8) { off_bytes <= 8 }
    data_size_bytes = big_int(r.read(1))
    # cells:(##(size * 8))
    cells_num = big_int(r.read(cell_num_size_bytes))
    # roots:(##(size * 8)) { roots >= 1 }
    roots_num = big_int(r.read(cell_num_size_bytes))

    # complete BOCs - ??? (absent:(##(size * 8)) { roots + absent <= cells })
    r.read(cell_num_size_bytes)

    # tot_cells_size:(##(off_bytes * 8))
    data_len = big_int(r.read(data_size_bytes))

    if flags.has_crc32c and crc32c(data[:-4]) != data[-4:]:
        raise ValueError("Checksum does not match")

    roots_index = [
        big_int(r.read(cell_num_size_bytes)) for _ in range(roots_num)
    ]

    if flags.has_cache_bits and not flags.has_index:
        raise ValueError("Cache flag cannot be set without index flag")

    index: list[int] = []
    if flags.has_index:
        idx_data = r.read(cells_num * data_size_bytes)

        for i in range(cells_num):
            off = i * data_size_bytes
            val = big_int(idx_data[off : off + data_size_bytes])
            if flags.has_cache_bits:
                # we don't need a cache, cause our loader uses memory
                val //= 2
            index.append(val)

    if cells_num > data_len // 2:
        raise ValueError(
            f"Cells num looks malicious: data len {data_len}, cells {cells_num}"
        )

    payload = r.read(data_len)
    cells = parse_cells(
        roots_index, cells_num, cell_num_size_bytes, payload, index
    )

    return cells


def parse_cells(
    roots_index: list[int],
    cells_num: int,
    ref_sz_bytes: int,
    data: bytes,
    index: list[int],
) -> list[Cell]:
    cells = [Cell() for _ in range(cells_num)]
    hash_size = 32
    depth_size = 2
    offset = 0

    for i in range(cells_num):
        if len(data) - offset < 2:
            raise ValueError("Failed to parse cell header, corrupted data")

        if index:
            # if we have index, then set offset from it,
            # it stores end of each cell
            offset = index[i - 1] if i > 0 else 0

        flags = data[offset]
        refs_num = flags & 0b111
        is_exotic = bool(flags & 0b1000)
        with_hashes = bool(flags & 0b10000)
        level_mask = flags >> 5

        if refs_num > 4:
            raise ValueError("Too many refs in cell")

        ln = data[offset + 1]
        one_more = ln % 2
        sz = ln // 2 + one_more

        offset += 2
        if len(data) - offset < sz:
            raise ValueError("Failed to parse cell payload, corrupted data")

        if with_hashes:
            mask_bits = int(math.ceil(math.log2(level_mask + 1)))
            hashes_num = mask_bits + 1
            offset += hashes_num * hash_size + hashes_num * depth_size

        payload = data[offset : offset + sz]

        offset += sz
        if len(data) - offset < refs_num * ref_sz_bytes:
            raise ValueError("Failed to parse cell refs, corrupted data")

        refs_index = [
            big_int(data[offset : offset + ref_sz_bytes])
            for _ in range(refs_num)
        ]
        offset += refs_num * ref_sz_bytes

        refs = []
        for y, id in enumerate(refs_index):
            if i == id:
                raise ValueError("Recursive reference of cells")
            if id < i and not index:
                raise ValueError(
                    "Reference to index which is behind parent cell"
                )
            if id >= len(cells):
                raise ValueError("Invalid index, out of scope")

            refs.append(cells[id])

        bits_sz = ln * 4

        # if not full byte
        if ln % 2 != 0:
            # find last bit of byte which indicates the end and cut it and next
            for y in range(8):
                if (payload[-1] >> y) & 1 == 1:
                    bits_sz += 3 - y
                    break

        cells[i].is_exotic = is_exotic
        cells[i].bits.write_bytes(payload)
        cells[i].bits.length = bits_sz
        cells[i].refs = refs

    roots = [cells[idx] for idx in roots_index]
    return roots


def big_int(b: bytes) -> int:
    return int.from_bytes(b, byteorder="big")
