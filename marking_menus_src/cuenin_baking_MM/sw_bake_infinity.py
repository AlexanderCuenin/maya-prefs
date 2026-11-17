"""
Bake Infinity
Turns pre/post infinity (cycle, oscillate, linear...) into real keys.
Bakes the curves of your selected keys (or the selected objects' curves)
on every frame of the playback range, then sets infinity back to constant so
the baked keys are what you see.
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


def bake_infinity():
    curves, _ = _curves_and_range()
    plugs = _plugs(curves)
    if not plugs:
        cmds.warning("Select keys or objects with animation first.")
        return
    start = int(round(cmds.playbackOptions(q=True, min=True)))
    end = int(round(cmds.playbackOptions(q=True, max=True)))

    cmds.undoInfo(openChunk=True, chunkName="bakeInfinity")
    cmds.refresh(suspend=True)
    try:
        cmds.bakeResults(
            plugs,
            time=(start, end),
            sampleBy=1,
            simulation=False,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
        )
        for plug in plugs:
            src = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
            for crv in src:
                cmds.setInfinity(crv, preInfinite="constant", postInfinite="constant")
    finally:
        cmds.refresh(suspend=False)
        cmds.undoInfo(closeChunk=True)


bake_infinity()
