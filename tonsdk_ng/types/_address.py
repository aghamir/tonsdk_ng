import base64
from typing import NamedTuple, Union, Optional

from tonsdk_ng.exceptions import InvalidAddressError
from tonsdk_ng.utils import bytes_to_b64str, crc16

from ._cell import Cell


class Address:
    BOUNCEABLE_TAG = 0x11
    NON_BOUNCEABLE_TAG = 0x51
    TEST_FLAG = 0x80

    def __init__(
        self,
        *,
        wc: int,
        hash_part: bytes,
        is_user_friendly: bool,
        is_url_safe: bool,
        is_bounceable: bool,
        is_test_only: bool,
    ):
        self.wc = wc
        self.hash_part = hash_part
        self.is_user_friendly = is_user_friendly
        self.is_url_safe = is_url_safe
        self.is_bounceable = is_bounceable
        self.is_test_only = is_test_only

    @classmethod
    def from_any(cls, val: Union["Address", Cell, str]) -> "Address":
        address: Optional["Address"] = None

        match val:
            case str():
                address = cls.from_string(val)
            case Address():
                address = cls.from_address(val)
            case Cell():
                address = cls.from_cell(val)

        if address is None:
            raise InvalidAddressError("Invalid address")

        return address

    @classmethod
    def from_address(cls, addr: "Address") -> "Address":
        return cls(
            wc=addr.wc,
            hash_part=addr.hash_part,
            is_test_only=addr.is_test_only,
            is_user_friendly=addr.is_user_friendly,
            is_bounceable=addr.is_bounceable,
            is_url_safe=addr.is_url_safe,
        )

    @classmethod
    def from_string(cls, addr: str) -> "Address":
        if addr.find("-") > 0 or addr.find("_") > 0:
            addr = addr.replace("-", "+").replace("_", "/")
            is_url_safe = True
        else:
            is_url_safe = False

        try:
            colon_index = addr.index(":")
        except ValueError:
            colon_index = -1

        if colon_index > -1:
            arr = addr.split(":")
            if len(arr) != 2:
                raise InvalidAddressError(f"Invalid address {addr}")

            wc = int(arr[0])
            if wc != 0 and wc != -1:
                raise InvalidAddressError(f"Invalid address wc {wc}")

            address_hex = arr[1]
            if len(address_hex) != 64:
                raise InvalidAddressError(f"Invalid address hex {addr}")

            is_user_friendly = False
            wc = wc
            hash_part = bytes.fromhex(address_hex)
            is_test_only = False
            is_bounceable = False
        else:
            is_user_friendly = True
            parse_result = parse_friendly_address(addr)
            wc = parse_result.workchain
            hash_part = parse_result.hash_part
            is_test_only = parse_result.is_test_only
            is_bounceable = parse_result.is_bounceable

        return cls(
            wc=wc,
            hash_part=hash_part,
            is_user_friendly=is_user_friendly,
            is_test_only=is_test_only,
            is_bounceable=is_bounceable,
            is_url_safe=is_url_safe,
        )

    @classmethod
    def from_cell(cls, cell: Cell) -> Optional["Address"]:
        data = "".join([str(cell.bits.get(x)) for x in range(cell.bits.length)])
        if len(data) < 267:
            return None
        wc = int(data[3:11], 2)
        hashpart = int(data[11 : 11 + 256], 2).to_bytes(32, "big").hex()
        return cls.from_string(f"{wc if wc != 255 else -1}:{hashpart}")

    def to_string(
        self,
        is_user_friendly: bool | None = None,
        is_url_safe: bool | None = None,
        is_bounceable: bool | None = None,
        is_test_only: bool | None = None,
    ) -> str:
        if is_user_friendly is None:
            is_user_friendly = self.is_user_friendly
        if is_url_safe is None:
            is_url_safe = self.is_url_safe
        if is_bounceable is None:
            is_bounceable = self.is_bounceable
        if is_test_only is None:
            is_test_only = self.is_test_only

        if not is_user_friendly:
            return f"{self.wc}:{self.hash_part.hex()}"

        tag = (
            Address.BOUNCEABLE_TAG
            if is_bounceable
            else Address.NON_BOUNCEABLE_TAG
        )
        if is_test_only:
            tag |= Address.TEST_FLAG

        addr = bytearray(34)
        addr[0] = tag
        addr[1] = self.wc
        addr[2:] = self.hash_part
        address_with_checksum = bytearray(36)
        address_with_checksum[:34] = addr
        address_with_checksum[34:] = crc16(addr)

        address_base_64 = bytes_to_b64str(address_with_checksum)
        if is_url_safe:
            address_base_64 = address_base_64.replace("+", "-").replace(
                "/", "_"
            )

        return address_base_64

    def to_buffer(self) -> bytes:
        return self.hash_part + bytearray([self.wc, self.wc, self.wc, self.wc])


class ParseResult(NamedTuple):
    is_test_only: bool
    is_bounceable: bool
    workchain: int
    hash_part: bytes


def parse_friendly_address(addr_str: str) -> ParseResult:
    if len(addr_str) != 48:
        raise InvalidAddressError(
            "User-friendly address should contain strictly 48 characters"
        )

    # avoid padding error (https://gist.github.com/perrygeo/ee7c65bb1541ff6ac770)
    data = base64.b64decode(addr_str + "==")

    if len(data) != 36:
        raise InvalidAddressError(
            "Unknown address type: byte length is not equal to 36"
        )

    addr = data[:34]
    crc = data[34:36]
    calced_crc = crc16(addr)
    if not (calced_crc[0] == crc[0] and calced_crc[1] == crc[1]):
        raise InvalidAddressError("Wrong crc16 hashsum")

    tag = addr[0]
    is_test_only = False
    is_bounceable = False
    if tag & Address.TEST_FLAG:
        is_test_only = True
        tag ^= Address.TEST_FLAG
    if (tag != Address.BOUNCEABLE_TAG) and (tag != Address.NON_BOUNCEABLE_TAG):
        raise InvalidAddressError("Unknown address tag")

    is_bounceable = tag == Address.BOUNCEABLE_TAG

    workchain = -1 if addr[1] == 255 else addr[1]
    if workchain != 0 and workchain != -1:
        raise InvalidAddressError(f"Invalid address wc {workchain}")

    return ParseResult(
        is_test_only=is_test_only,
        is_bounceable=is_bounceable,
        workchain=workchain,
        hash_part=bytes(addr[2:34]),
    )
