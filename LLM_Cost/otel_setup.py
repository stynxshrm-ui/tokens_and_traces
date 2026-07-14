"""
otel_setup.py — real OpenTelemetry SDK, GenAI semantic conventions.

Standard attributes use the official `gen_ai.*` namespace. The four metrics
this channel alerts on aren't part of the GenAI semconv yet, so they live
under a clearly-namespaced `tokens_traces.*` prefix — extending the
convention, not replacing it with a custom logger.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def get_tracer(service_name: str, verbose_console: bool = False):
    provider = TracerProvider()
    if verbose_console:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    return provider.get_tracer(service_name)


def emit_span(tracer, result: dict):
    """One span per ticket-triage request, GenAI semconv + tokens_traces.* ."""
    model_id = {"sonnet": "claude-sonnet-5",
                "haiku": "claude-haiku-4-5-20251001"}[result["model"]]
    with tracer.start_as_current_span("chat claude-ticket-triage") as span:
        span.set_attribute("gen_ai.system", "anthropic")
        span.set_attribute("gen_ai.request.model", model_id)
        span.set_attribute("gen_ai.response.model", model_id)
        span.set_attribute("gen_ai.usage.input_tokens", result["input_tok"])
        span.set_attribute("gen_ai.usage.output_tokens", result["output_tok"])
        span.set_attribute("tokens_traces.category", result["category"])
        span.set_attribute("tokens_traces.semantic_success", result["success"])
        span.set_attribute("tokens_traces.cost_usd", round(result["true_cost"], 6))
        span.set_attribute("tokens_traces.steps_to_completion", result["steps"])
        span.set_attribute("tokens_traces.latency_ms", result["latency_ms"])
        span.set_attribute("tokens_traces.routing_reason", result.get("routing_reason", "n/a"))
        span.set_attribute("tokens_traces.semantic_cache_hit", result.get("semantic_cache_hit", False))
