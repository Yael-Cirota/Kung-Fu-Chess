from server.infrastructure.repositories import GameRecordRepository, UserRecord, UserRepository


class FakeUserRepository:
    def find_by_username(self, username):
        return None

    def find_by_id(self, user_id):
        return None

    def create(self, username, password_hash, salt, elo):
        return UserRecord(user_id=1, username=username, password_hash=password_hash, salt=salt, elo=elo)

    def update_elo(self, user_id, elo):
        pass


class FakeGameRecordRepository:
    def record_result(self, white_id, black_id, winner_id, ended_at_ms, reason):
        pass


class TestUserRecord:
    def test_holds_the_given_fields(self):
        record = UserRecord(user_id=1, username="alice", password_hash="h", salt="s", elo=1200)
        assert record.user_id == 1
        assert record.username == "alice"
        assert record.elo == 1200


class TestProtocols:
    def test_fake_user_repository_satisfies_the_protocol(self):
        assert isinstance(FakeUserRepository(), UserRepository)

    def test_fake_game_record_repository_satisfies_the_protocol(self):
        assert isinstance(FakeGameRecordRepository(), GameRecordRepository)
