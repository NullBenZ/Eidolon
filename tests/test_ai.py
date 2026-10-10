"""
Tests for eidolon/ai.py — all mocked, no real API calls.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from eidolon.ai import (
    GemmaProvider,
    EffectsReply,
    EffectItem,
    changes_to_ai_items,
    load_dotenv,
    _is_contradiction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOOD_REPLY = json.dumps({
    "overall": "You updated a monitor and a keybind, which might break things.",
    "effects": [
        {"id": "Monitor:eDP-1", "meaning": "This will likely crash.", "fix": "Use preferred."},
        {"id": "Keybind:super:t", "meaning": "Opens kitty.", "fix": ""},
    ]
})

FENCED_REPLY = "```json\n" + GOOD_REPLY + "\n```"

MALFORMED_REPLY = "sure! here is your answer {broken json"

UNKNOWN_ID_REPLY = json.dumps({
    "overall": "Something happened.",
    "effects": [
        {"id": "DoesNotExist:x", "meaning": "Mysterious.", "fix": ""},
    ]
})


def _make_provider(api_key="test-key-12345"):
    """Create a GemmaProvider with a fake key, without hitting the network."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": api_key, "GEMMA_MODEL": "test-model"}):
        p = GemmaProvider()
    return p


def _mock_generate(raw_text):
    """Return a mock response object whose .text is raw_text."""
    resp = MagicMock()
    resp.text = raw_text
    return resp


# ---------------------------------------------------------------------------
# Good reply
# ---------------------------------------------------------------------------

def test_good_reply():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_generate(GOOD_REPLY)
    provider._client = mock_client

    reply, err = provider.explain([{"id": "Monitor:eDP-1", "kind": "Monitor"}])

    assert err is None
    assert reply is not None
    assert len(reply.effects) == 2
    assert reply.effects[0].id == "Monitor:eDP-1"
    assert "crash" in reply.effects[0].meaning


# ---------------------------------------------------------------------------
# Fenced JSON (```json ... ```)
# ---------------------------------------------------------------------------

def test_fenced_json():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_generate(FENCED_REPLY)
    provider._client = mock_client

    reply, err = provider.explain([{"id": "x"}])
    assert err is None
    assert reply is not None
    assert len(reply.effects) == 2


# ---------------------------------------------------------------------------
# Malformed JSON
# ---------------------------------------------------------------------------

def test_malformed_json():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_generate(MALFORMED_REPLY)
    provider._client = mock_client

    reply, err = provider.explain([{"id": "x"}])
    assert reply is None
    assert "malformed JSON" in err


# ---------------------------------------------------------------------------
# Unknown ids (should still parse, caller ignores unknown ids)
# ---------------------------------------------------------------------------

def test_unknown_ids():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_generate(UNKNOWN_ID_REPLY)
    provider._client = mock_client

    reply, err = provider.explain([{"id": "x"}])
    assert err is None
    assert reply is not None
    # the reply contains an id that doesn't match our input — that's fine,
    # the caller is responsible for ignoring it
    assert reply.effects[0].id == "DoesNotExist:x"


# ---------------------------------------------------------------------------
# Missing key
# ---------------------------------------------------------------------------

def test_missing_key():
    provider = _make_provider(api_key="")

    reply, err = provider.explain([{"id": "x"}])
    assert reply is None
    assert "not configured" in err


# ---------------------------------------------------------------------------
# Timeout / network error
# ---------------------------------------------------------------------------

def test_timeout():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("took too long")
    provider._client = mock_client

    reply, err = provider.explain([{"id": "x"}])
    assert reply is None
    assert "AI call failed" in err


# ---------------------------------------------------------------------------
# Quota / API error
# ---------------------------------------------------------------------------

def test_quota_error():
    provider = _make_provider()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    provider._client = mock_client

    reply, err = provider.explain([{"id": "x"}])
    assert reply is None
    assert "AI call failed" in err


# ---------------------------------------------------------------------------
# --no-ai (provider is never called; tested at integration level,
#  but we can also test that is_configured works)
# ---------------------------------------------------------------------------

def test_no_ai_flag():
    """When there is no key, is_configured returns False."""
    provider = _make_provider(api_key="")
    assert provider.is_configured is False

    provider2 = _make_provider(api_key="some-key")
    assert provider2.is_configured is True


# ---------------------------------------------------------------------------
# Key never in output
# ---------------------------------------------------------------------------

def test_key_never_in_output():
    """The API key must never appear in any error string."""
    secret = "super-secret-key-abc123"
    provider = _make_provider(api_key=secret)
    mock_client = MagicMock()
    # The exception message deliberately contains the key
    mock_client.models.generate_content.side_effect = Exception(
        f"Auth failed for key {secret}"
    )
    provider._client = mock_client

    reply, err = provider.explain([{"id": "x"}])
    assert reply is None
    assert secret not in err
    assert "***" in err


# ---------------------------------------------------------------------------
# changes_to_ai_items helper
# ---------------------------------------------------------------------------

def test_changes_to_ai_items():
    from eidolon.adapters.hyprland.comparator import ConfigChange
    from eidolon.models import Finding, Label, Severity

    f = Finding(
        rule_id="HYP-004", title="Bad mode", label=Label.VERIFIED,
        severity=Severity.ERROR, evidence="Mode not available",
        recommendation="Fix it", source="Hyprland Adapter", line_number=1,
    )
    ch = ConfigChange(
        category="Monitor", item_id="eDP-1",
        before_state="1920x1200@60", after_state="2560x1440@165",
        findings=[f],
    )
    items = changes_to_ai_items([ch])
    assert len(items) == 1
    assert items[0]["id"] == "Monitor:eDP-1"
    assert items[0]["status"] == "[VERIFIED] Mode not available"


# ---------------------------------------------------------------------------
# load_dotenv
# ---------------------------------------------------------------------------

def test_load_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('MY_TEST_VAR="hello"\nANOTHER=world\n# comment\n')

    # remove if already set
    os.environ.pop("MY_TEST_VAR", None)
    os.environ.pop("ANOTHER", None)

    load_dotenv(tmp_path)

    assert os.environ.get("MY_TEST_VAR") == "hello"
    assert os.environ.get("ANOTHER") == "world"

    # cleanup
    del os.environ["MY_TEST_VAR"]
    del os.environ["ANOTHER"]
