import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

LABEL_PREFIX = "kuma"

# Map of label suffix → monitor field name + type coercion
FIELD_MAP: dict[str, tuple[str, type]] = {
    "name": ("name", str),
    "type": ("type", str),
    "url": ("url", str),
    "interval": ("interval", int),
    "retryInterval": ("retryInterval", int),
    "maxretries": ("maxretries", int),
    "timeout": ("timeout", int),
    "method": ("method", str),
    "body": ("body", str),
    "headers": ("headers", str),
    "keyword": ("keyword", str),
    "hostname": ("hostname", str),
    "port": ("port", int),
    "ignoreTls": ("ignoreTls", bool),
    "maxredirects": ("maxredirects", int),
    "accepted_statuscodes": ("accepted_statuscodes", json.loads),
    "upsideDown": ("upsideDown", bool),
    "description": ("description", str),
    "expectedStatus": ("expectedStatus", int),
    "dns_resolve_type": ("dns_resolve_type", str),
    "dns_resolve_server": ("dns_resolve_server", str),
    "proxyId": ("proxyId", int),
    "authMethod": ("authMethod", str),
    "basic_auth_user": ("basic_auth_user", str),
    "basic_auth_pass": ("basic_auth_pass", str),
    "authDomain": ("authDomain", str),
    "authWorkstation": ("authWorkstation", str),
    "grpcUrl": ("grpcUrl", str),
    "grpcBody": ("grpcBody", str),
    "grpcMetadata": ("grpcMetadata", str),
    "grpcServiceName": ("grpcServiceName", str),
    "grpcMethod": ("grpcMethod", str),
    "grpcProtobuf": ("grpcProtobuf", str),
    "grpcEnableTls": ("grpcEnableTls", bool),
    "mqttTopic": ("mqttTopic", str),
    "mqttUsername": ("mqttUsername", str),
    "mqttPassword": ("mqttPassword", str),
    "mqttSuccessMessage": ("mqttSuccessMessage", str),
    "databaseConnectionString": ("databaseConnectionString", str),
    "databaseQuery": ("databaseQuery", str),
    "radiusUsername": ("radiusUsername", str),
    "radiusPassword": ("radiusPassword", str),
    "radiusSecret": ("radiusSecret", str),
    "radiusCalledStationId": ("radiusCalledStationId", str),
    "radiusCallingStationId": ("radiusCallingStationId", str),
}

# Labels that are handled separately and not passed as fields
RESERVED_LABELS = {
    "enable",
    "group",
    "tags",
    "notification_ids",
}


def _coerce(value: str, target: Any) -> Any:
    if target is bool:
        return value.lower() in ("true", "1", "yes")
    if callable(target) and target not in (str, int, float, bool):
        return target(value)
    return target(value)


def _build_monitor(kuma_labels: dict[str, str], prefix: str) -> Optional[dict]:
    """Build a single monitor config dict from a flat label map.

    kuma_labels keys are already stripped of the prefix (e.g. 'type', 'url').
    Returns None if enable is not truthy.
    """
    if kuma_labels.get("enable", "").lower() not in ("true", "1", "yes"):
        return None

    monitor: dict[str, Any] = {
        "type": "http",
        "active": True,
    }

    for label_key, value in kuma_labels.items():
        if label_key in RESERVED_LABELS:
            continue
        if label_key in FIELD_MAP:
            field_name, coercer = FIELD_MAP[label_key]
            try:
                monitor[field_name] = _coerce(value, coercer)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(
                    "Invalid value for %s.%s = %r: %s",
                    prefix,
                    label_key,
                    value,
                    e,
                )
        else:
            monitor[label_key] = value

    if "group" in kuma_labels:
        monitor["_group"] = kuma_labels["group"]

    if "tags" in kuma_labels:
        monitor["_tags"] = []
        for tag_str in kuma_labels["tags"].split(","):
            tag_str = tag_str.strip()
            if ":" in tag_str:
                tname, tval = tag_str.split(":", 1)
                monitor["_tags"].append(
                    {"name": tname.strip(), "value": tval.strip()}
                )
            else:
                monitor["_tags"].append({"name": tag_str, "value": ""})

    if "notification_ids" in kuma_labels:
        monitor["notificationIDList"] = {
            int(nid.strip()): True
            for nid in kuma_labels["notification_ids"].split(",")
            if nid.strip()
        }

    return monitor


def parse_labels(
    labels: dict[str, str], prefix: str = LABEL_PREFIX
) -> dict[str, dict]:
    """Parse Docker labels into one or more Uptime Kuma monitor config dicts.

    Supports two label schemes:

    1. Flat (single monitor, backwards compatible):
         kuma.enable=true  kuma.type=http  kuma.url=http://...
       Returns {"_default": <monitor>}

    2. Named (multiple monitors per container):
         kuma.http.enable=true  kuma.http.type=http  kuma.http.url=http://...
         kuma.docker.enable=true  kuma.docker.type=docker  ...
       Returns {"http": <monitor>, "docker": <monitor>}

    Named and flat labels must not be mixed on the same container.
    Returns an empty dict if no enabled monitors are found.
    """
    prefix_dot = f"{prefix}."

    # Partition labels: flat (kuma.field) vs named (kuma.<name>.<field>)
    flat: dict[str, str] = {}
    named: dict[str, dict[str, str]] = {}  # monitor_name → {field: value}

    for k, v in labels.items():
        if not k.startswith(prefix_dot):
            continue
        rest = k[len(prefix_dot):]
        if "." in rest:
            monitor_name, field = rest.split(".", 1)
            named.setdefault(monitor_name, {})[field] = v
        else:
            flat[rest] = v

    result: dict[str, dict] = {}

    if named:
        for monitor_name, mon_labels in named.items():
            monitor = _build_monitor(mon_labels, f"{prefix}.{monitor_name}")
            if monitor is not None:
                result[monitor_name] = monitor
    elif flat:
        monitor = _build_monitor(flat, prefix)
        if monitor is not None:
            result["_default"] = monitor

    return result


def build_unique_key(container_id: str, container_name: str, monitor_name: str = "_default") -> str:
    """Build a stable key for tracking managed monitors."""
    base = f"{container_name}_{container_id[:12]}"
    if monitor_name == "_default":
        return base
    return f"{base}_{monitor_name}"
