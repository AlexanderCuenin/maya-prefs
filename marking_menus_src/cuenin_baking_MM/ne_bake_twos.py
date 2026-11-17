"""
Bake Twos
Bakes the curves of your selected keys so there is a key every 2 frame(s).
Range: first to last selected key. If no keys are selected, the selected
objects' curves are baked over the playback range.
Only the curves you pick are baked, other channels are left alone.
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


STEP = 2


def bake(step):
    curves, (start, end) = _curves_and_range()
    plugs = _plugs(curves)
    if not plugs:
        cmds.warning("Select keys or objects with animation first.")
        return
    start, end = int(round(start)), int(round(end))
    if end <= start:
        cmds.warning("Select keys across a range of frames.")
        return

    cmds.undoInfo(openChunk=True, chunkName="bake")
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


bake(STEP)
