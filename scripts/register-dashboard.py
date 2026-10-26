#!/usr/bin/env python3
"""Register the Git-managed Homelab dashboard without clobbering user config."""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
from pathlib import Path


CONFIG_FILE = Path("/config/configuration.yaml")

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


def main() -> None:
    if not CONFIG_FILE.is_file():
        print(
            "Homelab: /config/configuration.yaml not found; "
            "dashboard YAML copied, but registration skipped."
        )
        return

    original = CONFIG_FILE.read_text(encoding="utf-8")

    # If users already customize Lovelace, preserve their settings.
    # A second top-level 'lovelace:' key would be invalid YAML.
    if re.search(r"(?m)^lovelace\s*:", original):
        if re.search(r"(?m)^\s{4}homelab-server\s*:", original):
            print("Homelab: dashboard is already registered.")
        else:
            print(
                "Homelab: existing lovelace: configuration found. "
                "Not modifying it. Add the homelab-server entry manually "
                "under lovelace.dashboards; see README."
            )
        return

    # One-time backup of the original HA configuration.
    backup = CONFIG_FILE.with_name("configuration.yaml.before-homelab")
    if not backup.exists():
        shutil.copy2(CONFIG_FILE, backup)

    updated = original.rstrip("\n") + "\n" + DASHBOARD_CONFIG
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=".configuration-homelab-",
        dir=CONFIG_FILE.parent,
        delete=False,
    ) as temporary:
        temporary.write(updated)
        temp_name = temporary.name

    original_stat = CONFIG_FILE.stat()
    os.chmod(temp_name, stat.S_IMODE(original_stat.st_mode))
    os.chown(temp_name, original_stat.st_uid, original_stat.st_gid)
    os.replace(temp_name, CONFIG_FILE)
    print("Homelab: registered YAML dashboard in configuration.yaml.")


if __name__ == "__main__":
    main()
