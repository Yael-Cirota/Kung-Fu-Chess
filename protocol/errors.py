class ProtocolError(Exception):
    """Raised by codec.decode when a raw frame cannot be turned into a message.
    `reason` is a stable, machine-readable constant - never a free-text message."""

    MALFORMED_JSON = "malformed_json"
    UNKNOWN_TYPE = "unknown_type"
    SCHEMA_MISMATCH = "schema_mismatch"

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
