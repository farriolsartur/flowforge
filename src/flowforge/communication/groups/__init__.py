"""FlowForge channel group implementations."""

from flowforge.communication.groups.competing import CompetingChannelGroup
from flowforge.communication.groups.fanout import FanOutChannelGroup

__all__ = [
    "FanOutChannelGroup",
    "CompetingChannelGroup",
]
