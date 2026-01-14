"""Tests for FlowForge exception types."""

from __future__ import annotations

import pytest

from flowforge import ComponentNotFoundError, FlowForgeError, PipelineConfigError


class TestFlowForgeError:
    """Tests for the base FlowForgeError exception."""

    def test_is_exception(self) -> None:
        """FlowForgeError should be an Exception subclass."""
        assert issubclass(FlowForgeError, Exception)

    def test_can_raise_and_catch(self) -> None:
        """FlowForgeError can be raised and caught."""
        with pytest.raises(FlowForgeError) as exc_info:
            raise FlowForgeError("test error")
        assert str(exc_info.value) == "test error"


class TestPipelineConfigError:
    """Tests for PipelineConfigError exception."""

    def test_is_flowforge_error(self) -> None:
        """PipelineConfigError should be a FlowForgeError subclass."""
        assert issubclass(PipelineConfigError, FlowForgeError)

    def test_can_raise_with_message(self) -> None:
        """PipelineConfigError can be raised with a message."""
        with pytest.raises(PipelineConfigError) as exc_info:
            raise PipelineConfigError("Invalid YAML syntax")
        assert "Invalid YAML syntax" in str(exc_info.value)

    def test_caught_as_flowforge_error(self) -> None:
        """PipelineConfigError can be caught as FlowForgeError."""
        with pytest.raises(FlowForgeError):
            raise PipelineConfigError("config error")


class TestComponentNotFoundError:
    """Tests for ComponentNotFoundError exception."""

    def test_is_flowforge_error(self) -> None:
        """ComponentNotFoundError should be a FlowForgeError subclass."""
        assert issubclass(ComponentNotFoundError, FlowForgeError)

    def test_stores_component_name(self) -> None:
        """ComponentNotFoundError should store the component name."""
        error = ComponentNotFoundError("my_algorithm")
        assert error.component_name == "my_algorithm"

    def test_default_message(self) -> None:
        """ComponentNotFoundError generates a default message."""
        error = ComponentNotFoundError("my_algorithm")
        assert "my_algorithm" in str(error)
        assert "not found" in str(error).lower()

    def test_custom_message(self) -> None:
        """ComponentNotFoundError accepts a custom message."""
        error = ComponentNotFoundError(
            "my_algorithm",
            message="Custom error: my_algorithm is not registered"
        )
        assert "Custom error" in str(error)

    def test_caught_as_flowforge_error(self) -> None:
        """ComponentNotFoundError can be caught as FlowForgeError."""
        with pytest.raises(FlowForgeError):
            raise ComponentNotFoundError("missing_component")
