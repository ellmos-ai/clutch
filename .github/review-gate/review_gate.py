#!/usr/bin/env python3
"""Signed, exact-SHA review receipts for GitHub branch protection.

The privileged GitHub Actions workflow executes this file from the default
branch only. Pull-request content is treated as data and is never imported or
executed. A successful status requires an OpenSSH signature from an allowed
reviewer or owner principal and a receipt bound to the current PR head SHA.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping


RECEIPT_SCHEMA = "ellmos.review-gate-receipt/v1"
SIGNATURE_NAMESPACE = "ellmos-review-gate"
STATUS_CONTEXT = "ellmos/review-gate"
DISPATCH_EVENT_TYPE = "ellmos-review-gate"
ACTIONS_APP_ID = 15368
MAX_RECEIPT_BYTES = 32 * 1024
MAX_SIGNATURE_BYTES = 8 * 1024
MAX_DISPATCH_BYTES = 64 * 1024
MAX_VALIDITY = timedelta(hours=24)

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_.:/-]{16,128}$")
_FINDING_KEYS = {"critical", "high", "medium", "low"}
_BASE_KEYS = {
    "schema",
    "kind",
    "repository",
    "pr_number",
    "head_sha",
    "verdict",
    "reviewer",
    "artifact_sha256",
    "findings",
    "checks",
    "issued_at",
    "valid_until",
    "nonce",
}
_OPTIONAL_KEYS = {"decision_id", "reason"}


class ReceiptValidationError(ValueError):
    """A review receipt, signature, or exact-SHA binding is invalid."""


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ReceiptValidationError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReceiptValidationError(f"{field} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReceiptValidationError(f"{field} is not a valid timestamp") from exc
    if parsed.microsecond:
        raise ReceiptValidationError(f"{field} must not contain fractional seconds")
    return parsed.astimezone(timezone.utc)


def canonical_receipt_bytes(receipt: Mapping[str, object]) -> bytes:
    """Return the one accepted byte representation for signing and dispatch."""
    return (
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def create_receipt(**values: object) -> dict[str, object]:
    """Create a schema-tagged receipt while enforcing kind-specific fields."""
    receipt = {"schema": RECEIPT_SCHEMA, **values}
    kind = receipt.get("kind")
    if kind == "owner_override":
        if not isinstance(receipt.get("decision_id"), str) or not receipt["decision_id"].strip():
            raise ReceiptValidationError("owner_override requires decision_id")
        if not isinstance(receipt.get("reason"), str) or not receipt["reason"].strip():
            raise ReceiptValidationError("owner_override requires reason")
    return receipt


def build_receipt(
    *,
    kind: str,
    repository: str,
    pr_number: int,
    head_sha: str,
    verdict: str,
    reviewer: str,
    artifact_path: Path,
    findings: Mapping[str, int],
    checks: list[str],
    valid_minutes: int = 60,
    decision_id: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Build a receipt from an immutable review artifact on disk."""
    issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    if valid_minutes < 1 or valid_minutes > int(MAX_VALIDITY.total_seconds() // 60):
        raise ReceiptValidationError("valid_minutes must be between 1 and 1440")
    artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    values: dict[str, object] = {
        "kind": kind,
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "verdict": verdict,
        "reviewer": reviewer,
        "artifact_sha256": artifact_hash,
        "findings": dict(findings),
        "checks": checks,
        "issued_at": _utc_text(issued),
        "valid_until": _utc_text(issued + timedelta(minutes=valid_minutes)),
        "nonce": secrets.token_urlsafe(24),
    }
    if decision_id is not None:
        values["decision_id"] = decision_id
    if reason is not None:
        values["reason"] = reason
    receipt = create_receipt(**values)
    validate_receipt(receipt, now=issued)
    return receipt


def validate_receipt(
    receipt: Mapping[str, object],
    *,
    expected_repository: str | None = None,
    expected_pr_number: int | None = None,
    expected_head_sha: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Validate schema, expiry, verdict invariants, and optional PR binding."""
    if not isinstance(receipt, Mapping):
        raise ReceiptValidationError("receipt must be a JSON object")
    unknown = set(receipt) - (_BASE_KEYS | _OPTIONAL_KEYS)
    missing = _BASE_KEYS - set(receipt)
    if unknown:
        raise ReceiptValidationError(f"unknown receipt fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ReceiptValidationError(f"missing receipt fields: {', '.join(sorted(missing))}")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ReceiptValidationError("unsupported receipt schema")

    kind = receipt.get("kind")
    if kind not in {"model_review", "owner_override"}:
        raise ReceiptValidationError("kind must be model_review or owner_override")
    repository = receipt.get("repository")
    if not isinstance(repository, str) or not _REPO_RE.fullmatch(repository):
        raise ReceiptValidationError("repository must be org/name")
    pr_number = receipt.get("pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise ReceiptValidationError("pr_number must be a positive integer")
    head_sha = receipt.get("head_sha")
    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
        raise ReceiptValidationError("head_sha must be a lowercase 40-character Git SHA")
    verdict = receipt.get("verdict")
    if verdict not in {"approve", "reject"}:
        raise ReceiptValidationError("verdict must be approve or reject")
    reviewer = receipt.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ReceiptValidationError("reviewer must be a non-empty short string")
    artifact_hash = receipt.get("artifact_sha256")
    if not isinstance(artifact_hash, str) or not _HASH_RE.fullmatch(artifact_hash):
        raise ReceiptValidationError("artifact_sha256 must be a lowercase SHA-256 hash")

    findings = receipt.get("findings")
    if not isinstance(findings, Mapping) or set(findings) != _FINDING_KEYS:
        raise ReceiptValidationError("findings must contain exactly critical, high, medium, and low")
    for key, value in findings.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ReceiptValidationError(f"finding count {key} must be a non-negative integer")

    checks = receipt.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in checks)
    ):
        raise ReceiptValidationError("checks must be a non-empty list of short strings")
    nonce = receipt.get("nonce")
    if not isinstance(nonce, str) or not _NONCE_RE.fullmatch(nonce):
        raise ReceiptValidationError("nonce must contain 16-128 safe characters")

    issued = _parse_utc(receipt.get("issued_at"), "issued_at")
    valid_until = _parse_utc(receipt.get("valid_until"), "valid_until")
    if valid_until <= issued:
        raise ReceiptValidationError("valid_until must be after issued_at")
    if valid_until - issued > MAX_VALIDITY:
        raise ReceiptValidationError("receipt validity must not exceed 24 hours")
    if now is not None:
        current = now.astimezone(timezone.utc)
        if issued > current + timedelta(minutes=5):
            raise ReceiptValidationError("receipt issued_at is too far in the future")
        if valid_until < current:
            raise ReceiptValidationError("receipt has expired")

    if kind == "model_review":
        if "decision_id" in receipt:
            raise ReceiptValidationError("model_review must not contain decision_id")
        if verdict == "approve" and (findings["critical"] or findings["high"]):
            raise ReceiptValidationError("approval cannot contain critical or high findings")
        if verdict == "reject" and (
            not isinstance(receipt.get("reason"), str) or not str(receipt["reason"]).strip()
        ):
            raise ReceiptValidationError("rejected model_review requires reason")
    else:
        if verdict != "approve":
            raise ReceiptValidationError("owner_override only supports approve")
        if not isinstance(receipt.get("decision_id"), str) or not str(receipt["decision_id"]).strip():
            raise ReceiptValidationError("owner_override requires decision_id")
        if not isinstance(receipt.get("reason"), str) or not str(receipt["reason"]).strip():
            raise ReceiptValidationError("owner_override requires reason")

    if expected_repository is not None and repository != expected_repository:
        raise ReceiptValidationError("receipt repository does not match the workflow repository")
    if expected_pr_number is not None and pr_number != expected_pr_number:
        raise ReceiptValidationError("receipt PR number does not match the live pull request")
    if expected_head_sha is not None and head_sha != expected_head_sha:
        raise ReceiptValidationError("receipt head SHA does not match the live pull request")
    return dict(receipt)


def validate_receipt_bytes(
    data: bytes,
    *,
    expected_repository: str | None = None,
    expected_pr_number: int | None = None,
    expected_head_sha: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    if not data or len(data) > MAX_RECEIPT_BYTES:
        raise ReceiptValidationError("receipt byte length is invalid")
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptValidationError("receipt is not valid UTF-8 JSON") from exc
    if not isinstance(receipt, dict):
        raise ReceiptValidationError("receipt must be a JSON object")
    if data != canonical_receipt_bytes(receipt):
        raise ReceiptValidationError("receipt bytes are not canonical")
    return validate_receipt(
        receipt,
        expected_repository=expected_repository,
        expected_pr_number=expected_pr_number,
        expected_head_sha=expected_head_sha,
        now=now,
    )


def _decode_b64(value: object, *, field: str, limit: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise ReceiptValidationError(f"{field} must be non-empty base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ReceiptValidationError(f"{field} is not valid base64") from exc
    if not decoded or len(decoded) > limit:
        raise ReceiptValidationError(f"{field} decoded length is invalid")
    return decoded


def encode_dispatch_payload(receipt_bytes: bytes, signature_bytes: bytes) -> dict[str, str]:
    if len(receipt_bytes) > MAX_RECEIPT_BYTES or len(signature_bytes) > MAX_SIGNATURE_BYTES:
        raise ReceiptValidationError("dispatch artifact is too large")
    return {
        "receipt_b64": base64.b64encode(receipt_bytes).decode("ascii"),
        "signature_b64": base64.b64encode(signature_bytes).decode("ascii"),
    }


def decode_dispatch_payload(payload: Mapping[str, object]) -> tuple[bytes, bytes]:
    return (
        _decode_b64(payload.get("receipt_b64"), field="receipt_b64", limit=MAX_RECEIPT_BYTES),
        _decode_b64(payload.get("signature_b64"), field="signature_b64", limit=MAX_SIGNATURE_BYTES),
    )


def principal_for_kind(kind: object) -> str:
    if kind == "model_review":
        return "ellmos-reviewer"
    if kind == "owner_override":
        return "ellmos-owner"
    raise ReceiptValidationError("cannot select signature principal for unknown receipt kind")


def verify_ssh_signature(
    receipt_bytes: bytes,
    signature_bytes: bytes,
    allowed_signers_bytes: bytes,
    *,
    principal: str,
) -> None:
    """Verify a detached OpenSSH signature without exposing a private key."""
    executable = shutil.which("ssh-keygen")
    if executable is None:
        raise ReceiptValidationError("ssh-keygen is unavailable for signature verification")
    if not allowed_signers_bytes or len(allowed_signers_bytes) > 64 * 1024:
        raise ReceiptValidationError("allowed signers content is missing or too large")
    with tempfile.TemporaryDirectory(prefix="ellmos-review-gate-") as temp_dir:
        root = Path(temp_dir)
        allowed = root / "allowed_signers"
        signature = root / "receipt.sig"
        allowed.write_bytes(allowed_signers_bytes)
        signature.write_bytes(signature_bytes)
        result = subprocess.run(
            [
                executable,
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                principal,
                "-n",
                SIGNATURE_NAMESPACE,
                "-s",
                str(signature),
            ],
            input=receipt_bytes,
            capture_output=True,
            timeout=20,
        )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReceiptValidationError(f"SSH signature verification failed: {detail or 'invalid signature'}")


def sign_receipt(receipt_path: Path, key_path: Path, output_path: Path) -> None:
    """Sign canonical receipt bytes without leaving an adjacent implicit .sig file."""
    receipt_bytes = receipt_path.read_bytes()
    validate_receipt_bytes(receipt_bytes, now=datetime.now(timezone.utc))
    executable = shutil.which("ssh-keygen")
    if executable is None:
        raise ReceiptValidationError("ssh-keygen is unavailable for receipt signing")
    if not key_path.is_file():
        raise ReceiptValidationError("signing key does not exist")
    if output_path.exists():
        raise ReceiptValidationError(f"refusing to overwrite existing signature: {output_path}")
    with tempfile.TemporaryDirectory(prefix="ellmos-review-gate-sign-") as temp_dir:
        temp_receipt = Path(temp_dir) / "receipt.json"
        temp_receipt.write_bytes(receipt_bytes)
        result = subprocess.run(
            [
                executable,
                "-Y",
                "sign",
                "-f",
                str(key_path),
                "-n",
                SIGNATURE_NAMESPACE,
                str(temp_receipt),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if result.returncode != 0:
            raise ReceiptValidationError(
                f"receipt signing failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        signature_path = Path(f"{temp_receipt}.sig")
        if not signature_path.is_file():
            raise ReceiptValidationError("ssh-keygen did not produce a detached signature")
        signature_bytes = signature_path.read_bytes()
    if not signature_bytes or len(signature_bytes) > MAX_SIGNATURE_BYTES:
        raise ReceiptValidationError("generated signature length is invalid")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as handle:
        handle.write(signature_bytes)


def _enabled(value: object, default: bool = False) -> bool:
    if isinstance(value, Mapping):
        return bool(value.get("enabled", default))
    if isinstance(value, bool):
        return value
    return default


def _names(items: object, field: str) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        if isinstance(item, Mapping) and isinstance(item.get(field), str):
            result.append(str(item[field]))
        elif isinstance(item, str):
            result.append(item)
    return result


def protection_put_payload(current: Mapping[str, object]) -> dict[str, object]:
    """Convert a branch-protection GET response into a restorable PUT body."""
    status = current.get("required_status_checks")
    status_payload: dict[str, object] | None = None
    if isinstance(status, Mapping):
        checks: list[dict[str, object]] = []
        raw_checks = status.get("checks")
        if isinstance(raw_checks, list):
            for check in raw_checks:
                if isinstance(check, Mapping) and isinstance(check.get("context"), str):
                    raw_app_id = check.get("app_id")
                    app_id = raw_app_id if isinstance(raw_app_id, int) and not isinstance(raw_app_id, bool) else -1
                    checks.append(
                        {
                            "context": str(check["context"]),
                            "app_id": app_id,
                        }
                    )
        if not checks:
            for context in status.get("contexts", []) if isinstance(status.get("contexts"), list) else []:
                if isinstance(context, str):
                    checks.append({"context": context, "app_id": -1})
        status_payload = {"strict": bool(status.get("strict", False)), "checks": checks}

    reviews = current.get("required_pull_request_reviews")
    reviews_payload: dict[str, object] | None = None
    if isinstance(reviews, Mapping):
        reviews_payload = {
            "dismiss_stale_reviews": bool(reviews.get("dismiss_stale_reviews", False)),
            "require_code_owner_reviews": bool(reviews.get("require_code_owner_reviews", False)),
            "required_approving_review_count": int(reviews.get("required_approving_review_count", 0)),
            "require_last_push_approval": bool(reviews.get("require_last_push_approval", False)),
        }
        bypass = reviews.get("bypass_pull_request_allowances")
        if isinstance(bypass, Mapping):
            reviews_payload["bypass_pull_request_allowances"] = {
                "users": _names(bypass.get("users"), "login"),
                "teams": _names(bypass.get("teams"), "slug"),
                "apps": _names(bypass.get("apps"), "slug"),
            }
        dismissal = reviews.get("dismissal_restrictions")
        if isinstance(dismissal, Mapping):
            reviews_payload["dismissal_restrictions"] = {
                "users": _names(dismissal.get("users"), "login"),
                "teams": _names(dismissal.get("teams"), "slug"),
                "apps": _names(dismissal.get("apps"), "slug"),
            }

    restrictions = current.get("restrictions")
    restrictions_payload: dict[str, object] | None = None
    if isinstance(restrictions, Mapping):
        restrictions_payload = {
            "users": _names(restrictions.get("users"), "login"),
            "teams": _names(restrictions.get("teams"), "slug"),
            "apps": _names(restrictions.get("apps"), "slug"),
        }

    return {
        "required_status_checks": status_payload,
        "enforce_admins": _enabled(current.get("enforce_admins")),
        "required_pull_request_reviews": reviews_payload,
        "restrictions": restrictions_payload,
        "required_linear_history": _enabled(current.get("required_linear_history")),
        "allow_force_pushes": _enabled(current.get("allow_force_pushes")),
        "allow_deletions": _enabled(current.get("allow_deletions")),
        "block_creations": _enabled(current.get("block_creations")),
        "required_conversation_resolution": _enabled(current.get("required_conversation_resolution")),
        "lock_branch": _enabled(current.get("lock_branch")),
        "allow_fork_syncing": _enabled(current.get("allow_fork_syncing")),
    }


def build_protection_payloads(
    current: Mapping[str, object],
    *,
    context: str = STATUS_CONTEXT,
    app_id: int = ACTIONS_APP_ID,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return (rollback, desired) payloads without changing GitHub."""
    rollback = protection_put_payload(current)
    desired = json.loads(json.dumps(rollback))
    desired["required_status_checks"] = {
        "strict": True,
        "checks": [{"context": context, "app_id": app_id}],
    }
    desired["required_pull_request_reviews"] = {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 0,
        "require_last_push_approval": False,
    }
    desired["enforce_admins"] = True
    desired["allow_force_pushes"] = False
    desired["allow_deletions"] = False
    desired["required_conversation_resolution"] = True
    return rollback, desired


def _resolve_token() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return str(os.environ[name])
    result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ReceiptValidationError("no GitHub token available")
    return result.stdout.strip()


def _github_api(
    method: str,
    path: str,
    *,
    token: str,
    payload: Mapping[str, object] | None = None,
) -> object:
    url = f"https://api.github.com/{path.lstrip('/')}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "ellmos-review-gate/1",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ReceiptValidationError(f"GitHub API {method} {path} failed: HTTP {exc.code}: {detail}") from exc
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _live_pr(repository: str, pr_number: int, *, token: str) -> dict[str, object]:
    result = _github_api("GET", f"repos/{repository}/pulls/{pr_number}", token=token)
    if not isinstance(result, dict):
        raise ReceiptValidationError("GitHub pull request response is invalid")
    return result


def _post_status(
    repository: str,
    sha: str,
    state: str,
    description: str,
    *,
    token: str,
    target_url: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "state": state,
        "context": STATUS_CONTEXT,
        "description": description[:140],
    }
    if target_url:
        payload["target_url"] = target_url
    _github_api("POST", f"repos/{repository}/statuses/{sha}", token=token, payload=payload)


def _run_url() -> str | None:
    server = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repository and run_id:
        return f"{server}/{repository}/actions/runs/{run_id}"
    return None


def workflow_pending(repository: str, pr_number: int, head_sha: str) -> None:
    token = _resolve_token()
    live = _live_pr(repository, pr_number, token=token)
    live_sha = ((live.get("head") or {}).get("sha") if isinstance(live.get("head"), Mapping) else None)
    if live.get("state") != "open" or live_sha != head_sha:
        raise ReceiptValidationError("pending status target is not the current open PR head")
    _post_status(
        repository,
        head_sha,
        "pending",
        "Awaiting a signed exact-SHA reviewer or owner receipt.",
        token=token,
        target_url=_run_url(),
    )


def workflow_dispatch(repository: str, payload: Mapping[str, object], allowed_signers: bytes) -> None:
    token = _resolve_token()
    receipt_bytes, signature_bytes = decode_dispatch_payload(payload)
    preliminary = validate_receipt_bytes(receipt_bytes, now=datetime.now(timezone.utc))
    pr_number = int(preliminary["pr_number"])
    live = _live_pr(repository, pr_number, token=token)
    live_head = live.get("head")
    live_sha = live_head.get("sha") if isinstance(live_head, Mapping) else None
    if live.get("state") != "open" or not isinstance(live_sha, str):
        raise ReceiptValidationError("receipt targets a pull request that is not open")

    try:
        receipt = validate_receipt_bytes(
            receipt_bytes,
            expected_repository=repository,
            expected_pr_number=pr_number,
            expected_head_sha=live_sha,
            now=datetime.now(timezone.utc),
        )
        verify_ssh_signature(
            receipt_bytes,
            signature_bytes,
            allowed_signers,
            principal=principal_for_kind(receipt["kind"]),
        )
        if receipt["verdict"] == "approve":
            description = (
                "Signed model review approved the exact PR head."
                if receipt["kind"] == "model_review"
                else f"Signed owner override: {receipt['decision_id']}"
            )
            _post_status(
                repository,
                live_sha,
                "success",
                description,
                token=token,
                target_url=_run_url(),
            )
            return
        raise ReceiptValidationError("signed review verdict is reject")
    except ReceiptValidationError as exc:
        _post_status(
            repository,
            live_sha,
            "failure",
            f"Review receipt rejected: {exc}",
            token=token,
            target_url=_run_url(),
        )
        raise


def dispatch_receipt(
    receipt_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    *,
    apply: bool,
) -> dict[str, object]:
    """Verify a local receipt against its live PR head and optionally dispatch it."""
    receipt_bytes = receipt_path.read_bytes()
    signature_bytes = signature_path.read_bytes()
    allowed_signers = allowed_signers_path.read_bytes()
    now = datetime.now(timezone.utc)
    receipt = validate_receipt_bytes(receipt_bytes, now=now)
    verify_ssh_signature(
        receipt_bytes,
        signature_bytes,
        allowed_signers,
        principal=principal_for_kind(receipt["kind"]),
    )
    repository = str(receipt["repository"])
    pr_number = int(receipt["pr_number"])
    token = _resolve_token()
    live = _live_pr(repository, pr_number, token=token)
    live_head = live.get("head")
    live_sha = live_head.get("sha") if isinstance(live_head, Mapping) else None
    if live.get("state") != "open" or not isinstance(live_sha, str):
        raise ReceiptValidationError("receipt targets a pull request that is not open")
    receipt = validate_receipt_bytes(
        receipt_bytes,
        expected_repository=repository,
        expected_pr_number=pr_number,
        expected_head_sha=live_sha,
        now=now,
    )
    client_payload = encode_dispatch_payload(receipt_bytes, signature_bytes)
    api_payload: dict[str, object] = {
        "event_type": DISPATCH_EVENT_TYPE,
        "client_payload": client_payload,
    }
    encoded_size = len(json.dumps(api_payload, separators=(",", ":")).encode("utf-8"))
    if encoded_size > MAX_DISPATCH_BYTES:
        raise ReceiptValidationError("repository_dispatch payload exceeds GitHub's 64 KiB limit")
    if apply:
        _github_api(
            "POST",
            f"repos/{repository}/dispatches",
            token=token,
            payload=api_payload,
        )
    return {
        "ok": True,
        "applied": apply,
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": live_sha,
        "verdict": receipt["verdict"],
        "kind": receipt["kind"],
        "payload_bytes": encoded_size,
    }


def _json_env_payload() -> dict[str, object]:
    return {
        "receipt_b64": os.environ.get("ELLMOS_RECEIPT_B64", ""),
        "signature_b64": os.environ.get("ELLMOS_SIGNATURE_B64", ""),
    }


def _allowed_signers_from_env() -> bytes:
    return _decode_b64(
        os.environ.get("ELLMOS_ALLOWED_SIGNERS_B64", ""),
        field="ELLMOS_ALLOWED_SIGNERS_B64",
        limit=64 * 1024,
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _write_new_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Signed exact-SHA GitHub review gate")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a canonical receipt bound to a review artifact")
    create.add_argument("--kind", required=True, choices=("model_review", "owner_override"))
    create.add_argument("--repo", required=True)
    create.add_argument("--pr", required=True, type=int)
    create.add_argument("--head-sha", required=True)
    create.add_argument("--verdict", required=True, choices=("approve", "reject"))
    create.add_argument("--reviewer", required=True)
    create.add_argument("--artifact", required=True, type=Path)
    create.add_argument("--critical", type=int, default=0)
    create.add_argument("--high", type=int, default=0)
    create.add_argument("--medium", type=int, default=0)
    create.add_argument("--low", type=int, default=0)
    create.add_argument("--check", action="append", required=True)
    create.add_argument("--valid-minutes", type=int, default=60)
    create.add_argument("--decision-id")
    create.add_argument("--reason")
    create.add_argument("--output", required=True, type=Path)

    sign = sub.add_parser("sign", help="Sign a canonical receipt with an OpenSSH private key")
    sign.add_argument("--receipt", required=True, type=Path)
    sign.add_argument("--key", required=True, type=Path)
    sign.add_argument("--output", required=True, type=Path)

    dispatch_local = sub.add_parser(
        "dispatch", help="Verify a signed receipt against the live PR and optionally dispatch it"
    )
    dispatch_local.add_argument("--receipt", required=True, type=Path)
    dispatch_local.add_argument("--signature", required=True, type=Path)
    dispatch_local.add_argument("--allowed-signers", required=True, type=Path)
    dispatch_local.add_argument("--apply", action="store_true")

    pending = sub.add_parser("workflow-pending", help="Mark a verified live PR head pending")
    pending.add_argument("--repo", required=True)
    pending.add_argument("--pr", required=True, type=int)
    pending.add_argument("--head-sha", required=True)

    dispatch = sub.add_parser("workflow-dispatch", help="Verify dispatch env and post exact-SHA status")
    dispatch.add_argument("--repo", required=True)

    verify = sub.add_parser("verify", help="Verify a local signed receipt")
    verify.add_argument("--receipt", required=True, type=Path)
    verify.add_argument("--signature", required=True, type=Path)
    verify.add_argument("--allowed-signers", required=True, type=Path)

    plan = sub.add_parser("protection-plan", help="Build desired and rollback branch-protection payloads")
    plan.add_argument("--current", required=True, type=Path)
    plan.add_argument("--output-dir", required=True, type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            receipt = build_receipt(
                kind=args.kind,
                repository=args.repo,
                pr_number=args.pr,
                head_sha=args.head_sha,
                verdict=args.verdict,
                reviewer=args.reviewer,
                artifact_path=args.artifact,
                findings={
                    "critical": args.critical,
                    "high": args.high,
                    "medium": args.medium,
                    "low": args.low,
                },
                checks=args.check,
                valid_minutes=args.valid_minutes,
                decision_id=args.decision_id,
                reason=args.reason,
            )
            _write_new_bytes(args.output, canonical_receipt_bytes(receipt))
            print(args.output)
        elif args.command == "sign":
            sign_receipt(args.receipt, args.key, args.output)
            print(args.output)
        elif args.command == "dispatch":
            print(
                json.dumps(
                    dispatch_receipt(
                        args.receipt,
                        args.signature,
                        args.allowed_signers,
                        apply=args.apply,
                    ),
                    ensure_ascii=False,
                )
            )
        elif args.command == "workflow-pending":
            workflow_pending(args.repo, args.pr, args.head_sha)
        elif args.command == "workflow-dispatch":
            workflow_dispatch(args.repo, _json_env_payload(), _allowed_signers_from_env())
        elif args.command == "verify":
            receipt_bytes = args.receipt.read_bytes()
            receipt = validate_receipt_bytes(receipt_bytes, now=datetime.now(timezone.utc))
            verify_ssh_signature(
                receipt_bytes,
                args.signature.read_bytes(),
                args.allowed_signers.read_bytes(),
                principal=principal_for_kind(receipt["kind"]),
            )
            print(json.dumps({"ok": True, "receipt": receipt}, ensure_ascii=False))
        elif args.command == "protection-plan":
            current = json.loads(args.current.read_text(encoding="utf-8"))
            rollback, desired = build_protection_payloads(current)
            rollback_path = args.output_dir / "rollback.json"
            desired_path = args.output_dir / "desired.json"
            if rollback_path.exists() or desired_path.exists():
                raise ReceiptValidationError("refusing to overwrite an existing protection plan")
            _write_json(rollback_path, rollback)
            _write_json(desired_path, desired)
            print(args.output_dir)
        return 0
    except (OSError, ReceiptValidationError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
