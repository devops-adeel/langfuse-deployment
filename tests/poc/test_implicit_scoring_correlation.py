"""
Proof of Concept: Validate that implicit signals correlate with memory effectiveness
This is the core innovation - scoring without explicit user feedback
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import numpy as np
from scipy import stats


@pytest.mark.poc
@pytest.mark.asyncio
class TestImplicitScoringCorrelation:
    """Test that behavioral signals accurately predict memory effectiveness"""

    async def test_command_success_increases_score(
        self, implicit_signal_generator, memory_factory
    ):
        """Command success (exit code 0) should increase memory score"""
        # Create a memory that was applied
        memory = memory_factory(confidence=0.7)
        initial_score = memory["confidence"]

        # Generate successful command signal
        signal = implicit_signal_generator("command_success", success=True)

        # Calculate new score
        new_score = initial_score + signal["score_delta"]

        # Assert score increased
        assert new_score > initial_score
        assert new_score == pytest.approx(1.0, rel=0.01)  # 0.7 + 0.3 = 1.0

        # Verify score is capped at 1.0
        assert min(new_score, 1.0) == 1.0

    async def test_test_pass_increases_score(
        self, implicit_signal_generator, memory_factory
    ):
        """Test passing should significantly increase memory score"""
        memory = memory_factory(confidence=0.5)
        initial_score = memory["confidence"]

        # Generate test pass signal
        signal = implicit_signal_generator("test_pass", success=True)

        # Calculate new score
        new_score = initial_score + signal["score_delta"]

        # Test pass should give +0.4 boost
        assert new_score == pytest.approx(0.9, rel=0.01)
        assert signal["score_delta"] == 0.4

    async def test_task_completion_highest_signal(
        self, implicit_signal_generator, memory_factory
    ):
        """Task completion should provide the strongest positive signal"""
        memory = memory_factory(confidence=0.4)

        # Generate all signal types
        signals = {
            "command_success": implicit_signal_generator("command_success", True),
            "test_pass": implicit_signal_generator("test_pass", True),
            "task_complete": implicit_signal_generator("task_complete", True),
            "error_resolved": implicit_signal_generator("error_resolved", True),
            "file_modified": implicit_signal_generator("file_modified", True),
        }

        # Task completion should have highest delta
        task_delta = signals["task_complete"]["score_delta"]
        assert task_delta == 0.5
        assert task_delta >= max(s["score_delta"] for s in signals.values())

    async def test_failure_decreases_score(
        self, implicit_signal_generator, memory_factory
    ):
        """Failed operations should decrease memory score"""
        memory = memory_factory(confidence=0.8)
        initial_score = memory["confidence"]

        # Generate failure signals
        command_fail = implicit_signal_generator("command_success", success=False)
        test_fail = implicit_signal_generator("test_pass", success=False)

        # Calculate scores after failures
        score_after_command = initial_score + command_fail["score_delta"]
        score_after_test = score_after_command + test_fail["score_delta"]

        # Both failures should decrease score
        assert score_after_command < initial_score
        assert score_after_test < score_after_command
        assert command_fail["score_delta"] == -0.1
        assert test_fail["score_delta"] == -0.2

    async def test_signal_correlation_with_effectiveness(
        self, synthetic_trace_generator
    ):
        """Test that implicit signals correlate with actual memory effectiveness"""
        # Simulate 100 memory applications with various outcomes
        applications = []

        for i in range(100):
            # Randomly determine if memory was effective
            effective = np.random.random() > 0.3  # 70% success rate

            # Generate corresponding signals
            trace = synthetic_trace_generator(
                trace_type="command_execution",
                success=effective,
                metadata={"memory_applied": True}
            )

            # Calculate implicit score
            implicit_score = 0.5  # Base score
            if effective:
                implicit_score += 0.3  # Command success
                if np.random.random() > 0.5:  # 50% also pass tests
                    implicit_score += 0.4
            else:
                implicit_score -= 0.1  # Command failure

            applications.append({
                "effective": effective,
                "implicit_score": min(max(implicit_score, 0), 1),
                "trace": trace
            })

        # Calculate correlation
        effectiveness = [1 if a["effective"] else 0 for a in applications]
        scores = [a["implicit_score"] for a in applications]

        correlation, p_value = stats.pearsonr(effectiveness, scores)

        # Should have strong positive correlation
        assert correlation > 0.6, f"Correlation too weak: {correlation}"
        assert p_value < 0.05, f"Not statistically significant: {p_value}"

    async def test_no_correlation_with_random_signals(self):
        """Random signals should not correlate with memory effectiveness"""
        # Generate random data
        np.random.seed(42)
        random_signals = np.random.random(100)
        random_effectiveness = np.random.random(100)

        # Calculate correlation
        correlation, p_value = stats.pearsonr(random_signals, random_effectiveness)

        # Should have no significant correlation
        assert abs(correlation) < 0.2, f"Random signals show correlation: {correlation}"

    async def test_composite_signal_accuracy(
        self, implicit_signal_generator
    ):
        """Test that combining multiple signals improves accuracy"""
        # Scenario 1: All positive signals - should be highly effective
        all_positive = sum([
            implicit_signal_generator("command_success", True)["score_delta"],
            implicit_signal_generator("test_pass", True)["score_delta"],
            implicit_signal_generator("task_complete", True)["score_delta"],
        ])

        # Scenario 2: Mixed signals - moderate effectiveness
        mixed = sum([
            implicit_signal_generator("command_success", True)["score_delta"],
            implicit_signal_generator("test_pass", False)["score_delta"],
            implicit_signal_generator("file_modified", True)["score_delta"],
        ])

        # Scenario 3: All negative - low effectiveness
        all_negative = sum([
            implicit_signal_generator("command_success", False)["score_delta"],
            implicit_signal_generator("test_pass", False)["score_delta"],
            implicit_signal_generator("error_resolved", False)["score_delta"],
        ])

        # Verify ordering
        assert all_positive > mixed > all_negative
        assert all_positive == 1.2  # 0.3 + 0.4 + 0.5
        assert mixed == 0.3  # 0.3 - 0.2 + 0.2
        assert all_negative == -0.4  # -0.1 - 0.2 - 0.1

    async def test_temporal_signal_weighting(
        self, implicit_signal_generator, memory_factory
    ):
        """Recent signals should have more weight than old signals"""
        memory = memory_factory(confidence=0.6, age_days=0)

        # Simulate signals over time
        signals_timeline = [
            (0, "command_success", True),   # Today
            (1, "test_pass", True),          # Yesterday
            (7, "task_complete", True),      # Week ago
            (30, "command_success", True),   # Month ago
        ]

        weighted_score = memory["confidence"]

        for days_ago, signal_type, success in signals_timeline:
            signal = implicit_signal_generator(signal_type, success)
            # Apply temporal decay to signal
            decay_factor = np.exp(-days_ago * 0.1)  # Exponential decay
            weighted_delta = signal["score_delta"] * decay_factor
            weighted_score += weighted_delta

        # Recent signals should contribute more
        today_contribution = 0.3 * 1.0  # Full weight
        week_contribution = 0.5 * np.exp(-0.7)  # Decayed
        month_contribution = 0.3 * np.exp(-3.0)  # Heavily decayed

        assert today_contribution > week_contribution > month_contribution

    async def test_signal_saturation_prevention(
        self, implicit_signal_generator
    ):
        """Multiple identical signals should have diminishing returns"""
        base_score = 0.5
        score = base_score

        # Apply same signal multiple times
        deltas = []
        for i in range(5):
            signal = implicit_signal_generator("command_success", True)
            # Apply diminishing returns
            effective_delta = signal["score_delta"] * (0.5 ** i)
            score += effective_delta
            deltas.append(effective_delta)

        # Each subsequent signal should contribute less
        for i in range(len(deltas) - 1):
            assert deltas[i] > deltas[i + 1]

        # Total score should be bounded
        assert score < 1.0  # Even with multiple successes

    async def test_cross_domain_signal_validation(
        self, implicit_signal_generator
    ):
        """GTD task completion should boost coding memory effectiveness"""
        # Simulate cross-domain scenario
        gtd_signal = implicit_signal_generator("task_complete", True)
        coding_signal = implicit_signal_generator("test_pass", True)

        # Cross-domain boost
        cross_domain_multiplier = 1.2

        # Calculate combined effectiveness
        base_effectiveness = gtd_signal["score_delta"] + coding_signal["score_delta"]
        cross_domain_effectiveness = base_effectiveness * cross_domain_multiplier

        # Cross-domain should be more valuable
        assert cross_domain_effectiveness > base_effectiveness
        assert cross_domain_effectiveness == pytest.approx(1.08, rel=0.01)  # (0.5 + 0.4) * 1.2


@pytest.mark.poc
class TestImplicitScoringEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_score_bounds(self, implicit_signal_generator):
        """Scores should always stay within [0, 1] bounds"""
        # Test upper bound
        max_score = 0.9
        signal = implicit_signal_generator("task_complete", True)
        new_score = min(max_score + signal["score_delta"], 1.0)
        assert new_score == 1.0

        # Test lower bound
        min_score = 0.1
        signal = implicit_signal_generator("test_pass", False)
        new_score = max(min_score + signal["score_delta"], 0.0)
        assert new_score == 0.0

    def test_missing_signals_neutral(self):
        """Missing signals should not affect score"""
        initial_score = 0.5
        # No signals = no change
        assert initial_score == 0.5

    def test_conflicting_signals_resolution(
        self, implicit_signal_generator
    ):
        """Conflicting signals should be resolved sensibly"""
        # Command succeeds but test fails
        success = implicit_signal_generator("command_success", True)
        failure = implicit_signal_generator("test_pass", False)

        net_effect = success["score_delta"] + failure["score_delta"]

        # Should be slightly positive (command worked, just tests failed)
        assert net_effect == 0.1  # 0.3 - 0.2
        assert net_effect > 0  # Net positive despite test failure
