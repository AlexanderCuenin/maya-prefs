# Maya prefs

Alex's Maya preferences. **This repo is the source of truth:** every time Maya starts it checks GitHub and makes Maya match what's here.

## Install (once per computer)

1. Download this repo (**Code > Download ZIP**) and unzip it anywhere.
2. Drag `tools/install.py` into a Maya viewport.
3. When asked, paste your GitHub token (see below) or skip it if you only want to pull.

That's it. The installer puts `maya_sync.py` in `~/maya/scripts` (shared by every Maya version), hooks it into `userSetup.py`, adds a **Prefs Sync** shelf button and does a first sync. Your old prefs are zipped to `~/maya/prefs_sync/backups/` before the first sync on each Maya version.

## How it works

- **On startup** the script asks GitHub for the latest commit id. If it's the same as last time, nothing is downloaded and the check takes a fraction of a second. If it changed, the repo is downloaded once (it's tiny) and kept in `~/maya/prefs_sync/repo`.
- Then it compares Maya with the repo and fixes whatever differs. Files (marking menus, shelves, workspaces) go in before Maya builds its UI. Settings, colors, hotkeys and panel layouts are applied once Maya is up.
- **Offline?** It uses the last downloaded copy and carries on.
- A change you make in Maya that you don't push gets put back at the next sync. Push it if you want to keep it.

## The Prefs Sync button

| Button | What it does |
|---|---|
| Pull from GitHub | Same as startup: make Maya match the repo |
| Check | Lists what differs in the Script Editor, changes nothing |
| Push my Maya changes to GitHub | Sends what **you** changed in Maya since the last sync |

Push only sends your own changes, on top of whatever is on GitHub now. If GitHub changed the same item in the meantime (say Claude edited it), GitHub's version is kept and you get a warning. Anything else that changed on GitHub is pulled in right after the push.

From the Script Editor: `import maya_sync` then `maya_sync.sync()`, `maya_sync.check()`, `maya_sync.push("message")`, `maya_sync.push(dry_run=True)` or `maya_sync.capture()`.

## Who can change this repo

Only you. On GitHub only the owner and collaborators you invite can push. Pushing from Maya uses **your** token, which lives only on your computer in `~/maya/prefs_sync/token.txt` and never goes in the repo.

Make the token here: <https://github.com/settings/personal-access-tokens/new>

- **Repository access:** Only select repositories > `maya-prefs`
- **Permissions:** Repository permissions > **Contents: Read and write**
- Pick an expiration you're happy with. When it expires, replace the text in `token.txt`.

The repo is public right now, so anyone can *see* it but nobody else can change it. To hide it too, make it private under **Settings > General > Danger Zone**. The same token then also lets Maya read it.

## What's in here

| Path | What it is | Edit it? |
|---|---|---|
| `prefs.json` | Active hotkey set, active workspace, playback (fps, speed, looping, default tangents, auto key) and animation / timeline / graph editor optionVars as `name: value` | Yes. Add any optionVar name and it'll be enforced |
| `colors.json` | UI and viewport colors: `rgb` (0-1 values), `index` (palette slots), `palette` | Yes |
| `panel_layouts.json` | Your **Panels > Saved Layouts** | Rarely |
| `hotkeys/*.mhk` | One file per hotkey set (Maya's own export format) | Through Maya |
| `hotkeys/runtime_commands.json` | Your custom runtime commands (what hotkeys call) | Yes |
| `marking_menus/menu_*.mel` | Your custom marking menus (Maya's built-in ones are left out) | Yes |
| `shelves/shelf_*.mel` | Shelves | Yes |
| `workspaces/*.json` | Saved workspaces | Rarely |
| `sync_config.json` | Turn categories on or off, keep deleted files, hide the startup message, extra optionVar patterns for capture | Yes |
| `tools/` | The sync script and installer. Pushing a new `tools/maya_sync.py` updates everyone's copy on the next sync | Claude does |

Deleting a file here removes it from Maya on the next sync, but only files the sync put there itself.

## Settings that need a restart

Shelves, marking menus and workspaces that change while Maya is open are written straight away. Shelves are reloaded live; marking menus and workspaces show up fully after a restart. Everything else applies live.

Works with Maya 2018 to 2026 (Python 2 and 3). `tests/test_sync_mock.py` runs the whole flow against a fake Maya and a fake GitHub: `python tests/test_sync_mock.py`.
