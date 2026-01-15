"""Channel factory for creating channels based on transport type."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from flowforge.communication.channels.inprocess import (
    InProcessInputChannel,
    InProcessOutputChannel,
)
from flowforge.communication.enums import (
    CompetingStrategy,
    DistributionMode,
    TransportType,
)
from flowforge.communication.groups.competing import CompetingChannelGroup
from flowforge.communication.groups.fanout import FanOutChannelGroup

if TYPE_CHECKING:
    from flowforge.communication.protocols import ChannelGroup, InputChannel, OutputChannel
    from flowforge.messages import Message


class ChannelFactory:
    """Factory for creating channels and channel groups.

    The ChannelFactory abstracts the creation of communication channels.

    Example:
        >>> factory = ChannelFactory()
        >>>
        >>> # Create an in-process channel pair
        >>> output, input_ch = factory.create_inprocess_pair(queue_size=100)
        >>>
        >>> # Create a channel group
        >>> group = factory.create_channel_group(
        ...     DistributionMode.FAN_OUT,
        ...     [output1, output2],
        ... )
    """

    def create_inprocess_pair(
        self,
        queue_size: int = 0,
        name: str | None = None,
    ) -> tuple[InProcessOutputChannel, InProcessInputChannel]:
        """Create a connected in-process output/input channel pair.

        Creates both channels sharing the same asyncio.Queue for
        same-process communication. For cross-process or distributed
        communication, use create_output_channel() and create_input_channel()
        separately in each process/worker.

        Args:
            queue_size: Maximum queue size (0 = unlimited).
            name: Base name for the channels.

        Returns:
            Tuple of (output_channel, input_channel).
        """
        queue: asyncio.Queue[Message[Any]] = asyncio.Queue(maxsize=queue_size)
        base_name = name or f"inprocess-{id(queue)}"

        output = InProcessOutputChannel(queue, name=f"{base_name}-out")
        input_ch = InProcessInputChannel(queue, name=f"{base_name}-in")

        return output, input_ch

    def create_output_channel(
        self,
        transport_type: TransportType,
        *,
        queue: asyncio.Queue[Any] | None = None,
        name: str | None = None,
        **config: Any,
    ) -> OutputChannel:
        """Create an output channel.

        For in-process channels, a queue must be provided (shared with input).

        Args:
            transport_type: Type of transport.
            queue: Shared queue for in-process (required for INPROCESS).
            name: Channel name.
            **config: Additional configuration.

        Returns:
            OutputChannel instance.

        Raises:
            ValueError: If queue is missing for INPROCESS.
            NotImplementedError: If transport_type is not supported.
        """
        if transport_type == TransportType.INPROCESS:
            if queue is None:
                raise ValueError("queue is required for INPROCESS output channels")
            return InProcessOutputChannel(queue, name=name)
        else:
            raise NotImplementedError(
                f"Transport type {transport_type.value} not yet implemented"
            )

    def create_input_channel(
        self,
        transport_type: TransportType,
        *,
        queue: asyncio.Queue[Any] | None = None,
        name: str | None = None,
        **config: Any,
    ) -> InputChannel:
        """Create an input channel.

        For in-process channels, a queue must be provided (shared with output).

        Args:
            transport_type: Type of transport.
            queue: Shared queue for in-process (required for INPROCESS).
            name: Channel name.
            **config: Additional configuration.

        Returns:
            InputChannel instance.

        Raises:
            ValueError: If queue is missing for INPROCESS.
            NotImplementedError: If transport_type is not supported.
        """
        if transport_type == TransportType.INPROCESS:
            if queue is None:
                raise ValueError("queue is required for INPROCESS input channels")
            return InProcessInputChannel(queue, name=name)
        else:
            raise NotImplementedError(
                f"Transport type {transport_type.value} not yet implemented"
            )

    def create_channel_group(
        self,
        distribution_mode: DistributionMode,
        channels: list[OutputChannel] | None = None,
        *,
        strategy: CompetingStrategy = CompetingStrategy.ROUND_ROBIN,
        name: str | None = None,
    ) -> ChannelGroup:
        """Create a channel group for distributing messages.

        Args:
            distribution_mode: How to distribute messages (FAN_OUT or COMPETING).
            channels: Initial list of output channels.
            strategy: Strategy for competing distribution.
            name: Group name.

        Returns:
            ChannelGroup instance.

        Raises:
            ValueError: If distribution_mode is unknown.
        """
        if distribution_mode == DistributionMode.FAN_OUT:
            return FanOutChannelGroup(channels=channels, name=name)
        elif distribution_mode == DistributionMode.COMPETING:
            return CompetingChannelGroup(
                channels=channels,
                strategy=strategy,
                name=name,
            )
        else:
            raise ValueError(f"Unknown distribution mode: {distribution_mode}")
