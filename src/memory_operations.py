#!/usr/bin/env python3
"""
Enhanced Memory Operations with Langfuse Integration
Adds OpenTelemetry tracing and implicit scoring
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

from prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)


class MemoryOperations:
    """
    Enhanced memory operations with observability and scoring
    """

    def __init__(self, memory_client=None):
        """
        Initialize memory operations

        Args:
            memory_client: Graphiti memory client instance
        """
        self.memory = memory_client
        self.prompt_manager = get_prompt_manager()
        self.langfuse = Langfuse() if os.getenv("LANGFUSE_PUBLIC_KEY") else None

    @observe(name="memory_search")
    async def search_memory(
        self,
        query: str,
        search_type: str = "semantic",
        gtd_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search memory with enhanced observability

        Args:
            query: Search query
            search_type: Type of search (exact, semantic, cross_domain)
            gtd_context: Current GTD context
            **kwargs: Additional search parameters

        Returns:
            Tuple of (memories, metadata)
        """
        start_time = time.time()

        # Get appropriate prompt template
        prompt_name = f"memory_search_{search_type}"
        prompt_data = self.prompt_manager.get_prompt(
            prompt_name,
            label="production",
            query=query,
            gtd_task=gtd_context.get('current_task', '') if gtd_context else '',
            session_type=kwargs.get('session_type', 'general'),
            **kwargs
        )

        # Add span attributes for OpenTelemetry
        langfuse_context.update_current_observation(
            metadata={
                "memory_operation": "search",
                "search_type": search_type,
                "query_length": len(query),
                "has_gtd_context": bool(gtd_context),
                "prompt_used": prompt_name
            }
        )

        try:
            # Execute memory search
            if self.memory:
                memories = await self.memory.search_with_temporal_weight(
                    query=query,
                    filter_source=kwargs.get('filter_source'),
                    include_historical=kwargs.get('include_historical', False)
                )
            else:
                # Mock response for testing
                memories = []

            # Calculate search metrics
            search_time = time.time() - start_time

            # Track implicit success signals
            metadata = {
                "search_time": search_time,
                "results_count": len(memories),
                "avg_confidence": sum(m.get('score', 0) for m in memories) / len(memories) if memories else 0,
                "search_type": search_type,
                "timestamp": datetime.now().isoformat()
            }

            # Update observation with results
            langfuse_context.update_current_observation(
                metadata={
                    **metadata,
                    "memory_found": len(memories) > 0,
                    "high_confidence_results": sum(1 for m in memories if m.get('score', 0) > 0.7)
                },
                output={"memories_returned": len(memories)}
            )

            # Track prompt effectiveness
            self.prompt_manager.track_prompt_usage(
                prompt_name=prompt_name,
                trace_id=langfuse_context.get_current_trace_id(),
                success=len(memories) > 0,
                metadata=metadata
            )

            return memories, metadata

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            langfuse_context.update_current_observation(
                metadata={"error": str(e), "memory_operation_failed": True}
            )
            raise

    @observe(name="memory_capture")
    async def capture_memory(
        self,
        memory_type: str,
        content: Dict[str, Any],
        gtd_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Capture memory with enhanced structure

        Args:
            memory_type: Type of memory (solution, pattern, tdd_cycle)
            content: Memory content to capture
            gtd_context: Current GTD context
            **kwargs: Additional parameters

        Returns:
            Captured memory with metadata
        """
        start_time = time.time()

        # Get capture prompt
        prompt_name = f"capture_{memory_type}"
        prompt_data = self.prompt_manager.get_prompt(
            prompt_name,
            label="production",
            **content,
            environment=kwargs.get('environment', 'development'),
            **kwargs
        )

        # Add span attributes
        langfuse_context.update_current_observation(
            metadata={
                "memory_operation": "capture",
                "memory_type": memory_type,
                "has_gtd_context": bool(gtd_context),
                "prompt_used": prompt_name
            }
        )

        try:
            # Structure the memory
            structured_memory = {
                "type": memory_type,
                "content": content,
                "gtd_context": gtd_context,
                "captured_at": datetime.now().isoformat(),
                "source": "langfuse_enhanced",
                **kwargs
            }

            # Store in memory system
            if self.memory:
                result = await self.memory.add_memory(
                    structured_memory,
                    source="langfuse_enhanced"
                )
                memory_id = result.get('uuid', 'unknown')
            else:
                memory_id = "test_memory_id"

            capture_time = time.time() - start_time

            # Update observation
            langfuse_context.update_current_observation(
                metadata={
                    "capture_time": capture_time,
                    "memory_id": memory_id,
                    "memory_captured": True
                },
                output={"memory_id": memory_id}
            )

            return {
                "memory_id": memory_id,
                "type": memory_type,
                "capture_time": capture_time,
                "success": True
            }

        except Exception as e:
            logger.error(f"Memory capture failed: {e}")
            langfuse_context.update_current_observation(
                metadata={"error": str(e), "memory_capture_failed": True}
            )
            raise

    @observe(name="memory_application")
    async def track_memory_application(
        self,
        memory_id: str,
        action_taken: str,
        result: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Track when a memory is applied and its outcome

        Args:
            memory_id: ID of the memory applied
            action_taken: Action taken based on memory
            result: Result of the action
            **kwargs: Additional tracking data

        Returns:
            Application tracking metadata
        """
        # Track implicit success signals
        success_indicators = {
            "command_executed": result.get('exit_code') == 0 if 'exit_code' in result else None,
            "tests_passed": result.get('tests_passed', None),
            "task_completed": result.get('task_completed', None),
            "error_resolved": result.get('error_resolved', None),
            "file_modified": result.get('file_modified', None)
        }

        # Calculate effectiveness score
        effectiveness = self._calculate_effectiveness(success_indicators)

        # Update trace metadata
        langfuse_context.update_current_observation(
            metadata={
                "memory_applied": memory_id,
                "action_taken": action_taken,
                "effectiveness_score": effectiveness,
                **success_indicators,
                "application_timestamp": datetime.now().isoformat()
            }
        )

        # Update memory score in system
        if self.memory and effectiveness > 0.5:
            try:
                await self.memory.update_memory_score(
                    memory_id=memory_id,
                    score_delta=effectiveness
                )
            except Exception as e:
                logger.warning(f"Failed to update memory score: {e}")

        return {
            "memory_id": memory_id,
            "effectiveness": effectiveness,
            "success_indicators": success_indicators
        }

    def _calculate_effectiveness(self, indicators: Dict[str, Any]) -> float:
        """
        Calculate memory effectiveness score from success indicators

        Args:
            indicators: Dictionary of success indicators

        Returns:
            Effectiveness score (0-1)
        """
        weights = {
            "command_executed": 0.3,
            "tests_passed": 0.4,
            "task_completed": 0.5,
            "error_resolved": 0.4,
            "file_modified": 0.2
        }

        total_weight = 0
        weighted_sum = 0

        for key, value in indicators.items():
            if value is not None and key in weights:
                weight = weights[key]
                total_weight += weight
                if value:
                    weighted_sum += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.5

    @observe(name="memory_ab_test")
    async def run_memory_ab_test(
        self,
        query: str,
        variants: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run A/B test on memory search prompts

        Args:
            query: Search query
            variants: List of prompt variants to test
            **kwargs: Additional parameters

        Returns:
            A/B test results
        """
        results = {}

        for variant in variants:
            start_time = time.time()

            # Get variant prompt
            prompt_data = self.prompt_manager.get_prompt(
                variant,
                query=query,
                **kwargs
            )

            # Execute search with variant
            if self.memory:
                memories = await self.memory.search_with_temporal_weight(query)
            else:
                memories = []

            search_time = time.time() - start_time

            # Track variant performance
            results[variant] = {
                "search_time": search_time,
                "results_count": len(memories),
                "avg_confidence": sum(m.get('score', 0) for m in memories) / len(memories) if memories else 0,
                "high_confidence_count": sum(1 for m in memories if m.get('score', 0) > 0.7)
            }

            # Update observation
            langfuse_context.update_current_observation(
                metadata={
                    f"variant_{variant}": results[variant],
                    "ab_test": True
                }
            )

        # Determine winner
        winner = max(results.keys(), key=lambda k: results[k]['high_confidence_count'])

        return {
            "winner": winner,
            "results": results,
            "query": query
        }


# Singleton instance
_memory_ops = None


def get_memory_operations(memory_client=None) -> MemoryOperations:
    """Get or create singleton MemoryOperations instance"""
    global _memory_ops
    if _memory_ops is None:
        _memory_ops = MemoryOperations(memory_client)
    return _memory_ops
