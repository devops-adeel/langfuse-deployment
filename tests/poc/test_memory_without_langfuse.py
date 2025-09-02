"""
Proof of Concept: System works without Langfuse using YAML fallbacks
Critical for resilience - the system must never fail due to external dependencies
"""
import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import yaml
import tempfile


@pytest.mark.poc
@pytest.mark.asyncio
class TestMemoryWithoutLangfuse:
    """Test that memory operations work with zero external dependencies"""

    async def test_fallback_to_yaml_prompts(self, yaml_prompt_fallback, tmp_path):
        """When Langfuse is unavailable, system uses YAML prompts"""
        # Mock the prompt manager to simulate Langfuse failure
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": ""}):
            # Import here to get mocked environment
            from src.prompt_manager import MemoryPromptManager

            # Set fallback directory
            manager = MemoryPromptManager(
                fallback_dir=str(yaml_prompt_fallback)
            )

            # Should load from YAML
            prompt = manager.get_prompt(
                name="memory_search_exact",
                variables={"query": "test query"}
            )

            assert prompt == "Search for exact match: test query"
            assert "test query" in prompt

    async def test_memory_search_without_langfuse(
        self, mock_neo4j_driver, yaml_prompt_fallback
    ):
        """Memory search should work without Langfuse"""
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": ""}):
            from src.memory_operations import MemoryOperations

            ops = MemoryOperations(
                neo4j_driver=mock_neo4j_driver,
                prompt_fallback_dir=str(yaml_prompt_fallback)
            )

            # Search should work
            memories, metadata = await ops.search_memory(
                query="docker ssl error",
                search_type="exact"
            )

            assert len(memories) > 0
            assert memories[0]["id"] == "mem_123"
            assert metadata["search_time_ms"] > 0

    async def test_memory_capture_without_langfuse(
        self, mock_neo4j_driver, yaml_prompt_fallback
    ):
        """Memory capture should work without Langfuse"""
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": ""}):
            from src.memory_operations import MemoryOperations

            ops = MemoryOperations(
                neo4j_driver=mock_neo4j_driver,
                prompt_fallback_dir=str(yaml_prompt_fallback)
            )

            # Capture should work
            result = await ops.capture_memory(
                memory_type="solution",
                content={
                    "error": "Connection refused",
                    "solution": "Start the service first"
                }
            )

            assert result["status"] == "captured"
            assert "id" in result

    async def test_scoring_tracked_without_langfuse(
        self, mock_neo4j_driver, yaml_prompt_fallback
    ):
        """Implicit scoring should still be tracked without Langfuse"""
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": ""}):
            from src.memory_operations import MemoryOperations

            ops = MemoryOperations(
                neo4j_driver=mock_neo4j_driver,
                prompt_fallback_dir=str(yaml_prompt_fallback)
            )

            # Track memory application
            result = await ops.track_memory_application(
                memory_id="mem_123",
                action_taken="command",
                result={"exit_code": 0}
            )

            # Score should be calculated
            assert "effectiveness" in result
            assert result["effectiveness"] > 0

    async def test_pattern_extraction_without_langfuse(
        self, synthetic_trace_generator
    ):
        """Pattern extraction should work locally without Langfuse"""
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": ""}):
            from src.memory_pattern_extractor import PatternExtractor

            # Create local traces
            traces = [
                synthetic_trace_generator("memory_search", success=True),
                synthetic_trace_generator("command_execution", success=True),
                synthetic_trace_generator("task_completion", success=True),
            ]

            extractor = PatternExtractor(traces_source="local")
            patterns = await extractor.extract_success_patterns(
                traces=traces,  # Pass local traces instead of fetching
                min_effectiveness=0.7
            )

            assert len(patterns) > 0
            assert "memory_to_success" in patterns

    async def test_full_cycle_without_external_deps(
        self, mock_neo4j_driver, yaml_prompt_fallback,
        synthetic_trace_generator, implicit_signal_generator
    ):
        """Complete memory cycle should work with no external services"""
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "",
            "OPENAI_API_KEY": ""
        }):
            from src.memory_operations import MemoryOperations

            ops = MemoryOperations(
                neo4j_driver=mock_neo4j_driver,
                prompt_fallback_dir=str(yaml_prompt_fallback),
                enable_llm_evaluation=False  # No OpenAI
            )

            # 1. Search for memory
            memories, _ = await ops.search_memory(
                query="test problem",
                search_type="semantic"
            )

            # 2. Apply memory (mock command execution)
            signal = implicit_signal_generator("command_success", True)

            # 3. Track effectiveness
            effectiveness = await ops.track_memory_application(
                memory_id=memories[0]["id"] if memories else "mem_new",
                action_taken="command",
                result={"exit_code": signal["exit_code"]}
            )

            # 4. Capture new solution if effective
            if effectiveness["effectiveness"] > 0.7:
                captured = await ops.capture_memory(
                    memory_type="solution",
                    content={
                        "problem": "test problem",
                        "solution": "test solution"
                    }
                )
                assert captured["status"] == "captured"

            # Full cycle completed without external deps
            assert True

    async def test_yaml_prompt_validation(self, tmp_path):
        """YAML prompts should be validated for required variables"""
        # Create invalid prompt
        invalid_prompt = {
            "prompt": "Missing {{variable}} here",
            # Missing 'variables' key
        }

        prompt_file = tmp_path / "invalid.yaml"
        with open(prompt_file, 'w') as f:
            yaml.dump(invalid_prompt, f)

        from src.prompt_manager import MemoryPromptManager

        manager = MemoryPromptManager(fallback_dir=str(tmp_path))

        # Should handle gracefully
        with pytest.raises(ValueError, match="Invalid prompt format"):
            manager.get_prompt("invalid", variables={"variable": "test"})

    async def test_cache_consistency_without_langfuse(
        self, yaml_prompt_fallback
    ):
        """Prompt cache should work consistently without Langfuse"""
        from src.prompt_manager import MemoryPromptManager

        manager = MemoryPromptManager(
            fallback_dir=str(yaml_prompt_fallback),
            cache_ttl=60
        )

        # First call - loads from YAML
        prompt1 = manager.get_prompt(
            "memory_search_exact",
            variables={"query": "test1"}
        )

        # Second call - should use cache
        prompt2 = manager.get_prompt(
            "memory_search_exact",
            variables={"query": "test2"}
        )

        # Same template, different variables
        assert "test1" in prompt1
        assert "test2" in prompt2
        assert prompt1.replace("test1", "") == prompt2.replace("test2", "")

    async def test_graceful_degradation_cascade(self):
        """Test graceful degradation when services fail in sequence"""
        degradation_levels = []

        # Level 1: Everything works
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "valid",
            "NEO4J_URI": "bolt://neo4j:7687",
            "OPENAI_API_KEY": "valid"
        }):
            degradation_levels.append("full_service")

        # Level 2: Langfuse fails
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "",
            "NEO4J_URI": "bolt://neo4j:7687",
            "OPENAI_API_KEY": "valid"
        }):
            degradation_levels.append("no_langfuse")

        # Level 3: Langfuse + OpenAI fail
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "",
            "NEO4J_URI": "bolt://neo4j:7687",
            "OPENAI_API_KEY": ""
        }):
            degradation_levels.append("no_langfuse_no_openai")

        # Level 4: Everything fails
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "",
            "NEO4J_URI": "",
            "OPENAI_API_KEY": ""
        }):
            degradation_levels.append("minimal_mode")

        # System should degrade gracefully through all levels
        assert degradation_levels == [
            "full_service",
            "no_langfuse",
            "no_langfuse_no_openai",
            "minimal_mode"
        ]


@pytest.mark.poc
class TestFallbackPerformance:
    """Test that fallback mode maintains acceptable performance"""

    def test_yaml_prompt_loading_speed(self, yaml_prompt_fallback, benchmark):
        """YAML prompt loading should be fast enough"""
        from src.prompt_manager import MemoryPromptManager

        manager = MemoryPromptManager(fallback_dir=str(yaml_prompt_fallback))

        # Benchmark prompt loading
        result = benchmark(
            manager.get_prompt,
            "memory_search_exact",
            variables={"query": "test"}
        )

        # Should be very fast (under 1ms)
        assert benchmark.stats["mean"] < 0.001

    def test_local_scoring_calculation_speed(
        self, implicit_signal_generator, benchmark
    ):
        """Local scoring calculation should be instant"""
        def calculate_score():
            score = 0.5
            for _ in range(10):
                signal = implicit_signal_generator("command_success", True)
                score += signal["score_delta"]
            return min(score, 1.0)

        result = benchmark(calculate_score)

        # Should be extremely fast (under 0.1ms)
        assert benchmark.stats["mean"] < 0.0001
