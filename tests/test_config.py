"""Tests for FlowForge Phase 4: Configuration System.

This module tests:
- Pydantic configuration models
- ConfigLoader YAML parsing
- Validation against registry and topology
- Defaults propagation
- Error handling for invalid configs
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from flowforge.communication.enums import (
    BackpressureMode,
    CompetingStrategy,
    DistributionMode,
    StartupSyncStrategy,
)
from flowforge.config import (
    BackpressureConfig,
    ComponentInstanceConfig,
    ConfigLoader,
    ConnectionConfig,
    DefaultsConfig,
    GlobalConfig,
    PipelineConfig,
    TransportConfig,
    WorkerConfig,
)
from flowforge.exceptions import PipelineConfigError


# =============================================================================
# Fixtures
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def loader() -> ConfigLoader:
    """Create a ConfigLoader instance."""
    return ConfigLoader()


@pytest.fixture
def simple_yaml_content() -> str:
    """Simple valid YAML configuration."""
    return """
global:
  name: test_pipeline
  version: "1.0"

algorithms:
  - name: algo_1
    type: test_algorithm
    config: {}

data_providers:
  - name: provider_1
    type: test_provider
    config: {}

connections:
  - source: provider_1
    targets: [algo_1]
"""


# =============================================================================
# BackpressureConfig Tests
# =============================================================================


class TestBackpressureConfig:
    """Tests for BackpressureConfig model."""

    def test_default_values(self) -> None:
        """Test default values are applied correctly."""
        config = BackpressureConfig()
        assert config.mode == BackpressureMode.BLOCK
        assert config.queue_size == 1000

    def test_string_mode_parsing_block(self) -> None:
        """Test that string 'block' is parsed to enum."""
        config = BackpressureConfig(mode="block")
        assert config.mode == BackpressureMode.BLOCK

    def test_string_mode_parsing_drop(self) -> None:
        """Test that string 'drop' is parsed to enum."""
        config = BackpressureConfig(mode="drop")
        assert config.mode == BackpressureMode.DROP

    def test_string_mode_case_insensitive(self) -> None:
        """Test that mode parsing is case-insensitive."""
        config = BackpressureConfig(mode="DROP")
        assert config.mode == BackpressureMode.DROP

    def test_invalid_mode_raises(self) -> None:
        """Test that invalid mode raises ValidationError."""
        with pytest.raises(ValidationError):
            BackpressureConfig(mode="invalid")

    def test_queue_size_must_be_positive(self) -> None:
        """Test that queue_size must be at least 1."""
        with pytest.raises(ValidationError):
            BackpressureConfig(queue_size=0)

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields raise ValidationError."""
        with pytest.raises(ValidationError):
            BackpressureConfig(mode="block", extra_field="value")


# =============================================================================
# DefaultsConfig Tests
# =============================================================================


class TestDefaultsConfig:
    """Tests for DefaultsConfig model."""

    def test_default_values(self) -> None:
        """Test default values are applied correctly."""
        config = DefaultsConfig()
        assert config.serialization == "json"
        assert config.distribution == DistributionMode.FAN_OUT
        assert config.strategy == CompetingStrategy.ROUND_ROBIN
        assert config.backpressure.mode == BackpressureMode.BLOCK

    def test_distribution_string_parsing_fan_out(self) -> None:
        """Test that string 'fan_out' is parsed to enum."""
        config = DefaultsConfig(distribution="fan_out")
        assert config.distribution == DistributionMode.FAN_OUT

    def test_distribution_string_parsing_hyphen(self) -> None:
        """Test that string 'fan-out' is parsed to enum."""
        config = DefaultsConfig(distribution="fan-out")
        assert config.distribution == DistributionMode.FAN_OUT

    def test_distribution_competing(self) -> None:
        """Test that competing distribution is parsed."""
        config = DefaultsConfig(distribution="competing")
        assert config.distribution == DistributionMode.COMPETING

    def test_strategy_string_parsing(self) -> None:
        """Test that strategy strings are parsed."""
        config = DefaultsConfig(strategy="round_robin")
        assert config.strategy == CompetingStrategy.ROUND_ROBIN

    def test_strategy_random(self) -> None:
        """Test random strategy parsing."""
        config = DefaultsConfig(strategy="random")
        assert config.strategy == CompetingStrategy.RANDOM

    def test_invalid_serialization_raises(self) -> None:
        """Test that invalid serialization raises ValidationError."""
        with pytest.raises(ValidationError):
            DefaultsConfig(serialization="invalid")

    def test_nested_backpressure(self) -> None:
        """Test that nested backpressure config works."""
        config = DefaultsConfig(
            backpressure=BackpressureConfig(mode="drop", queue_size=500)
        )
        assert config.backpressure.mode == BackpressureMode.DROP
        assert config.backpressure.queue_size == 500


# =============================================================================
# TransportConfig Tests
# =============================================================================


class TestTransportConfig:
    """Tests for TransportConfig model."""

    def test_required_type(self) -> None:
        """Test that type is required."""
        with pytest.raises(ValidationError):
            TransportConfig()

    def test_config_defaults_to_empty(self) -> None:
        """Test that config defaults to empty dict."""
        config = TransportConfig(type="zeromq")
        assert config.type == "zeromq"
        assert config.config == {}

    def test_with_config(self) -> None:
        """Test with additional config."""
        config = TransportConfig(type="zeromq", config={"port": 5555})
        assert config.config["port"] == 5555


# =============================================================================
# WorkerConfig Tests
# =============================================================================


class TestWorkerConfig:
    """Tests for WorkerConfig model."""

    def test_name_required(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError):
            WorkerConfig()

    def test_host_defaults_to_localhost(self) -> None:
        """Test that host defaults to localhost."""
        config = WorkerConfig(name="worker_1")
        assert config.host == "localhost"

    def test_with_custom_host(self) -> None:
        """Test with custom host."""
        config = WorkerConfig(name="worker_1", host="192.168.1.100")
        assert config.host == "192.168.1.100"

    def test_empty_name_raises(self) -> None:
        """Test that empty name raises ValidationError."""
        with pytest.raises(ValidationError):
            WorkerConfig(name="")


# =============================================================================
# ComponentInstanceConfig Tests
# =============================================================================


class TestComponentInstanceConfig:
    """Tests for ComponentInstanceConfig model."""

    def test_name_required(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError):
            ComponentInstanceConfig(type="some_type")

    def test_type_required(self) -> None:
        """Test that type is required."""
        with pytest.raises(ValidationError):
            ComponentInstanceConfig(name="my_algo")

    def test_defaults(self) -> None:
        """Test default values."""
        config = ComponentInstanceConfig(name="my_algo", type="algorithm_impl")
        assert config.name == "my_algo"
        assert config.type == "algorithm_impl"
        assert config.worker is None
        assert config.config == {}

    def test_with_worker(self) -> None:
        """Test with worker assignment."""
        config = ComponentInstanceConfig(
            name="my_algo", type="algorithm_impl", worker="worker_1"
        )
        assert config.worker == "worker_1"

    def test_with_config(self) -> None:
        """Test with component-specific config."""
        config = ComponentInstanceConfig(
            name="my_algo",
            type="algorithm_impl",
            config={"threshold": 0.5, "max_items": 100},
        )
        assert config.config["threshold"] == 0.5

    def test_empty_type_raises(self) -> None:
        """Test that empty type raises ValidationError."""
        with pytest.raises(ValidationError):
            ComponentInstanceConfig(name="my_algo", type="")

    def test_empty_name_raises(self) -> None:
        """Test that empty name raises ValidationError."""
        with pytest.raises(ValidationError):
            ComponentInstanceConfig(name="", type="some_type")


# =============================================================================
# ConnectionConfig Tests
# =============================================================================


class TestConnectionConfig:
    """Tests for ConnectionConfig model."""

    def test_required_fields(self) -> None:
        """Test that source and targets are required."""
        with pytest.raises(ValidationError):
            ConnectionConfig()

    def test_targets_must_not_be_empty(self) -> None:
        """Test that targets must have at least one element."""
        with pytest.raises(ValidationError):
            ConnectionConfig(source="provider", targets=[])

    def test_defaults(self) -> None:
        """Test default values (None for optional overrides)."""
        config = ConnectionConfig(source="provider", targets=["algo"])
        assert config.distribution is None
        assert config.strategy is None
        assert config.serialization is None
        assert config.backpressure is None

    def test_with_overrides(self) -> None:
        """Test with all overrides specified."""
        config = ConnectionConfig(
            source="provider",
            targets=["algo1", "algo2"],
            distribution="competing",
            strategy="random",
            serialization="msgpack",
            backpressure=BackpressureConfig(mode="drop", queue_size=100),
        )
        assert config.distribution == DistributionMode.COMPETING
        assert config.strategy == CompetingStrategy.RANDOM
        assert config.serialization == "msgpack"
        assert config.backpressure.mode == BackpressureMode.DROP

    def test_distribution_hyphen_parsing(self) -> None:
        """Test that 'fan-out' is parsed correctly."""
        config = ConnectionConfig(
            source="provider", targets=["algo"], distribution="fan-out"
        )
        assert config.distribution == DistributionMode.FAN_OUT


# =============================================================================
# GlobalConfig Tests
# =============================================================================


class TestGlobalConfig:
    """Tests for GlobalConfig model."""

    def test_name_required(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError):
            GlobalConfig()

    def test_defaults(self) -> None:
        """Test default values."""
        config = GlobalConfig(name="my_pipeline")
        assert config.version == "1.0"
        assert config.defaults.serialization == "json"
        assert config.transport is None
        assert config.sync_strategy == StartupSyncStrategy.RETRY_BACKOFF

    def test_sync_strategy_string_parsing(self) -> None:
        """Test that sync_strategy accepts strings."""
        config = GlobalConfig(name="my_pipeline", sync_strategy="retry_backoff")
        assert config.sync_strategy == StartupSyncStrategy.RETRY_BACKOFF

    def test_sync_strategy_control_channel(self) -> None:
        """Test control_channel sync strategy."""
        config = GlobalConfig(name="my_pipeline", sync_strategy="control_channel")
        assert config.sync_strategy == StartupSyncStrategy.CONTROL_CHANNEL

    def test_with_transport(self) -> None:
        """Test with transport configuration."""
        config = GlobalConfig(
            name="my_pipeline", transport=TransportConfig(type="zeromq")
        )
        assert config.transport.type == "zeromq"


# =============================================================================
# PipelineConfig Tests
# =============================================================================


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    def test_global_config_required(self) -> None:
        """Test that global_config is required."""
        with pytest.raises(ValidationError):
            PipelineConfig()

    def test_defaults(self) -> None:
        """Test default values."""
        config = PipelineConfig(global_config=GlobalConfig(name="test"))
        assert config.workers == []
        assert config.connections == []
        assert config.components_by_type == {}

    def test_get_all_component_instances(self) -> None:
        """Test get_all_component_instances helper method."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="algo_1", type="test_algo"),
                    ComponentInstanceConfig(name="algo_2", type="test_algo"),
                ],
                "data_provider": [
                    ComponentInstanceConfig(name="provider_1", type="test_provider")
                ],
            },
        )

        instances = config.get_all_component_instances()
        assert len(instances) == 3
        assert "algo_1" in instances
        assert "algo_2" in instances
        assert "provider_1" in instances

    def test_get_component_type(self) -> None:
        """Test get_component_type helper method."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="algo_1", type="test_algo")
                ],
                "data_provider": [
                    ComponentInstanceConfig(name="provider_1", type="test_provider")
                ],
            },
        )

        assert config.get_component_type("algo_1") == "algorithm"
        assert config.get_component_type("provider_1") == "data_provider"
        assert config.get_component_type("nonexistent") is None


# =============================================================================
# ConfigLoader Parsing Tests
# =============================================================================


class TestConfigLoaderParsing:
    """Tests for ConfigLoader YAML parsing."""

    def test_load_from_string_simple(
        self, loader: ConfigLoader, simple_yaml_content: str
    ) -> None:
        """Test loading from a simple YAML string."""
        config = loader.load_from_string(simple_yaml_content)

        assert config.global_config.name == "test_pipeline"
        assert config.global_config.version == "1.0"
        assert "algorithm" in config.components_by_type
        assert "data_provider" in config.components_by_type
        assert len(config.connections) == 1

    def test_load_from_string_missing_global(self, loader: ConfigLoader) -> None:
        """Test that missing global section raises error."""
        yaml_content = """
algorithms:
  - name: algo_1
    type: test_algo
    config: {}
"""
        with pytest.raises(PipelineConfigError, match="missing required 'global'"):
            loader.load_from_string(yaml_content)

    def test_load_from_string_invalid_yaml(self, loader: ConfigLoader) -> None:
        """Test that invalid YAML raises error."""
        yaml_content = "invalid: yaml: content:"
        with pytest.raises(PipelineConfigError, match="Invalid YAML"):
            loader.load_from_string(yaml_content)

    def test_load_from_string_not_mapping(self, loader: ConfigLoader) -> None:
        """Test that non-mapping YAML raises error."""
        yaml_content = "- item1\n- item2"
        with pytest.raises(PipelineConfigError, match="must be a YAML mapping"):
            loader.load_from_string(yaml_content)

    def test_load_file(self, loader: ConfigLoader) -> None:
        """Test loading from a file."""
        config = loader.load(FIXTURES_DIR / "valid_simple.yaml")

        assert config.global_config.name == "simple_pipeline"
        assert len(config.connections) == 1

    def test_load_file_not_found(self, loader: ConfigLoader) -> None:
        """Test that FileNotFoundError is wrapped."""
        with pytest.raises(PipelineConfigError, match="not found"):
            loader.load("/nonexistent/path/config.yaml")

    def test_load_fanout_config(self, loader: ConfigLoader) -> None:
        """Test loading fan-out configuration."""
        config = loader.load(FIXTURES_DIR / "valid_fanout.yaml")

        assert config.global_config.name == "fanout_pipeline"
        assert len(config.components_by_type.get("algorithm", [])) == 3
        assert config.connections[0].distribution == DistributionMode.FAN_OUT

    def test_load_competing_config(self, loader: ConfigLoader) -> None:
        """Test loading competing configuration."""
        config = loader.load(FIXTURES_DIR / "valid_competing.yaml")

        assert config.global_config.name == "competing_pipeline"
        assert config.connections[0].distribution == DistributionMode.COMPETING
        assert config.connections[0].strategy == CompetingStrategy.ROUND_ROBIN

    def test_load_with_workers(self, loader: ConfigLoader) -> None:
        """Test loading configuration with workers."""
        config = loader.load(FIXTURES_DIR / "valid_with_workers.yaml")

        assert len(config.workers) == 2
        assert config.workers[0].name == "data_worker"
        assert config.workers[1].name == "processing_worker"
        assert config.workers[1].config.get("threads") == 4

    def test_plural_to_singular_normalization(
        self, loader: ConfigLoader, simple_yaml_content: str
    ) -> None:
        """Test that plural section names are normalized to singular."""
        config = loader.load_from_string(simple_yaml_content)

        # 'algorithms' in YAML should become 'algorithm'
        assert "algorithm" in config.components_by_type
        # 'data_providers' should become 'data_provider'
        assert "data_provider" in config.components_by_type


# =============================================================================
# ConfigLoader Validation Tests
# =============================================================================


class TestConfigLoaderValidation:
    """Tests for ConfigLoader validation."""

    def test_validate_valid_config(self, loader: ConfigLoader) -> None:
        """Test that valid config passes validation."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            connections=[
                ConnectionConfig(source="provider_1", targets=["algo_1"])
            ],
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="algo_1", type="test_algo")
                ],
                "data_provider": [
                    ComponentInstanceConfig(name="provider_1", type="test_provider")
                ],
            },
        )

        errors = loader.validate(config)
        assert len(errors) == 0

    def test_validate_missing_source(self, loader: ConfigLoader) -> None:
        """Test that missing source is detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            connections=[
                ConnectionConfig(source="nonexistent", targets=["algo_1"])
            ],
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="algo_1", type="test_algo")
                ],
            },
        )

        errors = loader.validate(config)
        assert len(errors) >= 1
        assert any("nonexistent" in e and "not found" in e for e in errors)

    def test_validate_missing_target(self, loader: ConfigLoader) -> None:
        """Test that missing target is detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            connections=[
                ConnectionConfig(source="provider_1", targets=["nonexistent"])
            ],
            components_by_type={
                "data_provider": [
                    ComponentInstanceConfig(name="provider_1", type="test_provider")
                ],
            },
        )

        errors = loader.validate(config)
        assert len(errors) >= 1
        assert any("nonexistent" in e and "not found" in e for e in errors)

    def test_validate_self_loop(self, loader: ConfigLoader) -> None:
        """Test that self-loop is detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            connections=[
                ConnectionConfig(source="algo_1", targets=["algo_1"])
            ],
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="algo_1", type="test_algo")
                ],
            },
        )

        errors = loader.validate(config)
        assert len(errors) >= 1
        assert any("cannot target itself" in e for e in errors)

    def test_validate_duplicate_instance_names(self, loader: ConfigLoader) -> None:
        """Test that duplicate instance names are detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            connections=[],
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="duplicate", type="test_algo")
                ],
                "data_provider": [
                    ComponentInstanceConfig(name="duplicate", type="test_provider")
                ],
            },
        )

        errors = loader.validate(config)
        assert len(errors) >= 1
        assert any("Duplicate" in e and "duplicate" in e for e in errors)

    def test_validate_duplicate_worker_names(self, loader: ConfigLoader) -> None:
        """Test that duplicate worker names are detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            workers=[
                WorkerConfig(name="worker_1"),
                WorkerConfig(name="worker_1"),
            ],
        )

        errors = loader.validate(config)
        assert len(errors) >= 1
        assert any("Duplicate worker" in e for e in errors)

    def test_validate_unknown_worker_reference(self, loader: ConfigLoader) -> None:
        """Test that unknown worker reference is detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            workers=[WorkerConfig(name="worker_1")],
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(
                        name="algo_1", type="test_algo", worker="nonexistent_worker"
                    )
                ],
            },
        )

        errors = loader.validate(config)
        assert len(errors) >= 1
        assert any("unknown worker" in e.lower() for e in errors)

    def test_validate_from_fixture_invalid_missing(
        self, loader: ConfigLoader
    ) -> None:
        """Test validation of invalid_missing_component fixture."""
        config = loader.load(FIXTURES_DIR / "invalid_missing_component.yaml")
        errors = loader.validate(config)

        assert len(errors) >= 1
        assert any("nonexistent_provider" in e for e in errors)

    def test_validate_from_fixture_invalid_topology(
        self, loader: ConfigLoader
    ) -> None:
        """Test validation of invalid_topology fixture (self-loop)."""
        config = loader.load(FIXTURES_DIR / "invalid_topology.yaml")
        errors = loader.validate(config)

        assert len(errors) >= 1
        assert any("cannot target itself" in e for e in errors)

    def test_validate_from_fixture_invalid_worker(
        self, loader: ConfigLoader
    ) -> None:
        """Test validation of invalid_unknown_worker fixture."""
        config = loader.load(FIXTURES_DIR / "invalid_unknown_worker.yaml")
        errors = loader.validate(config)

        assert len(errors) >= 1
        assert any("nonexistent_worker" in e for e in errors)


# =============================================================================
# ConfigLoader Registry Validation Tests
# =============================================================================


class TestConfigLoaderRegistryValidation:
    """Tests for ConfigLoader registry-based validation."""

    def test_validate_with_registry_valid_types(self, loader: ConfigLoader) -> None:
        """Test that valid component types pass registry validation."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(name="algo_1", type="test_algo")
                ],
                "data_provider": [
                    ComponentInstanceConfig(name="provider_1", type="test_provider")
                ],
            },
        )

        errors = loader.validate_with_registry(config)
        # No errors for unknown section types because algorithm and data_provider are registered
        assert not any("Unknown component type" in e for e in errors)

    def test_validate_with_registry_unknown_section_type(
        self, loader: ConfigLoader
    ) -> None:
        """Test that unknown component section type is detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            components_by_type={
                "unknown_type": [
                    ComponentInstanceConfig(name="instance_1", type="some_impl")
                ],
            },
        )

        errors = loader.validate_with_registry(config)
        assert len(errors) >= 1
        assert any("Unknown component type" in e and "unknown_type" in e for e in errors)

    def test_validate_with_registry_unknown_instance_type(
        self, loader: ConfigLoader
    ) -> None:
        """Test that unknown component instance type is detected."""
        config = PipelineConfig(
            global_config=GlobalConfig(name="test"),
            components_by_type={
                "algorithm": [
                    ComponentInstanceConfig(
                        name="algo_1", type="nonexistent_component"
                    )
                ],
            },
        )

        errors = loader.validate_with_registry(config)
        assert len(errors) >= 1
        assert any(
            "nonexistent_component" in e and "unknown type" in e.lower()
            for e in errors
        )


# =============================================================================
# Defaults Propagation Tests
# =============================================================================


class TestDefaultsPropagation:
    """Tests for defaults propagation logic."""

    def test_connection_inherits_none_for_defaults(self) -> None:
        """Test that connection-level overrides are None when not specified."""
        config = PipelineConfig(
            global_config=GlobalConfig(
                name="test",
                defaults=DefaultsConfig(
                    distribution=DistributionMode.COMPETING,
                    strategy=CompetingStrategy.RANDOM,
                ),
            ),
            connections=[
                ConnectionConfig(source="a", targets=["b"])
            ],
            components_by_type={
                "data_provider": [
                    ComponentInstanceConfig(name="a", type="test_provider")
                ],
                "algorithm": [
                    ComponentInstanceConfig(name="b", type="test_algo")
                ],
            },
        )

        conn = config.connections[0]
        # Connection-level overrides should be None (not overridden)
        assert conn.distribution is None
        assert conn.strategy is None
        # The engine would apply defaults from global_config when conn.* is None

    def test_connection_override_takes_precedence(self) -> None:
        """Test that connection-level overrides take precedence."""
        config = PipelineConfig(
            global_config=GlobalConfig(
                name="test",
                defaults=DefaultsConfig(
                    distribution=DistributionMode.FAN_OUT,
                    serialization="json",
                ),
            ),
            connections=[
                ConnectionConfig(
                    source="a",
                    targets=["b"],
                    distribution=DistributionMode.COMPETING,
                    serialization="msgpack",
                )
            ],
            components_by_type={
                "data_provider": [
                    ComponentInstanceConfig(name="a", type="test_provider")
                ],
                "algorithm": [
                    ComponentInstanceConfig(name="b", type="test_algo")
                ],
            },
        )

        conn = config.connections[0]
        # Connection-level overrides should be set
        assert conn.distribution == DistributionMode.COMPETING
        assert conn.serialization == "msgpack"


# =============================================================================
# Integration Tests
# =============================================================================


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_full_pipeline_config_from_yaml(self, loader: ConfigLoader) -> None:
        """Test loading and validating a full pipeline configuration."""
        config = loader.load(FIXTURES_DIR / "valid_with_workers.yaml")
        errors = loader.validate(config)

        assert len(errors) == 0
        assert config.global_config.name == "distributed_pipeline"
        assert config.global_config.version == "2.0"
        assert config.global_config.defaults.serialization == "msgpack"
        assert config.global_config.defaults.backpressure.queue_size == 500
        assert len(config.workers) == 2
        assert len(config.components_by_type.get("algorithm", [])) == 2
        assert len(config.components_by_type.get("data_provider", [])) == 1
        assert len(config.connections) == 1

    def test_config_roundtrip_helpers(self, loader: ConfigLoader) -> None:
        """Test that helper methods work correctly after loading."""
        config = loader.load(FIXTURES_DIR / "valid_simple.yaml")

        all_instances = config.get_all_component_instances()
        assert "counter_1" in all_instances
        assert "printer_1" in all_instances

        assert config.get_component_type("counter_1") == "data_provider"
        assert config.get_component_type("printer_1") == "algorithm"

    def test_config_exports_from_main_module(self) -> None:
        """Test that config classes are exported from main flowforge module."""
        import flowforge

        assert hasattr(flowforge, "ConfigLoader")
        assert hasattr(flowforge, "PipelineConfig")
        assert hasattr(flowforge, "GlobalConfig")
        assert hasattr(flowforge, "ConnectionConfig")
        assert hasattr(flowforge, "BackpressureConfig")
        assert hasattr(flowforge, "DefaultsConfig")
        assert hasattr(flowforge, "WorkerConfig")
        assert hasattr(flowforge, "ComponentInstanceConfig")
        assert hasattr(flowforge, "TransportConfig")
