"""
Drag and drop this file into a Maya viewport to install Maya Prefs Sync.

It copies maya_sync.py (next to this file) into ~/maya/scripts so every Maya
version can use it, makes Maya sync on startup, adds a "Sync" shelf button,
and asks for your GitHub token (only needed to push changes from Maya).
"""
import os
import shutil

import maya.cmds as cmds
import maya.mel as mel

BLOCK_START = "# >>> maya_sync (added by install.py)"
BLOCK = BLOCK_START + """
try:
    import maya_sync
    maya_sync.startup()
except Exception as _exc:
    print("maya_sync startup failed: %s" % _exc)
# <<< maya_sync
"""


def _user_setup_path(shared_scripts):
    """Maya runs only the first userSetup.py it finds, and the version folder
    comes first. Use that one if it exists, otherwise the shared one."""
    version_scripts = os.path.normpath(cmds.internalVar(userScriptDir=True))
    candidate = os.path.join(version_scripts, "userSetup.py")
    if os.path.isfile(candidate):
        return candidate
    return os.path.join(shared_scripts, "userSetup.py")


def onMayaDroppedPythonFile(*_args):
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "maya_sync.py")
    if not os.path.isfile(src):
        cmds.confirmDialog(title="Maya Prefs Sync", message="maya_sync.py must sit next to install.py")
        return
    app = os.path.normpath(cmds.internalVar(userAppDir=True))
    scripts = os.path.join(app, "scripts")
    if not os.path.isdir(scripts):
        os.makedirs(scripts)
    shutil.copyfile(src, os.path.join(scripts, "maya_sync.py"))

    setup = _user_setup_path(scripts)
    text = open(setup).read() if os.path.isfile(setup) else ""
    if BLOCK_START not in text:
        with open(setup, "a") as fh:
            fh.write(("\n" if text and not text.endswith("\n") else "") + BLOCK)

    sync_dir = os.path.join(app, "prefs_sync")
    if not os.path.isdir(sync_dir):
        os.makedirs(sync_dir)
    token_file = os.path.join(sync_dir, "token.txt")
    if not os.path.isfile(token_file):
        res = cmds.promptDialog(
            title="Maya Prefs Sync",
            message="GitHub token for pushing from Maya (optional, you can add it later).\n"
                    "It is saved only on this computer, in\n" + token_file,
            button=["Save", "Skip"], defaultButton="Save", cancelButton="Skip", dismissString="Skip")
        token = cmds.promptDialog(q=True, text=True).strip() if res == "Save" else ""
        if token:
            with open(token_file, "w") as fh:
                fh.write(token)

    shelf = cmds.tabLayout(mel.eval("$_ms_tmp = $gShelfTopLevel"), q=True, selectTab=True)
    exists = [b for b in (cmds.shelfLayout(shelf, q=True, childArray=True) or [])
              if cmds.objectTypeUI(b) == "shelfButton"
              and cmds.shelfButton(b, q=True, label=True) == "Prefs Sync"]
    if not exists:
        cmds.shelfButton(parent=shelf, label="Prefs Sync", imageOverlayLabel="Sync",
                         image1="refresh.png", sourceType="python",
                         annotation="Pull prefs from GitHub, check them, or push your changes",
                         command="import maya_sync\nmaya_sync.show()")
        mel.eval("saveAllShelves $gShelfTopLevel")

    import sys
    sys.modules.pop("maya_sync", None)
    import maya_sync
    maya_sync.sync()
    maya_sync.show()
    cmds.confirmDialog(title="Maya Prefs Sync", button=["OK"], message=(
        "Installed.\n\nMaya now syncs with %s every time it starts.\n"
        "The 'Prefs Sync' button on shelf '%s' pulls, checks and pushes.\n\n"
        "Startup hook: %s" % (maya_sync.REPO, shelf, setup)))
