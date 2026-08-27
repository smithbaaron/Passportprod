# Passportprod

Salesforce DX project for the **Passport Labs production org**.

| | |
|---|---|
| Org | `passportlabs.my.salesforce.com` (production) |
| Org ID | `00DG0000000lbqIMAQ` |
| CLI alias | `prod` |
| Login URL | `https://login.salesforce.com` |

Metadata lives under `force-app/` in source format. Retrieve/deploy with the
`sf` CLI, e.g.:

```sh
sf project retrieve start --metadata ApexClass --target-org prod
sf project deploy start --source-dir force-app --target-org prod
```

## Connecting to the prod org

On a machine with a browser:

```sh
sf org login web --instance-url https://login.salesforce.com --alias prod --set-default
```

In headless environments (CI, Claude Code cloud sessions), use an SFDX auth
URL stored as a **secret** environment variable `SFDX_AUTH_URL`, then run:

```sh
./scripts/session-setup.sh
```

To produce the auth URL value from an already-authenticated machine:

```sh
sf org display --target-org prod --verbose   # shows "Sfdx Auth Url"
```

Treat that value like a password — it contains a live refresh token. Never
commit it.

## Claude Code cloud sessions: network access

The environment's network policy must allow the org's domains or API calls
will fail (`login.salesforce.com` alone is not enough). Allow at minimum:

- `passportlabs.my.salesforce.com` — all REST/SOAP/Metadata API traffic
- `login.salesforce.com` — OAuth token refresh
- `passportlabs.file.force.com` — content/file downloads (if needed)
- `passportlabs.lightning.force.com` — Lightning pages (rarely needed for CLI)
