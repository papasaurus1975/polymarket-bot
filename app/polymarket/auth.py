"""EIP-712 signing and wallet management. Raw private keys never leave this module."""


def sign_order(order: dict, private_key_path: str, passphrase: str) -> str:
    """Sign a CLOB order with EIP-712. Returns hex signature. Phase 5+."""
    raise NotImplementedError("Signing not yet implemented — Phase 5")
