from contextvars import ContextVar

active_mutuelle_id: ContextVar[int | None] = ContextVar("active_mutuelle_id", default=None)


def set_active_mutuelle(mutuelle_id: int | None) -> None:
    active_mutuelle_id.set(mutuelle_id)


def get_active_mutuelle_id() -> int | None:
    return active_mutuelle_id.get()
