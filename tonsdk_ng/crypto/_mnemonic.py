import hashlib
import hmac
import random

from nacl.bindings import crypto_sign_seed_keypair

from ._settings import PBKDF_ITERATIONS
from ._utils import get_secure_random_number, is_basic_seed
from .bip39 import english


def mnemonic_is_valid(mnemo_words: list[str]) -> bool:
    return len(mnemo_words) == 24 and is_basic_seed(
        mnemonic_to_entropy(mnemo_words)
    )


def mnemonic_to_entropy(mnemo_words: list[str]):
    sign = hmac.new(
        (" ".join(mnemo_words)).encode("utf-8"), bytes(0), hashlib.sha512
    ).digest()
    return sign


def mnemonic_to_seed(mnemo_words: list[str], seed: str):
    entropy = mnemonic_to_entropy(mnemo_words)
    return hashlib.pbkdf2_hmac("sha512", entropy, seed, PBKDF_ITERATIONS)


def mnemonic_to_private_key(mnemo_words: list[str]) -> tuple[bytes, bytes]:
    """
    :rtype: (bytes(public_key), bytes(secret_key))
    """
    seed = mnemonic_to_seed(mnemo_words, b"TON default seed")
    return crypto_sign_seed_keypair(seed[:32])


def mnemonic_to_wallet_key(mnemo_words: list[str]) -> tuple[bytes, bytes]:
    """
    :rtype: (bytes(public_key), bytes(secret_key))
    """
    _, priv_k = mnemonic_to_private_key(mnemo_words)
    return crypto_sign_seed_keypair(priv_k[:32])


def mnemonic_new(words_count: int = 24) -> list[str]:
    while True:
        mnemo_arr = []

        for _ in range(words_count):
            idx = get_secure_random_number(0, len(english))
            mnemo_arr.append(english[idx])

        if not is_basic_seed(mnemonic_to_entropy(mnemo_arr)):
            continue

        break
    return mnemo_arr


def mnemonic_from_password(password: str, words_count: int = 24) -> list[str]:
    rnd = random.Random(password)

    while True:
        mnemo_arr = [rnd.choice(english) for _ in range(words_count)]

        if not is_basic_seed(mnemonic_to_entropy(mnemo_arr)):
            continue

        break

    return mnemo_arr
