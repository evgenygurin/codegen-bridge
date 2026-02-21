"""Shared fixtures for telemetry tests.

Sets up the OpenTelemetry SDK TracerProvider once per session with an
InMemorySpanExporter.  Individual tests clear the exporter before/after
each test to get clean span assertions.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Module-level SDK setup — done once before any tests run.
# This avoids the "Overriding of current TracerProvider is not allowed" warning.
_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


@pytest.fixture
def trace_exporter() -> InMemorySpanExporter:
    """Provide a clean in-memory span exporter for each test."""
    _exporter.clear()
    yield _exporter
    _exporter.clear()
