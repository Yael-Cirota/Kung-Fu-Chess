"""Maps server engine time onto a client-local timeline that shares
render_ms's origin (see 'Preserving the two-clocks rule across the network'
and 'the one non-obvious bug this design exists to avoid'). Monotonic by
construction: local_ms never rewinds, so a piece is never snapped backward
past a square the server already resolved, even if the server's own
timestamp jumps backward."""

from typing import Optional


class ClockEstimator:
    def __init__(
        self,
        max_catchup_rate: float = 1.20,
        min_catchup_rate: float = 0.85,
        resync_threshold_ms: int = 1000,
    ):
        self._max_catchup_rate = max_catchup_rate
        self._min_catchup_rate = min_catchup_rate
        self._resync_threshold_ms = resync_threshold_ms

        # local_ms = server_ms - _offset. None until the first sample.
        self._offset: Optional[int] = None
        self._local_ms = 0
        # Signed correction still owed to _local_ms from the last sample:
        # positive means local_ms is behind and must catch up (speed up),
        # negative means it's ahead and must be reined in (slow down).
        # advance() bleeds this off gradually instead of jumping.
        self._catchup_remaining_ms = 0

    @property
    def local_ms(self) -> int:
        return self._local_ms

    def to_local(self, server_ms: int) -> int:
        offset = self._offset if self._offset is not None else 0
        return server_ms - offset

    def on_snapshot(self, server_ms: int, local_ms: int) -> None:
        """`local_ms` is the caller's own ground truth for "what local time is
        it right now" (RemoteGameSession passes its wall-clock-derived elapsed
        time). Snaps on the first sample or when drift exceeds
        resync_threshold_ms; otherwise sets up a bounded glide."""
        target_offset = server_ms - local_ms

        if self._offset is None or abs(target_offset - self._offset) > self._resync_threshold_ms:
            self._offset = target_offset
            self._local_ms = local_ms
            self._catchup_remaining_ms = 0
            return

        self._offset = target_offset
        self._catchup_remaining_ms = local_ms - self._local_ms

    def on_heartbeat_ack(self, client_sent_ms: int, server_ms: int, client_recv_ms: int) -> None:
        """A HeartbeatAck's server_ms was stamped mid-flight, not at receipt -
        half-RTT latency compensation before feeding the same rebasing logic
        on_snapshot uses."""
        half_rtt_ms = (client_recv_ms - client_sent_ms) // 2
        self.on_snapshot(server_ms + half_rtt_ms, client_recv_ms)

    def advance(self, ms: int) -> None:
        if ms <= 0:
            return
        if self._catchup_remaining_ms == 0:
            self._local_ms += ms
            return

        if self._catchup_remaining_ms > 0:
            step = min(round(ms * self._max_catchup_rate), ms + self._catchup_remaining_ms)
        else:
            step = max(round(ms * self._min_catchup_rate), ms + self._catchup_remaining_ms)
        step = max(step, 0)  # never move local_ms backward

        self._local_ms += step
        self._catchup_remaining_ms -= (step - ms)
