import hashlib
import uuid

from src.config import get_config, save_config
from src.logger import get_logger

logger = get_logger("auth")


def generate_machine_id() -> str:
    """Generate a unique machine fingerprint from MAC address + hostname."""
    fingerprints = []

    # MAC address
    try:
        mac = uuid.getnode()
        if mac != 0:
            fingerprints.append(format(mac, "x"))
    except Exception:
        pass

    # Hostname as secondary factor
    try:
        import socket
        fingerprints.append(socket.gethostname())
    except Exception:
        pass

    raw = "|".join(fingerprints)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_auth_headers() -> dict:
    """Return headers with X-Api-Key for CMS proxy calls."""
    api_key = get_config("api_key")
    if not api_key:
        return {}
    return {"X-Api-Key": api_key}


def _register_with_cms(machine_id: str) -> dict | None:
    """Call CMS /api/register to create a new user. Returns user info dict or None."""
    from src.http_client import sync_post

    cms_url = get_config("cms_base_url")
    try:
        resp = sync_post(
            f"{cms_url}/api/register",
            json={"machine_id": machine_id},
            headers={},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data")
        else:
            logger.error("CMS registration failed (HTTP %s): %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Cannot reach CMS at %s: %s", cms_url, e)
        return None


def get_or_register() -> bool:
    """Ensure the user has valid credentials. Returns True if ready.

    On first launch: generate machine_id, call CMS /api/register,
    persist user_id/api_key to config.enc.
    On subsequent launches: verify credentials exist.
    """
    api_key = get_config("api_key")
    user_id = get_config("user_id")

    if api_key and user_id:
        return True

    # First launch — register with CMS
    machine_id = generate_machine_id()
    logger.info("First launch detected. Machine ID: %s", machine_id)

    result = _register_with_cms(machine_id)
    if not result:
        logger.warning("CMS registration failed. Running in offline mode.")
        # Save machine_id anyway so we don't re-register as a different user
        save_config({"user_id": machine_id, "api_key": ""})
        return False

    api_key = result.get("api_key", "")

    save_config({
        "user_id": result.get("user_id", machine_id),
        "api_key": api_key,
    })

    logger.info("Registered with CMS. API key: %s...", api_key[:12])
    return True


def update_local_quota(remaining: float):
    """No-op: quota tracking removed (unused)."""
    pass
