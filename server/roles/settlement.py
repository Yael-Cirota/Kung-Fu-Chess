"""Server_Design.md §2/§5: the settlement role. `RatingUpdater` no longer
needs a live `rooms` dict (see its module docstring) - every GAME_OVER it
settles carries its own seat ids and end time - so this builder only needs
the event bus and the two repositories, exactly what a standalone settlement
process would have.

No `if __name__ == "__main__":` yet. Subscribing this to *some* `EventBus` is
already correct and requires no further code change - but today every
`EventBus` this codebase can construct (`InMemoryEventBus`) is process-local,
so a standalone settlement process would subscribe to a bus nothing else can
ever publish to and idle forever: correct, but useless, until §5's Redis
Streams consumer-group bus exists as an `EventBus` implementation. That's the
one piece of cross-process plumbing this role is actually blocked on, and
it's §5's work, not §2's."""

from typing import Optional

from server.application.elo import EloCalculator
from server.application.rating_updater import RatingUpdater
from common.config.schema import AppConfig
from common.events import EventBus
from server.infrastructure.db_writer import DbWriter
from server.infrastructure.repositories import GameRecordRepository, UserRepository


def build_settlement(
    config: AppConfig,
    bus: EventBus,
    users: UserRepository,
    game_records: GameRecordRepository,
    db_writer: Optional[DbWriter] = None,
) -> RatingUpdater:
    elo_calculator = EloCalculator(k_factor=config.matchmaking.k_factor)
    return RatingUpdater(bus, users, game_records, elo_calculator, db_writer=db_writer)
