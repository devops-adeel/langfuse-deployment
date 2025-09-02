#!/usr/bin/env python3
"""
Memory Intelligence Service
FastAPI service for memory operations with Langfuse integration
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from prompt_manager import get_prompt_manager
from memory_operations import get_memory_operations
from memory_pattern_extractor import get_pattern_extractor
from memory_evaluators import get_memory_evaluators

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Memory Intelligence Service",
    description="Enhanced memory operations with Langfuse observability",
    version="1.0.0"
)

# Initialize components
prompt_manager = get_prompt_manager()
memory_ops = get_memory_operations()
pattern_extractor = get_pattern_extractor()
evaluators = get_memory_evaluators()


# Request/Response Models
class MemorySearchRequest(BaseModel):
    query: str
    search_type: str = "semantic"
    gtd_context: Optional[Dict[str, Any]] = None
    include_historical: bool = False


class MemoryCaptureRequest(BaseModel):
    memory_type: str
    content: Dict[str, Any]
    gtd_context: Optional[Dict[str, Any]] = None


class MemoryApplicationRequest(BaseModel):
    memory_id: str
    action_taken: str
    result: Dict[str, Any]


class ABTestRequest(BaseModel):
    query: str
    variants: List[str]


class EvaluationRequest(BaseModel):
    dataset_name: str
    evaluator_name: str
    prompt_variants: Optional[List[str]] = None


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "langfuse": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
            "neo4j": bool(os.getenv("NEO4J_URI")),
            "openai": bool(os.getenv("OPENAI_API_KEY"))
        }
    }


# Memory Search Endpoint
@app.post("/memory/search")
async def search_memory(request: MemorySearchRequest):
    """
    Search memory with enhanced observability
    """
    try:
        memories, metadata = await memory_ops.search_memory(
            query=request.query,
            search_type=request.search_type,
            gtd_context=request.gtd_context,
            include_historical=request.include_historical
        )

        return {
            "success": True,
            "memories": memories,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Memory search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Memory Capture Endpoint
@app.post("/memory/capture")
async def capture_memory(request: MemoryCaptureRequest):
    """
    Capture memory with structured format
    """
    try:
        result = await memory_ops.capture_memory(
            memory_type=request.memory_type,
            content=request.content,
            gtd_context=request.gtd_context
        )

        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Memory capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Memory Application Tracking
@app.post("/memory/track-application")
async def track_application(request: MemoryApplicationRequest):
    """
    Track memory application and effectiveness
    """
    try:
        result = await memory_ops.track_memory_application(
            memory_id=request.memory_id,
            action_taken=request.action_taken,
            result=request.result
        )

        return {
            "success": True,
            "effectiveness": result
        }
    except Exception as e:
        logger.error(f"Application tracking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# A/B Testing Endpoint
@app.post("/memory/ab-test")
async def run_ab_test(request: ABTestRequest):
    """
    Run A/B test on memory search prompts
    """
    try:
        result = await memory_ops.run_memory_ab_test(
            query=request.query,
            variants=request.variants
        )

        return {
            "success": True,
            "test_results": result
        }
    except Exception as e:
        logger.error(f"A/B test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pattern Extraction Endpoint
@app.post("/patterns/extract")
async def extract_patterns(
    background_tasks: BackgroundTasks,
    hours_back: int = 24,
    min_effectiveness: float = 0.7
):
    """
    Extract successful memory patterns from traces
    """
    try:
        patterns = await pattern_extractor.extract_success_patterns(
            hours_back=hours_back,
            min_effectiveness=min_effectiveness
        )

        # Create dataset in background
        background_tasks.add_task(
            pattern_extractor.create_evaluation_dataset,
            patterns,
            f"memory_eval_{datetime.now().strftime('%Y%m%d')}"
        )

        return {
            "success": True,
            "patterns": patterns,
            "total_patterns": sum(len(p) for p in patterns.values())
        }
    except Exception as e:
        logger.error(f"Pattern extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Prompt Improvements Endpoint
@app.get("/patterns/improvements")
async def get_prompt_improvements():
    """
    Get prompt improvement suggestions
    """
    try:
        # Extract recent patterns
        patterns = await pattern_extractor.extract_success_patterns(
            hours_back=168  # Last week
        )

        improvements = await pattern_extractor.identify_prompt_improvements(
            patterns
        )

        return {
            "success": True,
            "improvements": improvements
        }
    except Exception as e:
        logger.error(f"Failed to get improvements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Evaluation Endpoints
@app.post("/evaluate/retrieval")
async def evaluate_retrieval(
    query: str,
    retrieved_memories: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
):
    """
    Evaluate memory retrieval quality
    """
    try:
        evaluation = await evaluators.evaluate_memory_retrieval(
            query=query,
            retrieved_memories=retrieved_memories,
            context=context
        )

        return {
            "success": True,
            "evaluation": evaluation
        }
    except Exception as e:
        logger.error(f"Retrieval evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate/dataset")
async def evaluate_dataset(request: EvaluationRequest):
    """
    Run evaluation on a dataset
    """
    try:
        results = await evaluators.run_dataset_evaluation(
            dataset_name=request.dataset_name,
            evaluator_name=request.evaluator_name,
            prompt_variants=request.prompt_variants
        )

        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        logger.error(f"Dataset evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Create Evaluators Endpoint
@app.post("/evaluators/create")
async def create_evaluators():
    """
    Create memory-specific evaluators in Langfuse
    """
    try:
        created = await evaluators.create_evaluators()

        return {
            "success": True,
            "evaluators_created": created
        }
    except Exception as e:
        logger.error(f"Failed to create evaluators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Prompt Management Endpoints
@app.get("/prompts/{prompt_name}")
async def get_prompt(
    prompt_name: str,
    version: Optional[int] = None,
    label: Optional[str] = "production"
):
    """
    Get a prompt template
    """
    try:
        prompt = prompt_manager.get_prompt(
            name=prompt_name,
            version=version,
            label=label
        )

        return {
            "success": True,
            "prompt": prompt
        }
    except Exception as e:
        logger.error(f"Failed to get prompt: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/prompts/{base_name}/variant")
async def create_variant(
    base_name: str,
    variant_suffix: str,
    modifications: Dict[str, Any]
):
    """
    Create a prompt variant for A/B testing
    """
    try:
        variant_name = prompt_manager.create_prompt_variant(
            base_name=base_name,
            variant_suffix=variant_suffix,
            modifications=modifications
        )

        return {
            "success": True,
            "variant_name": variant_name
        }
    except Exception as e:
        logger.error(f"Failed to create variant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Memory Intelligence Service starting...")

    # Verify connections
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        logger.warning("Langfuse not configured - using fallback mode")

    if not os.getenv("NEO4J_URI"):
        logger.warning("Neo4j not configured - memory storage disabled")

    logger.info("Memory Intelligence Service started successfully")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Memory Intelligence Service shutting down...")


if __name__ == "__main__":
    # Run the service
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
