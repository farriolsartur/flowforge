"""FlowForge channel implementations."""

from flowforge.communication.channels.inprocess import (
    InProcessInputChannel,
    InProcessOutputChannel,
)
from flowforge.communication.channels.multiplex import MultiplexInputChannel

__all__ = [
    "InProcessOutputChannel",
    "InProcessInputChannel",
    "MultiplexInputChannel",
]
