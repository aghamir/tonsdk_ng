from tonsdk_ng.contract.token.ft import JettonWallet
from tonsdk_ng.contract.wallet import Wallets, WalletVersionEnum
from tonsdk_ng.utils import Address, bytes_to_b64str, to_nano

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
mnemonics, pub_k, priv_k, wallet = Wallets.from_mnemonics(
    mnemonics=mnemonics, version=WalletVersionEnum.v3r2, workchain=0
)


"""transfer"""
body = JettonWallet().create_transfer_body(
    to_address=Address("address"),
    jetton_amount=to_nano(float("jettons amount"), "ton"),
)

query = wallet.create_transfer_message(
    to_addr="your jetton wallet address",
    amount=to_nano(0.1, "ton"),
    seqno=int("wallet seqno"),
    payload=body,
)

"""then send boc to blockchain"""
boc = bytes_to_b64str(query["message"].to_boc(False))
