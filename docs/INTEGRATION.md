# Langfuse + Grafana-OrbStack Integration Guide

**Time to first correlated trace: ~10 minutes**

## Quick Start

### 1. Ensure Both Stacks Are Running

```bash
# Langfuse (this repository)
make health

# Grafana-OrbStack (../grafana-orbstack)
cd ../grafana-orbstack
docker compose -f docker-compose.grafana.yml ps
```

### 2. Configure Trace Correlation

Add to your application's environment:

```bash
# Enable W3C Trace Context
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy.local:4318
export LANGFUSE_HOST=http://langfuse.local
```

### 3. Instrument Your Code

```python
from langfuse import observe, get_client
from opentelemetry import trace, baggage

langfuse = get_client()
tracer = trace.get_tracer(__name__)

@observe()  # Langfuse decorator
async def process_request(query: str):
    # Get OTel trace context
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()

    # Share trace ID between systems
    langfuse.update_current_trace(
        metadata={
            "tempo_trace_id": format(span_context.trace_id, '032x'),
            "tempo_span_id": format(span_context.span_id, '016x')
        }
    )

    # Your LLM logic here
    result = await llm.complete(query)
    return result
```

### 4. View Correlated Traces

- **Langfuse**: http://langfuse.local → Select trace → Check metadata for `tempo_trace_id`
- **Grafana**: http://grafana.local → Explore → Tempo → Search by trace ID

## Pre-configured Grafana Dashboards

### 1. Langfuse Operations Dashboard

Import to Grafana: `http://grafana.local/dashboard/import`

```json
{
  "title": "Langfuse Operations",
  "panels": [
    {
      "title": "LLM Request Rate",
      "targets": [{
        "expr": "rate(langfuse_llm_requests_total[5m])"
      }]
    },
    {
      "title": "Token Usage by Model",
      "targets": [{
        "expr": "sum by (model) (rate(langfuse_tokens_total[5m]))"
      }]
    },
    {
      "title": "Cost per Hour",
      "targets": [{
        "expr": "sum(rate(langfuse_cost_dollars[1h])) * 3600"
      }]
    }
  ]
}
```

### 2. Trace Correlation Dashboard

```json
{
  "title": "LLM to Infrastructure Correlation",
  "panels": [
    {
      "title": "Slow LLM Calls (>5s)",
      "datasource": "Tempo",
      "query": "{ .langfuse.model = \"gpt-4\" && duration > 5s }"
    },
    {
      "title": "Infrastructure Bottlenecks",
      "datasource": "Prometheus",
      "query": "container_memory_usage_bytes{name=~\"langfuse.*\"}"
    }
  ]
}
```

### 3. Cost Analysis Dashboard

```json
{
  "title": "AI Cost Analysis",
  "panels": [
    {
      "title": "Daily LLM Costs",
      "query": "sum(increase(langfuse_cost_dollars[24h]))"
    },
    {
      "title": "Infrastructure Costs",
      "query": "sum(rate(container_cpu_usage_seconds_total[24h])) * 0.024"
    }
  ]
}
```

## Troubleshooting Patterns

### Pattern 1: Slow LLM Response Investigation

```bash
# 1. Find slow traces in Langfuse
curl http://langfuse.local/api/public/traces \
  -H "Authorization: Bearer $LANGFUSE_SECRET_KEY" \
  --data '{"filter": {"latency": {">": 5000}}}'

# 2. Get tempo_trace_id from metadata
TEMPO_ID=$(jq -r '.data[0].metadata.tempo_trace_id' response.json)

# 3. Query infrastructure metrics
curl "http://prometheus.local/api/v1/query?query=\
  container_memory_usage_bytes{trace_id=\"$TEMPO_ID\"}"

# 4. View full trace in Grafana
open "http://grafana.local/explore?traceID=$TEMPO_ID"
```

### Pattern 2: Memory Loop Detection

```python
# Detect GraphRAG memory loops
def check_memory_loops(trace_id: str):
    # Query Tempo for repetitive patterns
    query = f'{{ trace:id = "{trace_id}" && name = "memory_search" }}'

    response = requests.get(
        "http://tempo.local/api/search",
        params={"q": query}
    )

    spans = response.json()["traces"][0]["spans"]

    if len([s for s in spans if "memory_search" in s["name"]]) > 10:
        print(f"⚠️ Memory loop detected in trace {trace_id}")
        print(f"View in Langfuse: http://langfuse.local/trace/{trace_id}")
        print(f"View in Tempo: http://grafana.local/explore?traceID={trace_id}")
```

### Pattern 3: Cost Attribution

```python
def analyze_trace_cost(langfuse_trace_id: str):
    # Get LLM costs from Langfuse
    langfuse_response = requests.get(
        f"http://langfuse.local/api/public/traces/{langfuse_trace_id}"
    )
    llm_cost = langfuse_response.json()["totalCost"]

    # Get infrastructure metrics from Prometheus
    tempo_id = langfuse_response.json()["metadata"]["tempo_trace_id"]
    prom_query = f'sum(rate(container_cpu_usage_seconds_total{{trace_id="{tempo_id}"}}[5m]))'

    prom_response = requests.get(
        "http://prometheus.local/api/v1/query",
        params={"query": prom_query}
    )

    cpu_usage = float(prom_response.json()["data"]["result"][0]["value"][1])
    infra_cost = cpu_usage * 0.024  # $/cpu-hour

    return {
        "trace_id": langfuse_trace_id,
        "llm_cost_usd": llm_cost,
        "infrastructure_cost_usd": infra_cost,
        "total_cost_usd": llm_cost + infra_cost,
        "langfuse_url": f"http://langfuse.local/trace/{langfuse_trace_id}",
        "tempo_url": f"http://grafana.local/explore?traceID={tempo_id}"
    }
```

### Pattern 4: Health Check Correlation

```bash
# Check if slow Langfuse responses correlate with infrastructure issues
make health  # Langfuse health

# Check Grafana metrics
curl -s http://prometheus.local/api/v1/query?query='up{job="langfuse"}' | \
  jq '.data.result[].value[1]'

# View service dependencies
open http://grafana.local/d/service-mesh
```

### Pattern 5: Emergency Response

When Langfuse shows high latency:

```bash
# 1. Quick diagnostics
docker stats --no-stream | grep langfuse

# 2. Check recent traces
curl http://langfuse.local/api/public/metrics/daily | jq '.data[0]'

# 3. View infrastructure correlation
open "http://grafana.local/d/langfuse-ops"

# 4. Scale if needed
docker compose scale langfuse-worker=3
```

## Configuration Reference

### Langfuse Environment Variables

```yaml
# Add to docker-compose.yml
langfuse-web:
  environment:
    # Enable OTLP export
    LANGFUSE_ENABLE_OTLP: "true"
    OTEL_EXPORTER_OTLP_ENDPOINT: "http://alloy.local:4318"
    OTEL_SERVICE_NAME: "langfuse"

    # Trace sampling (production)
    OTEL_TRACES_SAMPLER: "traceidratio"
    OTEL_TRACES_SAMPLER_ARG: "0.1"  # 10% sampling
```

### Grafana Alloy Configuration

```yaml
# ../grafana-orbstack/config/alloy-config.alloy
otelcol.receiver.otlp "langfuse" {
  grpc {
    endpoint = "0.0.0.0:4317"
  }
  http {
    endpoint = "0.0.0.0:4318"
  }
}

otelcol.processor.batch "langfuse" {
  send_batch_size = 1000
  timeout = "5s"
}

otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
  }
}
```

## Best Practices

### DO
- ✅ Use consistent trace IDs across both systems
- ✅ Set appropriate sampling rates (100% dev, 10% production)
- ✅ Include `service.name` in all spans
- ✅ Use semantic conventions for attributes
- ✅ Monitor both LLM and infrastructure costs

### DON'T
- ❌ Store sensitive data in trace attributes
- ❌ Create spans for operations <10ms
- ❌ Use high-cardinality attributes unnecessarily
- ❌ Forget to handle trace context in error paths
- ❌ Mix trace ID formats between systems

## Links

- [Langfuse Dashboard](http://langfuse.local)
- [Grafana Dashboards](http://grafana.local)
- [Prometheus Metrics](http://prometheus.local)
- [Tempo Traces](http://tempo.local)
- [Grafana Repository](../../grafana-orbstack)
