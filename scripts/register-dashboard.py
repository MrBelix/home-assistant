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
TEMPLATE = Path("/opt/ha-dashboards/homelab.yaml")
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


def ecoflow_view(entries: list[dict]) -> dict:
    view: dict = {
        "title": "EcoFlow",
        "path": "power",
        "icon": "mdi:battery-charging",
        "cards": [{
            "type": "markdown",
            "content": "## EcoFlow River 2\\nЖивлення та акумулятор",
        }],
    }

    if not entries:
        view["cards"].append({
            "type": "markdown",
            "content": "Сутності EcoFlow Cloud ще не знайдені. "
                       "Підключи станцію в Home Assistant і перезапусти контейнер, "
                       "щоб оновити цю вкладку.",
        })
        return view

    battery = match(entries, "sensor", "battery level", "main battery level")
    input_power = match(entries, "sensor", "total in power")
    output_power = match(entries, "sensor", "total out power")
    remaining = match(entries, "sensor", "remaining time")
    health = match(entries, "sensor", "state of health")
    ac = match(entries, "switch", "ac enabled")
    dc = match(entries, "switch", "dc 12v enabled", "dc enabled")
    status = match(entries, "sensor", "main status", "status")

    if battery:
        view["cards"].append({
            "type": "gauge",
            "entity": battery,
            "name": "Заряд батареї",
            "min": 0,
            "max": 100,
            "severity": {"red": 0, "yellow": 20, "green": 50},
        })

    primary = [
        (input_power, "Вхідна потужність"),
        (output_power, "Споживання"),
        (remaining, "Автономність"),
        (health, "Стан батареї"),
    ]
    tiles = [{"type": "tile", "entity": entity, "name": name}
             for entity, name in primary if entity]
    if tiles:
        view["cards"].append({"type": "grid", "columns": 2, "square": False, "cards": tiles})

    secondary = [
        {"entity": entity, "name": name}
        for entity, name in [
            (status, "Статус EcoFlow"),
            (ac, "AC вихід"),
            (dc, "DC 12V вихід"),
        ] if entity
    ]
    if secondary:
        view["cards"].append({
            "type": "entities",
            "title": "Керування та стан",
            "show_header_toggle": False,
            "entities": secondary,
        })

    if input_power and output_power:
        view["cards"].append({
            "type": "history-graph",
            "title": "Потужність за 24 години",
            "hours_to_show": 24,
            "entities": [
                {"entity": input_power, "name": "Вхід"},
                {"entity": output_power, "name": "Вихід"},
            ],
        })
    if not (battery or tiles or secondary):
        view["cards"].append({
            "type": "markdown",
            "content": "Сутності EcoFlow є, але назви не розпізнано. "
                       "Перевір їхні entity_id або додай їх вручну.",
        })
    print(
        "Homelab: EcoFlow entities detected:",
        ", ".join(x for x in [battery, input_power, output_power, remaining, health, ac, dc] if x),
    )
    return view


def write_dashboard() -> None:
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("views"), list):
        raise ValueError("Invalid Git-managed dashboard template")
    data["views"].append(ecoflow_view(ecoflow_entities()))
    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    # Atomically replace generated dashboard without changing any user configuration.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".homelab-", dir=DASHBOARD_FILE.parent, delete=False
    ) as temporary:
        temporary.write(output)
        temporary_name = temporary.name
    if DASHBOARD_FILE.exists():
        old_stat = DASHBOARD_FILE.stat()
        os.chmod(temporary_name, stat.S_IMODE(old_stat.st_mode))
        os.chown(temporary_name, old_stat.st_uid, old_stat.st_gid)
    os.replace(temporary_name, DASHBOARD_FILE)
    print("Homelab: dashboard updated from Git and the entity registry.")


def register_dashboard() -> None:
    if not CONFIG_FILE.exists():
        print("Homelab: configuration.yaml not found; dashboard registration skipped.")
        return

    original = CONFIG_FILE.read_text(encoding="utf-8")

    # Avoid corrupting configuration with a duplicate top-level lovelace key.
    if re.search(r"(?m)^lovelace\\s*:", original):
        if re.search(r"(?m)^\\s{4}homelab-server\\s*:", original):
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

    updated = original.rstrip("\\n") + "\\n" + DASHBOARD_CONFIG
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
