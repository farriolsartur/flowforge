"""FlowForge Engine for orchestrating pipeline execution.

This module provides the Engine class that orchestrates the complete
lifecycle of a pipeline: loading configuration, creating channels and
components, wiring them together, and managing execution and shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from flowforge.communication.channels.multiplex import MultiplexInputChannel
from flowforge.communication.factory import ChannelFactory
from flowforge.components.factory import ComponentFactory
from flowforge.components.protocols import Triggerable
from flowforge.config.loader import ConfigLoader
from flowforge.exceptions import PipelineConfigError

from .context import WorkerContext
from .topology import ResolvedChannel, TopologyResolver

if TYPE_CHECKING:
    from flowforge.communication.protocols import (
        ChannelGroup,
        InputChannel,
        OutputChannel,
    )
    from flowforge.components.base import Component
    from flowforge.config.models import PipelineConfig

logger = logging.getLogger(__name__)


class Engine:
    """Main orchestrator for pipeline execution.

    The Engine is responsible for the complete lifecycle of pipeline execution:

    1. Loading and validating pipeline configuration from YAML
    2. Resolving topology (determining channel configurations)
    3. Creating channels and channel groups for message distribution
    4. Instantiating components via ComponentFactory
    5. Wiring channels to components (setting _output_channel_group and _input_channel)
    6. Managing component lifecycle (on_start, run, on_stop)
    7. Handling graceful shutdown with timeout

    Example:
        >>> engine = Engine("pipeline.yaml")
        >>> await engine.run()  # Runs until completion or Ctrl+C

    Example with force_inprocess for local debugging:
        >>> engine = Engine("distributed_pipeline.yaml")
        >>> await engine.run(force_inprocess=True)  # Run all components locally

    Attributes:
        is_running: Whether the engine is currently running.
        components: Dictionary of component name to component instance (read-only).
    """

    def __init__(
        self,
        config_path: str,
        worker_name: str | None = None,
    ) -> None:
        """Initialize the Engine.

        Args:
            config_path: Path to the YAML configuration file.
            worker_name: Optional worker name for distributed execution.
                        If None, defaults to "main". For pipelines without
                        workers defined, this runs all components. For pipelines
                        with workers, use force_inprocess=True in run() to
                        execute all components locally regardless of worker
                        assignment.
        """
        self._config_path = config_path
        self._worker_name = worker_name or "main"

        # Runtime state (initialized in run())
        self._config: PipelineConfig | None = None
        self._context: WorkerContext | None = None
        self._components: dict[str, Component[Any]] = {}
        self._channels: list[tuple[OutputChannel, InputChannel]] = []
        self._channel_groups: dict[str, ChannelGroup] = {}
        self._target_inputs: dict[str, list[InputChannel]] = {}
        self._receiver_tasks: list[asyncio.Task[None]] = []
        self._triggerable_tasks: list[asyncio.Task[None]] = []
        self._multiplex_channels: list[MultiplexInputChannel] = []
        self._is_running = False

    async def run(self, force_inprocess: bool = False) -> None:
        """Run the pipeline to completion.

        This method performs the complete pipeline lifecycle:
        1. Loads and validates configuration
        2. Sets up channels and components
        3. Starts all components
        4. Waits for completion or cancellation
        5. Performs graceful shutdown

        Args:
            force_inprocess: If True, forces all channels to be in-process
                           regardless of worker placement. Useful for debugging
                           distributed pipelines locally.

        Raises:
            PipelineConfigError: If configuration is invalid.
            RuntimeError: If engine is already running.
        """
        if self._is_running:
            raise RuntimeError("Engine is already running")

        self._is_running = True

        try:
            # Phase 1: Load and validate configuration
            await self._initialize(force_inprocess)

            # Phase 2: Call on_start lifecycle hooks
            await self._call_lifecycle_hooks("on_start")

            # Phase 3: Start receivers (begin listening)
            self._start_receivers()

            # Phase 4: Start triggerables (components with run() method)
            self._start_triggerables()

            # Phase 5: Wait for completion
            await self._await_completion()

        except asyncio.CancelledError:
            logger.info("Engine received cancellation, initiating shutdown")
        except Exception as e:
            logger.error("Engine error: %s", e)
            raise
        finally:
            await self.shutdown()

    async def _initialize(self, force_inprocess: bool) -> None:
        """Initialize the engine: load config, create channels, wire components.

        Args:
            force_inprocess: Whether to force in-process channels.
        """
        # Step 1: Load configuration
        loader = ConfigLoader()
        self._config = loader.load(self._config_path)

        # Step 2: Validate configuration
        errors = loader.validate_with_registry(self._config)
        if errors:
            raise PipelineConfigError(
                "Configuration validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        logger.info(
            "Loaded pipeline '%s' v%s",
            self._config.global_config.name,
            self._config.global_config.version,
        )

        # Step 3: Create worker context
        self._context = WorkerContext(
            worker_name=self._worker_name,
            pipeline_config=self._config,
            force_inprocess=force_inprocess,
        )

        # Step 4: Resolve topology
        resolver = TopologyResolver()
        resolved_channels = resolver.resolve(
            self._config,
            self._worker_name if self._config.workers else None,
            force_inprocess,
        )

        # Step 5: Create channels and components
        self._create_channels(resolved_channels)
        self._create_components()
        await self._wire_components()

        logger.info(
            "Engine initialized: %d components, %d connections",
            len(self._components),
            len(resolved_channels),
        )

    def _create_channels(self, resolved: list[ResolvedChannel]) -> None:
        """Create all channels needed for the pipeline.

        This creates input/output channel pairs for each target in each
        connection, organizing them for later wiring.

        Args:
            resolved: List of resolved channel configurations.
        """
        factory = ChannelFactory()

        # Track channels per source (for creating channel groups)
        # source_name -> list of output_channels
        source_outputs: dict[str, list[OutputChannel]] = {}

        for channel_config in resolved:
            if channel_config.source not in source_outputs:
                source_outputs[channel_config.source] = []

            for target in channel_config.targets:
                # Create channel pair
                output_ch, input_ch = factory.create_inprocess_pair(
                    queue_size=channel_config.queue_size,
                    name=f"{channel_config.source}->{target}",
                )

                self._channels.append((output_ch, input_ch))
                source_outputs[channel_config.source].append(output_ch)

                # Collect all input channels for each target (supports multiple sources)
                if target not in self._target_inputs:
                    self._target_inputs[target] = []
                self._target_inputs[target].append(input_ch)

        # Create channel groups for each source
        for channel_config in resolved:
            outputs = source_outputs.get(channel_config.source, [])

            if outputs:
                group = factory.create_channel_group(
                    distribution_mode=channel_config.distribution_mode,
                    channels=outputs,
                    strategy=channel_config.strategy,
                    name=f"{channel_config.source}-group",
                )
                self._channel_groups[channel_config.source] = group

    def _create_components(self) -> None:
        """Create all component instances."""
        if not self._context:
            raise RuntimeError("Context not initialized")

        factory = ComponentFactory()

        for instance_config in self._context.get_components():
            component = factory.create_component(
                component_name=instance_config.type,
                instance_name=instance_config.name,
                config_dict=instance_config.config,
            )
            self._components[instance_config.name] = component

            logger.debug(
                "Created component '%s' (type: %s)",
                instance_config.name,
                instance_config.type,
            )

    async def _wire_components(self) -> None:
        """Wire channels to components.

        - Senders get their _output_channel_group set
        - Receivers get their _input_channel set
        - Multiple sources to same target use MultiplexInputChannel
        """
        # Wire output channel groups to senders
        for source_name, group in self._channel_groups.items():
            if source_name in self._components:
                component = self._components[source_name]
                if hasattr(component, "_output_channel_group"):
                    component._output_channel_group = group
                    logger.debug(
                        "Wired output channel group to '%s'",
                        source_name,
                    )

        # Wire input channels to receivers
        for target_name, input_channels in self._target_inputs.items():
            if target_name in self._components:
                component = self._components[target_name]
                if hasattr(component, "_input_channel"):
                    if len(input_channels) == 0:
                        input_channel = None
                    elif len(input_channels) == 1:
                        input_channel = input_channels[0]
                    else:
                        # Multiple sources - wrap in multiplex channel
                        input_channel = MultiplexInputChannel(
                            input_channels,
                            name=f"{target_name}-multiplex",
                        )
                        await input_channel.start()
                        self._multiplex_channels.append(input_channel)
                        logger.info(
                            "Component '%s' receiving from %d sources via multiplex",
                            target_name,
                            len(input_channels),
                        )

                    component._input_channel = input_channel
                    logger.debug(
                        "Wired input channel to '%s'",
                        target_name,
                    )

    async def _call_lifecycle_hooks(self, hook_name: str) -> None:
        """Call a lifecycle hook on all components.

        Args:
            hook_name: Either 'on_start' or 'on_stop'.
        """
        for name, component in self._components.items():
            hook = getattr(component, hook_name, None)
            if hook and callable(hook):
                logger.debug("Calling %s on '%s'", hook_name, name)
                await hook()

    def _start_receivers(self) -> None:
        """Start receiver components (begin listening for messages)."""
        for name, component in self._components.items():
            if hasattr(component, "_listen_and_dispatch") and hasattr(
                component, "_input_channel"
            ):
                if component._input_channel is not None:
                    task = asyncio.create_task(
                        component._listen_and_dispatch(),
                        name=f"receiver-{name}",
                    )
                    self._receiver_tasks.append(task)
                    logger.debug("Started receiver '%s'", name)

    def _start_triggerables(self) -> None:
        """Start triggerable components (components with run() method)."""
        for name, component in self._components.items():
            if isinstance(component, Triggerable):
                task = asyncio.create_task(
                    component.run(),
                    name=f"triggerable-{name}",
                )
                self._triggerable_tasks.append(task)
                logger.debug("Started triggerable '%s'", name)

    async def _await_completion(self) -> None:
        """Wait for all triggerable components to complete."""
        if self._triggerable_tasks:
            # Wait for all triggerables to finish
            results = await asyncio.gather(
                *self._triggerable_tasks, return_exceptions=True
            )

            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Triggerable task failed: %s", result, exc_info=result
                    )

            logger.info("All triggerables completed")

        # Wait briefly for final messages to propagate
        await asyncio.sleep(0.1)

        # Wait for receivers to finish processing (with timeout)
        if self._receiver_tasks:
            # Give receivers time to process remaining messages
            pending_receivers = [t for t in self._receiver_tasks if not t.done()]
            if pending_receivers:
                done, pending = await asyncio.wait(
                    pending_receivers,
                    timeout=5.0,
                )

                if pending:
                    logger.debug(
                        "%d receivers still running after triggerables completed "
                        "(waiting for EOS)",
                        len(pending),
                    )

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the pipeline.

        This method performs ordered shutdown:
        1. Requests stop on all Triggerable components
        2. Waits for END_OF_STREAM propagation (with timeout)
        3. Calls on_stop lifecycle hook on all components
        4. Closes all channels

        Args:
            timeout: Maximum seconds to wait for graceful shutdown.
        """
        if not self._is_running:
            return

        logger.info("Engine shutdown initiated (timeout: %.1fs)", timeout)

        # Step 1: Request stop on all triggerables
        for name, component in self._components.items():
            if isinstance(component, Triggerable):
                logger.debug("Requesting stop on '%s'", name)
                component.request_stop()

        # Step 2: Wait for triggerables to finish (with timeout)
        if self._triggerable_tasks:
            remaining_tasks = [t for t in self._triggerable_tasks if not t.done()]
            if remaining_tasks:
                done, pending = await asyncio.wait(
                    remaining_tasks,
                    timeout=timeout / 2,
                )

                # Cancel any still running
                for task in pending:
                    logger.warning(
                        "Cancelling triggerable task '%s' (did not stop in time)",
                        task.get_name(),
                    )
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        # Step 3: Wait for receivers to finish
        if self._receiver_tasks:
            remaining_tasks = [t for t in self._receiver_tasks if not t.done()]
            if remaining_tasks:
                done, pending = await asyncio.wait(
                    remaining_tasks,
                    timeout=timeout / 2,
                )

                # Cancel any still running
                for task in pending:
                    logger.debug(
                        "Cancelling receiver task '%s'",
                        task.get_name(),
                    )
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        # Step 4: Call on_stop lifecycle hooks
        await self._call_lifecycle_hooks("on_stop")

        # Step 5: Close all channel groups
        for name, group in self._channel_groups.items():
            await group.close()
            logger.debug("Closed channel group for '%s'", name)

        # Step 6: Close all multiplex channels
        for multiplex in self._multiplex_channels:
            await multiplex.close()
            logger.debug("Closed multiplex channel '%s'", multiplex.name)

        # Step 7: Close all individual channels
        for output_ch, input_ch in self._channels:
            try:
                await output_ch.close()
            except Exception:
                pass  # Channel may already be closed
            try:
                await input_ch.close()
            except Exception:
                pass

        # Clear state
        self._receiver_tasks.clear()
        self._triggerable_tasks.clear()
        self._multiplex_channels.clear()
        self._is_running = False

        logger.info("Engine shutdown complete")

    @property
    def is_running(self) -> bool:
        """Check if the engine is currently running."""
        return self._is_running

    @property
    def components(self) -> dict[str, Component[Any]]:
        """Get the component instances (read-only view).

        Returns:
            Dictionary mapping component names to instances.
        """
        return dict(self._components)
