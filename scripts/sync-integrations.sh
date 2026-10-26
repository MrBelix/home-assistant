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
    mkdir -p /config/dashboards
    cp /opt/ha-dashboards/homelab.yaml /config/dashboards/.homelab.yaml.tmp
    mv -f /config/dashboards/.homelab.yaml.tmp /config/dashboards/homelab.yaml

    # Register it only when configuration.yaml does not already define Lovelace.
    python3 /opt/ha-tools/register-dashboard.py
    echo "Synced Home Assistant dashboard: Homelab"
fi
