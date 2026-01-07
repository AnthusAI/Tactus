"""
Tests for determinism safety warnings.

Tests that non-deterministic functions (math.random, os.time, etc.)
trigger warnings when called outside checkpoint boundaries.
"""

import pytest
import warnings
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


class TestDeterminismWarnings:
    """Test suite for determinism warning system."""

    @pytest.mark.asyncio
    async def test_random_outside_checkpoint_warns(self):
        """math.random() outside checkpoint should emit warning."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            -- This should warn
            local x = math.random()
            return {value = x}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-warn", storage_backend=storage)

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = await runtime.execute(source=source, context={}, format="lua")

            # Check warning was emitted
            assert len(w) >= 1
            warning_messages = [str(warning.message) for warning in w]
            assert any("DETERMINISM WARNING" in msg for msg in warning_messages)
            assert any("math.random()" in msg for msg in warning_messages)

        # Execution should succeed despite warning
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_random_inside_checkpoint_no_warn(self):
        """math.random() inside checkpoint should NOT warn."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            -- This should NOT warn - inside Step.checkpoint
            local x = Step.checkpoint(function()
                return math.random()
            end)
            return {value = x}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-no-warn", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = await runtime.execute(source=source, context={}, format="lua")

            # No determinism warnings should be emitted
            warning_messages = [str(warning.message) for warning in w]
            determinism_warnings = [msg for msg in warning_messages if "DETERMINISM WARNING" in msg]
            assert len(determinism_warnings) == 0

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_os_time_warns(self):
        """os.time() outside checkpoint should warn."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {timestamp = {type = "number"}}
        }, function()
            local t = os.time()
            return {timestamp = t}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-time", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await runtime.execute(source=source, context={}, format="lua")

            warning_messages = [str(warning.message) for warning in w]
            assert any("os.time()" in msg for msg in warning_messages)

    @pytest.mark.asyncio
    async def test_os_date_warns(self):
        """os.date() outside checkpoint should warn."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {date = {type = "string"}}
        }, function()
            local d = os.date()
            return {date = d}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-date", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await runtime.execute(source=source, context={}, format="lua")

            warning_messages = [str(warning.message) for warning in w]
            assert any("os.date()" in msg for msg in warning_messages)

    @pytest.mark.asyncio
    async def test_deterministic_math_no_warn(self):
        """Deterministic math functions should NOT warn."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            -- These are deterministic, should not warn
            local x = math.sin(1.0)
            local y = math.sqrt(2.0)
            local z = math.floor(3.7)
            return {value = x + y + z}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-determ", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = await runtime.execute(source=source, context={}, format="lua")

            # No determinism warnings
            warning_messages = [str(warning.message) for warning in w]
            determinism_warnings = [msg for msg in warning_messages if "DETERMINISM WARNING" in msg]
            assert len(determinism_warnings) == 0

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_strict_mode_raises_error(self):
        """Strict mode should raise error instead of warning."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            local x = math.random()
            return {value = x}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(
            procedure_id="test-strict",
            storage_backend=storage,
            external_config={"strict_determinism": True},
        )

        # Should raise error, not just warn
        result = await runtime.execute(source=source, context={}, format="lua")

        assert result["success"] is False
        assert "error" in result
        assert "DETERMINISM WARNING" in result["error"]

    @pytest.mark.asyncio
    async def test_nested_checkpoints(self):
        """Nested checkpoints should maintain scope correctly."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            local outer = Step.checkpoint(function()
                local x = math.random()  -- OK: inside outer checkpoint

                local inner = Step.checkpoint(function()
                    return math.random()  -- OK: inside inner checkpoint
                end)

                return x + inner
            end)
            return {value = outer}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-nested", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = await runtime.execute(source=source, context={}, format="lua")

            # No determinism warnings
            warning_messages = [str(warning.message) for warning in w]
            determinism_warnings = [msg for msg in warning_messages if "DETERMINISM WARNING" in msg]
            assert len(determinism_warnings) == 0

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_math_random_three_forms(self):
        """Test all three forms of math.random() work correctly."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {
                a = {type = "number"},
                b = {type = "number"},
                c = {type = "number"}
            }
        }, function()
            local a = Step.checkpoint(function() return math.random() end)  -- [0, 1)
            local b = Step.checkpoint(function() return math.random(10) end)  -- [1, 10]
            local c = Step.checkpoint(function() return math.random(5, 15) end)
            return {a = a, b = b, c = c}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-forms", storage_backend=storage)

        result = await runtime.execute(source=source, context={}, format="lua")

        assert result["success"] is True
        # Verify ranges
        assert 0 <= result["result"]["a"] < 1
        assert 1 <= result["result"]["b"] <= 10
        assert 5 <= result["result"]["c"] <= 15

    @pytest.mark.asyncio
    async def test_warning_message_format(self):
        """Verify warning messages are clear and actionable."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            local x = math.random()
            return {value = x}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-msg", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await runtime.execute(source=source, context={}, format="lua")

            # Find the determinism warning
            warning_messages = [str(warning.message) for warning in w]
            determinism_warnings = [msg for msg in warning_messages if "DETERMINISM WARNING" in msg]

            assert len(determinism_warnings) > 0
            msg = determinism_warnings[0]

            # Check message contains key elements
            assert "math.random()" in msg
            assert "checkpoint" in msg.lower()
            assert "Step.checkpoint" in msg
            assert "replay" in msg.lower()
            assert "determinism" in msg.lower()

    @pytest.mark.asyncio
    async def test_randomseed_warns(self):
        """math.randomseed() outside checkpoint should warn."""
        source = """
        main = Procedure("main", {
            input = {},
            output = {value = {type = "number"}}
        }, function()
            math.randomseed(42)  -- Should warn
            local x = math.random()  -- Also warns
            return {value = x}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-seed", storage_backend=storage)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await runtime.execute(source=source, context={}, format="lua")

            warning_messages = [str(warning.message) for warning in w]
            # Should have warnings for both randomseed and random
            assert any("randomseed()" in msg for msg in warning_messages)
            assert any("random()" in msg for msg in warning_messages)
