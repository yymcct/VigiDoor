"""Supervisor handler context."""

import logging
from dataclasses import dataclass
from typing import Any, MutableMapping, Optional

from core.ipc import MessageBus
from db.writer_helper import DBWriterHelper


@dataclass
class SupervisorHandlerContext:
    message_bus: MessageBus
    shared_state: MutableMapping[str, Any]
    logger: logging.Logger
    db_writer: DBWriterHelper
