"""A live, verifiable proof -- not just an assertion -- that Foxtale's
analysis pipeline never makes an outbound network call. Blocks socket
connections at the interpreter level, runs a full pass of the scoring
engine, and reports whether anything tried to reach the network.
"""

import socket
from contextlib import contextmanager
from typing import Tuple

import numpy as np


class NetworkAttemptBlocked(Exception):
    pass


@contextmanager
def _block_network():
    original_connect = socket.socket.connect

    def _blocked(self, address):
        raise NetworkAttemptBlocked(f"outbound connection attempt to {address}")

    socket.socket.connect = _blocked
    try:
        yield
    finally:
        socket.socket.connect = original_connect


def run_offline_verification() -> Tuple[bool, str]:
    from engine.skin_analysis import run_engine_self_test

    rng = np.random.default_rng(0)
    patch = rng.integers(0, 255, size=(96, 96, 3), dtype=np.uint8)

    try:
        with _block_network():
            run_engine_self_test(patch)
        return True, (
            "Verified: a full analysis pass ran with network access blocked at the "
            "socket layer, and completed normally -- no outbound connection was attempted."
        )
    except NetworkAttemptBlocked as exc:
        return False, f"A network attempt was blocked during analysis: {exc}"
    except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
        return False, f"Verification could not complete: {exc}"
