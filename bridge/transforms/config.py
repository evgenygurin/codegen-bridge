"""Transform configuration models.

Uses Pydantic ``BaseModel`` for validation and serialisation, following the
same pattern as :mod:`bridge.middleware.config`.  Each transform type has its
own config model with an ``enabled`` flag and sensible defaults.

Profiles provide pre-built configurations for common deployment scenarios.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Individual transform configs ──────────────────────────


class NamespaceConfig(BaseModel):
    """Prefix all component names with a namespace.

    Tools/prompts: ``name`` -> ``{prefix}_{name}``
    Resources: ``proto://path`` -> ``proto://{prefix}/path``
    """

    enabled: bool = True
    prefix: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")


class ToolTransformEntry(BaseModel):
    """Rename or modify a single tool's metadata.

    Only fields explicitly set are applied; ``None`` means "keep original".
    """

    name: str | None = None
    description: str | None = None
    tags: set[str] | None = None
    enabled: bool = True


class ToolTransformConfig(BaseModel):
    """Transform tool schemas: rename, re-describe, re-tag, or hide tools.

    ``tools`` maps *current* tool names (after namespace, if any) to their
    desired transformations.
    """

    enabled: bool = True
    tools: dict[str, ToolTransformEntry] = Field(default_factory=dict)


class VisibilityRuleConfig(BaseModel):
    """Single visibility rule — show or hide matching components.

    Rules are evaluated in order. Later rules override earlier ones for
    the same component (last-write-wins).
    """

    enabled: bool = True
    names: set[str] | None = None
    tags: set[str] | None = None
    components: set[Literal["tool", "resource", "template", "prompt"]] | None = None
    match_all: bool = False


class VisibilityConfig(BaseModel):
    """Control which components are visible to clients.

    ``rules`` is an ordered list of visibility rules.  Each rule marks
    matching components as shown or hidden.  Rules are stacked — later
    rules override earlier ones.
    """

    enabled: bool = True
    rules: list[VisibilityRuleConfig] = Field(default_factory=list)


class VersionFilterConfig(BaseModel):
    """Filter components by semantic version range.

    Uses half-open intervals: ``[version_gte, version_lt)``.
    Omit a bound to leave it open-ended.
    """

    enabled: bool = True
    version_gte: str | None = None
    version_lt: str | None = None


# ── Top-level config ──────────────────────────────────────


class TransformsConfig(BaseModel):
    """Top-level transform configuration.

    Transforms are applied in a fixed order that matches the FastMCP
    transform chain semantics:

    1. **Namespace** — prefixes names (must be first so later transforms
       reference the namespaced names)
    2. **Tool Transform** — rename / re-describe individual tools
    3. **Visibility** — show/hide components by name, tag, or type
    4. **Version Filter** — filter by version range

    All transforms default to ``None`` (disabled).  Passing a sub-config
    with ``enabled=False`` also disables the transform.
    """

    namespace: NamespaceConfig | None = None
    tool_transform: ToolTransformConfig | None = None
    visibility: VisibilityConfig | None = None
    version_filter: VersionFilterConfig | None = None

    # ── Predefined profiles ────────────────────────────────

    @classmethod
    def passthrough(cls) -> TransformsConfig:
        """No transforms — all components pass through unchanged."""
        return cls()

    @classmethod
    def namespaced(cls, prefix: str) -> TransformsConfig:
        """Apply a namespace prefix to all components."""
        return cls(namespace=NamespaceConfig(prefix=prefix))

    @classmethod
    def setup_only(cls) -> TransformsConfig:
        """Show only setup tools; hide everything else."""
        return cls(
            visibility=VisibilityConfig(
                rules=[
                    VisibilityRuleConfig(enabled=False, match_all=True),
                    VisibilityRuleConfig(enabled=True, tags={"setup"}),
                ]
            )
        )

    @classmethod
    def execution_only(cls) -> TransformsConfig:
        """Show only execution and monitoring tools; hide setup."""
        return cls(
            visibility=VisibilityConfig(
                rules=[
                    VisibilityRuleConfig(enabled=False, match_all=True),
                    VisibilityRuleConfig(
                        enabled=True,
                        tags={"execution", "context", "monitoring"},
                    ),
                ]
            )
        )

    @classmethod
    def versioned(
        cls,
        *,
        version_gte: str | None = None,
        version_lt: str | None = None,
    ) -> TransformsConfig:
        """Show only components within a version range."""
        return cls(
            version_filter=VersionFilterConfig(
                version_gte=version_gte,
                version_lt=version_lt,
            )
        )
