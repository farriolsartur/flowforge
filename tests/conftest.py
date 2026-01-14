"""Shared pytest fixtures for FlowForge tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from flowforge import Message, MessageType


@pytest.fixture
def sample_data_message() -> Message[dict[str, Any]]:
    """Create a sample DATA message for testing."""
    return Message.data(
        payload={"value": 42, "name": "test"},
        source_component="test_provider",
    )


@pytest.fixture
def sample_error_message() -> Message[str]:
    """Create a sample ERROR message for testing."""
    return Message.error(
        error="Something went wrong",
        source_component="test_component",
    )


@pytest.fixture
def sample_eos_message() -> Message[None]:
    """Create a sample END_OF_STREAM message for testing."""
    return Message.end_of_stream(source_component="test_provider")
