# Memory Intelligence Layer Documentation

## Overview

The Memory Intelligence Layer enhances the Graphiti memory system with Langfuse's observability, prompt management, and evaluation capabilities. This creates a self-improving memory system that learns from every interaction.

## Architecture

```
┌─────────────────────────────────────────┐
│         Claude Code (MCP)                │
│         Terminal-based, No GUI           │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│     Memory Intelligence Layer            │
│  • Prompt Management (Langfuse)          │
│  • OpenTelemetry Tracing                 │
│  • Implicit Scoring                      │
│  • Pattern Extraction                    │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│        Langfuse Platform                 │
│  • Trace Storage                         │
│  • Prompt Versioning                     │
│  • Evaluation Datasets                   │
│  • A/B Testing                          │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│        Neo4j (Graphiti)                  │
│  • Memory Graph Storage                  │
│  • Temporal Weighting                    │
│  • Cross-Domain Links                    │
└─────────────────────────────────────────┘
```

## Key Features

### 1. Externalized Prompt Management

All memory operation prompts are managed in Langfuse, enabling:
- **Version Control**: Track prompt evolution over time
- **A/B Testing**: Compare prompt effectiveness
- **Zero-Latency Access**: Client-side caching with 60s TTL
- **100% Availability**: Local fallback prompts

#### Prompt Templates

- `memory_search_exact`: For specific technical queries
- `memory_search_semantic`: For conceptual searches
- `memory_search_cross_domain`: For GTD-coding insights
- `capture_solution`: For debugging solutions
- `capture_pattern`: For recurring patterns
- `capture_tdd_cycle`: For test-driven development

### 2. OpenTelemetry Integration

Every memory operation includes rich metadata:

```python
span.set_attribute("langfuse.trace.metadata.memory_operation", "search")
span.set_attribute("langfuse.trace.metadata.search_type", "cross_domain")
span.set_attribute("langfuse.trace.metadata.confidence_score", 0.85)
span.set_attribute("langfuse.trace.metadata.memory_applied", True)
```

### 3. Implicit Scoring System

Tracks success signals automatically:
- **Command Success**: Exit code 0 → +0.3 score
- **Tests Passed**: All tests green → +0.4 score
- **Task Completed**: Todo marked done → +0.5 score
- **Error Resolved**: Error disappears → +0.4 score
- **File Modified**: Expected file changed → +0.2 score

### 4. Pattern Extraction

Identifies successful patterns:
- Memory → Command → Success sequences
- Memory → Solution → Task completion
- Cross-domain insight discoveries
- High-effectiveness memory retrievals

### 5. Evaluation Framework

LLM-as-Judge evaluators assess:
- **Memory Relevance**: How well memories match queries
- **Cross-Domain Discovery**: Quality of insights across domains
- **Solution Effectiveness**: How well solutions solve problems
- **Memory Freshness**: Whether memories remain current

## Deployment

### Prerequisites

- Langfuse deployment running
- Neo4j database for Graphiti
- OpenAI API key for evaluations
- Docker with OrbStack (macOS)

### Quick Start

1. **Deploy the Memory Intelligence Layer**:
```bash
make memory-deploy
```

2. **Create evaluators in Langfuse**:
```bash
make memory-evaluators
```

3. **Test the API**:
```bash
make memory-test
```

### Configuration

Environment variables in `.env`:
```bash
# Langfuse Configuration
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=http://langfuse-web:3000

# Neo4j Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# OpenAI Configuration
OPENAI_API_KEY=your_api_key
```

## API Endpoints

### Memory Operations

#### Search Memory
```bash
POST /memory/search
{
  "query": "docker ssl error",
  "search_type": "exact",
  "gtd_context": {"current_task": "Fix deployment"}
}
```

#### Capture Memory
```bash
POST /memory/capture
{
  "memory_type": "solution",
  "content": {
    "error_description": "SSL certificate error",
    "solution": "Update CA certificates"
  }
}
```

#### Track Application
```bash
POST /memory/track-application
{
  "memory_id": "mem_123",
  "action_taken": "command",
  "result": {"exit_code": 0}
}
```

### Pattern Analysis

#### Extract Patterns
```bash
POST /patterns/extract?hours_back=24&min_effectiveness=0.7
```

#### Get Improvements
```bash
GET /patterns/improvements
```

### Evaluation

#### Evaluate Retrieval
```bash
POST /evaluate/retrieval
{
  "query": "test query",
  "retrieved_memories": [...],
  "context": {}
}
```

#### Run Dataset Evaluation
```bash
POST /evaluate/dataset
{
  "dataset_name": "memory_eval_20240101",
  "evaluator_name": "memory_relevance_judge",
  "prompt_variants": ["v1", "v2"]
}
```

## Usage with Claude Code

The Memory Intelligence Layer integrates seamlessly with Claude Code through the MCP server:

1. **Automatic Context**: GTD context is automatically included in memory searches
2. **Implicit Tracking**: Command executions are tracked without user intervention
3. **Silent Learning**: Every interaction improves the system
4. **No GUI Required**: All operations through terminal/API

### Example Flow

1. User asks: "How do I fix the SSL error?"
2. Memory search with `memory_search_exact` prompt
3. Memories retrieved with confidence scores
4. User applies suggested command
5. Command success tracked (exit code 0)
6. Memory effectiveness score updated
7. Pattern extracted for future dataset

## Monitoring

### Langfuse Dashboard

View in Langfuse UI:
- Memory operation traces
- Prompt performance metrics
- A/B test results
- Evaluation scores

### Metrics

Key metrics tracked:
- **Retrieval Precision**: % of relevant memories
- **Cross-Domain Discovery Rate**: Insights found per search
- **Solution Effectiveness**: % of solutions that work
- **Time to Resolution**: Memory retrieval → problem solved

## Continuous Improvement

The system improves through:

1. **Automatic Pattern Extraction**: Daily extraction of successful patterns
2. **Dataset Growth**: Successful patterns become test cases
3. **Prompt Optimization**: A/B testing identifies better prompts
4. **Score-Based Ranking**: Effective memories surface more often

### Improvement Cycle

```
Interaction → Trace → Pattern → Dataset → Evaluation → Prompt Update → Better Results
```

## Troubleshooting

### Common Issues

#### Langfuse Connection Failed
```bash
# Check credentials
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY

# Test connection
curl http://langfuse-web:3000/api/public/health
```

#### Neo4j Not Available
```bash
# Check Neo4j status
docker logs langfuse-neo4j

# Test connection
cypher-shell -a bolt://localhost:7687
```

#### Memory Service Unhealthy
```bash
# Check logs
docker logs langfuse-memory-intelligence

# Restart service
docker restart langfuse-memory-intelligence
```

### Debug Mode

Enable debug logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Best Practices

1. **Prompt Versioning**: Always version prompts with meaningful labels
2. **A/B Testing**: Test one variable at a time
3. **Evaluation Frequency**: Run evaluations weekly
4. **Pattern Review**: Review extracted patterns monthly
5. **Prompt Cleanup**: Archive unused prompt versions

## Performance

### Latency Impact

- **Prompt Retrieval**: ~39ms (cached) / ~150ms (first fetch)
- **Memory Search**: ~200ms typical
- **Pattern Extraction**: ~5s for 24 hours of traces
- **Evaluation Run**: ~30s for 100 items

### Resource Usage

- **Memory Service**: ~256MB RAM
- **Neo4j**: ~1GB RAM
- **Evaluation Runner**: ~512MB RAM during runs

## Security

- **No Secrets in Prompts**: Use variables, not hardcoded values
- **API Authentication**: All endpoints require auth tokens
- **Data Privacy**: Traces can be filtered by project/user
- **Audit Logging**: All operations logged with timestamps

## Future Enhancements

- [ ] Real-time pattern detection via webhooks
- [ ] Automatic prompt promotion based on scores
- [ ] Memory clustering for similar patterns
- [ ] Predictive memory pre-fetching
- [ ] Multi-model evaluation ensemble

## Support

For issues or questions:
1. Check logs: `docker logs langfuse-memory-intelligence`
2. Review traces in Langfuse UI
3. Consult this documentation
4. Open issue in repository
