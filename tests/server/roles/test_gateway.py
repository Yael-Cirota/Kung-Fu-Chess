import pytest

from server.roles.gateway import build_gateway


class TestBuildGateway:
    def test_raises_not_implemented_pointing_at_the_relay_blocker(self):
        with pytest.raises(NotImplementedError, match="ADR-001"):
            build_gateway()
