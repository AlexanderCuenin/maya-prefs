"""
Paste Key Times
Graph Editor: inserts keys on the frames saved by Copy Key Times. Curves that
already have a key on a frame are skipped. Inserted keys keep the curve shape,
and they get added to your selection.

Target curves: curves with selected keys, otherwise every curve on the
selected objects.
"""
import maya.cmds as cmds

VAR = "animTools_copiedKeyTimes"


def paste_key_times():
    if not cmds.optionVar(exists=VAR):
        cmds.warning("Nothing copied yet. Run Copy Key Times first.")
        return
    times = cmds.optionVar(q=VAR)
    if not isinstance(times, list):
        times = [times]
    if not times or times == [0]:
        cmds.warning("Nothing copied yet. Run Copy Key Times first.")
        return

    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not curves:
        sel = cmds.ls(selection=True)
        curves = (cmds.keyframe(sel, q=True, name=True) or []) if sel else []
    if not curves:
        cmds.warning("Select keys or objects to paste onto.")
        return

    added = 0
    cmds.undoInfo(openChunk=True, chunkName="pasteKeyTimes")
    try:
        for crv in set(curves):
            plugs = cmds.listConnections(crv + ".output", plugs=True, source=False, destination=True) or []
            if not plugs:
                continue
            existing = set(round(t, 4) for t in (cmds.keyframe(crv, q=True, timeChange=True) or []))
            for t in times:
                if round(t, 4) in existing:
                    continue
                cmds.setKeyframe(plugs[0], time=t, insert=True)
                cmds.selectKey(crv, add=True, time=(t, t))
                added += 1
    finally:
        cmds.undoInfo(closeChunk=True)

    print("Inserted %d key(s)." % added)


paste_key_times()
