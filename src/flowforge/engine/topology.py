"""FlowForge topology resolver for determining channel configurations.

This module provides the TopologyResolver class that takes pipeline
configuration and resolves connections into concrete channel specifications
with all settings merged from defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from flowforge.communication.enums import (
    CompetingStrategy,
    DistributionMode,
    TransportType,
)

if TYPE_CHECKING:
    from flowforge.config.models import PipelineConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedChannel:
    """Resolved channel configuration for a connection.

    This represents a fully-resolved connection with all settings determined
    (either from explicit configuration or defaults).

    Attributes:
        source: Name of the sending component.
        targets: Tuple of receiving component names.
        transport_type: How messages are transported (INPROCESS for MVP).
        distribution_mode: FAN_OUT or COMPETING distribution.
        strategy: Strategy for competing distribution (ROUND_ROBIN or RANDOM).
        queue_size: Maximum queue size for backpressure handling.
    """

    source: str
    targets: tuple[str, ...]
    transport_type: TransportType
    distribution_mode: DistributionMode
    strategy: CompetingStrategy
    queue_size: int


class TopologyResolver:
    """Resolves pipeline connections into channel configurations.

    The TopologyResolver takes a PipelineConfig and optional worker name,
    and produces ResolvedChannel objects that specify exactly how to
    create channels for each connection.

    For the MVP (Phase 5), all channels are INPROCESS. Phase 6 will add
    logic to determine MULTIPROCESS or DISTRIBUTED based on component
    placement across workers.

    Example:
        >>> resolver = TopologyResolver()
        >>> channels = resolver.resolve(config, worker_name=None)
        >>> for channel in channels:
        ...     print(f"{channel.source} -> {channel.targets}")
    """

    def resolve(
        self,
        config: PipelineConfig,
        worker_name: str | None = None,
        force_inprocess: bool = False,
    ) -> list[ResolvedChannel]:
        """Resolve pipeline connections to channel configurations.

        Args:
            config: The pipeline configuration.
            worker_name: Optional worker to filter components for.
                        If None, includes all components (single-process mode).
            force_inprocess: If True, all channels are INPROCESS regardless
                           of worker placement (for local debugging).

        Returns:
            List of ResolvedChannel configurations.
        """
        resolved: list[ResolvedChannel] = []
        defaults = config.global_config.defaults

        # Get components for this worker (or all if force_inprocess)
        worker_components = self._get_worker_components(config, worker_name, force_inprocess)

        for connection in config.connections:
            # Filter: include connection if source is in this worker
            # Skip filtering entirely when force_inprocess=True
            if worker_name and not force_inprocess and connection.source not in worker_components:
                continue

            # Resolve settings with defaults
            distribution = connection.distribution or defaults.distribution
            strategy = connection.strategy or defaults.strategy
            queue_size = (
                connection.backpressure.queue_size
                if connection.backpressure
                else defaults.backpressure.queue_size
            )

            # For MVP, always INPROCESS
            transport_type = TransportType.INPROCESS

            # Log if force_inprocess is used with workers configured
            if force_inprocess and config.workers:
                logger.warning(
                    "force_inprocess=True: connection %s -> %s using INPROCESS "
                    "(worker placement ignored for local debugging)",
                    connection.source,
                    connection.targets,
                )

            resolved.append(
                ResolvedChannel(
                    source=connection.source,
                    targets=tuple(connection.targets),
                    transport_type=transport_type,
                    distribution_mode=distribution,
                    strategy=strategy,
                    queue_size=queue_size,
                )
            )

        return resolved

    def _get_worker_components(
        self,
        config: PipelineConfig,
        worker_name: str | None,
        force_inprocess: bool = False,
    ) -> set[str]:
        """Get component instance names assigned to a worker.

        If force_inprocess=True, returns all components (ignores worker filtering).

        Args:
            config: The pipeline configuration.
            worker_name: Worker name to filter by, or None for all.
            force_inprocess: If True, return all components regardless of worker.

        Returns:
            Set of component instance names.
        """
        if worker_name is None or force_inprocess:
            # All components when no worker specified OR force_inprocess
            return set(config.get_all_component_instances().keys())

        # Filter by worker assignment
        components: set[str] = set()
        for instances in config.components_by_type.values():
            for instance in instances:
                # Include if assigned to this worker, or unassigned (defaults to any worker)
                if instance.worker == worker_name or instance.worker is None:
                    components.add(instance.name)
        return components
