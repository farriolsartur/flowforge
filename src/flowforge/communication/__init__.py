"""FlowForge communication layer."""

from flowforge.communication.channels import (
    InProcessInputChannel,
    InProcessOutputChannel,
    MultiplexInputChannel,
    MultiprocessInputChannel,
    MultiprocessOutputChannel,
    ZmqInputChannel,
    ZmqOutputChannel,
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
from flowforge.communication.sync import (
    ExponentialBackoffPolicy,
    MultiprocessControlChannel,
    ZmqControlChannel,
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
    "ExponentialBackoffPolicy",
    "MultiprocessControlChannel",
    "ZmqControlChannel",
    # Channels
    "InProcessOutputChannel",
    "InProcessInputChannel",
    "MultiplexInputChannel",
    "MultiprocessOutputChannel",
    "MultiprocessInputChannel",
    "ZmqOutputChannel",
    "ZmqInputChannel",
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
