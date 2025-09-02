#!/usr/bin/env python3
"""
Prompt Manager for Memory Operations
Integrates Langfuse Prompt Management with local fallbacks
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from langfuse import Langfuse

logger = logging.getLogger(__name__)


class MemoryPromptManager:
    """
    Manages prompts for memory operations with Langfuse integration
    and local fallback support
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the prompt manager

        Args:
            config_dir: Directory containing fallback prompt templates
        """
        self.config_dir = config_dir or Path("config/prompts")
        self.langfuse = None
        self.fallback_prompts = {}
        self.cache = {}
        self.cache_ttl = 60  # seconds

        # Initialize Langfuse if credentials available
        self._init_langfuse()

        # Load fallback prompts
        self._load_fallback_prompts()

    def _init_langfuse(self):
        """Initialize Langfuse client if credentials are available"""
        try:
            # Check for Langfuse credentials
            if all([
                os.getenv("LANGFUSE_PUBLIC_KEY"),
                os.getenv("LANGFUSE_SECRET_KEY")
            ]):
                self.langfuse = Langfuse()
                logger.info("Langfuse client initialized successfully")
            else:
                logger.warning("Langfuse credentials not found, using fallback prompts only")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            self.langfuse = None

    def _load_fallback_prompts(self):
        """Load fallback prompt templates from YAML files"""
        try:
            for yaml_file in self.config_dir.glob("*.yaml"):
                with open(yaml_file, 'r') as f:
                    prompts = yaml.safe_load(f)
                    if prompts:
                        self.fallback_prompts.update(prompts)
                        logger.info(f"Loaded fallback prompts from {yaml_file.name}")
        except Exception as e:
            logger.error(f"Failed to load fallback prompts: {e}")

    def get_prompt(
        self,
        name: str,
        version: Optional[int] = None,
        label: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        **variables
    ) -> Dict[str, Any]:
        """
        Get a prompt with Langfuse integration and fallback support

        Args:
            name: Prompt name
            version: Specific version (optional)
            label: Label like 'production' or 'staging' (optional)
            cache_ttl: Cache TTL in seconds (optional)
            **variables: Variables to compile into the prompt

        Returns:
            Dict containing compiled prompt and config
        """
        cache_ttl = cache_ttl or self.cache_ttl
        cache_key = f"{name}:{version}:{label}"

        # Check cache first
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < cache_ttl:
                logger.debug(f"Using cached prompt: {name}")
                return self._compile_prompt(cached['prompt'], cached['config'], variables)

        # Try Langfuse first
        if self.langfuse:
            try:
                prompt_obj = self.langfuse.get_prompt(
                    name=name,
                    version=version,
                    label=label,
                    cache_ttl_seconds=cache_ttl
                )

                # Cache the prompt
                self.cache[cache_key] = {
                    'prompt': prompt_obj.prompt,
                    'config': prompt_obj.config or {},
                    'timestamp': datetime.now()
                }

                logger.info(f"Retrieved prompt from Langfuse: {name}")
                return self._compile_prompt(
                    prompt_obj.prompt,
                    prompt_obj.config or {},
                    variables
                )

            except Exception as e:
                logger.warning(f"Failed to get prompt from Langfuse: {e}, using fallback")

        # Use fallback
        if name in self.fallback_prompts:
            fallback = self.fallback_prompts[name]
            logger.info(f"Using fallback prompt: {name}")
            return self._compile_prompt(
                fallback.get('prompt', ''),
                fallback.get('config', {}),
                variables
            )

        # No prompt found
        raise ValueError(f"Prompt not found: {name}")

    def _compile_prompt(
        self,
        template: str,
        config: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compile a prompt template with variables

        Args:
            template: Prompt template with {{variables}}
            config: Prompt configuration
            variables: Variables to substitute

        Returns:
            Compiled prompt and config
        """
        compiled = template

        # Simple variable substitution
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            compiled = compiled.replace(placeholder, str(value))

        return {
            'prompt': compiled,
            'config': config,
            'template': template,
            'variables': variables
        }

    def create_prompt_variant(
        self,
        base_name: str,
        variant_suffix: str,
        modifications: Dict[str, Any]
    ) -> str:
        """
        Create a variant of an existing prompt for A/B testing

        Args:
            base_name: Base prompt name
            variant_suffix: Suffix for the variant (e.g., 'v2')
            modifications: Changes to apply to the base prompt

        Returns:
            Name of the created variant
        """
        variant_name = f"{base_name}_{variant_suffix}"

        if self.langfuse:
            try:
                # Get base prompt
                base = self.langfuse.get_prompt(base_name)

                # Apply modifications
                new_prompt = modifications.get('prompt', base.prompt)
                new_config = {**base.config, **modifications.get('config', {})}

                # Create variant
                self.langfuse.create_prompt(
                    name=variant_name,
                    prompt=new_prompt,
                    config=new_config,
                    labels=modifications.get('labels', [])
                )

                logger.info(f"Created prompt variant: {variant_name}")
                return variant_name

            except Exception as e:
                logger.error(f"Failed to create prompt variant: {e}")
                raise
        else:
            # Create local variant
            base = self.fallback_prompts.get(base_name, {})
            self.fallback_prompts[variant_name] = {
                'prompt': modifications.get('prompt', base.get('prompt', '')),
                'config': {**base.get('config', {}), **modifications.get('config', {})}
            }
            return variant_name

    def track_prompt_usage(
        self,
        prompt_name: str,
        trace_id: str,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track prompt usage for effectiveness measurement

        Args:
            prompt_name: Name of the prompt used
            trace_id: Langfuse trace ID
            success: Whether the prompt led to success
            metadata: Additional metadata to track
        """
        if self.langfuse:
            try:
                # Add to trace metadata
                self.langfuse.trace(
                    id=trace_id,
                    metadata={
                        'prompt_used': prompt_name,
                        'prompt_success': success,
                        'prompt_metadata': metadata or {}
                    }
                )
                logger.debug(f"Tracked prompt usage: {prompt_name} (success={success})")
            except Exception as e:
                logger.error(f"Failed to track prompt usage: {e}")


# Singleton instance
_prompt_manager = None


def get_prompt_manager(config_dir: Optional[Path] = None) -> MemoryPromptManager:
    """Get or create singleton MemoryPromptManager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = MemoryPromptManager(config_dir)
    return _prompt_manager
