from server.application.auth_service import AuthErrorReason, AuthService, Pbkdf2PasswordHasher, PasswordHasher
from server.infrastructure.connection_factory import apply_schema
from server.infrastructure.sqlite_user_repository import SqliteUserRepository
import sqlite3


class FakeHasher:
    def hash(self, password, salt):
        return f"{password}:{salt}"

    def new_salt(self):
        return "fixed-salt"


def make_repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_schema(conn)
    return SqliteUserRepository(conn)


class TestRegister:
    def test_new_username_succeeds(self):
        service = AuthService(make_repo(), FakeHasher())
        result = service.register("alice", "hunter2")

        assert result.ok is True
        assert result.value.username == "alice"
        assert result.value.elo == 1200

    def test_duplicate_username_fails_without_mutating_the_repository(self):
        repo = make_repo()
        service = AuthService(repo, FakeHasher())
        service.register("alice", "hunter2")

        result = service.register("alice", "different_password")

        assert result.ok is False
        assert result.error == AuthErrorReason.USERNAME_TAKEN
        # No second row was created for "alice".
        assert repo.find_by_username("alice").password_hash == "hunter2:fixed-salt"

    def test_custom_starting_elo_is_used(self):
        service = AuthService(make_repo(), FakeHasher(), starting_elo=1500)
        result = service.register("bob", "pw")
        assert result.value.elo == 1500


class TestLogin:
    def test_correct_credentials_succeed(self):
        service = AuthService(make_repo(), FakeHasher())
        service.register("alice", "hunter2")

        result = service.login("alice", "hunter2")

        assert result.ok is True
        assert result.value.username == "alice"

    def test_unknown_username_fails(self):
        service = AuthService(make_repo(), FakeHasher())
        result = service.login("nobody", "pw")

        assert result.ok is False
        assert result.error == AuthErrorReason.INVALID_CREDENTIALS

    def test_wrong_password_fails(self):
        service = AuthService(make_repo(), FakeHasher())
        service.register("alice", "hunter2")

        result = service.login("alice", "wrong")

        assert result.ok is False
        assert result.error == AuthErrorReason.INVALID_CREDENTIALS


class TestPbkdf2PasswordHasher:
    def test_same_password_and_salt_produce_the_same_hash(self):
        hasher = Pbkdf2PasswordHasher(iterations=100)
        assert hasher.hash("pw", "salt") == hasher.hash("pw", "salt")

    def test_different_salts_produce_different_hashes(self):
        hasher = Pbkdf2PasswordHasher(iterations=100)
        assert hasher.hash("pw", "salt1") != hasher.hash("pw", "salt2")

    def test_new_salt_values_are_distinct(self):
        hasher = Pbkdf2PasswordHasher()
        assert hasher.new_salt() != hasher.new_salt()

    def test_satisfies_the_password_hasher_protocol(self):
        assert isinstance(Pbkdf2PasswordHasher(), PasswordHasher)

    def test_end_to_end_through_auth_service(self):
        service = AuthService(make_repo(), Pbkdf2PasswordHasher(iterations=100))
        service.register("alice", "hunter2")

        assert service.login("alice", "hunter2").ok is True
        assert service.login("alice", "wrong").ok is False
