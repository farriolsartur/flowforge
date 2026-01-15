"""FlowForge communication layer."""

from flowforge.communication.channels import (
    InProcessInputChannel,
    InProcessOutputChannel,
)
from flowforge.communication.enums import (
    BackpressureMode,
    CompetingStrategy,
    DistributionMode,
    StartupSyncStrategy,
    TransportType,
)
from flowforge.communication.factory import ChannelFactory
from flowforge.communication.groups import (
    CompetingChannelGroup,
    FanOutChannelGroup,
)
from flowforge.communication.protocols import (
    ChannelGroup,
    ControlChannel,
    InputChannel,
    OutputChannel,
    RetryPolicy,
    Serializer,
)
from flowforge.communication.serialization import (
    JSONSerializer,
    MessagePackSerializer,
    get_serializer,
)

__all__ = [
    # Enums
    "TransportType",
    "CompetingStrategy",
    "StartupSyncStrategy",
    "BackpressureMode",
    "DistributionMode",
    # Protocols
    "OutputChannel",
    "InputChannel",
    "ChannelGroup",
    "Serializer",
    "RetryPolicy",
    "ControlChannel",
    # Channels
    "InProcessOutputChannel",
    "InProcessInputChannel",
    # Groups
    "FanOutChannelGroup",
    "CompetingChannelGroup",
    # Serialization
    "JSONSerializer",
    "MessagePackSerializer",
    "get_serializer",
    # Factory
    "ChannelFactory",
]
