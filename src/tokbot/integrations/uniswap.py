"""Uniswap pair/pool resolution helpers using The Graph subgraphs."""

from __future__ import annotations

from typing import Optional
import requests


def resolve_pair_address(
    token0: str,
    token1: str,
    dex: str = "uniswap-v2",
    chain_id: int = 1,
    fee_bps: Optional[int] = None,
) -> Optional[str]:
    """Resolve a DEX pair/pool address for two tokens using The Graph.

    Supports:
    - Uniswap V2 (pairs)
    - Uniswap V3 (pools) with optional fee tier
    """
    t0 = token0.lower()
    t1 = token1.lower()
    if chain_id != 1:
        # Only Ethereum mainnet supported by default here
        return None
    if dex == "uniswap-v2":
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
        q_exact = "query($a:String!,$b:String!){pairs(where:{token0:$a, token1:$b}){ id token0{ id } token1{ id } }}"
        q_reverse = "query($a:String!,$b:String!){pairs(where:{token0:$b, token1:$a}){ id token0{ id } token1{ id } }}"
        for q in (q_exact, q_reverse):
            resp = requests.post(url, json={"query": q, "variables": {"a": t0, "b": t1}}, timeout=10)
            if resp.ok:
                data = resp.json().get("data", {}).get("pairs", [])
                if data:
                    return data[0]["id"]
    elif dex == "uniswap-v3":
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
        # Filter by fee tier if provided
        if fee_bps is not None:
            q_exact = (
                "query($a:String!,$b:String!,$fee:Int!){pools(where:{token0:$a, token1:$b, feeTier:$fee})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            q_reverse = (
                "query($a:String!,$b:String!,$fee:Int!){pools(where:{token0:$b, token1:$a, feeTier:$fee})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            vars = {"a": t0, "b": t1, "fee": int(fee_bps)}
        else:
            q_exact = (
                "query($a:String!,$b:String!){pools(where:{token0:$a, token1:$b})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            q_reverse = (
                "query($a:String!,$b:String!){pools(where:{token0:$b, token1:$a})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            vars = {"a": t0, "b": t1}
        pools: list[dict] = []
        for q in (q_exact, q_reverse):
            resp = requests.post(url, json={"query": q, "variables": vars}, timeout=10)
            if resp.ok:
                data = resp.json().get("data", {}).get("pools", [])
                if data:
                    pools.extend(data)
        if pools:
            # If multiple, prefer lowest fee
            pools.sort(key=lambda p: int(p.get("feeTier", 99999)))
            return pools[0]["id"]
    return None