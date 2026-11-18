"""
Build marking menus from readable sources.

Each marking menu lives in ``marking_menus_src/<menu name>/``:

    menu.json            the layout: one entry per item, in order
    <item>.py / .mel     the code each item runs, as a normal script file

``python tools/marking_menus.py build`` turns every source folder into the
``marking_menus/menu_<name>.mel`` file Maya reads (that's what gets synced).
``python tools/marking_menus.py extract path/to/menu_X.mel`` goes the other way,
for a marking menu made in Maya's Marking Menu Editor.

menu.json item fields:
    label      text shown in the menu
    position   N, NE, E, SE, S, SW, W, NW, or leave it out for the list below
    script     file next to menu.json; .py runs as Python, .mel as MEL
    bold       true / false (default false)
    icon       image shown next to the item (optional; a missing file is ignored)
    divider    true for a separator line in the list
    flags      any other menuItem flag Maya should get, e.g. {"echoCommand": 1}

Runs with plain Python 2.7 or 3 (no Maya needed).
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "marking_menus_src")
OUT = os.path.join(ROOT, "marking_menus")

# The order and defaults Maya's Marking Menu Editor writes.
_ORDER = ["label", "divider", "dividerLabel", "subMenu", "tearOff", "command",
          "optionBox", "header", "enable", "visible", "data", "radialPosition",
          "allowOptionBoxes", "postMenuCommandOnce", "enableCommandRepeat",
          "image", "echoCommand", "italicized", "boldFont", "sourceType", "longDivider"]
_DEFAULTS = {"divider": 0, "subMenu": 0, "tearOff": 0, "optionBox": 0, "header": 0,
             "enable": 1, "visible": 1, "data": 0, "allowOptionBoxes": 1,
             "postMenuCommandOnce": 0, "enableCommandRepeat": 1, "echoCommand": 0,
             "italicized": 0, "boldFont": 0, "longDivider": 1}
_STRING_FLAGS = {"label", "dividerLabel", "command", "radialPosition", "sourceType", "image"}


def _mel_quote(text):
    out = text.replace("\\", "\\\\").replace("\"", "\\\"")
    out = out.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return "\"" + out + "\""


def _mel_unquote(raw):
    body = raw[1:-1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), body)


def _slug(text):
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return s or "item"


# --------------------------------------------------------------------------
# build: sources -> .mel
# --------------------------------------------------------------------------
def _item_flags(item, folder):
    flags = {}
    flags["label"] = item.get("label", "")
    if item.get("divider"):
        flags["divider"] = 1
        flags["dividerLabel"] = item.get("label", "")
        flags["sourceType"] = "mel"
    else:
        script = item.get("script")
        if script:
            with io.open(os.path.join(folder, script), "r", encoding="utf-8") as fh:
                code = fh.read()
            flags["command"] = code.rstrip("\n")
            flags["sourceType"] = "python" if script.lower().endswith(".py") else "mel"
        else:
            flags["command"] = ""
            flags["sourceType"] = "mel"
    if item.get("position"):
        flags["radialPosition"] = item["position"]
    if item.get("icon"):
        flags["image"] = item["icon"]
    flags["boldFont"] = 1 if item.get("bold") else 0
    flags.update(item.get("flags", {}))
    return flags


def _emit(flags, index):
    lines = ["    menuItem"]
    for name in _ORDER:
        if name in ("command", "echoCommand") and flags.get("divider"):
            continue
        if name in flags:
            value = flags[name]
            if value is None:  # flag left out on purpose
                continue
        elif name in _DEFAULTS:
            value = _DEFAULTS[name]
        else:
            continue
        if name in _STRING_FLAGS:
            lines.append("        -%s %s " % (name, _mel_quote(value)))
        else:
            lines.append("        -%s %s" % (name, int(value)))
    for name in sorted(set(flags) - set(_ORDER)):  # anything extra
        value = flags[name]
        if value is None:
            continue
        lines.append("        -%s %s" % (name, _mel_quote(value) if isinstance(value, type(u"")) or isinstance(value, str) else int(value)))
    lines.append("        menuEditorMenuItem%d;" % index)
    return "\n".join(lines) + "\n"


def build_menu(folder):
    with io.open(os.path.join(folder, "menu.json"), "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    parts = [u"\n"]
    for i, item in enumerate(spec["items"], 1):
        parts.append(_emit(_item_flags(item, folder), i))
        parts.append(u"\n")
    parts.append(u"setParent -m ..;\n\n")
    return u"".join(parts), spec.get("file") or ("menu_%s.mel" % os.path.basename(folder))


_BUILT = os.path.join(SRC, ".built.json")  # hash of each .mel we last wrote


def _sha1(data):
    import hashlib
    return hashlib.sha1(data).hexdigest()


def build(out_dir=OUT, force=False):
    """Write marking_menus/*.mel from the sources. A .mel that was changed
    since the last build (e.g. edited in Maya and pushed from there) is left
    alone with a warning: run extract on it first, or pass force=True."""
    if not os.path.isdir(SRC):
        return []
    built = {}
    if os.path.isfile(_BUILT):
        with io.open(_BUILT, "r", encoding="utf-8") as fh:
            built = json.load(fh)
    made = []
    for name in sorted(os.listdir(SRC)):
        folder = os.path.join(SRC, name)
        if not os.path.isfile(os.path.join(folder, "menu.json")):
            continue
        text, fname = build_menu(folder)
        data = text.encode("utf-8")
        target = os.path.join(out_dir, fname)
        if os.path.isfile(target) and not force:
            with open(target, "rb") as fh:
                current = _sha1(fh.read())
            if current not in (built.get(fname), _sha1(data)):
                print("SKIPPED marking_menus/%s: it changed outside the sources. "
                      "Run: python tools/marking_menus.py extract marking_menus/%s" % (fname, fname))
                continue
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with open(target, "wb") as fh:
            fh.write(data)
        built[fname] = _sha1(data)
        made.append(fname)
        print("built marking_menus/%s" % fname)
    with io.open(_BUILT, "w", encoding="utf-8", newline="\n") as fh:
        text = json.dumps(built, indent=2, sort_keys=True)
        fh.write(text if isinstance(text, type(u"")) else text.decode("utf-8"))
        fh.write(u"\n")
    return made


# --------------------------------------------------------------------------
# extract: .mel -> sources
# --------------------------------------------------------------------------
_FLAG_RE = re.compile(r'^\s*-(\w+)\s+("(?:[^"\\]|\\.)*"|\S+)\s*$')


def parse_mel(text):
    items, current = [], None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "menuItem":
            current = []
            continue
        if current is None:
            continue
        m = _FLAG_RE.match(line)
        if m:
            raw = m.group(2)
            value = _mel_unquote(raw) if raw.startswith("\"") else int(raw)
            current.append((m.group(1), value))
        elif stripped.endswith(";"):
            items.append(current)
            current = None
    return items


def extract(mel_path, out_root=SRC):
    with io.open(mel_path, "r", encoding="utf-8") as fh:
        items = parse_mel(fh.read())
    fname = os.path.basename(mel_path)
    stem = fname[:-4]
    menu_name = stem[5:] if stem.lower().startswith("menu_") else stem
    folder = os.path.join(out_root, menu_name)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    spec, used = {"file": fname, "items": []}, set()
    for flags in items:
        f = dict(flags)
        entry = {"label": f.get("label", "")}
        if f.get("radialPosition"):
            entry["position"] = f["radialPosition"]
        if f.get("divider"):
            entry["divider"] = True
        if f.get("boldFont"):
            entry["bold"] = True
        if f.get("image"):
            entry["icon"] = f["image"]
        if not f.get("divider") and f.get("command", "") != "":
            ext = ".py" if f.get("sourceType") == "python" else ".mel"
            base = _slug(entry["label"])  # positions live only in menu.json
            script, n = base + ext, 2
            while script in used:
                script, n = "%s_%d%s" % (base, n, ext), n + 1
            used.add(script)
            with io.open(os.path.join(folder, script), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(f["command"] + "\n")
            entry["script"] = script
        # keep anything that differs from what build() would write anyway
        rebuilt = _item_flags(dict(entry, script=None), folder)
        extra = {}
        for k, v in f.items():
            if k in ("label", "dividerLabel", "command", "radialPosition", "boldFont", "image"):
                continue
            if k == "sourceType" and entry.get("script"):
                continue
            if k == "sourceType" and v == "mel":
                continue
            if v != rebuilt.get(k, _DEFAULTS.get(k)):
                extra[k] = v
        for k in _ORDER:  # flags Maya didn't write for this item
            if k in f or k in ("command", "echoCommand") and f.get("divider"):
                continue
            if k in rebuilt or k in _DEFAULTS:
                extra[k] = None
        if extra:
            entry["flags"] = extra
        spec["items"].append(entry)
    with io.open(os.path.join(folder, "menu.json"), "w", encoding="utf-8", newline="\n") as fh:
        text = json.dumps(spec, indent=2, ensure_ascii=False)
        fh.write(text if isinstance(text, type(u"")) else text.decode("utf-8"))
        fh.write(u"\n")
    print("extracted %s -> marking_menus_src/%s (%d items)" % (fname, menu_name, len(items)))
    return folder


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "build":
        build(force="--force" in args)
    elif args[0] == "extract" and len(args) > 1:
        for p in args[1:]:
            extract(p)
    else:
        print(__doc__)
        sys.exit(1)
