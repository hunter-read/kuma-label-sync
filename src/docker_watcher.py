import logging
from typing import Any

import docker

from .config import Config
from .monitor_builder import parse_labels, build_unique_key

logger = logging.getLogger(__name__)


class DockerWatcher:
    def __init__(self, config: Config):
        self.config = config
        self.client = docker.DockerClient(
            base_url=config.DOCKER_SOCKET
        )

    def get_desired_monitors(self) -> dict[str, dict[str, Any]]:
        """Scan all running containers and return desired monitor configs.

        Returns {unique_key: monitor_config}
        """
        desired: dict[str, dict] = {}

        try:
            containers = self.client.containers.list(
                filters={"status": "running"}
            )
        except Exception:
            logger.exception("Failed to list Docker containers")
            return desired

        for container in containers:
            labels = container.labels or {}
            monitor = parse_labels(labels, self.config.LABEL_PREFIX)
            if monitor is None:
                continue

            name = container.name or container.short_id
            key = build_unique_key(container.id, name)

            # Default name to container name if not set
            if "name" not in monitor:
                monitor["name"] = name

            monitor["_container_key"] = key
            desired[key] = monitor
            logger.debug("Found labeled container: %s → %s", name, key)

        logger.info("Discovered %d labeled containers", len(desired))
        return desired

    def listen_events(self, callback):
        """Listen for container start/stop events and invoke callback."""
        logger.info("Listening for Docker events…")
        events = self.client.events(
            decode=True,
            filters={
                "type": "container",
                "event": ["start", "stop", "die", "destroy"],
            },
        )
        for event in events:
            action = event.get("Action", "")
            actor = event.get("Actor", {})
            container_id = actor.get("ID", "")[:12]
            logger.info("Docker event: %s on %s", action, container_id)
            try:
                callback()
            except Exception:
                logger.exception("Error handling Docker event")