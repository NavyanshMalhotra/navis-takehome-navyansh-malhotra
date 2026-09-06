"""
OpenTelemetry Tracing and Telemetry Instrumentation for Nevis Agent Swarm.
Captures agent lifecycle spans, model invocations, and tool executions.
"""

import time
import logging
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

logger = logging.getLogger(__name__)


class InMemorySpanCollector(SpanExporter):
    """Stores exported spans in memory for runtime inspection and API export."""

    def __init__(self):
        self._spans: List[ReadableSpan] = []

    def export(self, spans: List[ReadableSpan]) -> SpanExportResult:
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def clear(self) -> None:
        self._spans.clear()

    @property
    def spans(self) -> List[ReadableSpan]:
        return list(self._spans)


class TelemetryManager:
    """Manages distributed tracing lifecycle for the Nevis ADK agent swarm."""

    _instance: Optional["TelemetryManager"] = None

    def __init__(self):
        self.collector = InMemorySpanCollector()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.collector))
        trace.set_tracer_provider(self.provider)
        self.tracer = trace.get_tracer("nevis-agent-swarm", "2.8.0")

    @classmethod
    def get_instance(cls) -> "TelemetryManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @contextmanager
    def trace_agent(self, agent_name: str, **attributes):
        """Context manager tracing an agent's execution phase."""
        start_t = time.time()
        with self.tracer.start_as_current_span(f"agent.{agent_name}") as span:
            span.set_attribute("agent.name", agent_name)
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(str(k), str(v))
            try:
                yield span
                span.set_attribute("agent.status", "SUCCESS")
            except Exception as exc:
                span.set_attribute("agent.status", "ERROR")
                span.set_attribute("agent.error", str(exc))
                span.record_exception(exc)
                raise
            finally:
                duration_ms = (time.time() - start_t) * 1000
                span.set_attribute("agent.duration_ms", round(duration_ms, 2))

    @contextmanager
    def trace_tool(self, tool_name: str, **attributes):
        """Context manager tracing tool execution."""
        start_t = time.time()
        with self.tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(str(k), str(v))
            try:
                yield span
                span.set_attribute("tool.status", "SUCCESS")
            except Exception as exc:
                span.set_attribute("tool.status", "ERROR")
                span.set_attribute("tool.error", str(exc))
                span.record_exception(exc)
                raise
            finally:
                duration_ms = (time.time() - start_t) * 1000
                span.set_attribute("tool.duration_ms", round(duration_ms, 2))

    def get_traces(self) -> List[Dict[str, Any]]:
        """Returns all captured spans serialized for API and audit inspectability."""
        traces = []
        for s in self.collector.spans:
            duration_ms = (
                (s.end_time - s.start_time) / 1_000_000 if s.end_time and s.start_time else 0.0
            )
            traces.append({
                "name": s.name,
                "context": {
                    "trace_id": format(s.context.trace_id, "032x") if s.context else "",
                    "span_id": format(s.context.span_id, "016x") if s.context else "",
                },
                "start_time_unix_nano": s.start_time,
                "end_time_unix_nano": s.end_time,
                "duration_ms": round(duration_ms, 2),
                "attributes": dict(s.attributes or {}),
                "status": s.status.status_code.name if s.status else "UNSET",
            })
        return traces

    def get_summary(self) -> Dict[str, Any]:
        """Summarizes agent and tool spans by counts, latency, and status."""
        spans = self.collector.spans
        agent_spans = [s for s in spans if s.name.startswith("agent.")]
        tool_spans = [s for s in spans if s.name.startswith("tool.")]
        errors = [s for s in spans if (s.attributes or {}).get("agent.status") == "ERROR" or (s.attributes or {}).get("tool.status") == "ERROR"]

        total_ms = sum(
            ((s.end_time - s.start_time) / 1_000_000 if s.end_time and s.start_time else 0.0)
            for s in agent_spans
        )

        return {
            "total_spans": len(spans),
            "agent_invocations": len(agent_spans),
            "tool_invocations": len(tool_spans),
            "error_count": len(errors),
            "total_agent_latency_ms": round(total_ms, 2),
            "active_agents": list({s.attributes.get("agent.name") for s in agent_spans if s.attributes and "agent.name" in s.attributes}),
        }

    def reset(self):
        self.collector.clear()


telemetry = TelemetryManager.get_instance()
