import httpj

from tonsdk_ng.boc import Cell
from tonsdk_ng.utils import b64str_to_bytes


class ToncenterClient:
    def __init__(
        self,
        base_url="https://testnet.toncenter.com/api/v2",
        api_key: str | None = None,
    ):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self.client = httpj.Client(
            base_url=base_url.rstrip("/"), headers=headers
        )

    def send(self, method, params):
        params = {k: v for k, v in params.items() if v is not None}
        request_data = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        response = self.client.post("/jsonRPC", json=request_data)
        response_json = response.json()
        if "result" in response_json:
            return response_json["result"]
        else:
            raise Exception(response_json["error"])

    def get_address_info(self, address):
        return self.send("getAddressInformation", {"address": address})

    def get_address_state(self, address):
        return self.send("getAddressState", {"address": address})

    def get_extended_address_info(self, address):
        return self.send("getExtendedAddressInformation", {"address": address})

    def get_wallet_info(self, address):
        return self.send("getWalletInformation", {"address": address})

    def get_transactions(
        self, address, limit=20, lt=None, hash=None, to_lt=None, archival=None
    ):
        return self.send(
            "getTransactions",
            {
                "address": address,
                "limit": limit,
                "lt": lt,
                "hash": hash,
                "to_lt": to_lt,
                "archival": archival,
            },
        )

    def get_balance(self, address):
        return self.send("getAddressBalance", {"address": address})

    def send_boc(self, base64):
        return self.send("sendBoc", {"boc": base64})

    def send_query(self, query):
        return self.send("sendQuerySimple", query)

    def get_estimate_fee(self, query):
        return self.send("estimateFee", query)

    def run_get_method(
        self, address: str, method: str, stack: list | None = None
    ):
        stack = stack or []
        return self.send(
            "runGetMethod",
            {"address": address, "method": method, "stack": stack},
        )

    def get_config_param(self, config_param_id):
        raw_result = self.send("getConfigParam", {"config_id": config_param_id})
        if raw_result["@type"] != "configInfo":
            raise Exception("getConfigParam expected type configInfo")
        if "config" not in raw_result:
            raise Exception("getConfigParam expected config")
        if raw_result["config"]["@type"] != "tvm.cell":
            raise Exception("getConfigParam expected type tvm.cell")
        if "bytes" not in raw_result["config"]:
            raise Exception("getConfigParam expected bytes")
        return Cell.one_from_boc(b64str_to_bytes(raw_result["config"]["bytes"]))

    def get_masterchain_info(self):
        return self.send("getMasterchainInfo", {})

    def get_block_shards(self, masterchain_block_number):
        return self.send("shards", {"seqno": masterchain_block_number})

    def get_block_transactions(
        self,
        workchain,
        shard_id,
        shard_block_number,
        limit,
        after_lt,
        address_hash,
    ):
        return self.send(
            "getBlockTransactions",
            {
                "workchain": workchain,
                "shard": shard_id,
                "seqno": shard_block_number,
                "count": limit,
                "after_lt": after_lt,
                "after_hash": address_hash,
            },
        )

    def get_masterchain_block_transactions(
        self, masterchain_block_number, limit, after_lt, address_hash
    ):
        return self.get_block_transactions(
            -1,
            "-9223372036854775808",
            masterchain_block_number,
            limit,
            after_lt,
            address_hash,
        )

    def get_block_header(self, workchain, shard_id, shard_block_number):
        return self.send(
            "getBlockHeader",
            {
                "workchain": workchain,
                "shard": shard_id,
                "seqno": shard_block_number,
            },
        )

    def get_masterchain_block_header(self, masterchain_block_number):
        return self.get_block_header(
            -1, "-9223372036854775808", masterchain_block_number
        )
