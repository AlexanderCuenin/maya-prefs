"""
Bake Custom Interval
Asks for a number, then bakes the curves of your selected keys so there is a
key every N frames. Same range rules as the other bake buttons.
"""
import math
import maya.cmds as cmds


def _curves_and_range():
    """Curves + (start, end). Selected keys win, else selected objects over the playback range."""
    sel_keys = cmds.keyframe(q=True, selected=True, name=True) or []
    if sel_keys:
        times = []
        for c in sel_keys:
            times += cmds.keyframe(c, q=True, selected=True, timeChange=True) or []
        return sel_keys, (min(times), max(times))
    sel = cmds.ls(selection=True)
    curves = (cmds.keyframe(sel, q=True, name=True) or []) if sel else []
    return curves, (cmds.playbackOptions(q=True, min=True), cmds.playbackOptions(q=True, max=True))


def _plugs(curves):
    plugs = []
    for c in set(curves):
        p = cmds.listConnections(c + ".output", plugs=True, source=False, destination=True) or []
        if p:
            plugs.append(p[0])
    return plugs


def bake_custom():
    result = cmds.promptDialog(
        title="Bake Custom Interval",
        message="Bake every N frames:",
        text="2",
        button=["Bake", "Cancel"],
        defaultButton="Bake",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if result != "Bake":
        return
    try:
        step = int(float(cmds.promptDialog(q=True, text=True)))
    except ValueError:
        cmds.warning("Enter a whole number.")
        return
    if step < 1:
        cmds.warning("Interval must be 1 or more.")
        return

    curves, (start, end) = _curves_and_range()
    plugs = _plugs(curves)
    if not plugs:
        cmds.warning("Select keys or objects with animation first.")
        return
    start, end = int(round(start)), int(round(end))
    if end <= start:
        cmds.warning("Select keys across a range of frames.")
        return

    cmds.undoInfo(openChunk=True, chunkName="bakeCustom")
    cmds.refresh(suspend=True)
    try:
        cmds.bakeResults(
            plugs,
            time=(start, end),
            sampleBy=step,
            simulation=False,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
        )
    finally:
        cmds.refresh(suspend=False)
        cmds.undoInfo(closeChunk=True)


bake_custom()
