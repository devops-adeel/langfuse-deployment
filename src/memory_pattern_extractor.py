#!/usr/bin/env python3
"""
Memory Pattern Extraction from Langfuse Traces
Identifies successful memory usage patterns for dataset creation
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from langfuse import Langfuse
from prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)


class MemoryPatternExtractor:
    """
    Extracts successful memory patterns from Langfuse traces
    for dataset creation and prompt optimization
    """

    def __init__(self):
        """Initialize the pattern extractor"""
        self.langfuse = Langfuse() if os.getenv("LANGFUSE_PUBLIC_KEY") else None
        self.prompt_manager = get_prompt_manager()
        self.patterns = defaultdict(list)

    async def extract_success_patterns(
        self,
        hours_back: int = 24,
        min_effectiveness: float = 0.7
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract successful memory patterns from recent traces

        Args:
            hours_back: How many hours to look back
            min_effectiveness: Minimum effectiveness score

        Returns:
            Dictionary of patterns by type
        """
        if not self.langfuse:
            logger.warning("Langfuse not configured")
            return {}

        from_timestamp = datetime.now() - timedelta(hours=hours_back)

        # Get recent traces
        traces = self.langfuse.fetch_traces(
            from_timestamp=from_timestamp,
            limit=100
        )

        patterns = {
            "memory_to_command": [],
            "memory_to_solution": [],
            "memory_to_task_completion": [],
            "cross_domain_insights": []
        }

        for trace in traces.data:
            # Get trace observations
            observations = self.langfuse.fetch_observations(
                trace_id=trace.id
            )

            # Extract patterns from observations
            extracted = self._extract_patterns_from_trace(
                trace,
                observations.data,
                min_effectiveness
            )

            for pattern_type, pattern_list in extracted.items():
                patterns[pattern_type].extend(pattern_list)

        logger.info(f"Extracted {sum(len(p) for p in patterns.values())} patterns")
        return patterns

    def _extract_patterns_from_trace(
        self,
        trace: Any,
        observations: List[Any],
        min_effectiveness: float
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract patterns from a single trace

        Args:
            trace: Langfuse trace object
            observations: List of observations
            min_effectiveness: Minimum effectiveness score

        Returns:
            Extracted patterns by type
        """
        patterns = defaultdict(list)

        # Track memory operations and subsequent actions
        memory_ops = []
        actions = []

        for obs in observations:
            metadata = obs.metadata or {}

            # Identify memory operations
            if metadata.get('memory_operation') == 'search':
                memory_ops.append({
                    'id': obs.id,
                    'query': obs.input,
                    'type': metadata.get('search_type'),
                    'results': obs.output,
                    'timestamp': obs.start_time
                })

            # Identify actions taken
            if metadata.get('command_executed') is not None:
                actions.append({
                    'type': 'command',
                    'success': metadata.get('command_executed'),
                    'timestamp': obs.start_time
                })
            elif metadata.get('task_completed') is not None:
                actions.append({
                    'type': 'task',
                    'success': metadata.get('task_completed'),
                    'timestamp': obs.start_time
                })
            elif metadata.get('error_resolved') is not None:
                actions.append({
                    'type': 'error_resolution',
                    'success': metadata.get('error_resolved'),
                    'timestamp': obs.start_time
                })

        # Match memory operations with subsequent actions
        for memory_op in memory_ops:
            for action in actions:
                if action['timestamp'] > memory_op['timestamp']:
                    # Found a memory->action sequence
                    time_delta = (action['timestamp'] - memory_op['timestamp']).total_seconds()

                    if time_delta < 300 and action['success']:  # Within 5 minutes
                        pattern = {
                            'memory_query': memory_op['query'],
                            'memory_type': memory_op['type'],
                            'action_type': action['type'],
                            'time_to_action': time_delta,
                            'trace_id': trace.id,
                            'effectiveness': self._calculate_pattern_effectiveness(
                                memory_op, action, trace
                            )
                        }

                        if pattern['effectiveness'] >= min_effectiveness:
                            pattern_type = f"memory_to_{action['type']}"
                            patterns[pattern_type].append(pattern)

        # Look for cross-domain insights
        if self._has_cross_domain_pattern(trace, observations):
            patterns['cross_domain_insights'].append({
                'trace_id': trace.id,
                'gtd_context': self._extract_gtd_context(observations),
                'coding_context': self._extract_coding_context(observations),
                'insight': self._extract_insight(observations)
            })

        return patterns

    def _calculate_pattern_effectiveness(
        self,
        memory_op: Dict[str, Any],
        action: Dict[str, Any],
        trace: Any
    ) -> float:
        """
        Calculate effectiveness score for a pattern

        Args:
            memory_op: Memory operation details
            action: Action taken
            trace: Parent trace

        Returns:
            Effectiveness score (0-1)
        """
        base_score = 0.5

        # Success gives base score
        if action['success']:
            base_score = 0.7

        # Quick action increases score
        time_bonus = max(0, 0.2 - (action.get('time_to_action', 300) / 1500))

        # High-confidence memory increases score
        if memory_op.get('results'):
            confidence_bonus = 0.1 * len([r for r in memory_op['results'] if r.get('score', 0) > 0.7])
            confidence_bonus = min(0.2, confidence_bonus)
        else:
            confidence_bonus = 0

        return min(1.0, base_score + time_bonus + confidence_bonus)

    def _has_cross_domain_pattern(self, trace: Any, observations: List[Any]) -> bool:
        """Check if trace contains cross-domain insights"""
        has_gtd = any(
            'gtd' in str(obs.metadata).lower() or 'task' in str(obs.metadata).lower()
            for obs in observations
        )
        has_coding = any(
            'code' in str(obs.metadata).lower() or 'debug' in str(obs.metadata).lower()
            for obs in observations
        )
        return has_gtd and has_coding

    def _extract_gtd_context(self, observations: List[Any]) -> Dict[str, Any]:
        """Extract GTD context from observations"""
        context = {}
        for obs in observations:
            metadata = obs.metadata or {}
            if 'gtd' in str(metadata).lower():
                context.update({
                    'task': metadata.get('current_task'),
                    'project': metadata.get('project'),
                    'phase': metadata.get('phase')
                })
        return context

    def _extract_coding_context(self, observations: List[Any]) -> Dict[str, Any]:
        """Extract coding context from observations"""
        context = {}
        for obs in observations:
            metadata = obs.metadata or {}
            if any(k in str(metadata).lower() for k in ['code', 'error', 'debug']):
                context.update({
                    'error': metadata.get('error'),
                    'language': metadata.get('language'),
                    'framework': metadata.get('framework')
                })
        return context

    def _extract_insight(self, observations: List[Any]) -> str:
        """Extract the key insight from observations"""
        for obs in observations:
            if obs.output and 'insight' in str(obs.output).lower():
                return str(obs.output)
        return "Cross-domain connection identified"

    async def create_evaluation_dataset(
        self,
        patterns: Dict[str, List[Dict[str, Any]]],
        dataset_name: str = "memory_evaluation"
    ) -> Dict[str, Any]:
        """
        Create Langfuse evaluation dataset from patterns

        Args:
            patterns: Extracted patterns
            dataset_name: Name for the dataset

        Returns:
            Dataset creation result
        """
        if not self.langfuse:
            logger.warning("Langfuse not configured")
            return {"error": "Langfuse not configured"}

        try:
            # Create or get dataset
            dataset = self.langfuse.create_dataset(
                name=dataset_name,
                description="Auto-generated from successful memory patterns",
                metadata={
                    "created_at": datetime.now().isoformat(),
                    "pattern_types": list(patterns.keys()),
                    "total_patterns": sum(len(p) for p in patterns.values())
                }
            )

            items_created = 0

            # Create dataset items from patterns
            for pattern_type, pattern_list in patterns.items():
                for pattern in pattern_list:
                    # Create evaluation item
                    input_data = {
                        "query": pattern.get('memory_query', ''),
                        "context": pattern.get('gtd_context', {})
                    }

                    expected_output = {
                        "action_type": pattern.get('action_type'),
                        "effectiveness": pattern.get('effectiveness', 0.5)
                    }

                    self.langfuse.create_dataset_item(
                        dataset_name=dataset_name,
                        input=input_data,
                        expected_output=expected_output,
                        metadata={
                            "pattern_type": pattern_type,
                            "trace_id": pattern.get('trace_id')
                        }
                    )
                    items_created += 1

            logger.info(f"Created {items_created} dataset items")

            return {
                "dataset_name": dataset_name,
                "items_created": items_created,
                "pattern_types": list(patterns.keys())
            }

        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            return {"error": str(e)}

    async def identify_prompt_improvements(
        self,
        patterns: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Identify potential prompt improvements from patterns

        Args:
            patterns: Extracted patterns

        Returns:
            List of improvement suggestions
        """
        improvements = []

        # Analyze pattern effectiveness by prompt type
        prompt_effectiveness = defaultdict(list)

        for pattern_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                if 'memory_type' in pattern:
                    prompt_name = f"memory_search_{pattern['memory_type']}"
                    prompt_effectiveness[prompt_name].append(
                        pattern.get('effectiveness', 0.5)
                    )

        # Identify underperforming prompts
        for prompt_name, scores in prompt_effectiveness.items():
            avg_score = sum(scores) / len(scores) if scores else 0

            if avg_score < 0.6:
                improvements.append({
                    'prompt': prompt_name,
                    'current_effectiveness': avg_score,
                    'recommendation': 'Consider revising - low effectiveness',
                    'sample_size': len(scores)
                })
            elif avg_score > 0.8:
                improvements.append({
                    'prompt': prompt_name,
                    'current_effectiveness': avg_score,
                    'recommendation': 'High performer - use as template',
                    'sample_size': len(scores)
                })

        return improvements


# Singleton instance
_pattern_extractor = None


def get_pattern_extractor() -> MemoryPatternExtractor:
    """Get or create singleton MemoryPatternExtractor instance"""
    global _pattern_extractor
    if _pattern_extractor is None:
        _pattern_extractor = MemoryPatternExtractor()
    return _pattern_extractor
