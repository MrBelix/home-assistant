#!/usr/bin/env python3
"""Install the Git-managed laptop-power package and enable YAML packages.

Never replace existing Home Assistant settings or overwrite custom packages.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
from pathlib import Path

CONFIG_DIR = Path("/config")
CONFIG_FILE = CONFIG_DIR / "configuration.yaml"
SOURCE = Path("/opt/ha-packages/mi_server_power.yaml")
DESTINATION = CONFIG_DIR / "packages/mi_server_power.yaml"
PACKAGES_LINE = "  packages: !include_dir_named packages\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=".power-package-", delete=False,
    ) as output:
        output.write(content)
        temporary_name = output.name
    os.chmod(temporary_name, 0o644)
    if path.exists():
        previous = path.stat()
        os.chmod(temporary_name, stat.S_IMODE(previous.st_mode))
        os.chown(temporary_name, previous.st_uid, previous.st_gid)
    os.replace(temporary_name, path)


def install_package() -> None:
    atomic_write(DESTINATION, SOURCE.read_text(encoding="utf-8"))
    print("Homelab Power: synced packages/mi_server_power.yaml.")


def register_packages() -> None:
    if not CONFIG_FILE.is_file():
        print("Homelab Power: configuration.yaml missing; registration skipped.")
        return

    original = CONFIG_FILE.read_text(encoding="utf-8")

    # Existing users may have custom packages and a different include path.
    # Never silently replace it with our own include configuration.
    if re.search(r"(?m)^\s{2}packages\s*:", original):
        if re.search(r"(?m)^\s{2}packages\s*:\s*!include_dir_named\s+packages\s*(?:#.*)?$", original):
            print("Homelab Power: packages/ already registered.")
        else:
            print(
                "Homelab Power: custom packages configuration detected; "
                "verify that /config/packages/mi_server_power.yaml is loaded."
            )
        return

    # For ordinary block-style homeassistant: insert a nested package include.
    # For inline / !include root settings, require manual action instead.
    match = re.search(r"(?m)^homeassistant:[ \t]*(?:#.*)?$", original)
    if match:
        updated = original[: match.end()] + "\n" + PACKAGES_LINE + original[match.end():]
    elif re.search(r"(?m)^homeassistant\s*:", original):
        print(
            "Homelab Power: nonstandard homeassistant: mapping found; "
            "add 'packages: !include_dir_named packages' manually under homeassistant."
        )
        return
    else:
        updated = original.rstrip("\n") + "\n\nhomeassistant:\n" + PACKAGES_LINE

    backup = CONFIG_FILE.with_name("configuration.yaml.before-power-monitor")
    if not backup.exists():
        shutil.copy2(CONFIG_FILE, backup)
    atomic_write(CONFIG_FILE, updated)
    print("Homelab Power: enabled homeassistant.packages from /config/packages/.")


if __name__ == "__main__":
    install_package()
    register_packages()
