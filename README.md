# PyDocker

A terminal UI for Docker built with Textual.

- **App**: `PyDocker`
- **Created by**: Vitor Corrêa
- **GitHub**: https://github.com/correavitor4

## Overview

PyDocker is a console-based Docker management dashboard. It shows Docker resources as tabs and lets you perform container operations directly from the keyboard.

### Features

- Tabbed view for:
  - Containers
  - Images
  - Volumes
  - Networks
- Container actions:
  - Start (`d`)
  - Stop (`s`)
  - Remove (`x`)
- View container logs in fullscreen mode with `l` (then `b` to go back)
- Create a new Docker network (`c`)
- Refresh data automatically every second
- Row-based selection for tables (whole row highlight)
- App title + subtitle include author credit and GitHub link

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install docker textual
```

## Run

```bash
python src/main.py
```

## Keybindings

- `r`: refresh containers table
- `i`: refresh images table
- `s`: stop selected container
- `d`: start selected container
- `x`: remove selected container
- `l`: show selected container logs (fullscreen mode)
- `b`: back from logs mode to main UI
- `c`: open network creation modal
- `q`: quit

## How logs work

- Select a container in `Containers` tab
- Press `l` to open `LogsScreen` (fullscreen with logs only)
- Press `b` to return to the main tabbed UI

## How network creation works

- Press `c` to open a modal
- Enter network name
- Press `Create` to create a `bridge` network (Docker API via `docker_client.networks.create`)

## Notes

- App is built with Textual 8+ and Docker SDK 7+.
- On startup, app checks Docker daemon availability via `docker_client.ping()`.
- If Docker is unavailable, it exits with an error message.

## Update policy (maintained by assistant)

All future changes involving build steps or major functionality must be added to this README with:
- feature description
- commands to use
- relevant keybindings
- side effects and behavior updates

## Changelog (most recent first)

- **Full English translation** (all UI labels, messages, comments and notifications).
- **App branding updated**: `PyDocker` with `Vitor Corrêa` and `https://github.com/correavitor4` included.
- **Tabbed UI** for Containters, Images, Volumes, Networks.
- **Logs-only screen** when pressing `l`, and back with `b`.
- **`create network` modal** for Docker network creation.
- **Set interval fixed**: `self.set_interval(1000, self.update_data)`.
- **Row-level selection** for all tables via `cursor_type='row'`.

## Contribution

Submit PRs against `main` and include README updates describing the behavior and setup.
