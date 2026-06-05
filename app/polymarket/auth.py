"""EIP-712 signing and wallet management for Polygon CLOB.

Private keys NEVER leave this module. Execution modules call sign_order()
and receive only the hex signature.

Phase 5: signing tested in paper mode (no live orders).
Phase 6: live CLOB order placement enabled after pre-live checklist passes.
"""
import os
import structlog

log = structlog.get_logger()


def load_wallet(keystore_path: str, passphrase: str):
    """Load an encrypted keystore file. Returns eth_account Account object."""
    try:
        from eth_account import Account
        with open(keystore_path) as f:
            import json
            keystore = json.load(f)
        account = Account.from_key(Account.decrypt(keystore, passphrase))
        log.info("wallet_loaded", address=account.address)
        return account
    except ImportError:
        raise RuntimeError(
            "eth_account not installed. Run: pip install eth-account web3"
        )


def get_wallet_address(keystore_path: str, passphrase: str) -> str:
    """Return wallet address without exposing private key."""
    account = load_wallet(keystore_path, passphrase)
    return account.address


def sign_order(order: dict, keystore_path: str, passphrase: str) -> str:
    """
    Sign a CLOB limit order with EIP-712 structured data.
    Returns hex signature string.

    order dict must contain:
        maker, taker, tokenId, makerAmount, takerAmount,
        expiration, nonce, feeRateBps, side, signatureType
    """
    try:
        from eth_account import Account
        from eth_account.structured_data.hashing import hash_domain, hash_message
    except ImportError:
        raise RuntimeError("eth_account not installed — Phase 6 only")

    account = load_wallet(keystore_path, passphrase)

    # EIP-712 domain for Polymarket CLOB on Polygon
    domain = {
        "name": "ClobAuthDomain",
        "version": "1",
        "chainId": 137,  # Polygon mainnet
    }

    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "Order": [
                {"name": "maker", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "feeRateBps", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
            ],
        },
        "primaryType": "Order",
        "domain": domain,
        "message": order,
    }

    signed = account.sign_typed_data(structured_data)
    log.info("order_signed", address=account.address,
             token_id=order.get("tokenId"))
    return signed.signature.hex()


def read_wallet_balances(address: str) -> dict:
    """
    Read-only: return USDC balance and open positions on Polygon.
    Used in Phase 5 dashboard (no private key needed for reads).
    """
    try:
        import httpx
        # Polymarket position endpoint (public)
        r = httpx.get(
            f"https://data-api.polymarket.com/positions",
            params={"user": address, "limit": 50},
            timeout=10,
        )
        r.raise_for_status()
        positions = r.json()
        total_value = sum(
            float(p.get("currentValue", 0)) for p in positions
        )
        return {
            "address": address,
            "positions": positions,
            "total_position_value_usd": round(total_value, 2),
            "position_count": len(positions),
        }
    except Exception as e:
        log.warning("wallet_read_failed", error=str(e))
        return {
            "address": address,
            "positions": [],
            "total_position_value_usd": 0.0,
            "position_count": 0,
            "error": str(e),
        }
