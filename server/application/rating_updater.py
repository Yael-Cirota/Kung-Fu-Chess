"""Settles a finished game: the one subscriber that turns a GAME_OVER event
into persisted Elo ratings and a game_records row.

GAME_OVER reaches the bus in two shapes and this handles both:
  - engine-driven (king captured), payload carries `engine_event`, whose
    `beneficiary_color` is the winning color;
  - forced resign (disconnect grace expired), payload carries `reason` and
    `resigned_color`, so the winner is the other color.

Settlement is idempotent per room. A room keeps ticking after a forced
resign, so the engine can still publish its own GAME_OVER afterwards; only
the first one for a given room counts.
"""

from typing import Dict, Optional, Set

from common.events import Event, EventBus, EventNames
from server.application.elo import EloCalculator
from server.application.game_room import GameRoom
from server.infrastructure.repositories import GameRecordRepository, UserRepository

WHITE = "white"
BLACK = "black"

# reason recorded when the engine, not a disconnect, ended the game
KING_CAPTURED = "king_captured"


def _opponent(color: str) -> str:
    return BLACK if color == WHITE else WHITE


class RatingUpdater:
    def __init__(
        self,
        bus: EventBus,
        rooms: Dict[str, GameRoom],
        users: UserRepository,
        game_records: GameRecordRepository,
        elo_calculator: EloCalculator,
    ):
        self._rooms = rooms
        self._users = users
        self._game_records = game_records
        self._elo_calculator = elo_calculator
        self._settled: Set[str] = set()
        bus.subscribe(EventNames.GAME_OVER, self._on_game_over)

    def _on_game_over(self, event: Event) -> None:
        room_id = event.payload.get("room_id")
        room = self._rooms.get(room_id)
        if room is None or room_id in self._settled:
            return

        seats = room.player_user_ids()
        white_id, black_id = seats.get(WHITE), seats.get(BLACK)
        if white_id is None or black_id is None:
            # An unseated or single-seat room (never matched, or a local test
            # room) has no rated result to settle.
            return

        self._settled.add(room_id)

        winner_color = self._winner_color(event)
        winner_id = seats.get(winner_color) if winner_color is not None else None
        if winner_id is not None:
            self._apply_elo(winner_id, seats[_opponent(winner_color)])

        self._game_records.record_result(
            white_id=white_id,
            black_id=black_id,
            winner_id=winner_id,
            ended_at_ms=self._ended_at_ms(event, room),
            reason=event.payload.get("reason") or KING_CAPTURED,
        )

    def _winner_color(self, event: Event) -> Optional[str]:
        engine_event = event.payload.get("engine_event")
        if engine_event is not None:
            color = engine_event.beneficiary_color
        else:
            resigned_color = event.payload.get("resigned_color")
            color = _opponent(resigned_color) if resigned_color in (WHITE, BLACK) else None
        return color if color in (WHITE, BLACK) else None

    def _ended_at_ms(self, event: Event, room: GameRoom) -> int:
        engine_event = event.payload.get("engine_event")
        return engine_event.at_ms if engine_event is not None else room.session.clock_ms

    def _apply_elo(self, winner_id: int, loser_id: int) -> None:
        winner = self._users.find_by_id(winner_id)
        loser = self._users.find_by_id(loser_id)
        if winner is None or loser is None:
            return
        new_winner_elo, new_loser_elo = self._elo_calculator.updated(winner.elo, loser.elo)
        self._users.update_elo(winner_id, new_winner_elo)
        self._users.update_elo(loser_id, new_loser_elo)
