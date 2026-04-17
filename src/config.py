import os


class Config:
    KUMA_URL: str = os.environ.get("KUMA_URL", "http://uptime-kuma:3001")
    KUMA_USERNAME: str = os.environ.get("KUMA_USERNAME", "")
    KUMA_PASSWORD: str = os.environ.get("KUMA_PASSWORD", "")
    SYNC_INTERVAL: int = int(os.environ.get("SYNC_INTERVAL", "30"))
    LABEL_PREFIX: str = os.environ.get("LABEL_PREFIX", "kuma")
    MANAGED_TAG: str = os.environ.get(
        "MANAGED_TAG", "managed-by-label-sync"
    )
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    DOCKER_SOCKET: str = os.environ.get(
        "DOCKER_SOCKET", "unix:///var/run/docker.sock"
    )