"""Compatibility shim for supervisor handlers package."""

from importlib import import_module as _import_module
import os as _os

__path__ = [_os.path.join(_os.path.dirname(__file__), "handlers")]

SupervisorHandlerContext = _import_module(__name__ + ".context").SupervisorHandlerContext
handle_heartbeat = _import_module(__name__ + ".heartbeat").handle_heartbeat
handle_alarm_intrusion = _import_module(__name__ + ".alarm_intrusion").handle_alarm_intrusion
handle_mqtt_command = _import_module(__name__ + ".mqtt_command").handle_mqtt_command

__all__ = [
    "SupervisorHandlerContext",
    "handle_heartbeat",
    "handle_alarm_intrusion",
    "handle_mqtt_command",
]
