from __future__ import annotations

import codecs
import math
from typing import TYPE_CHECKING

import nacl
from nacl.bindings import crypto_sign, crypto_sign_BYTES
from nacl.signing import SignedMessage

if TYPE_CHECKING:
    from tonsdk_ng.types import Cell


def move_to_end(
    index_hashmap: dict[bytes, int],
    topological_order_arr: list[tuple[bytes, "Cell"]],
    target: bytes,
) -> tuple[list[tuple[bytes, "Cell"]], dict[bytes, int]]:
    target_index = index_hashmap[target]
    for _hash in index_hashmap:
        if index_hashmap[_hash] > target_index:
            index_hashmap[_hash] -= 1
    index_hashmap[target] = len(topological_order_arr) - 1
    data = topological_order_arr.pop(target_index)
    topological_order_arr.append(data)
    for sub_cell in data[1].refs:
        topological_order_arr, index_hashmap = move_to_end(
            index_hashmap, topological_order_arr, sub_cell.bytes_hash()
        )
    return topological_order_arr, index_hashmap


def tree_walk(
    cell: "Cell",
    topological_order_arr: list[tuple[bytes, "Cell"]],
    index_hashmap: dict[bytes, int],
    parent_hash: bytes | None = None,
) -> tuple[list[tuple[bytes, "Cell"]], dict[bytes, int]]:
    cell_hash = cell.bytes_hash()
    if cell_hash in index_hashmap:
        if (
            parent_hash
            and index_hashmap[parent_hash] > index_hashmap[cell_hash]
        ):
            topological_order_arr, index_hashmap = move_to_end(
                index_hashmap, topological_order_arr, cell_hash
            )
        return topological_order_arr, index_hashmap

    index_hashmap[cell_hash] = len(topological_order_arr)
    topological_order_arr.append((cell_hash, cell))
    for sub_cell in cell.refs:
        topological_order_arr, index_hashmap = tree_walk(
            sub_cell, topological_order_arr, index_hashmap, cell_hash
        )
    return topological_order_arr, index_hashmap


def _crc32c(crc: int, b: bytes) -> int:
    POLY = 0x82F63B78

    crc ^= 0xFFFFFFFF
    for n in range(len(b)):
        crc ^= b[n]
        for _ in range(8):
            crc = (crc >> 1) ^ POLY if crc & 1 else crc >> 1
    return crc ^ 0xFFFFFFFF


def crc32c(b: bytes | bytearray) -> bytes:
    int_crc = _crc32c(0, b)
    return bytes(int_crc.to_bytes(4, byteorder="little"))


def crc16(data: bytes | bytearray) -> bytes:
    POLY = 0x1021
    reg = 0
    message = bytes(data) + bytes(2)

    for byte in message:
        mask = 0x80
        while mask > 0:
            reg <<= 1
            if byte & mask:
                reg += 1
            mask >>= 1
            if reg > 0xFFFF:
                reg &= 0xFFFF
                reg ^= POLY

    return bytes([math.floor(reg / 256), reg % 256])


def string_to_bytes(string: str, size: int = 1) -> bytes:
    if size == 1:
        buf = bytearray(string, "utf-8")
    elif size == 2:
        buf = bytearray(string, "utf-16")
    elif size == 4:
        buf = bytearray(string, "utf-32")
    return bytes(buf)


def sign_message(
    message: bytes,
    signing_key: bytes,
    encoder: nacl.encoding.Encoder = nacl.encoding.RawEncoder,
) -> SignedMessage:
    raw_signed = crypto_sign(message, signing_key)

    signature = encoder.encode(raw_signed[:crypto_sign_BYTES])
    message = encoder.encode(raw_signed[crypto_sign_BYTES:])
    signed = encoder.encode(raw_signed)

    return SignedMessage._from_parts(signature, message, signed)


def b64str_to_bytes(b64str: str) -> bytes:
    b64bytes = codecs.encode(b64str, "utf-8")
    return codecs.decode(b64bytes, "base64")


def b64str_to_hex(b64str: str) -> str:
    _bytes = b64str_to_bytes(b64str)
    _hex = codecs.encode(_bytes, "hex")
    return codecs.decode(_hex, "utf-8")


def bytes_to_b64str(bytes_arr: bytes) -> str:
    return codecs.decode(codecs.encode(bytes_arr, "base64"), "utf-8").replace(
        "\n", ""
    )
