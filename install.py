"""
Drag and drop this file into a Maya viewport to set Maya up from GitHub.

This one file is all you need on a new machine. It:
  1. asks for your GitHub token (optional, only needed to push from Maya),
  2. downloads the sync tool (tools/maya_sync.py) from the repo into
     ~/maya/scripts, shared by every Maya version,
  3. makes Maya sync on every startup and adds a "Prefs Sync" shelf button,
  4. pulls all your prefs from GitHub.
"""
import os
import shutil

try:
    from urllib.request import Request, urlopen
except ImportError:  # Python 2 (Maya 2018-2020)
    from urllib2 import Request, urlopen

import maya.cmds as cmds
import maya.mel as mel

REPO = "AlexanderCuenin/maya-prefs"
BRANCH = "main"

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


def _download_tool(token):
    url = "https://api.github.com/repos/%s/contents/tools/maya_sync.py?ref=%s" % (REPO, BRANCH)
    req = Request(url)
    req.add_header("Accept", "application/vnd.github.raw")
    req.add_header("User-Agent", "maya-sync-installer")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    resp = urlopen(req, timeout=30)
    try:
        return resp.read()
    finally:
        resp.close()


def onMayaDroppedPythonFile(*_args):
    app = os.path.normpath(cmds.internalVar(userAppDir=True))
    scripts = os.path.join(app, "scripts")
    sync_dir = os.path.join(app, "prefs_sync")
    for d in (scripts, sync_dir):
        if not os.path.isdir(d):
            os.makedirs(d)

    token_file = os.path.join(sync_dir, "token.txt")
    token = open(token_file).read().strip() if os.path.isfile(token_file) else ""
    if not token:
        res = cmds.promptDialog(
            title="Maya Prefs Sync",
            message="GitHub token for pushing from Maya (optional, you can add it later).\n"
                    "It is saved only on this computer, in\n" + token_file,
            button=["Save", "Skip"], defaultButton="Save", cancelButton="Skip", dismissString="Skip")
        token = cmds.promptDialog(q=True, text=True).strip() if res == "Save" else ""
        if token:
            with open(token_file, "w") as fh:
                fh.write(token)

    target = os.path.join(scripts, "maya_sync.py")
    try:
        data = _download_tool(token)
        with open(target, "wb") as fh:
            fh.write(data)
    except Exception as exc:
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "maya_sync.py")
        if os.path.isfile(local):
            shutil.copyfile(local, target)
            print("Could not download the sync tool (%s); used the copy next to install.py" % exc)
        elif not os.path.isfile(target):
            cmds.confirmDialog(title="Maya Prefs Sync", button=["OK"], message=(
                "Could not download the sync tool from GitHub:\n%s\n\n"
                "Check your internet connection (and token, if the repo is private) "
                "and drag install.py in again." % exc))
            return

    setup = _user_setup_path(scripts)
    text = open(setup).read() if os.path.isfile(setup) else ""
    if BLOCK_START not in text:
        with open(setup, "a") as fh:
            fh.write(("\n" if text and not text.endswith("\n") else "") + BLOCK)

    import sys
    sys.modules.pop("maya_sync", None)
    import maya_sync
    maya_sync.sync()  # pull everything first, shelves included
    maya_sync.add_menu()

    # Shelf button, unless one of the synced shelves already has it
    top = mel.eval("$_ms_tmp = $gShelfTopLevel")
    have = False
    for sh in cmds.tabLayout(top, q=True, childArray=True) or []:
        for b in cmds.shelfLayout(sh, q=True, childArray=True) or []:
            if cmds.objectTypeUI(b) == "shelfButton" and \
                    cmds.shelfButton(b, q=True, label=True) == "Prefs Sync":
                have = True
    shelf = cmds.tabLayout(top, q=True, selectTab=True)
    if not have:
        cmds.shelfButton(parent=shelf, label="Prefs Sync", imageOverlayLabel="Sync",
                         image1="refresh.png", sourceType="python",
                         annotation="Pull prefs from GitHub, check them, or push your changes",
                         command="import maya_sync\nmaya_sync.show()")
        mel.eval("saveAllShelves $gShelfTopLevel")
    maya_sync.show()
    cmds.confirmDialog(title="Maya Prefs Sync", button=["OK"], message=(
        "Installed.\n\nMaya now syncs with %s every time it starts.\n"
        "Pull, check and push from the 'Prefs Sync' menu or shelf button.%s\n\n"
        "Startup hook: %s" % (maya_sync.REPO,
                              "" if have else "\nThe new shelf button stays if you push once.",
                              setup)))
