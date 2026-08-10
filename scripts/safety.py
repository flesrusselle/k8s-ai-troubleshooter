#!/usr/bin/env python3
"""
Command safety classification for k8s-ai-troubleshooter.

Classifies a `kubectl` or `helm` command string into one of the repository's
four safety tiers. `commands/*.yaml` remains the human-facing source of truth;
`tests/test_safety.py` asserts that this module agrees with every catalogued
entry, so the two cannot drift.

Design rules, in order of importance:

1. **Parse, never substring-match.** Classification is driven by the argv verb
   path (`kubectl rollout restart`), not by searching the raw string. Substring
   matching both under-classifies (`"delete pod --force"` is never a contiguous
   substring of `kubectl delete pod web-1 -n prod --force`) and over-classifies
   (`kubectl logs deployment/scale-worker` contains `"scale"`).

2. **Fail closed.** Anything not positively recognised as read-only is
   `HUMAN_APPROVAL_REQUIRED`. Unknown verbs, unknown binaries and unparseable
   input all land there rather than in a SAFE tier.

3. **Every deletion is DESTRUCTIVE.** Classifying the `delete` verb itself,
   rather than enumerating resource spellings, is what makes `delete ns`,
   `delete namespace` and `delete persistentvolumeclaim` behave identically.

4. **The most severe segment wins.** Shell-chained commands are split and each
   segment classified, so `kubectl get pods && kubectl delete ns prod` cannot
   pass as a read.

5. **`--dry-run` never downgrades.** `--dry-run=none` is a valid value that
   executes for real, so treating the flag as a safety signal would be a
   bypass. Server-side dry-run also still invokes admission control.
"""

import shlex
from dataclasses import dataclass
from pathlib import Path

SAFE_READ = "SAFE_READ"
SAFE_DIAGNOSTIC = "SAFE_DIAGNOSTIC"
HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
DESTRUCTIVE = "DESTRUCTIVE"

#: Ascending severity. Used to pick the winner across chained segments.
SEVERITY_ORDER = [SAFE_READ, SAFE_DIAGNOSTIC, HUMAN_APPROVAL_REQUIRED, DESTRUCTIVE]

SHELL_OPERATORS = {"&&", "||", "|", ";", "&", "\n"}

# Tokens that may legitimately precede the real binary.
WRAPPER_TOKENS = {"sudo", "env", "command", "nohup", "time"}

#: Global flags that consume the following token as their value. These must be
#: skipped when locating the verb, or `kubectl --namespace prod delete pod web-1`
#: mistakes "prod" for the verb. A superset is safe: over-consuming can only
#: hide the verb, which fails closed. Flags written as `--flag=value` are
#: self-contained and need no entry here.
VALUE_TAKING_FLAGS = {
    # kubectl
    "-n", "--namespace", "--context", "--cluster", "--user", "--kubeconfig",
    "-s", "--server", "--token", "--as", "--as-group", "--as-uid",
    "--request-timeout", "--cache-dir", "--certificate-authority",
    "--client-certificate", "--client-key", "--tls-server-name",
    "--username", "--password", "-v", "--v", "--log-file", "--profile",
    "--profile-output",
    # helm
    "--kube-context", "--kube-apiserver", "--kube-token", "--kube-as-user",
    "--kube-as-group", "--kube-ca-file", "--kube-tls-server-name",
    "--registry-config", "--repository-cache", "--repository-config",
    "--burst-limit", "--qps",
}

# --- kubectl -------------------------------------------------------------

KUBECTL_READ_VERBS = {
    "get", "describe", "logs", "events", "cluster-info",
    "api-resources", "api-versions", "version", "wait",
}

KUBECTL_DIAGNOSTIC_VERBS = {"top", "explain", "diff", "kustomize"}

#: Two-token verb paths, needed wherever a subcommand flips the tier —
#: `rollout status` reads, `rollout restart` mutates.
KUBECTL_READ_SUBCOMMANDS = {
    ("config", "view"),
    ("config", "current-context"),
    ("config", "get-contexts"),
    ("config", "get-clusters"),
    ("config", "get-users"),
    ("auth", "can-i"),
    ("auth", "whoami"),
    ("rollout", "status"),
    ("rollout", "history"),
}

KUBECTL_DESTRUCTIVE_VERBS = {
    "delete",   # any deletion, regardless of resource spelling
    "drain",    # forcibly evicts every workload off a node
}

# --- helm ----------------------------------------------------------------

HELM_READ_VERBS = {
    "list", "ls", "status", "history", "get", "show", "inspect",
    "search", "version", "env",
}

HELM_DIAGNOSTIC_VERBS = {"template", "lint", "diff", "verify"}

HELM_READ_SUBCOMMANDS = {
    ("repo", "list"),
    ("plugin", "list"),
    ("dependency", "list"),
}

HELM_DESTRUCTIVE_VERBS = {"uninstall", "delete", "purge"}


@dataclass(frozen=True)
class Classification:
    """A safety verdict plus the reason it was reached."""

    safety: str
    reason: str


def _max_severity(classifications):
    """Return the most severe classification in the sequence."""
    return max(classifications, key=lambda c: SEVERITY_ORDER.index(c.safety))


def _tokenize(command):
    """
    Tokenize a command string, keeping shell operators as standalone tokens.

    Returns None if the string cannot be lexed (e.g. unbalanced quotes), which
    callers treat as a fail-closed condition.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _split_segments(tokens):
    """Split a token list on shell operators into individual command segments."""
    segments, current = [], []
    for token in tokens:
        if token in SHELL_OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _strip_wrappers(tokens):
    """Drop leading `VAR=value` assignments and wrapper binaries like `sudo`."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in WRAPPER_TOKENS or ("=" in token and not token.startswith("-")
                                       and token.split("=")[0].isidentifier()):
            index += 1
            continue
        break
    return tokens[index:]


def _flags(args):
    """Return the set of flag names in `args`, with any `=value` suffix removed."""
    return {arg.split("=")[0] for arg in args if arg.startswith("-")}


def _positionals(args):
    """
    Return non-flag arguments, which is where verbs and subcommands live.

    Values belonging to global flags are skipped so that they are never mistaken
    for the verb.
    """
    words = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("-"):
            skip_next = arg in VALUE_TAKING_FLAGS
            continue
        words.append(arg)
    return words


def _classify_kubectl(args):
    words = _positionals(args)
    flags = _flags(args)

    if not words:
        return Classification(HUMAN_APPROVAL_REQUIRED, "kubectl with no verb")

    verb = words[0]
    pair = (verb, words[1]) if len(words) > 1 else None

    if verb in KUBECTL_DESTRUCTIVE_VERBS:
        return Classification(DESTRUCTIVE, f"kubectl {verb} removes resources")

    # Flag-driven escalation: these turn an otherwise-mutating verb into a
    # deletion. `apply --prune` removes resources absent from the manifest;
    # `replace --force` deletes and recreates the object.
    if verb == "apply" and "--prune" in flags:
        return Classification(DESTRUCTIVE, "kubectl apply --prune deletes resources")
    if verb == "replace" and "--force" in flags:
        return Classification(DESTRUCTIVE, "kubectl replace --force deletes and recreates")

    if pair in KUBECTL_READ_SUBCOMMANDS:
        return Classification(SAFE_READ, f"kubectl {pair[0]} {pair[1]} is read-only")

    # A known two-token verb whose subcommand is not on the read list (e.g.
    # `rollout restart`, `config set-context`) mutates something.
    if verb in {"rollout", "config", "auth", "certificate"}:
        subcommand = words[1] if len(words) > 1 else "<none>"
        return Classification(
            HUMAN_APPROVAL_REQUIRED,
            f"kubectl {verb} {subcommand} is not a recognised read-only subcommand",
        )

    if verb in KUBECTL_READ_VERBS:
        return Classification(SAFE_READ, f"kubectl {verb} is read-only")

    if verb in KUBECTL_DIAGNOSTIC_VERBS:
        return Classification(SAFE_DIAGNOSTIC, f"kubectl {verb} is a non-mutating diagnostic")

    return Classification(
        HUMAN_APPROVAL_REQUIRED,
        f"kubectl {verb} is not a recognised read-only verb",
    )


def _classify_helm(args):
    words = _positionals(args)

    if not words:
        return Classification(HUMAN_APPROVAL_REQUIRED, "helm with no verb")

    verb = words[0]
    pair = (verb, words[1]) if len(words) > 1 else None

    if verb in HELM_DESTRUCTIVE_VERBS:
        return Classification(DESTRUCTIVE, f"helm {verb} removes a release")

    if pair in HELM_READ_SUBCOMMANDS:
        return Classification(SAFE_READ, f"helm {pair[0]} {pair[1]} is read-only")

    if verb in {"repo", "plugin", "dependency", "registry"}:
        subcommand = words[1] if len(words) > 1 else "<none>"
        return Classification(
            HUMAN_APPROVAL_REQUIRED,
            f"helm {verb} {subcommand} is not a recognised read-only subcommand",
        )

    if verb in HELM_READ_VERBS:
        return Classification(SAFE_READ, f"helm {verb} is read-only")

    if verb in HELM_DIAGNOSTIC_VERBS:
        return Classification(SAFE_DIAGNOSTIC, f"helm {verb} renders locally without mutating")

    return Classification(
        HUMAN_APPROVAL_REQUIRED,
        f"helm {verb} is not a recognised read-only verb",
    )


def _classify_segment(tokens):
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return Classification(HUMAN_APPROVAL_REQUIRED, "empty command segment")

    binary = Path(tokens[0]).name  # tolerate /usr/local/bin/kubectl
    args = tokens[1:]

    if binary == "kubectl":
        return _classify_kubectl(args)
    if binary == "helm":
        return _classify_helm(args)

    return Classification(
        HUMAN_APPROVAL_REQUIRED,
        f"{binary!r} is not a recognised read-only tool",
    )


def classify(command):
    """
    Classify a command string and explain the verdict.

    Chained commands are split on shell operators and the most severe segment
    determines the result.
    """
    if command is None or not command.strip():
        return Classification(HUMAN_APPROVAL_REQUIRED, "empty command")

    # Command substitution cannot be analysed statically, so refuse to call it
    # safe no matter what the visible verb is.
    if "$(" in command or "`" in command:
        return Classification(
            HUMAN_APPROVAL_REQUIRED,
            "command substitution cannot be statically classified",
        )

    tokens = _tokenize(command)
    if tokens is None:
        return Classification(HUMAN_APPROVAL_REQUIRED, "command could not be parsed")

    segments = _split_segments(tokens)
    if not segments:
        return Classification(HUMAN_APPROVAL_REQUIRED, "no command segments found")

    return _max_severity([_classify_segment(segment) for segment in segments])


def classify_command_safety(command):
    """Return only the safety tier. Kept for callers that want a bare string."""
    return classify(command).safety


def main():
    import sys

    if len(sys.argv) < 2:
        print("usage: safety.py '<command>' [...]", file=sys.stderr)
        return 2

    exit_code = 0
    for command in sys.argv[1:]:
        result = classify(command)
        print(f"{result.safety:<24} {command}\n{'':<24} ↳ {result.reason}")
        if result.safety in (HUMAN_APPROVAL_REQUIRED, DESTRUCTIVE):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
