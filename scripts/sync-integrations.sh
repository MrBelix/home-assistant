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
