# Maya prefs

Alex's Maya preferences. **This repo is the source of truth:** every time Maya starts it checks GitHub and makes Maya match what's here.

## Set up a Maya (new computer or new Maya version)

1. Open [`install.py`](install.py) on GitHub and click **Download raw file**.
2. Drag it into a Maya viewport.
3. Paste your GitHub token when asked (see below), or skip it if you only want to pull.

That one file does the rest: it downloads the sync tool from this repo into your shared Maya scripts folder (`~/Library/Preferences/Autodesk/maya/scripts` on a Mac, `Documents/maya/scripts` on Windows), hooks it into `userSetup.py`, adds a **Prefs Sync** menu and shelf button, and pulls all your prefs. Your old prefs are zipped to `prefs_sync/backups/` before the first sync on each Maya version.

## First time only: fill the repo from your Maya

The repo starts out with just the tool and your two new marking menus. To put the rest of your setup in it, install as above with your token, then click **Push my Maya changes to GitHub**. That sends your hotkeys, shelves, workspaces, panel layouts, colors and animation settings.

## How it works

- **On startup** the script asks GitHub for the latest commit id. If it's the same as last time, nothing is downloaded and the check takes a fraction of a second. If it changed, the repo is downloaded once (it's tiny) and kept in `~/maya/prefs_sync/repo`.
- Then it compares Maya with the repo and fixes whatever differs. Files (marking menus, shelves, workspaces) go in before Maya builds its UI. Settings, colors, hotkeys and panel layouts are applied once Maya is up.
- **Offline?** It uses the last downloaded copy and carries on.
- A change you make in Maya that you don't push gets put back at the next sync. Push it if you want to keep it.

## The Prefs Sync menu and button

| Button | What it does |
|---|---|
| Pull from GitHub | Same as startup: make Maya match the repo |
| Check | Lists what differs in the Script Editor, changes nothing |
| Push my Maya changes to GitHub | Sends what **you** changed in Maya since the last sync |

Push only sends your own changes, on top of whatever is on GitHub now. If GitHub changed the same item in the meantime (say Claude edited it), GitHub's version is kept and you get a warning. Anything else that changed on GitHub is pulled in right after the push.

From the Script Editor: `import maya_sync` then `maya_sync.sync()`, `maya_sync.check()`, `maya_sync.push("message")`, `maya_sync.push(dry_run=True)` or `maya_sync.capture()`.

## Who can change this repo

Only you. On GitHub only the owner and collaborators you invite can push. Pushing from Maya uses **your** token, which lives only on your computer in `~/maya/prefs_sync/token.txt` and never goes in the repo.

Make the token here (only you can, since it's tied to your account): <https://github.com/settings/personal-access-tokens/new>

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
| `marking_menus/menu_*.mel` | Your custom marking menus, the files Maya reads (Maya's built-in ones are left out) | Built from `marking_menus_src` where a source exists |
| `marking_menus_src/<menu>/` | Readable sources: `menu.json` (label, position, bold) and one `.py`/`.mel` file per item | Yes, then run `python tools/marking_menus.py build` |
| `shelves/shelf_*.mel` | Shelves | Yes |
| `workspaces/*.json` | Saved workspaces | Rarely |
| `sync_config.json` | Turn categories on or off, keep deleted files, hide the startup message, extra optionVar patterns for capture, and `retired` files to take out of Maya | Yes |
| `install.py` | The one-file installer | Claude does |
| `tools/` | The sync script and the marking menu builder. Pushing a new `tools/maya_sync.py` updates every Maya's copy on the next sync | Claude does |

Deleting a file here removes it from Maya on the next sync, but only files the sync put there itself. To take out a file the sync never installed (an old marking menu, say), list it under `retired` in `sync_config.json`. It's moved to `prefs_sync/retired/`, not deleted, and Push skips it.

## Marking menus as code

`marking_menus_src/` holds the menus Claude maintains as plain scripts: `cuenin_splines_MM`, `cuenin_baking_MM` and `cuenin_reset_MM` (the animBot-free reset menu). The animBot menus (`copyPaste`, `timeBookmarks`, `visibility`) are kept exactly as Maya wrote them, straight in `marking_menus/`. They need animBot installed to do anything. Edit an item's `.py`, or `menu.json` to move or rename items, then run `python tools/marking_menus.py build` to regenerate `marking_menus/menu_*.mel`. If a `.mel` was changed in Maya and pushed from there, the build won't overwrite it. Run `python tools/marking_menus.py extract marking_menus/menu_<name>.mel` first to bring that change into the sources.

## Live or restart?

At startup nothing ever needs a restart: files are put in place before Maya builds its UI, and settings are applied right after. When you click **Pull** while Maya is open:

| Category | When you see it |
|---|---|
| Marking menus | Live. The hotkey re-reads the menu file every time you press it |
| Hotkeys and runtime commands | Live |
| Shelves | Live. Changed shelves are reloaded in place |
| Animation settings, fps, playback, default tangents, auto key | Live |
| Colors | Live |
| Panel layouts (Saved Layouts) | Live |
| Workspaces | New ones show in the Workspace menu after a restart. If the one you're in changed, pick it again or restart |

Works with Maya 2018 to 2026 (Python 2 and 3). `tests/test_sync_mock.py` runs the whole flow against a fake Maya and a fake GitHub: `python tests/test_sync_mock.py`.
