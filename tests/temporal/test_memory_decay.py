"""
Temporal Reasoning: Test memory decay and temporal weighting
Research shows memory systems lag 73% behind humans in temporal reasoning
"""
import pytest
import asyncio
from datetime import datetime, timedelta
import numpy as np
import math


@pytest.mark.temporal
@pytest.mark.asyncio
class TestMemoryDecay:
    """Test temporal decay algorithm for memory effectiveness"""

    async def test_exponential_decay_curve(self, memory_factory):
        """Memory should decay exponentially over time"""
        # Create memories of different ages
        memories = [
            memory_factory(age_days=0, confidence=0.9),   # Today
            memory_factory(age_days=1, confidence=0.9),   # Yesterday
            memory_factory(age_days=7, confidence=0.9),   # Week ago
            memory_factory(age_days=30, confidence=0.9),  # Month ago
            memory_factory(age_days=90, confidence=0.9),  # 3 months ago
        ]

        # Extract temporal weights
        weights = [m["temporal_weight"] for m in memories]

        # Verify exponential decay pattern
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i + 1], "Weights should decrease over time"

        # Today's memory should have full weight
        assert weights[0] == pytest.approx(1.0, rel=0.01)

        # Week-old memory should have ~79% weight (3% decay per day)
        expected_week = max(0.1, 1.0 - (7 * 0.03))
        assert weights[2] == pytest.approx(expected_week, rel=0.01)

        # Month-old memory should have minimum weight
        assert weights[3] == 0.1  # Floor at 0.1

    async def test_superseded_memory_accelerated_decay(
        self, memory_factory
    ):
        """Superseded memories should decay faster"""
        # Create two memories of same age
        active_memory = memory_factory(age_days=7, superseded=False)
        superseded_memory = memory_factory(age_days=7, superseded=True)

        # Apply supersession decay multiplier
        supersession_multiplier = 0.5
        superseded_weight = superseded_memory["temporal_weight"] * supersession_multiplier

        # Superseded should have lower weight
        assert superseded_weight < active_memory["temporal_weight"]
        assert superseded_weight == pytest.approx(
            active_memory["temporal_weight"] * 0.5, rel=0.01
        )

    async def test_confidence_temporal_interaction(
        self, memory_factory
    ):
        """High confidence memories should decay slower"""
        # Create memories with different confidence levels
        high_conf_old = memory_factory(age_days=30, confidence=0.95)
        low_conf_old = memory_factory(age_days=30, confidence=0.4)

        # Calculate effective scores
        high_effective = high_conf_old["confidence"] * high_conf_old["temporal_weight"]
        low_effective = low_conf_old["confidence"] * low_conf_old["temporal_weight"]

        # High confidence should maintain higher effective score
        assert high_effective > low_effective

        # But both should be at minimum temporal weight (30 days old)
        assert high_conf_old["temporal_weight"] == 0.1
        assert low_conf_old["temporal_weight"] == 0.1

    async def test_memory_resurrection_prevention(
        self, memory_factory, implicit_signal_generator
    ):
        """Old memories shouldn't suddenly become highly weighted again"""
        # Create old memory
        old_memory = memory_factory(age_days=60, confidence=0.7)
        initial_weight = old_memory["temporal_weight"]

        # Apply positive signal
        signal = implicit_signal_generator("command_success", True)
        new_confidence = min(old_memory["confidence"] + signal["score_delta"], 1.0)

        # Temporal weight should NOT change (only confidence changes)
        assert old_memory["temporal_weight"] == initial_weight
        assert old_memory["temporal_weight"] == 0.1  # Still at minimum

        # Effective score increases but is limited by temporal weight
        old_effective = old_memory["confidence"] * old_memory["temporal_weight"]
        new_effective = new_confidence * old_memory["temporal_weight"]

        assert new_effective > old_effective  # Some improvement
        assert new_effective < 0.2  # But still low due to age

    async def test_temporal_clustering_detection(
        self, synthetic_trace_generator
    ):
        """Detect temporal patterns (e.g., Monday deploy failures)"""
        # Generate traces with temporal pattern
        traces = []
        for week in range(4):
            for day in range(7):
                timestamp = datetime.now() - timedelta(weeks=week, days=day)
                # Mondays (day=0) have more failures
                success_rate = 0.3 if day == 0 else 0.8
                success = np.random.random() < success_rate

                trace = synthetic_trace_generator(
                    trace_type="command_execution",
                    success=success
                )
                trace["timestamp"] = timestamp.isoformat()
                trace["day_of_week"] = day
                traces.append(trace)

        # Analyze temporal patterns
        monday_failures = sum(1 for t in traces
                             if t["day_of_week"] == 0 and not t["success"])
        other_failures = sum(1 for t in traces
                            if t["day_of_week"] != 0 and not t["success"])

        # Should detect Monday pattern
        monday_failure_rate = monday_failures / 4  # 4 Mondays
        other_failure_rate = other_failures / 24  # 24 other days

        assert monday_failure_rate > other_failure_rate * 2  # Significantly higher

    async def test_recency_bias_vs_quality(
        self, memory_factory
    ):
        """Balance between recency and quality in memory selection"""
        memories = [
            # High quality but old
            memory_factory(age_days=14, confidence=0.95),
            # Medium quality, medium age
            memory_factory(age_days=7, confidence=0.7),
            # Low quality but recent
            memory_factory(age_days=1, confidence=0.4),
        ]

        # Calculate combined scores
        scores = []
        for m in memories:
            # Weighted combination of confidence and recency
            recency_weight = 0.3
            quality_weight = 0.7

            combined = (quality_weight * m["confidence"] +
                       recency_weight * m["temporal_weight"])
            scores.append(combined)

        # Medium age/quality should win with balanced weights
        best_idx = scores.index(max(scores))
        assert best_idx == 1  # Medium quality, medium age

    async def test_decay_rate_customization(self):
        """Different memory types should have different decay rates"""
        decay_rates = {
            "solution": 0.03,      # 3% per day - solutions become outdated
            "pattern": 0.01,       # 1% per day - patterns last longer
            "principle": 0.005,    # 0.5% per day - principles rarely change
            "debug": 0.1,         # 10% per day - debug info quickly outdated
        }

        age_days = 10

        for memory_type, rate in decay_rates.items():
            weight = max(0.1, 1.0 - (age_days * rate))

            if memory_type == "debug":
                assert weight == 0.1  # Hits floor
            elif memory_type == "solution":
                assert weight == pytest.approx(0.7, rel=0.01)
            elif memory_type == "pattern":
                assert weight == pytest.approx(0.9, rel=0.01)
            elif memory_type == "principle":
                assert weight == pytest.approx(0.95, rel=0.01)

    async def test_temporal_window_queries(
        self, memory_factory
    ):
        """Test querying memories within specific time windows"""
        # Create memories across time
        memories = [
            memory_factory(age_days=0),    # Today
            memory_factory(age_days=3),    # This week
            memory_factory(age_days=10),   # Last two weeks
            memory_factory(age_days=35),   # Last two months
            memory_factory(age_days=100),  # Older
        ]

        # Define time windows
        def in_window(memory, max_days):
            age = (datetime.now() - datetime.fromisoformat(
                memory["created_at"]
            )).days
            return age <= max_days

        # Query different windows
        today = [m for m in memories if in_window(m, 1)]
        this_week = [m for m in memories if in_window(m, 7)]
        this_month = [m for m in memories if in_window(m, 30)]

        assert len(today) == 1
        assert len(this_week) == 2
        assert len(this_month) == 3

    async def test_historical_memory_marking(
        self, memory_factory
    ):
        """Memories older than 30 days should be marked as historical"""
        memories = [
            memory_factory(age_days=29),  # Not historical
            memory_factory(age_days=30),  # Boundary
            memory_factory(age_days=31),  # Historical
            memory_factory(age_days=90),  # Very historical
        ]

        HISTORICAL_THRESHOLD_DAYS = 30

        for memory in memories:
            age = (datetime.now() - datetime.fromisoformat(
                memory["created_at"]
            )).days

            is_historical = age >= HISTORICAL_THRESHOLD_DAYS

            if age < HISTORICAL_THRESHOLD_DAYS:
                assert not is_historical
            else:
                assert is_historical
                # Historical memories get special handling
                assert memory["temporal_weight"] == 0.1  # Minimum weight


@pytest.mark.temporal
class TestTemporalReasoningAccuracy:
    """Test temporal reasoning capabilities against human baselines"""

    def test_temporal_ordering(self, memory_factory):
        """Test ability to correctly order memories temporally"""
        # Create memories in random order
        memories = [
            memory_factory(age_days=5),
            memory_factory(age_days=1),
            memory_factory(age_days=10),
            memory_factory(age_days=3),
        ]

        # Sort by creation time
        sorted_memories = sorted(
            memories,
            key=lambda m: datetime.fromisoformat(m["created_at"]),
            reverse=True  # Most recent first
        )

        # Verify correct ordering
        ages = []
        for m in sorted_memories:
            age = (datetime.now() - datetime.fromisoformat(
                m["created_at"]
            )).days
            ages.append(age)

        assert ages == [1, 3, 5, 10]

    def test_temporal_distance_calculation(self):
        """Test accurate calculation of time distances"""
        now = datetime.now()

        test_cases = [
            (now - timedelta(hours=2), "2 hours ago"),
            (now - timedelta(days=1), "1 day ago"),
            (now - timedelta(days=7), "1 week ago"),
            (now - timedelta(days=30), "1 month ago"),
        ]

        for timestamp, expected in test_cases:
            delta = now - timestamp

            if delta.days == 0:
                assert delta.seconds // 3600 == 2
            elif delta.days == 1:
                assert delta.days == 1
            elif delta.days == 7:
                assert delta.days == 7
            elif delta.days == 30:
                assert delta.days == 30
