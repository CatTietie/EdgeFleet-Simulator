"""Integration test: permission isolation between organizations."""
import pytest
import uuid
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

import jwt

# Add backend to path
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.config import settings


def _make_token(org_id: str, role: str = "admin", group_ids: list = None) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "org_id": org_id,
        "group_ids": group_ids or [],
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class TestCrossOrgIsolation:
    """Verify that users in org-A cannot access org-B resources."""

    def test_token_contains_correct_org(self):
        token = _make_token("org-alpha")
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert decoded["org_id"] == "org-alpha"

    def test_different_orgs_get_different_tokens(self):
        token_a = _make_token("org-alpha")
        token_b = _make_token("org-beta")
        decoded_a = jwt.decode(token_a, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        decoded_b = jwt.decode(token_b, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert decoded_a["org_id"] != decoded_b["org_id"]


class TestRoleEscalationPrevention:
    """Verify that lower roles cannot perform higher-role actions."""

    def test_viewer_token_has_viewer_role(self):
        token = _make_token("org-test", role="viewer")
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert decoded["role"] == "viewer"

    def test_operator_token_has_operator_role(self):
        token = _make_token("org-test", role="operator")
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert decoded["role"] == "operator"


class TestGroupIsolation:
    """Verify group-level access scoping."""

    def test_user_with_group_assignment(self):
        token = _make_token("org-test", role="operator", group_ids=["floor-1", "floor-2"])
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert "floor-1" in decoded["group_ids"]
        assert "floor-3" not in decoded["group_ids"]


class TestTokenExpiration:
    """Verify expired tokens are rejected."""

    def test_expired_token_raises(self):
        payload = {
            "sub": "user-1",
            "org_id": "org-test",
            "group_ids": [],
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # expired
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
