"""Narrow local MCP bridge for the approved NovelAI Tailscale workflow.

This server intentionally exposes a small fixed surface:

* redacted Tailscale status and Serve status;
* redacted, read-only API status for the ``svc:dokushodo`` definition and
  observed service hosts;
* one confirmation-gated advertisement for ``svc:dokushodo`` to the local
  Caddy listener.

It does not expose arbitrary shell commands, API writes, login, tagging, reset,
Funnel, credentials, hostnames, IP addresses, or raw Tailscale output.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

SERVER_NAME = "novelai-tailscale-mcp"
SERVER_VERSION = "0.2.2"
CONFIRMATION = "AUTHORIZE_SVC_DOKUSHODO_ADVERTISE"
API_BASE_URL = "https://api.tailscale.com/api/v2"
API_TOKEN_ENV = "TAILSCALE_API_TOKEN"
SERVICE_NAME = "svc:dokushodo"
ADVERTISEMENT = [
    "serve",
    f"--service={SERVICE_NAME}",
    "--https=443",
    "--yes",
    "127.0.0.1:8080",
]


TOOLS: list[dict[str, Any]] = [
    {
        "name": "tailscale_status",
        "description": "Return redacted local Tailscale backend, node, tag, and service-host status.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "tailscale_serve_status",
        "description": "Return redacted Tailscale Serve status and whether the dokushodo service is present.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "tailscale_api_service_status",
        "description": (
            "Read-only Tailscale API check for the svc:dokushodo definition and "
            "service-host counts. It distinguishes an explicit empty host list from "
            "an empty or unrecognized response. It never returns addresses, device IDs, "
            "or raw API output."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "tailscale_advertise_dokushodo",
        "description": (
            "Write action: advertise the fixed svc:dokushodo HTTPS endpoint to "
            "local Caddy at 127.0.0.1:8080. Requires exact confirmation and a "
            "tagged/approved Tailscale service host."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "confirmation": {
                    "type": "string",
                    "description": f"Must equal {CONFIRMATION}.",
                }
            },
            "required": ["confirmation"],
            "additionalProperties": False,
        },
    },
]


def _redact(value: str) -> str:
    """Remove URL, DNS, IP, and local-path details from command diagnostics."""

    result = re.sub(r"https?://[^\s]+", "<url>", value, flags=re.IGNORECASE)
    result = re.sub(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", "<dns>", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b", "<ip>", result)
    result = re.sub(r"\b(?:[0-9a-f]{1,4}:){2,}[0-9a-f:]+\b", "<ipv6>", result, flags=re.IGNORECASE)
    result = re.sub(r"(?i)(?:[a-z]:)?\\[^\r\n ]+", "<path>", result)
    return result.strip()


def _classify_failure(stdout: str, stderr: str) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if "tagged nodes" in text or "tag-based" in text:
        return "host_tag_required"
    if "approval" in text or "approve" in text or "pending" in text:
        return "admin_approval_required"
    if "permission" in text or "forbidden" in text or "not authorized" in text:
        return "permission_denied"
    if "not found" in text or "does not exist" in text:
        return "service_or_command_not_found"
    return "command_failed"


def _run_tailscale(arguments: list[str], timeout_seconds: float = 15.0) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("tailscale")
    if executable is None:
        raise RuntimeError("tailscale_cli_unavailable")
    try:
        return subprocess.run(
            [executable, *arguments],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("tailscale_command_timeout") from exc


def _parse_json_command(arguments: list[str]) -> tuple[dict[str, Any] | None, int, str]:
    try:
        result = _run_tailscale(arguments)
    except RuntimeError as exc:
        return None, 1, str(exc)
    if result.returncode != 0:
        return None, result.returncode, _classify_failure(result.stdout, result.stderr)
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, 1, "tailscale_json_unparseable"
    if not isinstance(parsed, dict):
        return None, 1, "tailscale_json_not_an_object"
    return parsed, result.returncode, ""


def _api_get(path: str) -> tuple[dict[str, Any] | None, str | None]:
    token = os.environ.get(API_TOKEN_ENV, "").strip()
    if not token:
        return None, "api_token_not_configured"
    request = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15.0) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        return None, f"api_http_{exc.code}"
    except urllib.error.URLError:
        return None, "api_unreachable"
    except TimeoutError:
        return None, "api_timeout"
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        return None, "api_json_unparseable"
    if not isinstance(payload, dict):
        return None, "api_json_not_an_object"
    return payload, None


def _service_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("vipServices")
    if not isinstance(entries, list):
        entries = payload.get("services")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _is_target_service(entry: dict[str, Any]) -> bool:
    for field in ("name", "displayName"):
        value = entry.get(field)
        if isinstance(value, str) and value.removeprefix("svc:").casefold() == "dokushodo":
            return True
    return False


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "other"


def _payload_shape(payload: dict[str, Any]) -> dict[str, Any]:
    paths: dict[str, str] = {}

    def visit(value: Any, prefix: str, depth: int) -> None:
        if len(paths) >= 64:
            return
        if isinstance(value, dict):
            keys = sorted(key for key in value if isinstance(key, str))
            for key in keys:
                path = f"{prefix}.{key}" if prefix else key
                child = value[key]
                paths[path] = _json_type(child)
                if depth < 2 and isinstance(child, (dict, list)):
                    visit(child, path, depth + 1)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            visit(value[0], f"{prefix}[]", depth)

    visit(payload, "", 0)
    return {
        "service_host_payload_shape": paths,
        "service_host_payload_shape_truncated": len(paths) >= 64,
    }


def _service_host_summary(payload: dict[str, Any]) -> dict[str, Any]:
    hosts = payload.get("hosts")
    if not isinstance(hosts, list):
        hosts = payload.get("devices")
    if not isinstance(hosts, list):
        if not payload:
            return {
                "service_host_observation": "unknown_empty_response",
                "service_host_payload_kind": "empty_object",
                **_payload_shape(payload),
            }
        return {
            "service_host_observation": "unavailable",
            "service_host_payload_kind": "unrecognized_object",
            **_payload_shape(payload),
        }
    host_records = [host for host in hosts if isinstance(host, dict)]
    approved_count = sum(
        host.get("approved") is True or "approved" in str(host.get("approvalLevel", "")).casefold()
        for host in host_records
    )
    ready_count = sum(str(host.get("configured", "")).casefold() in {"ready", "connected"} for host in host_records)
    return {
        "service_host_observation": "available",
        "service_host_payload_kind": "recognized_host_collection",
        "service_host_count": len(host_records),
        "approved_service_host_count": approved_count,
        "ready_service_host_count": ready_count,
        **_payload_shape(payload),
    }


def _api_service_status() -> dict[str, Any]:
    services, service_error = _api_get("/tailnet/-/vip-services")
    if services is None:
        return {"ok": False, "read_only": True, "error": service_error}
    entries = _service_entries(services)
    definition_present = any(_is_target_service(entry) for entry in entries)
    result: dict[str, Any] = {
        "ok": True,
        "read_only": True,
        "api_service_count": len(entries),
        "service_definition_present": definition_present,
        "local_service_advertisement_present": _serve_status().get("dokushodo_service_present"),
    }
    if not definition_present:
        result["service_host_observation"] = "not_applicable"
        return result
    hosts, host_error = _api_get(f"/tailnet/-/services/{SERVICE_NAME}/devices")
    if hosts is None:
        result["service_host_observation"] = "unavailable"
        result["service_host_error"] = host_error
        return result
    result.update(_service_host_summary(hosts))
    return result


def _service_host_capability_present(cap_map: dict[str, Any], *, serve_present: bool = False) -> bool:
    """Recognize the target capability or verified local Serve configuration."""

    service_key = f"services/{SERVICE_NAME.removeprefix('svc:')}"
    return service_key in cap_map or serve_present


def _status() -> dict[str, Any]:
    data, exit_code, error = _parse_json_command(["status", "--json"])
    if data is None:
        return {"ok": False, "exit_code": exit_code, "error": error}
    self_data = data.get("Self")
    if not isinstance(self_data, dict):
        self_data = {}
    cap_map = self_data.get("CapMap")
    if not isinstance(cap_map, dict):
        cap_map = {}
    tags = self_data.get("Tags")
    if not isinstance(tags, list):
        tags = []
    peers = data.get("Peer")
    if not isinstance(peers, dict):
        peers = {}
    serve_status = _serve_status()
    capability_map_present = _service_host_capability_present(cap_map)
    serve_present = serve_status.get("dokushodo_service_present") is True
    capability_observation = (
        "capability_map" if capability_map_present else "serve_configuration" if serve_present else "unavailable"
    )
    return {
        "ok": True,
        "backend_state": data.get("BackendState"),
        "self_online": self_data.get("Online"),
        "self_dns_name_present": bool(self_data.get("DNSName")),
        "tag_count": len(tags),
        "service_host_capability_present": _service_host_capability_present(cap_map, serve_present=serve_present),
        "service_host_capability_observation": capability_observation,
        "peer_count": len(peers),
    }


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _serve_status() -> dict[str, Any]:
    data, exit_code, error = _parse_json_command(["serve", "status", "--json"])
    if data is None:
        return {"ok": False, "exit_code": exit_code, "error": error}
    serialized = json.dumps(data, separators=(",", ":")).lower()
    web = data.get("Web")
    web_count = len(web) if isinstance(web, dict) else 0
    proxy_strings = [item.lower() for item in _walk_strings(data) if "127.0.0.1" in item or "localhost" in item]
    return {
        "ok": True,
        "web_entry_count": web_count,
        "loopback_proxy_present": bool(proxy_strings),
        "caddy_8080_proxy_present": "127.0.0.1:8080" in serialized or "localhost:8080" in serialized,
        "dokushodo_service_present": "svc:dokushodo" in serialized,
    }


def _advertise(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("confirmation") != CONFIRMATION:
        return {"ok": False, "error": "confirmation_required"}
    try:
        result = _run_tailscale(ADVERTISEMENT, timeout_seconds=30.0)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    if result.returncode != 0:
        return {
            "ok": False,
            "exit_code": result.returncode,
            "error": _classify_failure(result.stdout, result.stderr),
            "diagnostic": _redact(f"{result.stdout}\n{result.stderr}"),
        }
    return {"ok": True, "exit_code": result.returncode, "diagnostic": "advertisement_command_succeeded"}


def _tool_result(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
        "isError": is_error,
    }


def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "tailscale_status":
        return _tool_result(_status())
    if name == "tailscale_serve_status":
        return _tool_result(_serve_status())
    if name == "tailscale_api_service_status":
        result = _api_service_status()
        return _tool_result(result, is_error=not bool(result.get("ok")))
    if name == "tailscale_advertise_dokushodo":
        result = _advertise(arguments)
        return _tool_result(result, is_error=not bool(result.get("ok")))
    return _tool_result({"ok": False, "error": "unknown_tool"}, is_error=True)


def _write_message(message: dict[str, Any]) -> None:
    encoded = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, Any] | None:
    first = sys.stdin.buffer.readline()
    if not first:
        return None
    if first.lower().startswith(b"content-length:"):
        length = int(first.split(b":", 1)[1].strip())
        while True:
            header = sys.stdin.buffer.readline()
            if header in (b"\r\n", b"\n", b""):
                break
        payload = sys.stdin.buffer.read(length)
    else:
        payload = first.strip()
    if not payload:
        return None
    parsed = json.loads(payload.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else None


def main() -> None:
    for request in iter(_read_message, None):
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            requested_version = request.get("params", {}).get("protocolVersion")
            protocol_version = requested_version if isinstance(requested_version, str) else "2024-11-05"
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": protocol_version,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                        "instructions": "Only use the fixed dokushodo advertisement after explicit approval; never infer tagging or admin authority.",
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            _write_message({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "tools/list":
            _write_message({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = request.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str) or not isinstance(arguments, dict):
                result = _tool_result({"ok": False, "error": "invalid_tool_arguments"}, is_error=True)
            else:
                result = _dispatch_tool(name, arguments)
            _write_message({"jsonrpc": "2.0", "id": request_id, "result": result})
        elif request_id is not None:
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "method_not_found"},
                }
            )


if __name__ == "__main__":
    main()
