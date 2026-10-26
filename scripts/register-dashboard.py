#!/usr/bin/env python3
"""Build Git-managed Homelab dashboard and safely register it in Home Assistant.

Entity ids are discovered from HA's persistent entity registry at container start.
The source dashboard in the image is never edited.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path

import yaml


CONFIG_DIR = Path("/config")
CONFIG_FILE = CONFIG_DIR / "configuration.yaml"
REGISTRY_FILE = CONFIG_DIR / ".storage/core.entity_registry"
DASHBOARD_FILE = CONFIG_DIR / "dashboards/homelab.yaml"

DASHBOARD_CONFIG = """
# Homelab dashboard (Git-managed)
lovelace:
  mode: storage
  dashboards:
    homelab-server:
      mode: yaml
      filename: dashboards/homelab.yaml
      title: Homelab
      icon: mdi:server
      show_in_sidebar: true
"""


def normalized_name(entry: dict) -> str:
    value = entry.get("original_name") or entry.get("name") or entry["entity_id"].split(".", 1)[-1]
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def ecoflow_entities() -> list[dict]:
    if not REGISTRY_FILE.exists():
        return []
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        entries = data.get("data", {}).get("entities", [])
        return [
            entry for entry in entries
            if entry.get("platform") == "ecoflow_cloud"
            and not entry.get("disabled_by")
            and not entry.get("hidden_by")
            and entry.get("entity_id", "").startswith(("sensor.", "switch.", "binary_sensor."))
        ]
    except (OSError, ValueError, TypeError) as exc:
        print(f"Homelab: cannot read EcoFlow entity registry: {exc}")
        return []


def match(entries: list[dict], domain: str, *suffixes: str) -> str | None:
    for suffix in suffixes:
        for entry in entries:
            if not entry["entity_id"].startswith(domain + "."):
                continue
            name = normalized_name(entry)
            if name == suffix or name.endswith(" " + suffix):
                return entry["entity_id"]
    return None


# The Home Assistant YAML dashboard uses native !include for separate views.
# The EcoFlow view is rendered from its own YAML template using actual entity ids.
TEMPLATE_DIR = Path("/opt/ha-dashboards")


def placeholder_entities(entries: list[dict]) -> dict[str, str | None]:
    return {
        "@ecoflow_battery": match(entries, "sensor", "battery level", "main battery level"),
        "@ecoflow_input": match(entries, "sensor", "total in power"),
        "@ecoflow_ac_voltage": match(entries, "sensor", "ac in volts", "ac input voltage"),
        "@ecoflow_output": match(entries, "sensor", "total out power"),
        "@ecoflow_remaining": match(entries, "sensor", "remaining time"),
        "@ecoflow_health": match(entries, "sensor", "state of health"),
        "@ecoflow_ac": match(entries, "switch", "ac enabled"),
        "@ecoflow_dc": match(entries, "switch", "dc 12v enabled", "dc enabled"),
        "@ecoflow_status": match(entries, "sensor", "main status", "status"),
    }


def resolve_entities(node, entities: dict[str, str | None]):
    """Resolve @ecoflow_* placeholders; omit unavailable cards or entity rows."""
    if isinstance(node, list):
        return [
            resolved
            for value in node
            if (resolved := resolve_entities(value, entities)) is not None
        ]
    if isinstance(node, dict):
        obj = dict(node)
        entity = obj.get("entity")
        if isinstance(entity, str) and entity.startswith("@ecoflow_"):
            actual = entities.get(entity)
            if not actual:
                return None
            obj["entity"] = actual

        for key in ("cards", "entities"):
            if key in obj:
                obj[key] = resolve_entities(obj[key], entities)
                if not obj[key]:
                    return None
        return obj
    return node


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".homelab-", dir=path.parent, delete=False
    ) as temporary:
        temporary.write(content)
        temporary_name = temporary.name
    os.chmod(temporary_name, 0o644)
    if path.exists():
        old_stat = path.stat()
        os.chmod(temporary_name, stat.S_IMODE(old_stat.st_mode))
        os.chown(temporary_name, old_stat.st_uid, old_stat.st_gid)
    os.replace(temporary_name, path)


def write_dashboard() -> None:
    # Source control owns YAML; no need to rewrite the server view in Python.
    # Home Assistant resolves these !include directives when reading the dashboard.
    atomic_write(
        DASHBOARD_FILE,
        (TEMPLATE_DIR / "homelab.yaml").read_text(encoding="utf-8"),
    )
    atomic_write(
        CONFIG_DIR / "dashboards/views/server.yaml",
        (TEMPLATE_DIR / "views/server.yaml").read_text(encoding="utf-8"),
    )

    ecoflow_template = yaml.safe_load(
        (TEMPLATE_DIR / "views/ecoflow.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(ecoflow_template, dict) or not isinstance(ecoflow_template.get("cards"), list):
        raise ValueError("Invalid EcoFlow YAML view template")

    entities = placeholder_entities(ecoflow_entities())
    rendered = resolve_entities(ecoflow_template, entities)
    if len(rendered["cards"]) == 1:
        rendered["cards"].append({
            "type": "markdown",
            "content": "Сутності EcoFlow поки не знайдені. Перевір підключення та перезапусти Home Assistant.",
        })
    atomic_write(
        CONFIG_DIR / "dashboards/views/ecoflow.yaml",
        yaml.safe_dump(rendered, allow_unicode=True, sort_keys=False, width=100),
    )
    print(
        "Homelab: views synced; EcoFlow entities:",
        ", ".join(value for value in entities.values() if value) or "(none found)",
    )


def register_dashboard() -> None:
    if not CONFIG_FILE.exists():
        print("Homelab: configuration.yaml not found; dashboard registration skipped.")
        return

    original = CONFIG_FILE.read_text(encoding="utf-8")

    # Avoid corrupting configuration with a duplicate top-level lovelace key.
    if re.search(r"(?m)^lovelace\s*:", original):
        if re.search(r"(?m)^\s{4}homelab-server\s*:", original):
            print("Homelab: dashboard already registered.")
        else:
            print(
                "Homelab: custom lovelace configuration detected; "
                "add homelab-server under lovelace.dashboards manually."
            )
        return

    backup = CONFIG_FILE.with_name("configuration.yaml.before-homelab")
    if not backup.exists():
        shutil.copy2(CONFIG_FILE, backup)

    updated = original.rstrip("\n") + "\n" + DASHBOARD_CONFIG
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".configuration-homelab-",
        dir=CONFIG_FILE.parent, delete=False
    ) as temporary:
        temporary.write(updated)
        temporary_name = temporary.name

    old_stat = CONFIG_FILE.stat()
    os.chmod(temporary_name, stat.S_IMODE(old_stat.st_mode))
    os.chown(temporary_name, old_stat.st_uid, old_stat.st_gid)
    os.replace(temporary_name, CONFIG_FILE)
    print("Homelab: registered YAML dashboard in configuration.yaml.")


if __name__ == "__main__":
    write_dashboard()
    register_dashboard()
