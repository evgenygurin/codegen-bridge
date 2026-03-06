# Codegen Bridge — developer commands
# Usage: just <recipe>  (install just: https://github.com/casey/just)

set dotenv-load := true

# Default: show available recipes
default:
    @just --list

# ── Setup ──────────────────────────────────────────────

# Install all dependencies (dev included)
install:
    uv sync --dev

# Reinstall everything from scratch (fixes pydantic_core issues)
reinstall:
    uv sync --dev --reinstall

# ── Quality ────────────────────────────────────────────

# Run linter
lint:
    uv run ruff check .

# Run linter with auto-fix
lint-fix:
    uv run ruff check . --fix

# Check formatting
fmt-check:
    uv run ruff format --check .

# Auto-format code
fmt:
    uv run ruff format .

# Run type checker (strict mode)
typecheck:
    uv run mypy bridge/

# ── Testing ────────────────────────────────────────────

# Run full test suite
test *ARGS:
    uv run pytest -v {{ARGS}}

# Run tests with short tracebacks (CI-style)
test-ci:
    uv run pytest -v --tb=short -q

# Run a single test file
test-file FILE:
    uv run pytest {{FILE}} -v

# Run MCP integration tests (full protocol round-trip, structured logging)
mcp-test *ARGS:
    uv run pytest tests/test_mcp_integration.py -v -s --tb=short {{ARGS}}

# ── Combined ───────────────────────────────────────────

# Run all checks: lint + format check + typecheck + tests
check: lint fmt-check typecheck test

# Quick pre-commit check (lint + typecheck only, no tests)
pre-commit: lint fmt-check typecheck

# ── Server ─────────────────────────────────────────────

# Run MCP server directly (for debugging)
serve:
    uv run python -m bridge.server
