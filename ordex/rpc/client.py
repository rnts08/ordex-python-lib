"""
JSON-RPC client for ordexcoind / ordexgoldd.

Provides a clean Python interface to the full node's RPC API.
"""

from __future__ import annotations

import json
import itertools
from typing import Any, Optional

import requests


class RpcError(Exception):
    """Error returned by the RPC server."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"RPC error {code}: {message}")


class RpcClient:
    """JSON-RPC 1.0 client for ordexcoind / ordexgoldd.

    Usage::

        rpc = RpcClient("http://127.0.0.1:25175", "rpcuser", "rpcpass")
        info = rpc.getblockchaininfo()
        print(info["blocks"])
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:25175",
        username: str = "rpcuser",
        password: str = "rpcpass",
        timeout: int = 30,
    ) -> None:
        self.url = url
        self.auth = (username, password)
        self.timeout = timeout
        self._id_counter = itertools.count(1)

    def call(self, method: str, *params: Any) -> Any:
        """Make a JSON-RPC call.

        Args:
            method: The RPC method name.
            *params: Positional parameters.

        Returns:
            The ``result`` field from the RPC response.

        Raises:
            RpcError: If the RPC server returns an error.
            requests.RequestException: On network errors.
        """
        payload = {
            "jsonrpc": "1.0",
            "id": next(self._id_counter),
            "method": method,
            "params": list(params),
        }
        response = requests.post(
            self.url,
            json=payload,
            auth=self.auth,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            err = data["error"]
            raise RpcError(err.get("code", -1), err.get("message", "Unknown error"))

        return data.get("result")

    def __getattr__(self, name: str):
        """Allow calling RPC methods as Python methods.

        Example: ``rpc.getblockchaininfo()`` calls ``call("getblockchaininfo")``.
        """
        def method_caller(*args):
            return self.call(name, *args)
        return method_caller

    # -- Convenience methods (typed) ----------------------------------------

    def getblockchaininfo(self) -> dict:
        return self.call("getblockchaininfo")

    def getblockcount(self) -> int:
        return self.call("getblockcount")

    def getblockhash(self, height: int) -> str:
        return self.call("getblockhash", height)

    def getblock(self, blockhash: str, verbosity: int = 1) -> dict:
        return self.call("getblock", blockhash, verbosity)

    def getbestblockhash(self) -> str:
        return self.call("getbestblockhash")

    def getrawtransaction(self, txid: str, verbose: bool = True) -> Any:
        return self.call("getrawtransaction", txid, verbose)

    def decoderawtransaction(self, hex_string: str) -> dict:
        return self.call("decoderawtransaction", hex_string)

    def sendrawtransaction(self, hex_string: str) -> str:
        return self.call("sendrawtransaction", hex_string)

    def getnetworkinfo(self) -> dict:
        return self.call("getnetworkinfo")

    def getpeerinfo(self) -> list:
        return self.call("getpeerinfo")

    def getbalance(self, account: str = "*", minconf: int = 1) -> float:
        return self.call("getbalance", account, minconf)

    def getnewaddress(self, label: str = "", address_type: str = "") -> str:
        args = [label]
        if address_type:
            args.append(address_type)
        return self.call("getnewaddress", *args)

    def dumpprivkey(self, address: str) -> str:
        return self.call("dumpprivkey", address)

    def estimatesmartfee(self, conf_target: int) -> dict:
        return self.call("estimatesmartfee", conf_target)
