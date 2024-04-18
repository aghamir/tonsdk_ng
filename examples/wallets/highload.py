from tonsdk_ng.contract.wallet import Wallets, WalletVersionEnum
from tonsdk_ng.utils import bytes_to_b64str, to_nano

mnemonics = []
_mnemonics, _pub_k, _priv_k, wallet = Wallets.from_mnemonics(
    mnemonics, WalletVersionEnum("hv2"), 0
)

query = wallet.create_init_external_message()
base64_boc = bytes_to_b64str(query["message"].to_boc(False))

recieps = [
    {
        "address": "destination address",
        "payload": "comment",
        "amount": to_nano(float("amount"), "ton"),
        "send_mode": 3,
    },
    {
        "address": "destination address",
        "payload": "comment",
        "amount": to_nano(float("amount"), "ton"),
        "send_mode": 3,
    },
    {
        "address": "destination address",
        "payload": "comment",
        "amount": to_nano(float("amount"), "ton"),
        "send_mode": 3,
    },
]

query = wallet.create_transfer_message(recipients_list=recieps, query_id=0)

boc = bytes_to_b64str(
    query["message"].to_boc(False)
)  # send this boc to blockchain
