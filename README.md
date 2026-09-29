# opencode-openrouter-providers

Pick **which provider serves your OpenRouter model**, directly from OpenCode's
prompt bar — and keep the list fresh automatically.

OpenCode does not discover the providers behind an OpenRouter model. The second
dropdown in the prompt bar (the *variant* selector, labelled **Default**) only
lists options **you declare yourself**. This tool declares them for you: for
every OpenRouter model served by more than one provider, it writes one variant
per provider into your `opencode.jsonc`.

Result: choose a model, then open the variant dropdown and pick
`Morph`, `DeepInfra`, `Together`, … or `Auto (OpenRouter)`.

No API key is required — OpenRouter's models/endpoints API is public.

```
┌─────────────────────────────────────────────┐
│  +  Build ⌄   DeepSeek V4.1 Flash ⌄         │
│                          ┌────────────────┐ │
│                          │ Venice         │ │
│                          │ …              │ │
│                          │ Morph          │ │
│                          │ InferenceNet   │ │
│                          │ Auto (OR)      │ │
│                          └────────────────┘ │
└─────────────────────────────────────────────┘
```

## Install

```bash
git clone <this-repo> opencode-openrouter-providers
cd opencode-openrouter-providers
./install.sh
```

`install.sh` sets up a daily refresh:

| OS      | Mechanism                                              |
| ------- | ------------------------------------------------------ |
| macOS   | launchd agent — runs at login and daily at 08:00       |
| Linux   | crontab entry — daily at 08:00                         |

It also runs once immediately, then tells you to restart OpenCode.

## Manual use

```bash
python3 gen-providers.py                 # update the default config
python3 gen-providers.py --dry-run       # preview, write nothing
python3 gen-providers.py --config PATH   # target another config file
python3 gen-providers.py --min-providers 3
python3 gen-providers.py --models deepseek/deepseek-v4.1-flash,openai/gpt-5
python3 gen-providers.py --allow-fallbacks
```

Options:

| Flag                  | Meaning                                                             |
| --------------------- | ------------------------------------------------------------------- |
| `--config PATH`       | Config to edit. Default `~/.config/opencode/opencode.jsonc`         |
| `--min-providers N`   | Only add variants to models with ≥ N providers (default 2)          |
| `--models a,b`        | Limit the run to specific model ids                                 |
| `--allow-fallbacks`   | Let OpenRouter fall back if your chosen provider is down            |
| `--dry-run`           | Show the result without writing                                     |
| `--no-backup`         | Skip the `.bak` file                                                |

## What it writes

Into your `opencode.jsonc`, under `provider.openrouter.models.<model>.variants`:

```jsonc
"deepseek/deepseek-v4.1-flash": {
  "variants": {
    "Venice":           { "provider": { "only": ["venice/fp8"],    "allow_fallbacks": false } },
    "Together":         { "provider": { "only": ["together"],      "allow_fallbacks": false } },
    "Morph":            { "provider": { "only": ["morph"],         "allow_fallbacks": false } },
    "Auto (OpenRouter)":{ "provider": { "sort": "price" } }
  }
}
```

Everything else in your config (`apiKey`, MCP servers, plugins, default model)
is preserved. A `.bak` copy is written before each run.

## Notes and caveats

- **Cheapest is last.** The variant menu is bottom-anchored and clips the top
  when the list is long, so variants are ordered most-expensive → cheapest.
  Your cheapest providers stay visible without scrolling.
- **One provider = no menu.** Models served by a single provider get no
  variants — there would be nothing to choose.
- **`allow_fallbacks: false`** pins the provider: if it is down, the request
  fails. Pass `--allow-fallbacks` for a soft pin that falls back automatically.
- **Dead providers.** The script lists whatever the API reports without probing
  all combinations, so a provider that is temporarily down may appear. It
  disappears on the next refresh.
- **`Auto (OpenRouter)`** asks OpenRouter to sort by price each request. It is
  *usually* cheap but not guaranteed to be the absolute cheapest endpoint.
- **Restart required.** OpenCode reads its config at startup; a refresh only
  takes effect after you restart it.

## Uninstall

```bash
./uninstall.sh
```

This removes the scheduled job. It does not touch your `opencode.jsonc` — delete
the `variants` blocks by hand if you want them gone (or restore a `.bak`).

## License

MIT