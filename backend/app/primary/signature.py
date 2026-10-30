"""Digital signature for discharge letters with a personal security key.

The doctor signs with a FIDO2 / WebAuthn key: a hospital badge or USB/NFC key
(e.g. YubiKey NFC) tapped on the reader, or a platform authenticator such as
Touch ID. The server issues a one-time challenge bound to the letter; only the
key's public part is stored here.

For demos without hardware there is a "software" key: the browser creates a
P-256 key pair in memory (WebCrypto, never stored) and signs the same challenge.
It is clearly labelled as simulated in the UI and in the audit log.

Lost key: the doctor (or IT on their behalf) reports it lost and it is blocked
at once. The doctor signs with a backup key registered earlier. Without a
backup, the IT admin checks identity in person and issues a one-time recovery
code (24 h) that allows registering one new key. Until then a senior doctor signs.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import load_der_public_key
from fastapi import HTTPException
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from .. import state

RP_ID = os.getenv("EHDS_RP_ID", "localhost")
RP_NAME = "EHDS Connect"
ORIGINS = os.getenv("EHDS_ORIGINS", "http://localhost:8080,http://localhost:5173,http://localhost:3000").split(",")
CHALLENGE_TTL = timedelta(minutes=5)
RECOVERY_TTL = timedelta(hours=24)
WEBAUTHN, SOFTWARE = "webauthn", "software"
METHOD = {WEBAUTHN: "security key (FIDO2/WebAuthn)", SOFTWARE: "simulated security key (demo)"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _public(k: dict) -> dict:
    return {key: k[key] for key in ("id", "kind", "label", "credential_id", "status", "created_at", "status_changed_at")}


def keys(user_id: str) -> list[dict]:
    rows = state.query("SELECT * FROM security_keys WHERE user_id = ? ORDER BY created_at", (user_id,))
    return [_public(r) for r in rows]


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def _valid_recovery(user_id: str, code: str | None) -> dict | None:
    if not code:
        return None
    row = state.one("SELECT * FROM recovery_codes WHERE code_hash = ? AND user_id = ? AND used_at IS NULL",
                    (_hash_code(code), user_id))
    if not row or datetime.fromisoformat(row["expires_at"]) < _utcnow():
        return None
    return row


def _enrolment_mode(user: dict, recovery_code: str | None) -> str:
    rows = state.query("SELECT status FROM security_keys WHERE user_id = ?", (user["id"],))
    if any(r["status"] == "active" for r in rows):
        return "backup"
    if not rows:
        return "first"
    if _valid_recovery(user["id"], recovery_code):
        return "recovery"
    raise HTTPException(403, {"message": "Your key was reported lost. Ask your IT admin for a one-time recovery code "
                                         "(identity check in person), then register a new key.",
                              "needs_recovery_code": True})


def _new_challenge(user: dict, purpose: str, ref: str | None = None) -> bytes:
    raw = secrets.token_bytes(32)
    with state.tx() as c:
        c.execute("INSERT INTO key_challenges (challenge,user_id,purpose,ref,created_at) VALUES (?,?,?,?,?)",
                  (bytes_to_base64url(raw), user["id"], purpose, ref, state.now()))
    return raw


def _consume_challenge(user: dict, challenge: str, purpose: str, ref: str | None = None) -> None:
    with state.tx() as c:
        row = c.execute("SELECT * FROM key_challenges WHERE challenge = ? AND user_id = ? AND purpose = ? AND used = 0",
                        (challenge, user["id"], purpose)).fetchone()
        if not row or (ref is not None and row["ref"] != ref) or \
                datetime.fromisoformat(row["created_at"]) + CHALLENGE_TTL < _utcnow():
            raise HTTPException(401, "The signing request expired. Please try again.")
        c.execute("UPDATE key_challenges SET used = 1 WHERE challenge = ?", (challenge,))


def registration_options(user: dict, recovery_code: str | None = None) -> dict:
    mode = _enrolment_mode(user, recovery_code)
    raw = _new_challenge(user, "register")
    existing = state.query("SELECT credential_id FROM security_keys WHERE user_id = ? AND kind = ?", (user["id"], WEBAUTHN))
    opts = generate_registration_options(
        rp_id=RP_ID, rp_name=RP_NAME, user_id=user["id"].encode(), user_name=user.get("email") or user["id"],
        user_display_name=user["name"], challenge=raw,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"])) for r in existing],
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.DISCOURAGED,
                                                               user_verification=UserVerificationRequirement.PREFERRED))
    return {"challenge": bytes_to_base64url(raw), "mode": mode, "webauthn": json.loads(options_to_json(opts))}


def _verify_software(public_key_der: bytes, challenge: str, signature_b64: str) -> None:
    pub = load_der_public_key(public_key_der)
    if not isinstance(pub, ec.EllipticCurvePublicKey) or pub.curve.name != "secp256r1":
        raise HTTPException(422, "Expected a P-256 public key")
    sig = base64url_to_bytes(signature_b64)
    if len(sig) != 64:
        raise HTTPException(401, "Signature could not be verified.")
    der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
    try:
        pub.verify(der, challenge.encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise HTTPException(401, "Signature could not be verified.") from None


def register(user: dict, kind: str, label: str | None, challenge: str, credential: dict | None = None,
             public_key: str | None = None, signature: str | None = None, recovery_code: str | None = None) -> dict:
    mode = _enrolment_mode(user, recovery_code)
    _consume_challenge(user, challenge, "register")
    if kind == WEBAUTHN:
        if not credential:
            raise HTTPException(422, "Missing WebAuthn credential")
        try:
            v = verify_registration_response(credential=credential, expected_challenge=base64url_to_bytes(challenge),
                                             expected_rp_id=RP_ID, expected_origin=ORIGINS,
                                             require_user_verification=False)
        except Exception as e:  # webauthn raises several exception types for invalid responses
            raise HTTPException(401, f"Security key could not be registered: {e}") from None
        cred_id, pub, count = bytes_to_base64url(v.credential_id), v.credential_public_key, v.sign_count
    elif kind == SOFTWARE:
        if not public_key or not signature:
            raise HTTPException(422, "Missing public key or proof of possession")
        pub = base64url_to_bytes(public_key)
        _verify_software(pub, challenge, signature)
        cred_id, count = "sw-" + secrets.token_hex(8), 0
    else:
        raise HTTPException(422, "Unknown key type")
    kid = "k-" + secrets.token_hex(6)
    with state.tx() as c:
        c.execute("INSERT INTO security_keys (id,user_id,kind,label,credential_id,public_key,sign_count,status,created_at) "
                  "VALUES (?,?,?,?,?,?,?,'active',?)",
                  (kid, user["id"], kind, (label or METHOD[kind])[:60], cred_id, pub, count, state.now()))
        if mode == "recovery":
            c.execute("UPDATE recovery_codes SET used_at = ? WHERE code_hash = ?", (state.now(), _hash_code(recovery_code or "")))
        state.audit(user, "auth", "security_key_registered", outcome=mode, details={"key_id": kid, "kind": kind}, conn=c)
    return _public(state.one("SELECT * FROM security_keys WHERE id = ?", (kid,)))


def report_lost(user: dict, key_id: str, owner_id: str | None = None) -> dict:
    owner = owner_id or user["id"]
    row = state.one("SELECT * FROM security_keys WHERE id = ? AND user_id = ?", (key_id, owner))
    if not row:
        raise HTTPException(404, "Key not found")
    with state.tx() as c:
        c.execute("UPDATE security_keys SET status='lost', status_changed_at=? WHERE id=?", (state.now(), key_id))
        state.audit(user, "auth", "security_key_lost", outcome="blocked", details={"key_id": key_id, "owner": owner}, conn=c)
    return _public(state.one("SELECT * FROM security_keys WHERE id = ?", (key_id,)))


def issue_recovery_code(admin: dict, user_id: str) -> dict:
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    expires = (_utcnow() + RECOVERY_TTL).isoformat(timespec="seconds")
    with state.tx() as c:
        c.execute("INSERT INTO recovery_codes (code_hash,user_id,issued_by,expires_at) VALUES (?,?,?,?)",
                  (_hash_code(code), user_id, admin["id"], expires))
        state.audit(admin, "auth", "recovery_code_issued", outcome="identity_checked_in_person",
                    details={"for_user": user_id, "expires_at": expires}, conn=c)
    return {"code": code, "expires_at": expires, "note": "Shown once. Hand it over in person; it allows one new key."}


def sign_challenge(user: dict, letter_id: str) -> dict:
    active = state.query("SELECT * FROM security_keys WHERE user_id = ? AND status = 'active'", (user["id"],))
    if not active:
        raise HTTPException(409, {"message": "Register a security key before signing.", "needs_key": True})
    raw = _new_challenge(user, "sign", letter_id)
    web = [k for k in active if k["kind"] == WEBAUTHN]
    opts = None
    if web:
        opts = json.loads(options_to_json(generate_authentication_options(
            rp_id=RP_ID, challenge=raw, user_verification=UserVerificationRequirement.PREFERRED,
            allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(k["credential_id"])) for k in web])))
    return {"challenge": bytes_to_base64url(raw), "keys": [_public(k) for k in active], "webauthn": opts}


def verify(user: dict, letter_id: str, key_id: str, challenge: str, assertion: dict | None = None,
           signature: str | None = None) -> dict:
    key = state.one("SELECT * FROM security_keys WHERE id = ? AND user_id = ?", (key_id, user["id"]))
    if not key or key["status"] != "active":
        raise HTTPException(401, "This security key is not active.")
    _consume_challenge(user, challenge, "sign", letter_id)
    if key["kind"] == WEBAUTHN:
        if not assertion:
            raise HTTPException(422, "Missing security key response")
        try:
            v = verify_authentication_response(credential=assertion, expected_challenge=base64url_to_bytes(challenge),
                                               expected_rp_id=RP_ID, expected_origin=ORIGINS,
                                               credential_public_key=key["public_key"],
                                               credential_current_sign_count=key["sign_count"],
                                               require_user_verification=False)
        except Exception:
            raise HTTPException(401, "Signature could not be verified.") from None
        with state.tx() as c:
            c.execute("UPDATE security_keys SET sign_count = ? WHERE id = ?", (v.new_sign_count, key_id))
    else:
        if not signature:
            raise HTTPException(422, "Missing signature")
        _verify_software(key["public_key"], challenge, signature)
    return {"key_id": key_id, "kind": key["kind"], "label": key["label"], "method": METHOD[key["kind"]],
            "signed_at": state.now()}
