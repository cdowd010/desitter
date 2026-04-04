"""Tests for controlplane/automation.py — RenderTrigger and should_render."""
from __future__ import annotations

import pytest

from desitter.controlplane.automation import (
    DEFAULT_RENDER_TRIGGERS,
    RenderTrigger,
    should_render,
)


class TestRenderTrigger:
    def test_construction(self):
        t = RenderTrigger("claim")
        assert t.resource == "claim"
        assert t.surfaces is None

    def test_with_surfaces(self):
        t = RenderTrigger("prediction", surfaces=["health", "metrics"])
        assert t.surfaces == ["health", "metrics"]


class TestDefaultTriggers:
    def test_all_canonical_resources_present(self):
        expected = {
            "claim", "assumption", "prediction", "analysis",
            "independence_group", "theory", "discovery",
            "dead_end", "parameter",
        }
        actual = {t.resource for t in DEFAULT_RENDER_TRIGGERS}
        assert actual == expected


class TestShouldRender:
    def test_default_triggers_match(self):
        for resource in ("claim", "prediction", "parameter"):
            assert should_render(resource) is True

    def test_unknown_resource(self):
        assert should_render("nonexistent_resource") is False

    def test_custom_triggers(self):
        custom = [RenderTrigger("special")]
        assert should_render("special", triggers=custom) is True
        assert should_render("claim", triggers=custom) is False

    def test_empty_triggers(self):
        assert should_render("claim", triggers=[]) is False
