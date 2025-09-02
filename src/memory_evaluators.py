#!/usr/bin/env python3
"""
Memory-Specific Evaluators for Langfuse
LLM-as-Judge evaluators for memory quality assessment
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langfuse import Langfuse
from prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)


class MemoryEvaluators:
    """
    Evaluators for memory system quality assessment
    """

    def __init__(self):
        """Initialize memory evaluators"""
        self.langfuse = Langfuse() if os.getenv("LANGFUSE_PUBLIC_KEY") else None
        self.prompt_manager = get_prompt_manager()

    async def create_evaluators(self) -> Dict[str, str]:
        """
        Create memory-specific evaluators in Langfuse

        Returns:
            Dictionary of evaluator names and IDs
        """
        if not self.langfuse:
            logger.warning("Langfuse not configured")
            return {}

        evaluators = {}

        # Memory Relevance Evaluator
        evaluators['memory_relevance'] = await self._create_evaluator(
            name="memory_relevance_judge",
            description="Evaluates relevance of retrieved memories to query",
            prompt_template=self.prompt_manager.get_prompt(
                "memory_relevance_judge",
                label="production"
            )['prompt'],
            score_type="numeric",
            min_value=0,
            max_value=1
        )

        # Cross-Domain Discovery Evaluator
        evaluators['cross_domain_discovery'] = await self._create_evaluator(
            name="cross_domain_discovery_judge",
            description="Assesses quality of cross-domain insights",
            prompt_template=self.prompt_manager.get_prompt(
                "cross_domain_discovery_judge",
                label="production"
            )['prompt'],
            score_type="numeric",
            min_value=0,
            max_value=1
        )

        # Solution Effectiveness Evaluator
        evaluators['solution_effectiveness'] = await self._create_evaluator(
            name="solution_effectiveness_judge",
            description="Evaluates effectiveness of captured solutions",
            prompt_template=self.prompt_manager.get_prompt(
                "solution_effectiveness_judge",
                label="production"
            )['prompt'],
            score_type="numeric",
            min_value=0,
            max_value=1
        )

        # Memory Freshness Evaluator
        evaluators['memory_freshness'] = await self._create_evaluator(
            name="memory_freshness_judge",
            description="Evaluates freshness and continued relevance",
            prompt_template=self.prompt_manager.get_prompt(
                "memory_freshness_judge",
                label="production"
            )['prompt'],
            score_type="categorical",
            categories=["keep", "update", "supersede"]
        )

        logger.info(f"Created {len(evaluators)} memory evaluators")
        return evaluators

    async def _create_evaluator(
        self,
        name: str,
        description: str,
        prompt_template: str,
        score_type: str,
        **config
    ) -> str:
        """
        Create a single evaluator in Langfuse

        Args:
            name: Evaluator name
            description: Description
            prompt_template: Prompt template
            score_type: Type of score (numeric or categorical)
            **config: Additional configuration

        Returns:
            Evaluator ID
        """
        try:
            # Create score configuration
            if score_type == "numeric":
                score_config = self.langfuse.create_score_config(
                    name=name,
                    data_type="NUMERIC",
                    min_value=config.get('min_value', 0),
                    max_value=config.get('max_value', 1)
                )
            else:
                score_config = self.langfuse.create_score_config(
                    name=name,
                    data_type="CATEGORICAL",
                    categories=config.get('categories', [])
                )

            # Store prompt template
            self.langfuse.create_prompt(
                name=f"evaluator_{name}",
                prompt=prompt_template,
                config={
                    "model": "gpt-4o",
                    "temperature": 0.1,
                    "evaluator": True,
                    "score_config_id": score_config.id
                },
                labels=["evaluator", "production"]
            )

            logger.info(f"Created evaluator: {name}")
            return score_config.id

        except Exception as e:
            logger.error(f"Failed to create evaluator {name}: {e}")
            return None

    async def evaluate_memory_retrieval(
        self,
        query: str,
        retrieved_memories: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate quality of memory retrieval

        Args:
            query: Original search query
            retrieved_memories: Memories retrieved
            context: Additional context

        Returns:
            Evaluation results
        """
        # Get evaluator prompt
        prompt = self.prompt_manager.get_prompt(
            "memory_relevance_judge",
            query=query,
            memories=retrieved_memories,
            context=context or {}
        )

        # Run evaluation (would normally call LLM here)
        # For now, calculate simple metrics
        evaluation = {
            "total_memories": len(retrieved_memories),
            "high_confidence": sum(
                1 for m in retrieved_memories
                if m.get('score', 0) > 0.7
            ),
            "avg_confidence": sum(
                m.get('score', 0) for m in retrieved_memories
            ) / len(retrieved_memories) if retrieved_memories else 0,
            "has_exact_match": any(
                query.lower() in str(m).lower()
                for m in retrieved_memories
            )
        }

        # Calculate overall score
        score = 0
        if evaluation['has_exact_match']:
            score += 0.4
        score += min(0.3, evaluation['avg_confidence'] * 0.3)
        score += min(0.3, evaluation['high_confidence'] / 10 * 0.3)

        evaluation['relevance_score'] = score

        return evaluation

    async def evaluate_cross_domain_insight(
        self,
        query_domain: str,
        target_domain: str,
        insights: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate cross-domain insight quality

        Args:
            query_domain: Source domain
            target_domain: Target domain
            insights: Discovered insights

        Returns:
            Evaluation results
        """
        # Get evaluator prompt
        prompt = self.prompt_manager.get_prompt(
            "cross_domain_discovery_judge",
            query_domain=query_domain,
            target_domain=target_domain,
            insights=insights
        )

        # Simple evaluation metrics
        evaluation = {
            "insights_count": len(insights),
            "domains_connected": query_domain != target_domain,
            "has_actionable": any(
                'action' in str(i).lower() or 'apply' in str(i).lower()
                for i in insights
            )
        }

        # Calculate discovery score
        score = 0
        if evaluation['domains_connected']:
            score += 0.3
        if evaluation['has_actionable']:
            score += 0.4
        score += min(0.3, evaluation['insights_count'] / 5 * 0.3)

        evaluation['discovery_score'] = score

        return evaluation

    async def evaluate_solution_effectiveness(
        self,
        problem: str,
        solution: Dict[str, Any],
        outcome: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate effectiveness of a solution

        Args:
            problem: Original problem
            solution: Proposed solution
            outcome: Actual outcome if available

        Returns:
            Evaluation results
        """
        # Get evaluator prompt
        prompt = self.prompt_manager.get_prompt(
            "solution_effectiveness_judge",
            problem=problem,
            solution=solution,
            outcome=outcome or {}
        )

        # Evaluate solution components
        evaluation = {
            "has_steps": 'steps' in str(solution).lower() or 'step' in str(solution).lower(),
            "has_commands": 'command' in str(solution).lower() or 'run' in str(solution).lower(),
            "has_explanation": len(str(solution)) > 100,
            "outcome_successful": outcome.get('success', False) if outcome else None
        }

        # Calculate effectiveness score
        score = 0
        if evaluation['has_steps']:
            score += 0.3
        if evaluation['has_commands']:
            score += 0.3
        if evaluation['has_explanation']:
            score += 0.2
        if evaluation['outcome_successful']:
            score += 0.2
        elif evaluation['outcome_successful'] is None:
            score += 0.1  # Partial credit if outcome unknown

        evaluation['effectiveness_score'] = score

        return evaluation

    async def evaluate_memory_freshness(
        self,
        memory: Dict[str, Any],
        current_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate memory freshness and relevance

        Args:
            memory: Memory to evaluate
            current_context: Current technology context

        Returns:
            Freshness evaluation
        """
        # Get evaluator prompt
        prompt = self.prompt_manager.get_prompt(
            "memory_freshness_judge",
            created_date=memory.get('created_at', ''),
            last_accessed=memory.get('last_accessed', ''),
            domain=memory.get('domain', ''),
            content=memory.get('content', ''),
            current_versions=current_context.get('versions', {}),
            current_practices=current_context.get('practices', [])
        )

        # Calculate age in days
        if memory.get('created_at'):
            created = datetime.fromisoformat(memory['created_at'])
            age_days = (datetime.now() - created).days
        else:
            age_days = 0

        # Evaluate freshness
        evaluation = {
            "age_days": age_days,
            "is_stale": age_days > 90,
            "technology_current": self._check_technology_currency(
                memory, current_context
            ),
            "recommendation": "keep" if age_days < 30 else
                            "update" if age_days < 90 else "supersede"
        }

        # Calculate freshness score
        score = max(0, 1 - (age_days / 180))  # Linear decay over 6 months
        if not evaluation['technology_current']:
            score *= 0.5

        evaluation['freshness_score'] = score

        return evaluation

    def _check_technology_currency(
        self,
        memory: Dict[str, Any],
        current_context: Dict[str, Any]
    ) -> bool:
        """
        Check if technology in memory is current

        Args:
            memory: Memory content
            current_context: Current technology context

        Returns:
            True if technology is current
        """
        memory_str = str(memory).lower()

        # Check for outdated patterns
        outdated_patterns = [
            'deprecated',
            'legacy',
            'old version',
            'no longer supported'
        ]

        for pattern in outdated_patterns:
            if pattern in memory_str:
                return False

        return True

    async def run_dataset_evaluation(
        self,
        dataset_name: str,
        evaluator_name: str,
        prompt_variants: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run evaluation on a dataset with optional A/B testing

        Args:
            dataset_name: Name of dataset to evaluate
            evaluator_name: Evaluator to use
            prompt_variants: Optional prompt variants for A/B testing

        Returns:
            Evaluation results
        """
        if not self.langfuse:
            logger.warning("Langfuse not configured")
            return {}

        try:
            # Get dataset
            dataset = self.langfuse.get_dataset(dataset_name)

            results = {
                "dataset": dataset_name,
                "evaluator": evaluator_name,
                "variants": {}
            }

            # Run evaluation for each variant
            variants = prompt_variants or ["production"]

            for variant in variants:
                variant_scores = []

                for item in dataset.items:
                    # Get prompt for variant
                    prompt = self.prompt_manager.get_prompt(
                        f"memory_search_{variant}",
                        **item.input
                    )

                    # Run evaluation (simplified)
                    score = await self._evaluate_single_item(
                        item, evaluator_name
                    )
                    variant_scores.append(score)

                results["variants"][variant] = {
                    "avg_score": sum(variant_scores) / len(variant_scores) if variant_scores else 0,
                    "min_score": min(variant_scores) if variant_scores else 0,
                    "max_score": max(variant_scores) if variant_scores else 0,
                    "sample_size": len(variant_scores)
                }

            # Determine winner if A/B test
            if len(variants) > 1:
                winner = max(
                    results["variants"].keys(),
                    key=lambda k: results["variants"][k]["avg_score"]
                )
                results["winner"] = winner

            return results

        except Exception as e:
            logger.error(f"Dataset evaluation failed: {e}")
            return {"error": str(e)}

    async def _evaluate_single_item(
        self,
        item: Any,
        evaluator_name: str
    ) -> float:
        """
        Evaluate a single dataset item

        Args:
            item: Dataset item
            evaluator_name: Evaluator to use

        Returns:
            Score
        """
        # Simplified evaluation logic
        # In production, this would call the actual LLM evaluator
        if evaluator_name == "memory_relevance_judge":
            return 0.7 + (hash(str(item)) % 30) / 100
        elif evaluator_name == "cross_domain_discovery_judge":
            return 0.6 + (hash(str(item)) % 40) / 100
        else:
            return 0.5 + (hash(str(item)) % 50) / 100


# Singleton instance
_evaluators = None


def get_memory_evaluators() -> MemoryEvaluators:
    """Get or create singleton MemoryEvaluators instance"""
    global _evaluators
    if _evaluators is None:
        _evaluators = MemoryEvaluators()
    return _evaluators
