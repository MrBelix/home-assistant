#!/bin/sh
set -eu

mkdir -p /config/custom_components

for component in ecoflow_cloud beszel; do
    source="/opt/ha-integrations/$component"
    target="/config/custom_components/$component"
    staging="/config/custom_components/.$component.staging"

    if [ ! -f "$source/manifest.json" ]; then
        echo "Missing bundled integration: $component" >&2
        exit 1
    fi

    rm -rf "$staging"
    cp -a "$source" "$staging"
    test -f "$staging/manifest.json"

    rm -rf "$target"
    mv "$staging" "$target"

    echo "Synced Home Assistant integration: $component"
done

# Dashboard definition is bundled in the image, not fetched at runtime.
# /config is persistent, so copy the Git-managed version on every restart.
if [ -f /opt/ha-dashboards/homelab.yaml ]; then
    # Generate from the version-controlled template + current HA entity registry.
    # Register it only when configuration.yaml does not already define Lovelace.
    python3 /opt/ha-tools/register-dashboard.py
    echo "Rendered Home Assistant dashboard: Homelab"
fi

# Packages are rendered into the existing /config volume, just like dashboard YAML.
if [ -f /opt/ha-packages/mi_server_power.yaml ]; then
    python3 /opt/ha-tools/register-power-package.py
fi
