from tonsdk_ng.contract.token.nft import NFTItem
from tonsdk_ng.contract.wallet import Wallets, WalletVersionEnum
from tonsdk_ng.types import Address
from tonsdk_ng.utils import bytes_to_b64str, to_nano

"""your wallet mnemonics"""
mnemonics = [
    "always",
    "crystal",
    "grab",
    "glance",
    "cause",
    "dismiss",
    "answer",
    "expose",
    "once",
    "session",
    "tunnel",
    "topic",
    "defense",
    "such",
    "army",
    "smile",
    "exhibit",
    "misery",
    "runway",
    "tone",
    "want",
    "primary",
    "piano",
    "language",
]
wallet = Wallets.from_mnemonics(
    mnemonics=mnemonics, version=WalletVersionEnum.v3r2, workchain=0
)


"""transfer"""
body = NFTItem().create_transfer_body(
    new_owner_address=Address.from_string("new owner address")
)
query = wallet.create_transfer_message(
    to_addr="nft addr",
    amount=to_nano(0.1, "ton"),
    seqno=int("wallet seqno"),
    payload=body,
)

"""then send boc to blockchain"""
boc = bytes_to_b64str(query["message"].to_boc(False))
