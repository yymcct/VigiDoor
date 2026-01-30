"""Supervisor handler context."""

from dataclasses import dataclass


@dataclass
class SupervisorHandlerContext:
    message_bus: object
    shared_state: object
    logger: object
