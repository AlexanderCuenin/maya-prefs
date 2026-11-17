"""Mock round trip for maya_sync: fake Maya + fake GitHub, no network.
Run: python tests/test_sync_mock.py"""
import os, sys, tempfile, shutil, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import maya_sync as ms

class FakeMaya(object):
    def __init__(self, root, populated):
        self.root = root
        self.prefs = os.path.join(root, "2024", "prefs")
        for d in ("markingMenus", "hotkeys", "workspaces", "shelves"):
            os.makedirs(os.path.join(self.prefs, d))
        self.ov = {}; self.hksets = {"Maya_Default": ""}; self.hkcur = "Maya_Default"
        self.rtc = {}; self.rgb = {"graphEditorBackground": [0.2,0.2,0.2]}
        self.panels = {}; self.tangent = ["auto", "auto"]
        if populated:
            for f in ("menu_AnimTools.mel", "menu_PoseTools.mel",
                      "menu_ChangePanelLayout.mel", "menu_ShippedWithMaya.mel"):
                open(os.path.join(self.prefs, "markingMenus", f), "w").write("// mm")
            open(os.path.join(self.prefs, "workspaces", "MyAnim.json"), "w").write("{}")
            open(os.path.join(self.prefs, "shelves", "shelf_Anim.mel"), "w").write("// shelf")
            self.ov = {"timeSliderTickSize": 3, "graphEditorCurveColor": [1, 2, 3],
                       "playbackSpeed": 1.0, "RecentFilesList": ["a.ma"],
                       "defaultTangentIn": "spline", "unrelatedPref": 1,
                       "ghostFramesList": []}
            self.hksets["AlexKeys"] = "keys!"; self.hkcur = "AlexKeys"
            self.rtc["myBreakdown"] = {"command": "print 1", "commandLanguage": "python"}
            self.rgb["graphEditorBackground"] = [0.1, 0.3, 0.5]
            self.panels["cfg1"] = {"label": "AnimLayout", "configString": "global string $gMainPane; paneLayout -e -cn \"horizontal2\" $gMainPane;",
                                   "panels": [(False, "Persp", "modelPanel", "c", "e"), (False, "Graph", "scriptedPanel", "c2", "e2")]}
            self.tangent = ["spline", "stepped"]

    # --- cmds API surface used by the tool
    def internalVar(self, userPrefDir=False, userMarkingMenuDir=False, userShelfDir=False):
        if userPrefDir: return self.prefs + "/"
        if userMarkingMenuDir: return os.path.join(self.prefs, "markingMenus") + "/"
        if userShelfDir: return os.path.join(self.prefs, "shelves") + "/"
    def about(self, version=False, apiVersion=False):
        return "2024" if version else 20240000
    def savePrefs(self, **kw): pass
    def optionVar(self, exists=None, q=None, list=False, intValue=None, floatValue=None, stringValue=None,
                  clearArray=None, intValueAppend=None, floatValueAppend=None, stringValueAppend=None):
        if list: return sorted(self.ov)
        if exists is not None: return exists in self.ov
        if q is not None:
            v = self.ov.get(q, 0); return v[:] if isinstance(v, type([])) else v
        for pair in (intValue, floatValue, stringValue):
            if pair: self.ov[pair[0]] = pair[1]; return
        if clearArray: self.ov[clearArray] = []; return
        for pair in (intValueAppend, floatValueAppend, stringValueAppend):
            if pair: self.ov.setdefault(pair[0], []).append(pair[1]); return
    def hotkeySet(self, name=None, q=False, e=False, current=False, hotkeySetArray=False,
                  ex=None, ip=None, delete=False, exists=False):
        if exists: return name in self.hksets
        if q and current: return self.hkcur
        if q and hotkeySetArray: return list(self.hksets)
        if ex: open(ex, "w").write(name + "|" + self.hksets[name]); return
        if ip:
            n, body = open(ip).read().split("|", 1); self.hksets[n] = body; return
        if delete: del self.hksets[name]; return
        if e and current: self.hkcur = name
    def runTimeCommand(self, name=None, q=False, e=False, userCommandArray=False, exists=False, delete=False, **kw):
        if userCommandArray: return list(self.rtc)
        if exists: return name in self.rtc
        if q:
            k = list(kw)[0]
            if k not in self.rtc[name]: raise RuntimeError("no flag")
            return self.rtc[name][k]
        if delete: del self.rtc[name]; return
        kw.pop("default", None); self.rtc[name] = kw
    def workspaceLayoutManager(self, q=False, current=False): return "MyAnim" if self.ov else "Maya Classic"
    def getPanel(self, allConfigs=False): return list(self.panels)
    def panelConfiguration(self, cfg=None, q=False, label=None, userCreated=None, numberOfPanels=False,
                           configString=None, labelStrings=False, typeStrings=False, createStrings=False,
                           editStrings=False, isFixedState=False, sceneConfig=None, addPanel=None):
        if q:
            c = self.panels[cfg]
            if userCreated: return True
            if numberOfPanels: return len(c["panels"])
            if label: return c["label"]
            if configString: return c["configString"]
            idx = {"labelStrings": 1, "typeStrings": 2, "createStrings": 3, "editStrings": 4, "isFixedState": 0}
            for k, i in idx.items():
                if locals()[k]: return [p[i] for p in c["panels"]]
        self.panels["cfg%d" % (len(self.panels) + 10)] = {"label": label, "configString": configString, "panels": addPanel}
    def deleteUI(self, n, panelConfig=False): del self.panels[n]
    def playbackOptions(self, q=False, **kw):
        if q: return {"playbackSpeed": 0.0, "maxPlaybackSpeed": 1.0, "loop": "continuous", "by": 1.0, "view": "active"}[list(kw)[0]]
    def currentUnit(self, q=False, time=None): return "ntsc" if q else None
    def keyTangent(self, q=False, g=False, inTangentType=False, outTangentType=False, weightedTangents=False):
        if q:
            if inTangentType: return [self.tangent[0]]
            if outTangentType: return [self.tangent[1]]
            return [False]
        if isinstance(inTangentType, str): self.tangent[0] = inTangentType
        if isinstance(outTangentType, str): self.tangent[1] = outTangentType
    def autoKeyframe(self, q=False, state=None): return True if q else None
    def displayRGBColor(self, name=None, *vals, **kw):
        if kw.get("list"): return ["%s %s" % (k, " ".join(map(str, v))) for k, v in self.rgb.items()]
        self.rgb[name] = list(vals)
    def displayColor(self, *a, **kw): raise RuntimeError("n/a")
    def colorIndex(self, *a, **kw): raise RuntimeError("n/a")


class Maya(FakeMaya):
    """Adds what maya_sync uses on top of the export/import fake."""
    def __init__(self, root, populated):
        FakeMaya.__init__(self, root, populated)
        self.unit, self.ws, self.deferred = "film", "Maya Classic", []
        if populated:
            self.ws, self.unit = "MyAnim", "ntsc"
            open(os.path.join(self.prefs, "hotkeys", "AlexKeys.mhk"), "w").write("raw")
    def internalVar(self, userAppDir=False, **kw):
        if userAppDir: return self.root + "/"
        return FakeMaya.internalVar(self, **kw)
    def about(self, batch=False, **kw):
        return False if batch else FakeMaya.about(self, **kw)
    def currentUnit(self, q=False, time=None):
        if q: return self.unit
        self.unit = time
    def workspaceLayoutManager(self, q=False, current=False, setCurrent=None):
        if setCurrent: self.ws = setCurrent; return
        return self.ws
    def evalDeferred(self, fn, lowestPriority=False): self.deferred.append(fn)
    def inViewMessage(self, **kw): self.last_message = kw.get("amg")


class Mel(object):
    def eval(self, s):
        if "gShelfTopLevel" in s or "gMainWindow" in s: return None  # no UI in tests
        if "saveCurrentWorkspace" in s: return None
        raise AssertionError("unexpected mel: " + s)


class FakeGitHub(object):
    """Commits are folders; head is the branch tip."""
    def __init__(self, root):
        self.root, self.n, self.online = root, 0, True
        os.makedirs(root)
        self.head = self._new(None, {"README.md": b"# prefs\n", "sync_config.json": b"{}",
                                     "tools/maya_sync.py": open(ms.__file__.replace(".pyc", ".py"), "rb").read()})
    def _dir(self, sha): return os.path.join(self.root, sha)
    def _new(self, parent, files):
        self.n += 1
        sha = ("%040d" % self.n)
        d = self._dir(sha)
        if parent: shutil.copytree(self._dir(parent), d)
        else: os.makedirs(d)
        for rel, data in files.items():
            p = os.path.join(d, *rel.split("/"))
            if data is None:
                os.remove(p); continue
            if not os.path.isdir(os.path.dirname(p)): os.makedirs(os.path.dirname(p))
            open(p, "wb").write(data)
        return sha
    def edit(self, files):  # what Claude does with a git push
        self.head = self._new(self.head, files)
    def read(self, rel):
        return open(os.path.join(self._dir(self.head), *rel.split("/")), "rb").read()
    def exists(self, rel):
        return os.path.exists(os.path.join(self._dir(self.head), *rel.split("/")))
    # patched into maya_sync
    def latest_commit(self):
        if not self.online: raise ms.URLError("offline")
        return self.head
    def download(self, sha, log, dest=None):
        dest = dest or ms.repo_cache()
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(self._dir(sha), dest)
    def commit(self, parent, files, message):
        assert parent == self.head, "push must build on the branch tip"
        self.head = self._new(parent, files)
        self.last_message = message
        return self.head


def use(maya):
    ms.cmds, ms.mel = maya, Mel()


tmp = tempfile.mkdtemp()
try:
    gh = FakeGitHub(os.path.join(tmp, "github"))
    ms.latest_commit, ms._download, ms._commit = gh.latest_commit, gh.download, gh.commit
    ms._token = lambda: "tok"
    ms._self_update = lambda root, log: None  # don't overwrite the module under test

    inst = os.path.join(tmp, "install", "scripts", "others")
    os.makedirs(inst)
    open(os.path.join(inst, "menu_ShippedWithMaya.mel"), "w").write("")
    os.environ["MAYA_LOCATION"] = os.path.join(tmp, "install")

    # 1. Machine A: install, first sync (empty repo), then push to seed it
    a = Maya(os.path.join(tmp, "A"), True)
    use(a)
    assert ms.sync() == []
    seeded = ms.push("seed")
    print("seed:", len(seeded), "changes")
    prefs = json.loads(gh.read("prefs.json"))
    assert prefs["optionvars"]["timeSliderTickSize"] == 3
    assert "RecentFilesList" not in prefs["optionvars"] and "unrelatedPref" not in prefs["optionvars"]
    assert prefs["active_hotkey_set"] == "AlexKeys" and prefs["active_workspace"] == "MyAnim"
    assert prefs["playback"]["fps"] == "ntsc"
    assert gh.exists("marking_menus/menu_AnimTools.mel")
    assert not gh.exists("marking_menus/menu_ChangePanelLayout.mel")  # Maya default left out
    assert gh.exists("shelves/shelf_Anim.mel") and gh.exists("hotkeys/AlexKeys.mhk")
    assert "AnimLayout" in json.loads(gh.read("panel_layouts.json"))
    assert ms.push(dry_run=True) == []          # nothing left to push
    assert ms.check() == []                      # and A matches the repo

    # 2. Machine B (fresh Maya) gets everything at startup
    b = Maya(os.path.join(tmp, "B"), False)
    use(b)
    ms.startup()
    assert len(b.deferred) == 2  # settings pass + menu
    for fn in b.deferred: fn()
    assert b.ov["timeSliderTickSize"] == 3 and b.ov["graphEditorCurveColor"] == [1, 2, 3]
    assert b.unit == "ntsc" and b.tangent == ["spline", "stepped"] and b.ws == "MyAnim"
    assert b.hkcur == "AlexKeys" and b.rtc["myBreakdown"]["command"] == "print 1"
    assert b.rgb["graphEditorBackground"] == [0.1, 0.3, 0.5]
    assert [p["label"] for p in b.panels.values()] == ["AnimLayout"]
    assert os.path.exists(os.path.join(b.prefs, "shelves", "shelf_Anim.mel"))
    assert sorted(os.listdir(os.path.join(b.prefs, "markingMenus"))) == ["menu_AnimTools.mel", "menu_PoseTools.mel"]
    assert os.listdir(os.path.join(b.root, "prefs_sync", "backups")), "first sync must back up"
    assert ms.check() == [], ms.check()
    assert b.last_message == "Prefs up to date"

    # 3. Claude edits the repo: change a setting, add a menu, delete a shelf
    p = json.loads(gh.read("prefs.json")); p["optionvars"]["timeSliderTickSize"] = 5
    gh.edit({"prefs.json": json.dumps(p, indent=2).encode(),
             "marking_menus/menu_NewMM.mel": b"// new", "shelves/shelf_Anim.mel": None})
    changes = ms.sync()
    print("pull after Claude edit:", changes)
    assert b.ov["timeSliderTickSize"] == 5
    assert os.path.exists(os.path.join(b.prefs, "markingMenus", "menu_NewMM.mel"))
    assert not os.path.exists(os.path.join(b.prefs, "shelves", "shelf_Anim.mel"))
    assert ms.check() == []

    # 4. Drift: a local change shows up in check and sync puts it back
    b.ov["timeSliderTickSize"] = 9
    assert len(ms.check()) == 1 and b.ov["timeSliderTickSize"] == 9
    ms.sync()
    assert b.ov["timeSliderTickSize"] == 5

    # 5. Push merges: B changes one thing while Claude changes another
    b.ov["defaultTangentIn"] = "linear"
    open(os.path.join(b.prefs, "markingMenus", "menu_PoseTools.mel"), "w").write("// edited in maya")
    p = json.loads(gh.read("prefs.json")); p["optionvars"]["graphEditorCurveColor"] = [4, 5, 6]
    gh.edit({"prefs.json": json.dumps(p, indent=2).encode()})
    pushed = ms.push("tweaks")
    print("push with remote edit:", pushed)
    p = json.loads(gh.read("prefs.json"))
    assert p["optionvars"]["defaultTangentIn"] == "linear"       # B's change sent
    assert p["optionvars"]["graphEditorCurveColor"] == [4, 5, 6]  # Claude's change kept
    assert gh.read("marking_menus/menu_PoseTools.mel") == b"// edited in maya"
    assert b.ov["graphEditorCurveColor"] == [4, 5, 6]              # and B pulled it in
    assert ms.check() == []

    # 6. Conflict: both change the same setting -> GitHub's value wins, reported
    b.ov["timeSliderTickSize"] = 7
    p = json.loads(gh.read("prefs.json")); p["optionvars"]["timeSliderTickSize"] = 6
    gh.edit({"prefs.json": json.dumps(p, indent=2).encode()})
    assert ms.push() == []
    assert json.loads(gh.read("prefs.json"))["optionvars"]["timeSliderTickSize"] == 6
    assert b.ov["timeSliderTickSize"] == 6

    # 7. Deleting something in Maya and pushing removes it from the repo
    os.remove(os.path.join(b.prefs, "markingMenus", "menu_NewMM.mel"))
    ms.push()
    assert not gh.exists("marking_menus/menu_NewMM.mel")

    # 8. Machine A (still on the old copy) catches up; offline keeps last copy
    use(a)
    ms.sync()
    assert a.ov["timeSliderTickSize"] == 6 and not os.path.exists(os.path.join(a.prefs, "shelves", "shelf_Anim.mel"))
    gh.online = False
    a.ov["timeSliderTickSize"] = 1
    ms.sync()
    assert a.ov["timeSliderTickSize"] == 6

    # 9. Retired files are moved out of Maya and never captured
    gh.online = True
    use(b)
    open(os.path.join(b.prefs, "markingMenus", "menu_curveTangents_MM.mel"), "w").write("// old")
    cfg = json.loads(gh.read("sync_config.json"))
    cfg["retired"] = {"marking_menus": ["menu_curveTangents*.mel"]}
    gh.edit({"sync_config.json": json.dumps(cfg).encode()})
    assert any("retire menu_curveTangents_MM.mel" in c for c in ms.sync())
    assert not os.path.exists(os.path.join(b.prefs, "markingMenus", "menu_curveTangents_MM.mel"))
    assert os.path.exists(os.path.join(b.root, "prefs_sync", "retired", "marking_menus", "menu_curveTangents_MM.mel"))
    open(os.path.join(b.prefs, "markingMenus", "menu_curveTangents_MM.mel"), "w").write("// old")
    assert not any("curveTangents" in c for c in ms.push(dry_run=True))

    # 10. A repo menu with a built-in's name is installed and never dropped by push
    gh.edit({"marking_menus/menu_ChangePanelLayout.mel": b"// alex's own version"})
    ms.sync()
    assert open(os.path.join(b.prefs, "markingMenus", "menu_ChangePanelLayout.mel")).read() == "// alex's own version"
    assert ms.push(dry_run=True) == []

    # 11. No token -> push refuses politely
    gh.online = True
    ms._token = lambda: ""
    assert ms.push() == []
    print("ALL SYNC CHECKS PASSED")
finally:
    shutil.rmtree(tmp)
