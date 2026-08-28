from __future__ import annotations

from tools.mcp.tailscale_mcp import _service_host_capability_present, _service_host_summary


def test_service_specific_capability_proves_target_service_host() -> None:
    assert _service_host_capability_present({"services/dokushodo": []}) is True


def test_legacy_generic_capability_does_not_prove_target_service_host() -> None:
    assert _service_host_capability_present({"service-host": []}) is False


def test_unrelated_service_capability_does_not_prove_target_service_host() -> None:
    assert _service_host_capability_present({"services/other": []}) is False


def test_verified_target_serve_configuration_proves_local_service_host() -> None:
    assert _service_host_capability_present({}, serve_present=True) is True


def test_missing_capability_and_serve_configuration_is_unavailable() -> None:
    assert _service_host_capability_present({}) is False


def test_empty_service_host_response_remains_unknown() -> None:
    result = _service_host_summary({})

    assert result["service_host_observation"] == "unknown_empty_response"
    assert result["service_host_payload_kind"] == "empty_object"
    assert result["service_host_payload_shape"] == {}
    assert result["service_host_payload_shape_truncated"] is False


def test_explicit_empty_host_collection_proves_zero_observed_hosts() -> None:
    result = _service_host_summary({"hosts": []})

    assert result["service_host_observation"] == "available"
    assert result["service_host_payload_kind"] == "recognized_host_collection"
    assert result["service_host_count"] == 0
    assert result["approved_service_host_count"] == 0
    assert result["ready_service_host_count"] == 0


def test_unrecognized_nonempty_response_is_not_interpreted_as_host_data() -> None:
    result = _service_host_summary({"status": "pending"})

    assert result["service_host_observation"] == "unavailable"
    assert result["service_host_payload_kind"] == "unrecognized_object"
    assert result["service_host_payload_shape"] == {"status": "string"}
