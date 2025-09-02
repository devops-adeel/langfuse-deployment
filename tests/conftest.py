"""
Shared test fixtures for Memory Intelligence Layer
"""
import os
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch
import json
import tempfile
from pathlib import Path

# Set test environment
os.environ["TEST_MODE"] = "true"
os.environ["LANGFUSE_HOST"] = "http://test-langfuse:3000"
os.environ["NEO4J_URI"] = "bolt://test-neo4j:7687"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_langfuse_client():
    """Mock Langfuse client for testing"""
    client = Mock()
    client.get_prompt = Mock(return_value={
        "prompt": "Test prompt with {{variable}}",
        "version": 1,
        "config": {}
    })
    client.trace = Mock()
    client.span = Mock()
    client.score = Mock()
    return client


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for testing"""
    driver = Mock()
    session = Mock()
    result = Mock()

    # Mock query results
    result.data = Mock(return_value=[
        {
            "memory_id": "mem_123",
            "content": "Test memory content",
            "confidence": 0.85,
            "created_at": datetime.now().isoformat(),
            "temporal_weight": 0.9
        }
    ])

    session.run = Mock(return_value=result)
    driver.session = Mock(return_value=session)
    return driver


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    client = Mock()
    response = Mock()
    response.choices = [Mock(message=Mock(content="Evaluation result: PASS"))]
    client.chat.completions.create = Mock(return_value=response)
    return client


@pytest.fixture
def synthetic_trace_generator():
    """Generate synthetic traces for testing"""
    def generate_trace(
        trace_type: str = "memory_search",
        success: bool = True,
        duration_ms: int = 200,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        trace = {
            "id": f"trace_{datetime.now().timestamp()}",
            "type": trace_type,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            "success": success,
            "metadata": metadata or {}
        }

        if trace_type == "memory_search":
            trace["metadata"].update({
                "query": "docker ssl error",
                "search_type": "exact",
                "results_count": 3 if success else 0,
                "confidence_scores": [0.9, 0.75, 0.6] if success else []
            })
        elif trace_type == "command_execution":
            trace["metadata"].update({
                "command": "docker compose up",
                "exit_code": 0 if success else 1,
                "memory_applied": True
            })
        elif trace_type == "task_completion":
            trace["metadata"].update({
                "task_id": "task_123",
                "gtd_context": {"project": "deployment"},
                "memory_used": True,
                "completion_time": duration_ms
            })

        return trace

    return generate_trace


@pytest.fixture
def memory_factory():
    """Factory for creating test memories"""
    def create_memory(
        memory_type: str = "solution",
        age_days: int = 0,
        confidence: float = 0.8,
        superseded: bool = False
    ) -> Dict[str, Any]:
        created_at = datetime.now() - timedelta(days=age_days)

        memory = {
            "id": f"mem_{datetime.now().timestamp()}",
            "type": memory_type,
            "created_at": created_at.isoformat(),
            "confidence": confidence,
            "superseded": superseded,
            "temporal_weight": max(0.1, 1.0 - (age_days * 0.03))  # 3% decay per day
        }

        if memory_type == "solution":
            memory["content"] = {
                "error": "SSL certificate verification failed",
                "solution": "Update CA certificates with: docker compose down && docker compose up",
                "context": {"service": "langfuse", "environment": "production"}
            }
        elif memory_type == "pattern":
            memory["content"] = {
                "pattern": "Docker SSL errors on Monday deploys",
                "frequency": 5,
                "success_rate": 0.8
            }
        elif memory_type == "tdd_cycle":
            memory["content"] = {
                "test": "test_memory_search",
                "implementation": "async def search_memory(...)",
                "refactored": True
            }

        return memory

    return create_memory


@pytest.fixture
def implicit_signal_generator():
    """Generate implicit signals for testing scoring"""
    def generate_signal(signal_type: str, success: bool = True) -> Dict[str, Any]:
        signals = {
            "command_success": {
                "type": "command_execution",
                "exit_code": 0 if success else 1,
                "score_delta": 0.3 if success else -0.1
            },
            "test_pass": {
                "type": "test_execution",
                "passed": success,
                "score_delta": 0.4 if success else -0.2
            },
            "task_complete": {
                "type": "task_completion",
                "completed": success,
                "score_delta": 0.5 if success else 0
            },
            "error_resolved": {
                "type": "error_resolution",
                "resolved": success,
                "score_delta": 0.4 if success else -0.1
            },
            "file_modified": {
                "type": "file_change",
                "expected": success,
                "score_delta": 0.2 if success else 0
            }
        }

        signal = signals.get(signal_type, signals["command_success"])
        signal["timestamp"] = datetime.now().isoformat()
        return signal

    return generate_signal


@pytest.fixture
def yaml_prompt_fallback(tmp_path):
    """Create temporary YAML prompt files for fallback testing"""
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()

    prompts = {
        "memory_search_exact": {
            "prompt": "Search for exact match: {{query}}",
            "variables": ["query"]
        },
        "memory_search_semantic": {
            "prompt": "Search semantically for: {{query}} in context: {{context}}",
            "variables": ["query", "context"]
        },
        "capture_solution": {
            "prompt": "Capture solution for error: {{error}} with fix: {{solution}}",
            "variables": ["error", "solution"]
        }
    }

    for name, content in prompts.items():
        file_path = prompt_dir / f"{name}.yaml"
        import yaml
        with open(file_path, 'w') as f:
            yaml.dump(content, f)

    return prompt_dir


@pytest.fixture
def mock_memory_operations():
    """Mock memory operations for testing"""
    from unittest.mock import AsyncMock

    ops = AsyncMock()
    ops.search_memory = AsyncMock(return_value=([
        {
            "id": "mem_1",
            "content": "Test solution",
            "confidence": 0.9,
            "temporal_weight": 0.95
        }
    ], {"search_time_ms": 150}))

    ops.capture_memory = AsyncMock(return_value={
        "id": "mem_new",
        "status": "captured"
    })

    ops.track_memory_application = AsyncMock(return_value={
        "effectiveness": 0.85
    })

    return ops


@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests"""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = []

        def record(self, operation: str, duration_ms: float, metadata: Dict = None):
            self.metrics.append({
                "operation": operation,
                "duration_ms": duration_ms,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            })

        def get_stats(self, operation: str = None):
            filtered = self.metrics
            if operation:
                filtered = [m for m in self.metrics if m["operation"] == operation]

            if not filtered:
                return None

            durations = [m["duration_ms"] for m in filtered]
            return {
                "count": len(durations),
                "mean": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
                "p50": sorted(durations)[len(durations)//2],
                "p95": sorted(durations)[int(len(durations)*0.95)] if len(durations) > 20 else max(durations)
            }

    return PerformanceTracker()


@pytest.fixture
def docker_compose_test():
    """Docker compose for integration tests"""
    import subprocess
    import time

    compose_file = Path(__file__).parent / "docker-compose.test.yml"

    # Start test containers
    subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d"], check=True)

    # Wait for services to be ready
    time.sleep(5)

    yield

    # Cleanup
    subprocess.run(["docker", "compose", "-f", str(compose_file), "down", "-v"], check=True)


# Markers for test organization
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_docker: marks tests that require Docker"
    )
