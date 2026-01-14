"""FlowForge exception types."""

from __future__ import annotations


class FlowForgeError(Exception):
    """Base exception for all FlowForge errors."""

    pass


class PipelineConfigError(FlowForgeError):
    """Raised when pipeline configuration is invalid.

    This includes YAML parsing errors, missing required fields,
    invalid topology, and schema validation failures.
    """

    pass


class ComponentNotFoundError(FlowForgeError):
    """Raised when a component is not found in the registry.

    This occurs when configuration references a component name
    that has not been registered via @algorithm, @data_provider,
    or custom component decorators.
    """

    def __init__(self, component_name: str, message: str | None = None) -> None:
        self.component_name = component_name
        if message is None:
            message = f"Component '{component_name}' not found in registry"
        super().__init__(message)
