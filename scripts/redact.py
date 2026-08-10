#!/usr/bin/env python3
"""
Secret redaction for cluster output before it reaches an AI assistant.

`k8s-ai-troubleshooter` works by feeding real cluster output — `kubectl
describe`, `kubectl logs`, `kubectl get -o yaml` — to a model. That output
routinely contains credentials:

- `describe pod` prints every environment variable value, including the ones
  holding database passwords;
- `get secret -o yaml` prints the base64 payload in full;
- application logs print connection strings, bearer tokens and stack traces
  carrying API keys;
- `kubeconfig` carries `client-key-data` and bearer tokens.

Sending any of that to a hosted model publishes it. This module scrubs it first.

Design rules:

1. **Preserve diagnostic value.** Redaction replaces the *value*, never the key,
   the structure, or the surrounding text. `DB_PASSWORD: hunter2` becomes
   `DB_PASSWORD: [REDACTED:password:8f14e45f]` — you can still see that the
   variable is set, which is often the diagnosis.

2. **Fingerprint, don't just blank.** The trailing hash is the first 8 hex
   characters of the SHA-256 of the value. Identical secrets produce identical
   fingerprints, so you can still tell "the token in the pod spec is the same
   one the sidecar is failing on" without learning either. Fingerprints are not
   reversible, but they do confirm a guess, so treat a bundle as
   need-to-know rather than public.

3. **Bias to over-redaction.** A redacted `LOG_LEVEL` costs one follow-up
   command. A leaked production credential costs a rotation. Where the two
   trade off, this module redacts.

4. **Idempotent.** Running it twice is a no-op; `[REDACTED:...]` markers are not
   themselves redactable.

This is a best-effort filter, not a guarantee. It cannot recognise a secret that
looks like ordinary text (a password stored in a variable named `MODE`, say).
Review a bundle before sharing it.
"""

import argparse
import hashlib
import re
import sys

REDACTION_MARKER = "REDACTED"

#: Substrings that mark a key as holding a secret. Matched case-insensitively
#: against the key name. Deliberately broad, per design rule 3.
SENSITIVE_KEY_PARTS = (
    "password", "passwd", "pwd", "secret", "token", "apikey", "api_key",
    "accesskey", "access_key", "secretkey", "secret_key", "credential",
    "private_key", "privatekey", "session", "cookie", "signature",
    "encryption", "passphrase", "auth_token", "authtoken", "bearer",
    "connection_string", "connectionstring", "dsn", "client_secret",
    "clientsecret", "webhook_url", "sasl", "keystore", "truststore",
)

#: Keys that look sensitive by the rule above but are safe and load-bearing for
#: diagnosis. Matched as a whole key, case-insensitively.
KEY_ALLOWLIST = frozenset({
    "secretName", "secretKeyRef", "secretRef", "tokenRequests",
    "serviceAccountName", "imagePullSecrets", "secrets",
    "automountServiceAccountToken", "authMode", "authType",
    "tokenReviewEndpoint", "sessionAffinity",
})


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:8]


def _marker(kind: str, value: str) -> str:
    return f"[{REDACTION_MARKER}:{kind}:{fingerprint(value)}]"


def _key_is_sensitive(key: str) -> bool:
    stripped = key.strip().strip('"').strip("'")
    if stripped in KEY_ALLOWLIST:
        return False
    lowered = stripped.lower()
    if lowered in {k.lower() for k in KEY_ALLOWLIST}:
        return False
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _already_redacted(value: str) -> bool:
    return value.strip().startswith(f"[{REDACTION_MARKER}:")


#: A connection string is URL-shaped and its secret is the password component,
#: which URL_CREDENTIALS has already replaced by the time the key-name rules run.
_URL_SHAPED = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def _is_url_with_redacted_credentials(value: str) -> bool:
    """
    True when `value` is a URL whose credentials were already redacted.

    Such a value must be left alone. Blanking the whole of
    `postgres://app:[REDACTED]@db.prod.svc:5432/main` because the key is named
    `DSN` would destroy the host, port and database name — frequently the answer
    to "why can't this pod reach its database".

    The check deliberately requires an existing marker. A URL with no credential
    portion falls through to full redaction, because for keys like `webhook_url`
    the secret is the path rather than a password.
    """
    stripped = value.strip()
    return bool(_URL_SHAPED.match(stripped)) and f"[{REDACTION_MARKER}:" in stripped


# --------------------------------------------------------------------------
# High-confidence standalone patterns. These are redacted wherever they appear,
# regardless of the key they sit under, because the value itself is unambiguous.
# --------------------------------------------------------------------------

STANDALONE_PATTERNS = [
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("aws-key-id", re.compile(r"\b(?:AKIA|ASIA|AROA|AIDA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("gcp-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
]

#: proto://user:password@host — the password is the capture that matters.
URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)(?P<user>[^:@/\s]{1,128}):(?P<secret>[^@/\s]{1,256})@"
)

#: Authorization: Bearer <token> / Authorization: Basic <blob>
AUTH_HEADER = re.compile(
    r"(?P<prefix>(?i:authorization)\s*[:=]\s*(?i:bearer|basic|token)\s+)(?P<secret>[A-Za-z0-9._~+/=-]{8,})"
)

# --------------------------------------------------------------------------
# Structured key/value forms, redacted only when the key looks sensitive.
# --------------------------------------------------------------------------

#: YAML / `kubectl describe` style:  KEY: value
YAML_KV = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.\-/]{1,128}):(?P<sep>[ \t]+)(?P<value>\S.*)$")

#: Env / dotenv style:  KEY=value
ENV_KV = re.compile(r"(?P<key>\b[A-Za-z_][A-Za-z0-9_]{0,128})=(?P<value>[^\s,;)]+)")

#: JSON style:  "key": "value"
JSON_KV = re.compile(r'(?P<key>"[A-Za-z0-9_.\-/]{1,128}")(?P<sep>\s*:\s*)"(?P<value>[^"]*)"')


def _redact_standalone(text, stats):
    for kind, pattern in STANDALONE_PATTERNS:
        def repl(match, kind=kind):
            stats[kind] = stats.get(kind, 0) + 1
            return _marker(kind, match.group(0))

        text = pattern.sub(repl, text)

    def url_repl(match):
        secret = match.group("secret")
        if _already_redacted(secret):
            return match.group(0)
        stats["url-credentials"] = stats.get("url-credentials", 0) + 1
        return f"{match.group('scheme')}{match.group('user')}:{_marker('url-credentials', secret)}@"

    text = URL_CREDENTIALS.sub(url_repl, text)

    def auth_repl(match):
        secret = match.group("secret")
        if _already_redacted(secret):
            return match.group(0)
        stats["auth-header"] = stats.get("auth-header", 0) + 1
        return f"{match.group('prefix')}{_marker('auth-header', secret)}"

    return AUTH_HEADER.sub(auth_repl, text)


def _redact_json_kv(text, stats):
    def repl(match):
        key, value = match.group("key"), match.group("value")
        if not _key_is_sensitive(key) or _already_redacted(value) or not value:
            return match.group(0)
        if _is_url_with_redacted_credentials(value):
            return match.group(0)
        stats["key-value"] = stats.get("key-value", 0) + 1
        return f'{key}{match.group("sep")}"{_marker("key-value", value)}"'

    return JSON_KV.sub(repl, text)


def _redact_env_kv(text, stats):
    def repl(match):
        key, value = match.group("key"), match.group("value")
        if not _key_is_sensitive(key) or _already_redacted(value) or not value:
            return match.group(0)
        if _is_url_with_redacted_credentials(value):
            return match.group(0)
        stats["key-value"] = stats.get("key-value", 0) + 1
        return f"{key}={_marker('key-value', value)}"

    return ENV_KV.sub(repl, text)


def _redact_yaml_lines(text, stats):
    """
    Redact `key: value` lines, plus every value nested under a `data:` or
    `stringData:` block.

    The block handling matters: in `kubectl get secret -o yaml` the keys are
    arbitrary filenames (`ca.crt`, `.dockerconfigjson`, `app-config`), so no
    key-name heuristic can catch them. Everything under those blocks is a
    secret payload by definition.
    """
    out = []
    secret_block_indent = None

    for line in text.split("\n"):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Leaving the data: block once indentation returns to its level or less.
        if secret_block_indent is not None and stripped and indent <= secret_block_indent:
            secret_block_indent = None

        if re.match(r"^\s*(data|stringData):\s*$", line):
            secret_block_indent = indent
            out.append(line)
            continue

        match = YAML_KV.match(line)
        if match:
            key, value = match.group("key"), match.group("value")
            in_secret_block = secret_block_indent is not None and indent > secret_block_indent
            exempt = _already_redacted(value) or _is_url_with_redacted_credentials(value)
            if (in_secret_block or _key_is_sensitive(key)) and not exempt:
                kind = "secret-data" if in_secret_block else "key-value"
                stats[kind] = stats.get(kind, 0) + 1
                out.append(f"{match.group('indent')}{key}:{match.group('sep')}{_marker(kind, value)}")
                continue

        out.append(line)

    return "\n".join(out)


def redact(text: str):
    """
    Redact secrets in `text`.

    Returns (redacted_text, stats) where stats maps a redaction kind to the
    number of values replaced.
    """
    stats = {}
    text = _redact_standalone(text, stats)
    text = _redact_yaml_lines(text, stats)
    text = _redact_json_kv(text, stats)
    text = _redact_env_kv(text, stats)
    return text, stats


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Redact secrets from cluster output before sharing it with an AI assistant.",
    )
    parser.add_argument(
        "files", nargs="*",
        help="Files to redact in place. Reads stdin and writes stdout when omitted.",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print a redaction summary to stderr.",
    )
    parser.add_argument(
        "--fail-on-secret", action="store_true",
        help="Exit 1 if anything was redacted. For use as a CI or pre-share gate.",
    )
    args = parser.parse_args(argv)

    total = {}

    if not args.files:
        redacted, stats = redact(sys.stdin.read())
        sys.stdout.write(redacted)
        total = stats
    else:
        for name in args.files:
            with open(name, "r", encoding="utf-8", errors="replace") as handle:
                redacted, stats = redact(handle.read())
            with open(name, "w", encoding="utf-8") as handle:
                handle.write(redacted)
            for kind, count in stats.items():
                total[kind] = total.get(kind, 0) + count

    if args.stats or args.fail_on_secret:
        if total:
            summary = ", ".join(f"{kind}={count}" for kind, count in sorted(total.items()))
            print(f"redacted: {summary}", file=sys.stderr)
        else:
            print("redacted: nothing matched", file=sys.stderr)

    if args.fail_on_secret and total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
