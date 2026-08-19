"""Server_Design.md §2's five deployable roles. Each module here is a
narrowed composition root - the analogue of `server/main.py`'s `build_server`
but for one role's slice of the object graph - not a copy of the monolith's
behavior. See each module's docstring for what it builds and, where relevant,
why it doesn't yet ship a standalone `python -m server.roles.<role>` entry
point (`docker-compose.yml` keeps all five commented out for the same
reason)."""
