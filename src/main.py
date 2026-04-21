import logging
import sys
import threading
import time

from .config import Config
from .docker_watcher import DockerWatcher
from .kuma_client import KumaClient

config = Config()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("label-sync")


def sync(
    watcher: DockerWatcher,
    kuma: KumaClient,
    managed_tag_name: str,
) -> None:
    logger.info("Starting sync…")

    managed_tag = kuma.find_or_create_tag(managed_tag_name)
    managed_tag_id = managed_tag["id"]

    desired = watcher.get_desired_monitors()
    existing = kuma.get_managed_monitors(managed_tag_name)

    desired_keys = set(desired.keys())
    existing_keys = set(existing.keys())

    group_cache: dict[str, int] = {}

    def resolve_group(name: str) -> int:
        if name not in group_cache:
            group_cache[name] = kuma.find_or_create_group(name)
        return group_cache[name]

    for key in desired_keys - existing_keys:
        monitor_cfg = desired[key].copy()
        group_name = monitor_cfg.pop("_group", None)
        extra_tags = monitor_cfg.pop("_tags", [])
        container_key = monitor_cfg.pop("_container_key", key)

        if group_name:
            monitor_cfg["parent"] = resolve_group(group_name)

        monitor_cfg.pop("tags", None)

        try:
            result = kuma.add_monitor(monitor_cfg)
            monitor_id = result.get("monitorID")
            if monitor_id:
                kuma.add_monitor_tag(
                    monitor_id, managed_tag_id, container_key
                )
                for t in extra_tags:
                    tag_obj = kuma.find_or_create_tag(t["name"])
                    kuma.add_monitor_tag(
                        monitor_id, tag_obj["id"], t.get("value", "")
                    )
        except Exception:
            logger.exception("Failed to create monitor for %s", key)

    for key in desired_keys & existing_keys:
        monitor_cfg = desired[key].copy()
        group_name = monitor_cfg.pop("_group", None)
        extra_tags = monitor_cfg.pop("_tags", [])
        monitor_cfg.pop("_container_key", None)
        monitor_cfg.pop("tags", None)

        existing_monitor = existing[key]
        monitor_id = existing_monitor["id"]

        if group_name:
            monitor_cfg["parent"] = resolve_group(group_name)

        changed_field = None
        for field, new_val in monitor_cfg.items():
            if field.startswith("_"):
                continue
            old_val = existing_monitor.get(field)
            if old_val != new_val:
                changed_field = field
                logger.debug(
                    "Monitor %d %r: %r → %r",
                    monitor_id, field, old_val, new_val,
                )
                break

        if changed_field:
            try:
                kuma.edit_monitor(monitor_id, monitor_cfg)
            except Exception:
                logger.exception(
                    "Failed to update monitor %d", monitor_id
                )

    for key in existing_keys - desired_keys:
        monitor = existing[key]
        try:
            kuma.delete_monitor(monitor["id"])
        except Exception:
            logger.exception(
                "Failed to delete monitor %d", monitor["id"]
            )

    logger.info(
        "Sync complete: %d created, %d checked, %d removed",
        len(desired_keys - existing_keys),
        len(desired_keys & existing_keys),
        len(existing_keys - desired_keys),
    )


def main() -> None:
    logger.info("Uptime Kuma Label Sync starting…")
    logger.info("Kuma URL: %s", config.KUMA_URL)
    logger.info("Sync interval: %ds", config.SYNC_INTERVAL)
    logger.info("Label prefix: %s", config.LABEL_PREFIX)

    if not config.KUMA_USERNAME or not config.KUMA_PASSWORD:
        logger.error("KUMA_USERNAME and KUMA_PASSWORD are required")
        sys.exit(1)

    kuma = KumaClient(
        base_url=config.KUMA_URL,
        username=config.KUMA_USERNAME,
        password=config.KUMA_PASSWORD,
    )

    watcher = DockerWatcher(config)

    kuma.wait_ready()
    sync(watcher, kuma, config.MANAGED_TAG)

    _debounce_timer: threading.Timer | None = None
    _debounce_lock = threading.Lock()

    def on_event():
        nonlocal _debounce_timer
        with _debounce_lock:
            if _debounce_timer is not None:
                _debounce_timer.cancel()
            _debounce_timer = threading.Timer(
                5.0, sync, args=(watcher, kuma, config.MANAGED_TAG)
            )
            _debounce_timer.daemon = True
            _debounce_timer.start()

    event_thread = threading.Thread(
        target=watcher.listen_events,
        args=(on_event,),
        daemon=True,
    )
    event_thread.start()

    while True:
        time.sleep(config.SYNC_INTERVAL)
        try:
            sync(watcher, kuma, config.MANAGED_TAG)
        except Exception:
            logger.exception("Periodic sync failed")


if __name__ == "__main__":
    main()