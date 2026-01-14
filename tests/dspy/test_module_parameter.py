"""
Tests for DSPy module parameter configuration.

Tests that the `module` parameter correctly selects DSPy modules:
- Default "Predict" for simple pass-through
- "ChainOfThought" for reasoning traces
"""

import pytest

from tactus.dspy.agent import DSPyAgentHandle, create_dspy_agent
from tactus.dspy.config import reset_lm_configuration


class TestModuleParameterConfiguration:
    """Test module parameter configuration."""

    def setup_method(self):
        """Reset LM configuration before each test."""
        reset_lm_configuration()

    def test_default_module_is_predict(self):
        """Test that default module is Raw (simple pass-through)."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
        )
        assert agent.module == "Raw"

    def test_module_can_be_set_to_chain_of_thought(self):
        """Test that module can be explicitly set to ChainOfThought."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            module="ChainOfThought",
        )
        assert agent.module == "ChainOfThought"

    def test_module_to_strategy_mapping_predict(self):
        """Test that Predict maps to 'predict' strategy."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            module="Predict",
        )
        assert agent._module_to_strategy("Predict") == "predict"

    def test_module_to_strategy_mapping_chain_of_thought(self):
        """Test that ChainOfThought maps to 'chain_of_thought' strategy."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            module="ChainOfThought",
        )
        assert agent._module_to_strategy("ChainOfThought") == "chain_of_thought"

    def test_unknown_module_raises_error(self):
        """Test that unknown module names raise ValueError."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
        )
        with pytest.raises(ValueError, match="Unknown module"):
            agent._module_to_strategy("UnknownModule")


class TestCreateDspyAgentModule:
    """Test module parameter in create_dspy_agent factory."""

    def setup_method(self):
        """Reset LM configuration before each test."""
        reset_lm_configuration()

    def test_create_dspy_agent_default_module(self):
        """Test that create_dspy_agent uses Raw by default."""
        agent = create_dspy_agent(
            name="test_agent",
            config={
                "system_prompt": "Test prompt",
                "model": "openai/gpt-4o-mini",
            },
        )
        assert agent.module == "Raw"

    def test_create_dspy_agent_explicit_module(self):
        """Test that create_dspy_agent accepts explicit module parameter."""
        agent = create_dspy_agent(
            name="test_agent",
            config={
                "system_prompt": "Test prompt",
                "model": "openai/gpt-4o-mini",
                "module": "ChainOfThought",
            },
        )
        assert agent.module == "ChainOfThought"

    def test_create_dspy_agent_predict_module(self):
        """Test that create_dspy_agent accepts Predict module explicitly."""
        agent = create_dspy_agent(
            name="test_agent",
            config={
                "system_prompt": "Test prompt",
                "model": "openai/gpt-4o-mini",
                "module": "Predict",
            },
        )
        assert agent.module == "Predict"


class TestModuleBuildsCorrectly:
    """Test that the internal DSPy module is built with correct strategy."""

    def setup_method(self):
        """Reset LM configuration before each test."""
        reset_lm_configuration()

    def test_predict_module_uses_predict_strategy(self):
        """Test that Predict module uses predict strategy internally."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            module="Predict",
        )
        # The internal module should have the correct strategy
        assert agent._module.strategy == "predict"

    def test_chain_of_thought_module_uses_cot_strategy(self):
        """Test that ChainOfThought module uses chain_of_thought strategy internally."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            module="ChainOfThought",
        )
        # The internal module should have the correct strategy
        assert agent._module.strategy == "chain_of_thought"
