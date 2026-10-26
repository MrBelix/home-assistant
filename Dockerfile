# Integration sources are resolved during build, never at container start.
# This ARG must be global because it is referenced in a FROM instruction.
ARG HOME_ASSISTANT_IMAGE=ghcr.io/home-assistant/home-assistant:stable

FROM alpine:3.22 AS integration_sources

RUN apk add --no-cache ca-certificates curl tar

# EcoFlow Cloud v1.7.2
ARG ECOFLOW_COMMIT=de02d680cdfe1adcec60c43047ff3ed3da15e0ee
# Beszel-HASS v1.2.1
ARG BESZEL_COMMIT=afbcf1c5b18beaf1ec4a383776f8f59ed3ae7f08

RUN set -eux; \
    mkdir -p /src/ecoflow /src/beszel; \
    curl --fail --location --silent --show-error --retry 3 \
      "https://codeload.github.com/tolwi/hassio-ecoflow-cloud/tar.gz/${ECOFLOW_COMMIT}" \
      | tar -xz -C /src/ecoflow --strip-components=1; \
    curl --fail --location --silent --show-error --retry 3 \
      "https://codeload.github.com/cgfm/Beszel-HASS/tar.gz/${BESZEL_COMMIT}" \
      | tar -xz -C /src/beszel --strip-components=1; \
    test -f /src/ecoflow/custom_components/ecoflow_cloud/manifest.json; \
    test -f /src/beszel/custom_components/beszel/manifest.json

FROM ${HOME_ASSISTANT_IMAGE}

COPY --from=integration_sources /src/ecoflow/custom_components/ecoflow_cloud/ /opt/ha-integrations/ecoflow_cloud/
COPY --from=integration_sources /src/beszel/custom_components/beszel/ /opt/ha-integrations/beszel/

# /config is a persistent volume: files copied there during build would be masked.
# s6-overlay runs this script before Home Assistant starts.
COPY --chmod=0755 scripts/sync-integrations.sh /etc/cont-init.d/10-sync-integrations

# Version-controlled dashboard template and runtime registry-aware renderer.
COPY dashboards/ /opt/ha-dashboards/
COPY scripts/register-dashboard.py /opt/ha-tools/register-dashboard.py

# Host AC-power sensor and dashboard stats (Home Assistant packages).
COPY packages/ /opt/ha-packages/
COPY scripts/register-power-package.py /opt/ha-tools/register-power-package.py
