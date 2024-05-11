from tonsdk_ng.boc import begin_cell
from tonsdk_ng.types import Address

cell = (
    begin_cell()
    .store_uint(4, 32)
    .store_address(
        Address.from_string("EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG")
    )
    .end_cell()
)
