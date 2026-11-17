"""
maya_sync - keep Maya's preferences in step with a GitHub repo.

The GitHub repo is the source of truth. On every Maya start this script:

  1. asks GitHub for the latest commit id (one tiny request),
  2. downloads the repo only if that id changed since last time,
  3. compares your local prefs with the repo and fixes anything that differs.

When nothing changed it finishes in a fraction of a second.

Commands (Python tab of the Script Editor):

    import maya_sync
    maya_sync.sync()          # pull from GitHub and apply (the shelf button)
    maya_sync.check()         # only report what differs, change nothing
    maya_sync.capture()       # save your current Maya setup in repo format

Works with Maya 2018-2026 (Python 2 and 3).
"""
from __future__ import print_function

import datetime
import fnmatch
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

try:
    import maya.cmds as cmds
    import maya.mel as mel
except ImportError:  # lets the tests import this outside Maya
    cmds = None
    mel = None

try:  # Python 3
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:  # Python 2 (Maya 2018-2020)
    from urllib2 import Request, urlopen, HTTPError, URLError

__version__ = "1.1.0"

# --------------------------------------------------------------------------
# Where your prefs live on GitHub. Claude sets these; edit if you rename the
# repo. For a private repo, put a read-only GitHub token in
# ~/maya/prefs_sync/token.txt (or the MAYA_SYNC_TOKEN environment variable).
# --------------------------------------------------------------------------
REPO = "AlexanderCuenin/maya-prefs"
BRANCH = "main"

CHECK_TIMEOUT = 3      # seconds to wait for GitHub's "latest commit" answer
DOWNLOAD_TIMEOUT = 30  # seconds to wait for the repo download

# Repo layout: category -> (folder in repo, local folder getter, file patterns)
FILE_CATEGORIES = [
    ("marking_menus", "marking_menus", lambda: _internal("userMarkingMenuDir"), ["menu_*.mel"]),
    ("shelves", "shelves", lambda: _internal("userShelfDir"), ["shelf_*.mel"]),
    ("workspaces", "workspaces", lambda: os.path.join(prefs_dir(), "workspaces"), ["*.json"]),
]

DEFAULT_CONFIG = {
    "sync": {
        "marking_menus": True, "shelves": True, "workspaces": True,
        "hotkeys": True, "panel_layouts": True, "settings": True,
        "colors": True,
    },
    "remove_deleted_files": True,
    "show_message": True,
}

# optionVars captured by capture(): animation / timeline / graph editor
# settings. Add names or patterns to "capture_patterns" in sync_config.json.
CAPTURE_PATTERNS = [
    "*anim*", "*graphEditor*", "*graphEd*", "*dopeSheet*", "*timeSlider*",
    "*timeline*", "*timeControl*", "*playback*", "*tangent*", "*keyTick*",
    "*tick*", "*keyframe*", "*setKey*", "*autoKey*", "*ghost*", "*onionSkin*",
    "*bufferCurve*", "*workingUnitTime*", "*fps*", "*frameRate*",
    "*framesPerSecond*", "*loopPlayback*", "*rangeSlider*", "*stepped*",
    "*breakdown*", "*weightedTangent*", "*trax*", "*timeEditor*",
    "*keyFilter*", "*keyStats*", "*infinity*", "*snapKeys*",
    "*evaluationMode*", "*parallelEval*", "*cachedPlayback*",
]
# Machine-specific optionVars that never belong in the repo.
EXCLUDE_PATTERNS = [
    "*recent*", "*path*", "*dir", "*directory*", "*folder*", "*project*",
    "*lastopen*", "*last*file*", "*license*", "*geometry*", "*windowpos*",
    "*position*", "*sessionid*", "*mru*", "*history*", "*workspacelayout*",
]
KNOWN_DEFAULT_MARKING_MENUS = set(n.lower() for n in [
    "menu_ChangePanelLayout.mel", "menu_ChangePanelType.mel",
    "menu_ChangeSelectionMask.mel", "menu_CommonModelingPanes.mel",
    "menu_SelectionMaskingMM.mel", "menu_HotboxCenter.mel",
    "menu_HotboxNorth.mel", "menu_HotboxSouth.mel", "menu_HotboxEast.mel",
    "menu_HotboxWest.mel", "menu_PolygonsMM.mel", "menu_SubdivsMM.mel",
    "menu_NURBSMM.mel", "menu_PaintEffectsMM.mel",
])


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
class _Log(object):
    def __init__(self, quiet=False):
        self.lines, self.changes, self.warnings, self.quiet = [], [], [], quiet

    def info(self, msg):
        self.lines.append(msg)
        if not self.quiet:
            print("[maya_sync] " + msg)

    def change(self, msg):
        self.changes.append(msg)
        self.info("  " + msg)

    def warn(self, msg):
        self.warnings.append(msg)
        self.info("WARNING: " + msg)


def _norm(path):
    return os.path.normpath(os.path.expanduser(path))


def _internal(flag):
    return _norm(cmds.internalVar(**{flag: True}))


def prefs_dir():
    return _internal("userPrefDir")


def app_dir():
    """~/maya (shared by every Maya version)."""
    return _internal("userAppDir")


def sync_dir():
    return os.path.join(app_dir(), "prefs_sync")


def repo_cache():
    return os.path.join(sync_dir(), "repo")


def _maya_version():
    try:
        return str(cmds.about(version=True))
    except Exception:
        return "unknown"


def _file_hash(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path, default=None):
    try:
        with io.open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return default


def _write_json(path, data):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if isinstance(text, type(u"")) else text.decode("utf-8"))
        fh.write(u"\n")


def _match_any(name, patterns):
    low = name.lower()
    return any(fnmatch.fnmatchcase(low, p.lower()) for p in patterns)


def _same(a, b):
    """Loose equality: numbers within 1e-4, lists element-wise."""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-4
    return a == b


def _list_files(folder, patterns):
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder)
                  if os.path.isfile(os.path.join(folder, f))
                  and _match_any(f, patterns))


# --------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------
def _token():
    tok = os.environ.get("MAYA_SYNC_TOKEN", "").strip()
    if tok:
        return tok
    path = os.path.join(sync_dir(), "token.txt")
    if os.path.isfile(path):
        with open(path) as fh:
            return fh.read().strip()
    return ""


def _http_get(url, accept, timeout, method=None, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url, data=data)
    if method:
        req.get_method = lambda: method
    if data is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "maya-sync")
    tok = _token()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    resp = urlopen(req, timeout=timeout)
    try:
        return resp.read()
    finally:
        resp.close()


def latest_commit():
    """Commit id of the branch tip on GitHub (a 40 character string)."""
    url = "https://api.github.com/repos/%s/commits/%s" % (REPO, BRANCH)
    return _http_get(url, "application/vnd.github.sha", CHECK_TIMEOUT).decode("ascii").strip()


def _download(sha, log, dest=None):
    """Download the repo at ``sha`` and unpack it into ``dest`` (default: the
    local cache)."""
    dest = dest or repo_cache()
    url = "https://api.github.com/repos/%s/zipball/%s" % (REPO, sha)
    data = _http_get(url, "application/vnd.github+json", DOWNLOAD_TIMEOUT)
    tmp = dest + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            # GitHub wraps everything in "<owner>-<repo>-<sha>/"
            parts = info.filename.split("/", 1)
            if len(parts) < 2 or not parts[1] or info.filename.endswith("/"):
                continue
            rel = parts[1]
            if rel.startswith("/") or ".." in rel.split("/"):
                continue
            target = os.path.join(tmp, *rel.split("/"))
            if not os.path.isdir(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(tmp, dest)
    log.info("Downloaded %s @ %s (%d KB)" % (REPO, sha[:7], len(data) // 1024))


def _repo_state_path():
    return os.path.join(sync_dir(), "repo_state.json")


def _local_state_path():
    """Per Maya version: what we last installed into this prefs folder."""
    return os.path.join(sync_dir(), "state_%s.json" % _maya_version().replace(" ", "_"))


def fetch(log=None, offline=False):
    """Make sure the local cache matches GitHub. Returns the cached commit id."""
    log = log or _Log()
    repo_state = _read_json(_repo_state_path(), {}) or {}
    cached = repo_state.get("sha") if os.path.isdir(repo_cache()) else None
    if offline:
        return cached
    try:
        sha = latest_commit()
    except HTTPError as exc:
        hint = " (private repo? add a token, see README)" if exc.code in (401, 403, 404) else ""
        log.warn("GitHub said %s for %s%s; using the last copy" % (exc.code, REPO, hint))
        return cached
    except Exception as exc:  # offline, DNS, SSL, timeout...
        log.warn("could not reach GitHub (%s); using the last copy" % exc)
        return cached
    if sha != cached:
        try:
            _download(sha, log)
            _write_json(_repo_state_path(), {"sha": sha, "fetched": datetime.datetime.now().isoformat()})
            cached = sha
        except Exception as exc:
            log.warn("download failed (%s); using the last copy" % exc)
    return cached


def load_config(root=None):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = _read_json(os.path.join(root or repo_cache(), "sync_config.json"), {}) or {}
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


# --------------------------------------------------------------------------
# optionVars
# --------------------------------------------------------------------------
def _read_optionvar(name):
    """Plain JSON value of an optionVar, or None if it doesn't exist."""
    if not cmds.optionVar(exists=name):
        return None
    value = cmds.optionVar(q=name)
    if isinstance(value, (list, tuple)):
        return [int(v) if isinstance(v, bool) else v for v in value]
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return u"%s" % value


def _write_optionvar(name, value):
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        cmds.optionVar(intValue=(name, value))
    elif isinstance(value, float):
        cmds.optionVar(floatValue=(name, value))
    elif isinstance(value, (list, tuple)):
        cmds.optionVar(clearArray=name)
        if all(isinstance(v, (bool, int)) for v in value):
            flag, conv = "intValueAppend", int
        elif all(isinstance(v, (int, float)) for v in value):
            flag, conv = "floatValueAppend", float
        else:
            flag, conv = "stringValueAppend", lambda v: u"%s" % v
        for item in value:
            cmds.optionVar(**{flag: (name, conv(item))})
    else:
        cmds.optionVar(stringValue=(name, u"%s" % value))


# --------------------------------------------------------------------------
# Playback / timeline state that lives outside optionVars
# --------------------------------------------------------------------------
_PLAYBACK = [
    # key, getter, setter
    ("fps", lambda: cmds.currentUnit(q=True, time=True), lambda v: cmds.currentUnit(time=v)),
    ("playbackSpeed", lambda: cmds.playbackOptions(q=True, playbackSpeed=True), lambda v: cmds.playbackOptions(playbackSpeed=v)),
    ("maxPlaybackSpeed", lambda: cmds.playbackOptions(q=True, maxPlaybackSpeed=True), lambda v: cmds.playbackOptions(maxPlaybackSpeed=v)),
    ("loop", lambda: cmds.playbackOptions(q=True, loop=True), lambda v: cmds.playbackOptions(loop=v)),
    ("by", lambda: cmds.playbackOptions(q=True, by=True), lambda v: cmds.playbackOptions(by=v)),
    ("view", lambda: cmds.playbackOptions(q=True, view=True), lambda v: cmds.playbackOptions(view=v)),
    ("inTangentType", lambda: cmds.keyTangent(q=True, g=True, inTangentType=True)[0], lambda v: cmds.keyTangent(g=True, inTangentType=v)),
    ("outTangentType", lambda: cmds.keyTangent(q=True, g=True, outTangentType=True)[0], lambda v: cmds.keyTangent(g=True, outTangentType=v)),
    ("weightedTangents", lambda: bool(cmds.keyTangent(q=True, g=True, weightedTangents=True)[0]), lambda v: cmds.keyTangent(g=True, weightedTangents=bool(v))),
    ("autoKey", lambda: bool(cmds.autoKeyframe(q=True, state=True)), lambda v: cmds.autoKeyframe(state=bool(v))),
]


def _read_playback():
    out = {}
    for key, get, _set in _PLAYBACK:
        try:
            out[key] = get()
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------
# Colors
# --------------------------------------------------------------------------
def _read_colors():
    rgb = {}
    for line in cmds.displayRGBColor(list=True) or []:
        parts = line.split()
        try:
            rgb[parts[0]] = [round(float(p), 4) for p in parts[1:4]]
        except (ValueError, IndexError):
            pass
    index = {}
    try:
        names = [l.split()[0] for l in cmds.displayColor(list=True) or []]
    except Exception:
        names = []
    for name in names:
        entry = {}
        for mode in ("active", "dormant"):
            try:
                entry[mode] = int(cmds.displayColor(name, q=True, **{mode: True}))
            except Exception:
                pass
        if entry:
            index[name] = entry
    palette = {}
    for i in range(1, 32):
        try:
            palette[str(i)] = [round(float(v), 4) for v in cmds.colorIndex(i, q=True)]
        except Exception:
            break
    return {"rgb": rgb, "index": index, "palette": palette}


# --------------------------------------------------------------------------
# Panel layouts and runtime commands
# --------------------------------------------------------------------------
def _read_panel_layouts():
    out = {}
    for cfg in cmds.getPanel(allConfigs=True) or []:
        try:
            if not cmds.panelConfiguration(cfg, q=True, userCreated=True):
                continue
            q = lambda **kw: cmds.panelConfiguration(cfg, q=True, **kw)
            n = q(numberOfPanels=True) or 0
            cols = [q(isFixedState=True) or [], q(labelStrings=True) or [],
                    q(typeStrings=True) or [], q(createStrings=True) or [],
                    q(editStrings=True) or []]
            panels = []
            for i in range(n):
                vals = [c[i] if i < len(c) else "" for c in cols]
                panels.append({"fixed": bool(vals[0]), "label": vals[1], "type": vals[2],
                               "create": vals[3], "edit": vals[4]})
            out[q(label=True)] = {"configString": q(configString=True), "panels": panels}
        except Exception:
            continue
    return out


def _panel_layout_nodes():
    nodes = {}
    for cfg in cmds.getPanel(allConfigs=True) or []:
        try:
            nodes[cmds.panelConfiguration(cfg, q=True, label=True)] = cfg
        except Exception:
            pass
    return nodes


def _make_panel_layout(label, entry):
    node = _panel_layout_nodes().get(label)
    if node:
        try:
            cmds.deleteUI(node, panelConfig=True)
        except Exception:
            pass
    add = [(p.get("fixed", False), p.get("label", ""), p.get("type", ""),
            p.get("create", ""), p.get("edit", "")) for p in entry.get("panels", [])]
    cmds.panelConfiguration(label=label, sceneConfig=False, userCreated=True,
                            configString=entry.get("configString", ""), addPanel=add)


_RTC_FLAGS = ("command", "commandLanguage", "annotation", "category", "image",
              "label", "tags", "keywords", "plugin")


def _read_runtime_commands():
    out = {}
    try:
        names = cmds.runTimeCommand(q=True, userCommandArray=True) or []
    except Exception:
        names = []
    for name in names:
        info = {}
        for flag in _RTC_FLAGS:
            try:
                val = cmds.runTimeCommand(name, q=True, **{flag: True})
                if val not in (None, "", []):
                    info[flag] = val
            except Exception:
                pass
        out[name] = info
    return out


def _make_runtime_command(name, info):
    if cmds.runTimeCommand(name, exists=True):
        try:
            cmds.runTimeCommand(name, e=True, delete=True)
        except Exception:
            pass
    kwargs = dict((k, v) for k, v in info.items() if k in _RTC_FLAGS and v not in (None, ""))
    kwargs.setdefault("command", "")
    try:
        cmds.runTimeCommand(name, default=False, **kwargs)
    except Exception:
        for flag in ("label", "tags", "keywords", "plugin"):  # flags older Mayas lack
            kwargs.pop(flag, None)
        cmds.runTimeCommand(name, **kwargs)


# --------------------------------------------------------------------------
# Shelves: Maya keeps shelves in memory and rewrites the files on exit, so a
# shelf that changes while Maya is open has to be reloaded in the UI too.
# --------------------------------------------------------------------------
def _shelf_top():
    try:
        return mel.eval("$_ms_tmp = $gShelfTopLevel")
    except Exception:
        return None


def _reload_shelf(path, remove=False):
    top = _shelf_top()
    if not top or not cmds.tabLayout(top, exists=True):
        return False  # no UI yet: Maya will load the file itself
    name = os.path.basename(path)[len("shelf_"):-len(".mel")]
    full = top + "|" + name
    if cmds.shelfLayout(full, exists=True):
        cmds.deleteUI(full, layout=True)
    if not remove:
        mel.eval('loadNewShelf "%s"' % path.replace("\\", "/"))
    return True


# --------------------------------------------------------------------------
# The sync itself
# --------------------------------------------------------------------------
def _sync_files(root, cfg, state, apply, log, live_ui):
    managed = state.setdefault("files", {})
    for cat, repo_sub, local_dir_fn, patterns in FILE_CATEGORIES:
        if not cfg["sync"].get(cat, True):
            continue
        src_dir = os.path.join(root, repo_sub)
        dst_dir = local_dir_fn()
        wanted = _list_files(src_dir, patterns)
        for name in wanted:
            src, dst = os.path.join(src_dir, name), os.path.join(dst_dir, name)
            h = _file_hash(src)
            key = cat + "/" + name
            if os.path.isfile(dst) and _file_hash(dst) == h:
                managed[key] = h
                continue
            log.change("%s: %s %s" % (cat, "update" if os.path.isfile(dst) else "add", name))
            if apply:
                if not os.path.isdir(dst_dir):
                    os.makedirs(dst_dir)
                shutil.copyfile(src, dst)
                managed[key] = h
                if cat == "shelves" and live_ui:
                    _reload_shelf(dst)
        retired = cfg.get("retired", {}).get(cat, [])
        for name in _list_files(dst_dir, retired) if retired else []:
            log.change("%s: retire %s (moved to prefs_sync/retired)" % (cat, name))
            if apply:
                keep = os.path.join(sync_dir(), "retired", cat)
                if not os.path.isdir(keep):
                    os.makedirs(keep)
                shutil.move(os.path.join(dst_dir, name), os.path.join(keep, name))
                managed.pop(cat + "/" + name, None)
        if cfg.get("remove_deleted_files", True):
            for key in [k for k in managed if k.startswith(cat + "/")]:
                name = key.split("/", 1)[1]
                if name in wanted:
                    continue
                dst = os.path.join(dst_dir, name)
                if os.path.isfile(dst):
                    log.change("%s: remove %s (deleted from repo)" % (cat, name))
                    if apply:
                        if cat == "shelves" and live_ui:
                            _reload_shelf(dst, remove=True)
                        os.remove(dst)
                if apply:
                    managed.pop(key, None)


def _sync_hotkeys(root, prefs, state, apply, log):
    folder = os.path.join(root, "hotkeys")
    applied = state.setdefault("hotkey_sets", {})
    rtc = _read_json(os.path.join(folder, "runtime_commands.json"), {}) or {}
    current = _read_runtime_commands()
    for name, info in sorted(rtc.items()):
        mine = current.get(name)
        if mine is not None and all(_same(mine.get(k), v) for k, v in info.items()):
            continue
        log.change("runtime command: %s %s" % ("update" if mine is not None else "add", name))
        if apply:
            try:
                _make_runtime_command(name, info)
            except Exception as exc:
                log.warn("runtime command %s failed: %s" % (name, exc))

    existing = set(cmds.hotkeySet(q=True, hotkeySetArray=True) or [])
    for fname in _list_files(folder, ["*.mhk"]):
        set_name = fname[:-4]
        path = os.path.join(folder, fname)
        h = _file_hash(path)
        if set_name in existing and applied.get(set_name) == h:
            continue
        log.change("hotkey set: %s %s" % ("update" if set_name in existing else "add", set_name))
        if not apply:
            continue
        try:
            if set_name in existing:
                if cmds.hotkeySet(q=True, current=True) == set_name:
                    cmds.hotkeySet("Maya_Default", e=True, current=True)
                cmds.hotkeySet(set_name, e=True, delete=True)
            cmds.hotkeySet(e=True, ip=path)
            applied[set_name] = h
        except Exception as exc:
            log.warn("hotkey set %s failed: %s" % (set_name, exc))

    want = prefs.get("active_hotkey_set")
    if want and cmds.hotkeySet(q=True, current=True) != want:
        if apply and not cmds.hotkeySet(want, exists=True):
            log.warn("hotkey set '%s' is not in the repo or in Maya" % want)
        else:
            log.change("active hotkey set -> %s" % want)
            if apply:
                cmds.hotkeySet(want, e=True, current=True)


def _sync_settings(prefs, apply, log):
    for name, value in sorted((prefs.get("optionvars") or {}).items()):
        mine = _read_optionvar(name)
        if mine is not None and _same(mine, value):
            continue
        log.change("setting %s: %s -> %s" % (name, json.dumps(mine), json.dumps(value)))
        if apply:
            try:
                _write_optionvar(name, value)
            except Exception as exc:
                log.warn("setting %s failed: %s" % (name, exc))
    playback = prefs.get("playback") or {}
    current = _read_playback()
    for key, _get, setter in _PLAYBACK:  # fps first: it changes the others
        if key not in playback or _same(current.get(key), playback[key]):
            continue
        log.change("playback %s: %s -> %s" % (key, current.get(key), playback[key]))
        if apply:
            try:
                setter(playback[key])
            except Exception as exc:
                log.warn("playback %s failed: %s" % (key, exc))


def _sync_colors(colors, apply, log):
    current = _read_colors()
    for name, rgb in sorted((colors.get("rgb") or {}).items()):
        if _same((current["rgb"].get(name) or [])[:3], rgb[:3]):
            continue
        log.change("color %s -> %s" % (name, rgb))
        if apply:
            try:
                cmds.displayRGBColor(name, *rgb[:3])
            except Exception as exc:
                log.warn("color %s failed: %s" % (name, exc))
    for name, entry in sorted((colors.get("index") or {}).items()):
        for mode, value in sorted(entry.items()):
            if current["index"].get(name, {}).get(mode) == value:
                continue
            log.change("color %s (%s) -> index %s" % (name, mode, value))
            if apply:
                try:
                    cmds.displayColor(name, value, **{mode: True})
                except Exception as exc:
                    log.warn("color %s failed: %s" % (name, exc))
    for idx, rgb in sorted((colors.get("palette") or {}).items(), key=lambda kv: int(kv[0])):
        if _same(current["palette"].get(idx), rgb[:3]):
            continue
        log.change("palette color %s -> %s" % (idx, rgb))
        if apply:
            try:
                cmds.colorIndex(int(idx), *rgb[:3])
            except Exception as exc:
                log.warn("palette color %s failed: %s" % (idx, exc))


def _sync_panel_layouts(layouts, apply, log):
    current = _read_panel_layouts()
    for label, entry in sorted(layouts.items()):
        if label in current and _same_json(current[label], entry):
            continue
        log.change("panel layout: %s %s" % ("update" if label in current else "add", label))
        if apply:
            try:
                _make_panel_layout(label, entry)
            except Exception as exc:
                log.warn("panel layout %s failed: %s" % (label, exc))


def _same_json(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _first_run_backup(log):
    """Zip the prefs folder once per Maya version before the first sync."""
    marker = os.path.join(sync_dir(), "backup_done_%s" % _maya_version().replace(" ", "_"))
    if os.path.exists(marker):
        return
    src = prefs_dir()
    folder = os.path.join(sync_dir(), "backups")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(folder, "prefs_%s_%s.zip" % (_maya_version().replace(" ", "_"), stamp))
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, _dirs, files in os.walk(src):
            for f in files:
                full = os.path.join(base, f)
                try:
                    zf.write(full, os.path.relpath(full, os.path.dirname(src)))
                except Exception:
                    pass
    open(marker, "w").close()
    log.info("Backed up your prefs to %s" % dest)


def _self_update(root, log):
    new = os.path.join(root, "tools", "maya_sync.py")
    here = os.path.abspath(__file__)
    if here.endswith(".pyc"):
        here = here[:-1]
    if os.path.isfile(new) and os.path.isfile(here) and _file_hash(new) != _file_hash(here):
        try:
            shutil.copyfile(new, here)
            log.change("sync script updated (active next time Maya starts)")
        except Exception as exc:
            log.warn("could not update the sync script: %s" % exc)


def _run(apply, phases, offline=False, quiet=False):
    if cmds is None:
        raise RuntimeError("run this inside Maya")
    t0 = time.time()
    log = _Log(quiet=quiet)
    sha = fetch(log, offline=offline)
    root = repo_cache()
    if not sha or not os.path.isdir(root):
        log.warn("no copy of the repo yet; nothing to sync")
        return log
    cfg = load_config(root)
    prefs = _read_json(os.path.join(root, "prefs.json"), {}) or {}
    state = _read_json(_local_state_path(), {}) or {}
    if apply:
        _first_run_backup(log)
    live_ui = "ui" in phases and _shelf_top() is not None

    if "files" in phases:
        _sync_files(root, cfg, state, apply, log, live_ui)
        if apply:
            _self_update(root, log)
    if "ui" in phases:
        on = cfg["sync"]
        if on.get("settings", True):
            _sync_settings(prefs, apply, log)
        if on.get("colors", True):
            _sync_colors(_read_json(os.path.join(root, "colors.json"), {}) or {}, apply, log)
        if on.get("hotkeys", True):
            _sync_hotkeys(root, prefs, state, apply, log)
        if on.get("panel_layouts", True):
            _sync_panel_layouts(_read_json(os.path.join(root, "panel_layouts.json"), {}) or {}, apply, log)
        if on.get("workspaces", True) and prefs.get("active_workspace"):
            try:
                cur = cmds.workspaceLayoutManager(q=True, current=True)
                if cur != prefs["active_workspace"]:
                    log.change("workspace -> %s" % prefs["active_workspace"])
                    if apply:
                        cmds.workspaceLayoutManager(setCurrent=prefs["active_workspace"])
            except Exception as exc:
                log.warn("workspace switch failed: %s" % exc)

    if apply:
        state["sha"] = sha
        state["synced"] = datetime.datetime.now().isoformat()
        _write_json(_local_state_path(), state)
        if log.changes and "ui" in phases:
            try:
                cmds.savePrefs(general=True, hotkeys=True, colors=True, menuSets=True, uiLayout=True)
            except Exception:
                try:
                    cmds.savePrefs()
                except Exception:
                    pass
    verb = "applied" if apply else "differ"
    log.info("%s @ %s: %d change(s) %s, %d warning(s), %.2fs"
             % (REPO, sha[:7], len(log.changes), verb, len(log.warnings), time.time() - t0))
    return log


def _message(log, apply=True):
    if not log.changes and not log.warnings:
        text = "Prefs up to date"
    else:
        text = "Prefs: %d change(s) %s" % (len(log.changes), "applied" if apply else "to apply")
        if log.warnings:
            text += ", %d warning(s) (see Script Editor)" % len(log.warnings)
    try:
        cmds.inViewMessage(amg=text, pos="topCenter", fade=True, fadeStayTime=2500)
    except Exception:
        pass


def sync(offline=False):
    """Pull from GitHub and make Maya match the repo. Returns the change list."""
    log = _run(True, ("files", "ui"), offline=offline)
    _message(log)
    return log.changes


def check(offline=False):
    """Report what differs from the repo without changing anything."""
    log = _run(False, ("files", "ui"), offline=offline)
    _message(log, apply=False)
    return log.changes


_startup_log = None


def startup():
    """Called from userSetup.py. Files go in before the UI is built (so shelves,
    marking menus and workspaces load fresh); settings follow once Maya is up."""
    global _startup_log
    try:
        if cmds.about(batch=True):
            return
    except Exception:
        pass
    _startup_log = _run(True, ("files",))

    def _later():
        log = _run(True, ("ui",), offline=True)
        log.changes = _startup_log.changes + log.changes
        log.warnings = _startup_log.warnings + log.warnings
        if load_config().get("show_message", True) and (log.changes or log.warnings):
            _message(log)

    cmds.evalDeferred(_later, lowestPriority=True)
    cmds.evalDeferred(add_menu, lowestPriority=True)


MENU = "mayaSyncMenu"


def add_menu():
    """A 'Prefs Sync' menu in Maya's main menu bar (rebuilt every start, so it
    never depends on a shelf)."""
    try:
        if cmds.about(batch=True):
            return
        main = mel.eval("$_ms_tmp = $gMainWindow")
        if not main:
            return
        if cmds.menu(MENU, exists=True):
            cmds.deleteUI(MENU)
        cmds.menu(MENU, parent=main, label="Prefs Sync", tearOff=True)
        cmds.menuItem(label="Pull from GitHub", command=lambda *_: sync())
        cmds.menuItem(label="Check (change nothing)", command=lambda *_: check())
        cmds.menuItem(label="Push my changes...", command=lambda *_: show())
        cmds.menuItem(divider=True)
        cmds.menuItem(label="Open the repo on GitHub",
                      command=lambda *_: cmds.launch(web="https://github.com/" + REPO))
    except Exception as exc:
        print("[maya_sync] could not add the menu: %s" % exc)


# --------------------------------------------------------------------------
# capture(): write your current Maya setup in the repo's format
# --------------------------------------------------------------------------
def _default_marking_menus():
    names = set(KNOWN_DEFAULT_MARKING_MENUS)
    loc = os.environ.get("MAYA_LOCATION", "")
    for sub in ("scripts", "resources"):
        top = os.path.join(loc, sub)
        if loc and os.path.isdir(top):
            for _p, _d, files in os.walk(top):
                names.update(f.lower() for f in files
                             if f.lower().startswith("menu_") and f.lower().endswith(".mel"))
    return names


def capture(folder=None, extra_patterns=None, include_default_menus=False, quiet=False):
    """Save your current Maya prefs in the repo layout (to ``folder``, default
    ~/maya/prefs_sync/capture) and zip it. Returns the zip path."""
    if cmds is None:
        raise RuntimeError("run this inside Maya")
    folder = _norm(folder or os.path.join(sync_dir(), "capture"))
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    try:
        cmds.savePrefs(general=True, hotkeys=True, colors=True, menuSets=True, uiLayout=True)
    except Exception:
        pass
    try:
        mel.eval("saveCurrentWorkspace;")
    except Exception:
        pass

    defaults = set() if include_default_menus else _default_marking_menus()
    retired = load_config().get("retired", {})
    for cat, repo_sub, local_dir_fn, patterns in FILE_CATEGORIES:
        src = local_dir_fn()
        for name in _list_files(src, patterns):
            if cat == "marking_menus" and name.lower() in defaults:
                continue
            if _match_any(name, retired.get(cat, [])):
                continue
            dst = os.path.join(folder, repo_sub)
            if not os.path.isdir(dst):
                os.makedirs(dst)
            shutil.copyfile(os.path.join(src, name), os.path.join(dst, name))

    hk = os.path.join(folder, "hotkeys")
    os.makedirs(hk)
    for s in cmds.hotkeySet(q=True, hotkeySetArray=True) or []:
        if s == "Maya_Default":
            continue
        try:
            cmds.hotkeySet(s, e=True, ex=os.path.join(hk, s + ".mhk"))
        except Exception as exc:
            print("[maya_sync] hotkey set %s not exported: %s" % (s, exc))
    _write_json(os.path.join(hk, "runtime_commands.json"), _read_runtime_commands())

    patterns = CAPTURE_PATTERNS + list(extra_patterns or []) + \
        list(load_config().get("capture_patterns", []))
    tracked = set(((_read_json(os.path.join(repo_cache(), "prefs.json"), {}) or {})
                   .get("optionvars") or {}).keys())
    optionvars = {}
    for name in sorted(cmds.optionVar(list=True) or []):
        if name in tracked or (_match_any(name, patterns)
                               and not _match_any(name, EXCLUDE_PATTERNS)):
            try:
                value = _read_optionvar(name)
            except Exception:
                value = None
            if value is not None:
                optionvars[name] = value
    try:
        workspace = cmds.workspaceLayoutManager(q=True, current=True)
    except Exception:
        workspace = None
    _write_json(os.path.join(folder, "prefs.json"), {
        "active_hotkey_set": cmds.hotkeySet(q=True, current=True),
        "active_workspace": workspace,
        "playback": _read_playback(),
        "optionvars": optionvars,
    })
    _write_json(os.path.join(folder, "colors.json"), _read_colors())
    _write_json(os.path.join(folder, "panel_layouts.json"), _read_panel_layouts())
    _write_json(os.path.join(folder, "captured_from.json"), {
        "maya_version": _maya_version(),
        "date": datetime.datetime.now().isoformat(),
        "platform": sys.platform,
    })

    zpath = folder.rstrip("/\\") + ".zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, _dirs, files in os.walk(folder):
            for f in files:
                full = os.path.join(base, f)
                zf.write(full, os.path.relpath(full, folder))
    if not quiet:
        print("[maya_sync] Captured your prefs to %s (and %s)" % (folder, zpath))
    return zpath


# --------------------------------------------------------------------------
# push(): send changes you made inside Maya back to GitHub
#
# Needs a fine-grained GitHub token limited to this one repo with
# "Contents: Read and write", saved in ~/maya/prefs_sync/token.txt. The token
# never goes into the repo. Only you (the repo owner) can make such a token.
#
# It is a three-way merge: your current Maya setup is compared with the copy
# you last synced, and only what YOU changed is sent, on top of whatever is on
# GitHub now. So edits Claude pushed in the meantime are kept. If you and the
# repo both changed the same item, the repo's version is kept and you're told.
# --------------------------------------------------------------------------
# JSON files merged key by key: file -> (depth of keys, may keys be removed?)
_JSON_FILES = {
    "prefs.json": (2, False),
    "colors.json": (2, False),
    "panel_layouts.json": (1, True),
    "hotkeys/runtime_commands.json": (1, True),
}
# Folders merged file by file: folder -> patterns
_FILE_DIRS = dict((sub, pats) for _c, sub, _f, pats in FILE_CATEGORIES)
_FILE_DIRS["hotkeys"] = ["*.mhk"]
_DELETE = object()


def _flatten(data, depth):
    if depth == 0 or not isinstance(data, dict):
        return {(): data}
    out = {}
    for key, value in data.items():
        for sub, leaf in _flatten(value, depth - 1).items():
            out[(key,) + sub] = leaf
    return out


def _set_path(data, path, value):
    for key in path[:-1]:
        data = data.setdefault(key, {})
    if value is _DELETE:
        data.pop(path[-1], None)
    else:
        data[path[-1]] = value


def _hash_or_none(path):
    return _file_hash(path) if os.path.isfile(path) else None


def _plan_push(base, local, remote, cfg):
    """Work out what to send. Returns (changes, conflicts, new_files) where
    new_files maps repo path -> bytes or None (delete)."""
    changes, conflicts, new_files = [], [], {}
    on = cfg["sync"]
    skip_dirs = set(sub for c, sub, _f, _p in FILE_CATEGORIES if not on.get(c, True))
    if not on.get("hotkeys", True):
        skip_dirs.add("hotkeys")

    for sub, pats in sorted(_FILE_DIRS.items()):
        if sub in skip_dirs:
            continue
        names = set(_list_files(os.path.join(base, sub), pats)) | \
            set(_list_files(os.path.join(local, sub), pats))
        for name in sorted(names):
            rel = sub + "/" + name
            b = _hash_or_none(os.path.join(base, sub, name))
            l = _hash_or_none(os.path.join(local, sub, name))
            r = _hash_or_none(os.path.join(remote, sub, name))
            if l == b:
                continue  # you didn't touch it
            if r != b and r != l:
                conflicts.append(rel)
                continue
            if r == l:
                continue  # already on GitHub
            if l is None:
                new_files[rel] = None
                changes.append("remove " + rel)
            else:
                with open(os.path.join(local, sub, name), "rb") as fh:
                    new_files[rel] = fh.read()
                changes.append(("add " if b is None else "update ") + rel)

    for rel, (depth, removable) in sorted(_JSON_FILES.items()):
        if rel == "colors.json" and not on.get("colors", True):
            continue
        if rel == "panel_layouts.json" and not on.get("panel_layouts", True):
            continue
        if rel.startswith("hotkeys/") and not on.get("hotkeys", True):
            continue
        parts = rel.split("/")
        b_data = _read_json(os.path.join(base, *parts), {}) or {}
        l_data = _read_json(os.path.join(local, *parts), {}) or {}
        r_data = _read_json(os.path.join(remote, *parts), {}) or {}
        if rel == "prefs.json" and not on.get("settings", True):
            l_data = dict(l_data, optionvars=b_data.get("optionvars", {}),
                          playback=b_data.get("playback", {}))
        bf, lf, rf = _flatten(b_data, depth), _flatten(l_data, depth), _flatten(r_data, depth)
        edits = []
        for path, value in lf.items():
            if path in bf and _same(bf[path], value):
                continue
            edits.append((path, value))
        if removable:
            edits += [(p, _DELETE) for p in bf if p not in lf]
        merged = json.loads(json.dumps(r_data))
        touched = False
        for path, value in sorted(edits, key=lambda e: [u"%s" % k for k in e[0]]):
            label = rel + ": " + ".".join(u"%s" % k for k in path)
            b_val, r_val = bf.get(path, _DELETE), rf.get(path, _DELETE)
            r_changed = not (r_val is b_val or (r_val is not _DELETE and b_val is not _DELETE
                                                and _same(r_val, b_val)))
            same_as_remote = (value is _DELETE and r_val is _DELETE) or \
                (value is not _DELETE and r_val is not _DELETE and _same(value, r_val))
            if same_as_remote:
                continue
            if r_changed:
                conflicts.append(label)
                continue
            _set_path(merged, path, value)
            touched = True
            changes.append(("remove " if value is _DELETE else "set ") + label)
        if touched:
            text = json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            new_files[rel] = text if isinstance(text, bytes) else text.encode("utf-8")
    return changes, conflicts, new_files


def _api(method, path, body=None):
    url = "https://api.github.com/repos/%s/%s" % (REPO, path)
    raw = _http_get(url, "application/vnd.github+json", DOWNLOAD_TIMEOUT, method=method, body=body)
    return json.loads(raw.decode("utf-8")) if raw else {}


def _commit(parent_sha, new_files, message):
    import base64
    tree = []
    for rel, content in sorted(new_files.items()):
        if content is None:
            tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": None})
            continue
        blob = _api("POST", "git/blobs", {"content": base64.b64encode(content).decode("ascii"),
                                          "encoding": "base64"})
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    base_tree = _api("GET", "git/commits/" + parent_sha)["tree"]["sha"]
    new_tree = _api("POST", "git/trees", {"base_tree": base_tree, "tree": tree})
    commit = _api("POST", "git/commits", {"message": message, "tree": new_tree["sha"],
                                          "parents": [parent_sha]})
    _api("PATCH", "git/refs/heads/" + BRANCH, {"sha": commit["sha"], "force": False})
    return commit["sha"]


def push(message=None, dry_run=False):
    """Send the changes you made in Maya to GitHub. Returns the change list.
    dry_run=True only lists what would be sent."""
    if cmds is None:
        raise RuntimeError("run this inside Maya")
    log = _Log()
    if not dry_run and not _token():
        log.warn("no GitHub token. Make a fine-grained token for %s with "
                 "'Contents: Read and write' and save it in %s"
                 % (REPO, os.path.join(sync_dir(), "token.txt")))
        _message(log)
        return []
    base = repo_cache()
    base_sha = (_read_json(_repo_state_path(), {}) or {}).get("sha")
    if not base_sha or not os.path.isdir(base):
        log.warn("sync once before pushing so there is a copy to compare with")
        return []
    remote_sha = latest_commit()
    remote = base
    tmp = tempfile.mkdtemp(prefix="maya_sync_")
    try:
        if remote_sha != base_sha:
            remote = os.path.join(tmp, "remote")
            _download(remote_sha, log, dest=remote)
        local = os.path.join(tmp, "local")
        capture(local, quiet=True)
        changes, conflicts, new_files = _plan_push(base, local, remote, load_config(remote))
        for c in conflicts:
            log.warn("kept GitHub's version of %s (it changed there too)" % c)
        for c in changes:
            log.change(c)
        if not new_files:
            log.info("nothing to push")
        elif dry_run:
            log.info("%d change(s) would be pushed" % len(changes))
        else:
            msg = message or "Update from Maya %s on %s" % (_maya_version(), sys.platform)
            if len(changes) <= 8:
                msg += "\n\n" + "\n".join("- " + c for c in changes)
            new_sha = _commit(remote_sha, new_files, msg)
            log.info("Pushed %d change(s) to %s @ %s" % (len(changes), REPO, new_sha[:7]))
        if not dry_run and (new_files or remote_sha != base_sha):
            fetch(log)  # refresh the local copy to the new commit
            # Bring in anything that changed on GitHub in the meantime and
            # record what is now installed, so the next check is clean.
            pulled = _run(True, ("files", "ui"), offline=True, quiet=True)
            for c in pulled.changes:
                log.info("  pulled from GitHub: " + c)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not dry_run:
        _message(log)
    return log.changes


# --------------------------------------------------------------------------
# Window (the shelf button opens this)
# --------------------------------------------------------------------------
WINDOW = "mayaSyncWin"


def show():
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    cmds.window(WINDOW, title="Maya Prefs Sync", widthHeight=(360, 210), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnOffset=("both", 8))
    state = _read_json(_local_state_path(), {}) or {}
    cmds.text(label="Repo: %s (%s)" % (REPO, BRANCH), align="left")
    cmds.text(label="Last sync: %s @ %s" % ((state.get("synced") or "never")[:16].replace("T", " "),
                                            (state.get("sha") or "-")[:7]), align="left")
    cmds.separator(height=6, style="in")
    cmds.button(label="Pull from GitHub", height=30, command=lambda *_: sync(),
                annotation="Make Maya match the repo")
    cmds.button(label="Check (change nothing)", command=lambda *_: check())
    cmds.separator(height=6, style="in")
    field = cmds.textField(placeholderText="What did you change? (optional)")
    cmds.button(label="Push my Maya changes to GitHub", height=30,
                command=lambda *_: push(cmds.textField(field, q=True, text=True) or None),
                annotation="Needs your token in ~/maya/prefs_sync/token.txt")
    cmds.showWindow(WINDOW)
