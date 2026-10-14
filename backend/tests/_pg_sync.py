"""Sincronización explícita para tests de concurrencia contra Postgres real.

En vez de "disparar dos requests y ver quién gana" (depende del scheduler), se PAUSA una operación
a mitad de su transacción —con sus locks de fila ya tomados— y recién cuando la segunda quedó
realmente BLOQUEADA en Postgres (se verifica en pg_stat_activity) se la deja continuar. Así cada
orden de ejecución se reproduce siempre, con los locks reales de la base."""

import threading
import time

import sqlalchemy as sa

PAUSE_TIMEOUT_S = 30


class Pause:
    """Envuelve una función de la app: corre la original y luego se detiene (una sola vez) hasta release()."""

    def __init__(self) -> None:
        self.reached = threading.Event()
        self.released = threading.Event()
        self._used = False
        self._lock = threading.Lock()

    def wrap(self, fn):
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            with self._lock:
                first = not self._used
                self._used = True
            if first:
                self.reached.set()
                if not self.released.wait(PAUSE_TIMEOUT_S):
                    raise RuntimeError("Pause no fue liberada a tiempo")
            return result

        return wrapper

    def wait_reached(self) -> None:
        assert self.reached.wait(PAUSE_TIMEOUT_S), "la operación nunca llegó al punto de pausa"

    def release(self) -> None:
        self.released.set()


def blocked_sessions(engine) -> int:
    """Cantidad de sesiones de esta base esperando un lock de fila/transacción."""
    with engine.connect() as conn:
        return conn.execute(
            sa.text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid() AND wait_event_type = 'Lock'"
            )
        ).scalar_one()


def wait_until_blocked(engine, expected: int = 1, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if blocked_sessions(engine) >= expected:
            return
        time.sleep(0.05)
    raise AssertionError(f"se esperaban {expected} sesión(es) bloqueada(s) en Postgres y no aparecieron")


def assert_not_blocked_for(engine, seconds: float = 0.5) -> None:
    """Comprueba que NO hay sesiones esperando locks durante una ventana (operaciones independientes)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert blocked_sessions(engine) == 0, "una operación quedó bloqueada esperando a otra no relacionada"
        time.sleep(0.05)
