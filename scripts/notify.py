#!/usr/bin/env python3
"""
Multi-target webhook alert dispatcher for k8s-ai-troubleshooter.

Supported targets
-----------------
  slack       Slack Incoming Webhook
  pagerduty   PagerDuty Events API v2
  googlechat  Google Chat Incoming Webhook

Usage (library)
---------------
    from notify import build_payload, send_alert

    payload = build_payload(session_entry, report, target="slack")
    send_alert("slack", webhook_url, payload, dry_run=False)

Usage (CLI — via k8s-ai notify)
---------------------------------
    k8s-ai notify --target slack --session-id <uuid> [--dry-run]

Environment variables (URL fallbacks)
--------------------------------------
  K8S_AI_NOTIFY_SLACK_URL
  K8S_AI_NOTIFY_PAGERDUTY_URL
  K8S_AI_NOTIFY_GOOGLECHAT_URL

Each target has a separate URL so you can configure all three and select
the one to use at call time without repeating the URL on every invocation.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

# Map target name → env var for webhook URL
_TARGET_ENV_VARS: Dict[str, str] = {
    "slack": "K8S_AI_NOTIFY_SLACK_URL",
    "pagerduty": "K8S_AI_NOTIFY_PAGERDUTY_URL",
    "googlechat": "K8S_AI_NOTIFY_GOOGLECHAT_URL",
}

SUPPORTED_TARGETS = tuple(_TARGET_ENV_VARS.keys())


# ── Payload builders ───────────────────────────────────────────────────────────

def _slack_payload(session: Dict[str, Any], report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Slack Block Kit message."""
    status = (report or {}).get("status", "UNKNOWN") if report else session.get("status", "UNKNOWN")
    runbook = session.get("runbook") or "—"
    unhealthy = session.get("unhealthy_pods", 0)
    scope = session.get("scope", "—")
    ts = session.get("timestamp", "—")
    sid = session.get("session_id", "—")

    colour = {"CRITICAL": "danger", "ATTENTION": "warning", "DEGRADED": "warning"}.get(
        status, "good"
    )

    hypotheses_text = ""
    if report and report.get("hypotheses"):
        lines = [
            f"• [{h['confidence']}] *{h['title']}*: {h['rationale']}"
            for h in report["hypotheses"][:3]
        ]
        hypotheses_text = "\n".join(lines)

    spikes_text = ""
    if report and report.get("resource_spikes"):
        lines = [
            f"• {s['pod']}/{s['container']} {s['resource'].upper()}: {s['usage_pct']}% ({s['severity']})"
            for s in report["resource_spikes"][:3]
        ]
        spikes_text = "\n".join(lines)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"⚠️ k8s-ai Alert — {status}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                {"type": "mrkdwn", "text": f"*Scope:*\n{scope}"},
                {"type": "mrkdwn", "text": f"*Unhealthy pods:*\n{unhealthy}"},
                {"type": "mrkdwn", "text": f"*Runbook:*\n{runbook}"},
                {"type": "mrkdwn", "text": f"*Session ID:*\n`{sid}`"},
                {"type": "mrkdwn", "text": f"*Timestamp:*\n{ts}"},
            ],
        },
    ]
    if hypotheses_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Hypotheses:*\n{hypotheses_text}"},
        })
    if spikes_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Resource Spikes:*\n{spikes_text}"},
        })
    blocks.append({"type": "divider"})

    return {
        "attachments": [
            {
                "color": colour,
                "blocks": blocks,
            }
        ]
    }


def _pagerduty_payload(session: Dict[str, Any], report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """PagerDuty Events API v2 payload."""
    status = (report or {}).get("status", "UNKNOWN") if report else "UNKNOWN"
    severity_map = {"CRITICAL": "critical", "ATTENTION": "warning", "DEGRADED": "warning"}
    pd_severity = severity_map.get(status, "info")
    sid = session.get("session_id", "k8s-ai-unknown")

    summary_parts = [f"k8s-ai [{status}]"]
    if session.get("scope"):
        summary_parts.append(session["scope"])
    if session.get("unhealthy_pods"):
        summary_parts.append(f"{session['unhealthy_pods']} unhealthy pods")

    custom_details: Dict[str, Any] = {
        "session_id": sid,
        "timestamp": session.get("timestamp"),
        "source": session.get("source"),
        "runbook": session.get("runbook"),
        "confidence": session.get("confidence"),
    }
    if report:
        custom_details["hypotheses"] = [
            {"title": h["title"], "confidence": h["confidence"]}
            for h in (report.get("hypotheses") or [])[:5]
        ]
        custom_details["resource_spikes"] = report.get("resource_spikes", [])

    return {
        "routing_key": "",  # Caller must inject the integration key separately if using PD API v2
        "event_action": "trigger",
        "dedup_key": f"k8s-ai-{sid}",
        "payload": {
            "summary": " · ".join(summary_parts),
            "severity": pd_severity,
            "source": "k8s-ai-troubleshooter",
            "custom_details": custom_details,
        },
    }


def _googlechat_payload(session: Dict[str, Any], report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Google Chat Incoming Webhook payload (Cards v2)."""
    status = (report or {}).get("status", "UNKNOWN") if report else "UNKNOWN"
    runbook = session.get("runbook") or "—"
    unhealthy = session.get("unhealthy_pods", 0)
    scope = session.get("scope", "—")
    ts = session.get("timestamp", "—")

    icon = {"CRITICAL": "🔴", "ATTENTION": "🟡", "DEGRADED": "🟠"}.get(status, "🟢")

    widgets = [
        {"textParagraph": {"text": f"<b>{icon} k8s-ai Alert — {status}</b>"}},
        {"columns": {"columnItems": [
            {"widgets": [
                {"decoratedText": {"topLabel": "Scope", "text": scope}},
                {"decoratedText": {"topLabel": "Runbook", "text": runbook}},
            ]},
            {"widgets": [
                {"decoratedText": {"topLabel": "Unhealthy pods", "text": str(unhealthy)}},
                {"decoratedText": {"topLabel": "Timestamp", "text": ts}},
            ]},
        ]}},
    ]

    if report and report.get("hypotheses"):
        hyp_text = "\n".join(
            f"• [{h['confidence']}] {h['title']}"
            for h in report["hypotheses"][:3]
        )
        widgets.append({"textParagraph": {"text": f"<b>Hypotheses:</b>\n{hyp_text}"}})

    if report and report.get("resource_spikes"):
        spike_text = "\n".join(
            f"• {s['pod']}/{s['container']} {s['resource'].upper()}: {s['usage_pct']}% ({s['severity']})"
            for s in report["resource_spikes"][:3]
        )
        widgets.append({"textParagraph": {"text": f"<b>Resource Spikes:</b>\n{spike_text}"}})

    return {
        "cardsV2": [
            {
                "cardId": f"k8s-ai-alert-{session.get('session_id', 'unknown')}",
                "card": {
                    "header": {
                        "title": "k8s AI Troubleshooter",
                        "subtitle": f"Alert — {status}",
                        "imageUrl": "https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/monitor_heart/default/24px.svg",
                    },
                    "sections": [{"widgets": widgets}],
                },
            }
        ]
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def build_payload(
    session: Dict[str, Any],
    report: Optional[Dict[str, Any]],
    target: str,
) -> Dict[str, Any]:
    """Build a webhook-ready payload dict for the given *target*.

    Parameters
    ----------
    session:
        A session log entry dict (from sessions.jsonl).
    report:
        An optional ``InvestigationReport.to_dict()`` result. Pass ``None``
        when dispatching from the session log without a fresh investigation.
    target:
        One of ``"slack"``, ``"pagerduty"``, ``"googlechat"``.
    """
    target = target.lower()
    builders = {
        "slack": _slack_payload,
        "pagerduty": _pagerduty_payload,
        "googlechat": _googlechat_payload,
    }
    if target not in builders:
        raise ValueError(f"Unsupported target '{target}'. Choose from: {', '.join(SUPPORTED_TARGETS)}")
    return builders[target](session, report)


def resolve_url(target: str, explicit_url: Optional[str] = None) -> Optional[str]:
    """Return the webhook URL: explicit arg > env var. Returns None if neither set."""
    if explicit_url:
        return explicit_url
    env_var = _TARGET_ENV_VARS.get(target.lower())
    return os.environ.get(env_var, "") if env_var else None


def send_alert(
    target: str,
    url: str,
    payload: Dict[str, Any],
    dry_run: bool = False,
) -> bool:
    """POST *payload* as JSON to *url*.

    Returns True on success (or dry_run). Raises ``urllib.error.URLError``
    on network failure.
    """
    if dry_run:
        print(f"[dry-run] Target: {target}")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return True

    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError(f"Invalid webhook URL scheme: {url}")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "k8s-ai-troubleshooter/0.2"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310 # noqa: S310
            return resp.status < 400
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Webhook POST failed: HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Webhook POST network error: {exc.reason}") from exc
