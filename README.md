# tendrl-cli

The Tendrl platform in your terminal — one colorful, scriptable CLI covering
**Contact** (devices, messages, dashboards, IAM), **Strand** (workflows and
runs), and **Surface** (file and payload scanning).

The device SDKs handle the device data plane. `tendrl-cli` covers everything
else: the account plane you'd otherwise reach through the web console.

## Install

```bash
uv tool install git+https://github.com/tendrl-inc-labs/tendrl-cli
```

or with pipx / pip:

```bash
pipx install git+https://github.com/tendrl-inc-labs/tendrl-cli
```

Requires Python 3.10+. Full documentation: [tendrl.com/docs](https://tendrl.com/docs/contact/sdks/cli/getting-started/).

## Quick start

```bash
# sign in (session commands: whoami, accounts, billing)
tendrl-cli login

# data-plane commands use per-product API keys
export TENDRL_API_KEY=...      # Contact account key
export STRAND_API_KEY=...      # Strand key
export SURFACE_KEY=...         # Surface key (sfk_...)

tendrl-cli contact entities list
tendrl-cli contact insights usage
tendrl-cli strand workflows run wf_123 --data '{"data": {"temp": 71.2}}'
tendrl-cli strand runs list --limit 10
tendrl-cli surface scan file ./firmware.bin
```

Every command takes `--json` for scripting:

```bash
tendrl-cli --json contact entities list | jq '.data[].name'
```

Anything without a curated verb is reachable through the escape hatch:

```bash
tendrl-cli api contact GET /entities/abc/heartbeat
tendrl-cli api strand POST /workflows/wf_1/run -d '{"data": {}}'
```

## Configuration

| Setting | Flag | Environment | Stored |
|---|---|---|---|
| Platform origin | `--app-url` | `TENDRL_APP_URL` | `tendrl-cli config set-url` |
| Contact key | `--key` | `TENDRL_API_KEY` (or `CONTACT_API_KEY`) | `tendrl-cli config set-key contact` |
| Strand key | `--key` | `STRAND_API_KEY` | `tendrl-cli config set-key strand` |
| Surface key | `--key` | `SURFACE_KEY` (or `SURFACE_API_KEY`) | `tendrl-cli config set-key surface` |

Flags beat environment variables, which beat the config file
(`~/.config/tendrl/config.json`, written with `0600` permissions).

Note: `TENDRL_KEY` (the device/entity key used by the SDKs) is deliberately
not read — this is an account tool, not a device.

## Command map

```
tendrl-cli
├── login / logout / whoami        session (email + password)
├── accounts  list · switch · show
├── billing   plans
├── contact   entities · messages · files · fanouts · directories ·
│             dashboards · alerts · flows · services · insights ·
│             keys · users · roles · policies · audit · deployments
├── strand    workflows (save/run/versions/export/import) · runs ·
│             connectors · functions · vault · configurations ·
│             templates · keys · team · roles · usage · audit · whoami
├── surface   scan (file/payload, --local daemon) · history · account · profiles · keys
├── config    show · path · set-url · set-key · unset-key · set-scanner
└── api       <service> <METHOD> <path>   raw escape hatch
```

Destructive commands prompt before acting (pass `--yes` to skip). Keys and
secrets are shown once on create/rotate — save them when they appear.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
pytest
```

Tests mock all HTTP with respx; nothing touches the live API.
