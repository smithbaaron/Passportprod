#!/usr/bin/env bash
# Bootstrap a Claude Code cloud session (or any fresh machine) for this repo:
# installs the Salesforce CLI and authenticates to the prod org.
#
# Auth expects the environment variable SFDX_AUTH_URL to hold the org's
# Salesforce DX auth URL (format: force://<clientId>::<refreshToken>@<host>).
# Store it as a SECRET environment variable in the Claude Code environment
# settings — never commit it to the repo.
set -euo pipefail

if ! command -v sf >/dev/null 2>&1; then
  echo "Installing @salesforce/cli..."
  npm install -g @salesforce/cli
fi
sf version

if [ -n "${SFDX_AUTH_URL:-}" ]; then
  echo "Authenticating to prod org from SFDX_AUTH_URL..."
  printf '%s' "$SFDX_AUTH_URL" | sf org login sfdx-url --sfdx-url-stdin --alias=prod --set-default
  sf org display -o prod
else
  echo "SFDX_AUTH_URL not set - skipping org auth."
  echo "Add it as a secret env var in the environment settings, or log in manually:"
  echo "  sf org login sfdx-url|jwt|web (see README.md 'Connecting to the prod org')"
fi
