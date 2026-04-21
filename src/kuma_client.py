import logging
import time
from typing import Optional

from uptime_kuma_api import UptimeKumaApi, MonitorType
from uptime_kuma_api import UptimeKumaException

logger = logging.getLogger(__name__)

_STRIP_FIELDS = {"active", "_group", "_tags", "_container_key", "tags"}


class KumaClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.api: Optional[UptimeKumaApi] = None

    def _connect(self) -> None:
        if self.api is not None:
            try:
                self.api.disconnect()
            except Exception:
                pass

        self.api = UptimeKumaApi(self.base_url)
        self.api.login(self.username, self.password)
        logger.info("Connected to Uptime Kuma via Socket.IO")

    def _ensure_connected(self) -> None:
        if self.api is None:
            self._connect()

    def _call(self, fn, *args, **kwargs):
        self._ensure_connected()
        try:
            return fn(*args, **kwargs)
        except UptimeKumaException as e:
            if "not logged in" in str(e).lower():
                logger.warning("Session expired, reconnecting…")
                self._connect()
                return fn(*args, **kwargs)
            raise

    def wait_ready(self, timeout: int = 120) -> None:
        start = time.time()
        while time.time() - start < timeout:
            try:
                self._connect()
                return
            except Exception as e:
                logger.info("Waiting for Uptime Kuma… (%s)", e)
                time.sleep(3)
        raise TimeoutError("Uptime Kuma did not become ready in time")

    def reconnect(self) -> None:
        logger.info("Reconnecting to Uptime Kuma…")
        self._connect()

    # ── Monitors ──────────────────────────────────────────────

    def get_monitors(self) -> list[dict]:
        self._ensure_connected()
        return self.api.get_monitors()

    def add_monitor(self, monitor: dict) -> dict:
        self._ensure_connected()
        mon_type = monitor.pop("type", "http")
        monitor["type"] = self._resolve_type(mon_type)

        for field in _STRIP_FIELDS:
            monitor.pop(field, None)

        logger.info("Creating monitor: %s", monitor.get("name"))
        result = self.api.add_monitor(**monitor)
        logger.info("Created monitor ID: %s", result.get("monitorID"))
        return result

    def edit_monitor(self, monitor_id: int, monitor: dict) -> dict:
        self._ensure_connected()
        if "type" in monitor:
            monitor["type"] = self._resolve_type(monitor["type"])

        for field in _STRIP_FIELDS:
            monitor.pop(field, None)

        logger.info(
            "Updating monitor %d: %s", monitor_id, monitor.get("name")
        )
        return self.api.edit_monitor(monitor_id, **monitor)

    def delete_monitor(self, monitor_id: int) -> dict:
        self._ensure_connected()
        logger.info("Deleting monitor %d", monitor_id)
        return self.api.delete_monitor(monitor_id)

    # ── Tags ─────────────────────────────────────────────────

    def get_tags(self) -> list[dict]:
        self._ensure_connected()
        return self.api.get_tags()

    def add_tag(self, name: str, color: str = "#4CAF50") -> dict:
        self._ensure_connected()
        return self.api.add_tag(name=name, color=color)

    def find_or_create_tag(self, name: str) -> dict:
        tags = self.get_tags()
        for t in tags:
            if t.get("name") == name:
                return t
        return self.add_tag(name)

    def add_monitor_tag(
        self, monitor_id: int, tag_id: int, value: str = ""
    ) -> None:
        self._ensure_connected()
        self.api.add_monitor_tag(
            tag_id=tag_id, monitor_id=monitor_id, value=value
        )

    # ── Groups ───────────────────────────────────────────────

    def get_monitor_groups(self) -> dict[str, int]:
        monitors = self.get_monitors()
        return {
            m["name"]: m["id"]
            for m in monitors
            if m.get("type") == MonitorType.GROUP
        }

    def find_or_create_group(self, group_name: str) -> int:
        groups = self.get_monitor_groups()
        if group_name in groups:
            return groups[group_name]
        result = self.api.add_monitor(
            type=MonitorType.GROUP, name=group_name
        )
        return result.get("monitorID")

    # ── Managed monitors ─────────────────────────────────────

    def get_managed_monitors(self, managed_tag: str) -> dict[str, dict]:
        tag = None
        for t in self.get_tags():
            if t.get("name") == managed_tag:
                tag = t
                break
        if not tag:
            return {}

        tag_id = tag["id"]
        monitors = self.get_monitors()
        managed = {}
        for m in monitors:
            for mt in m.get("tags", []):
                if mt.get("tag_id") == tag_id:
                    value = mt.get("value", m.get("name", ""))
                    managed[value] = m
        return managed

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _resolve_type(type_str) -> MonitorType:
        if isinstance(type_str, MonitorType):
            return type_str
        type_map = {
            "http": MonitorType.HTTP,
            "tcp": MonitorType.PORT,
            "port": MonitorType.PORT,
            "ping": MonitorType.PING,
            "keyword": MonitorType.KEYWORD,
            "dns": MonitorType.DNS,
            "docker": MonitorType.DOCKER,
            "push": MonitorType.PUSH,
            "steam": MonitorType.STEAM,
            "mqtt": MonitorType.MQTT,
            "grpc-keyword": MonitorType.GRPC_KEYWORD,
            "sqlserver": MonitorType.SQLSERVER,
            "postgres": MonitorType.POSTGRES,
            "mysql": MonitorType.MYSQL,
            "mongodb": MonitorType.MONGODB,
            "radius": MonitorType.RADIUS,
            "redis": MonitorType.REDIS,
            "group": MonitorType.GROUP,
            "json-query": MonitorType.JSON_QUERY,
            "real-browser": MonitorType.REAL_BROWSER,
        }
        resolved = type_map.get(type_str.lower())
        if resolved is None:
            logger.warning(
                "Unknown monitor type '%s', defaulting to HTTP",
                type_str,
            )
            return MonitorType.HTTP
        return resolved