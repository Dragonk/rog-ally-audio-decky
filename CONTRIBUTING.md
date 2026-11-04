# Contributing

Thanks for helping improve ROG Ally Audio.

## Development

1. Fork and clone the repository.
2. Install Node.js 22, pnpm 9 and Python 3.11+.
3. Run:

```bash
pnpm install
pnpm typecheck
pnpm build
python -m pip install pytest
pytest -q
```

## Hardware support changes

Do not broaden the supported-device list just because another device uses a similar codec. Speaker tuning is hardware-specific. New devices should have:

- real-device validation,
- dedicated preset tuning,
- a stable output-device identifier,
- explicit model detection,
- documentation of the tested environment.

## Preset changes

For changes to Balanced/Cinema/Loud:

- explain the acoustic goal,
- include before/after values,
- keep Bypass an empty output chain,
- run `tests/test_presets.py`,
- report real-device listening/testing when applicable.
