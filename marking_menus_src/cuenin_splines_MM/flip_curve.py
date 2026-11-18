"""
Flip Average
Graph Editor: flips selected keys (value * -1) around the average value of the
selected keys, so the curve mirrors over its own center.
Works per curve. Tangents flip with the values.

Set USE_MIDPOINT = True to pivot on (min + max) / 2 instead of the mean.
That's a truer "center" if your keys are bunched up on one side.
"""
import maya.cmds as cmds

USE_MIDPOINT = False


def flip_average():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not curves:
        cmds.warning("Select some keys in the Graph Editor first.")
        return

    cmds.undoInfo(openChunk=True, chunkName="flipAverage")
    try:
        for crv in curves:
            sel_times = cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []
            sel_values = cmds.keyframe(crv, q=True, selected=True, valueChange=True) or []
            if not sel_times:
                continue

            if USE_MIDPOINT:
                anchor = (min(sel_values) + max(sel_values)) / 2.0
            else:
                anchor = sum(sel_values) / float(len(sel_values))

            for t in sel_times:
                cmds.scaleKey(
                    crv,
                    time=(t, t),
                    timeScale=1,
                    timePivot=0,
                    valueScale=-1,
                    valuePivot=anchor,
                )
    finally:
        cmds.undoInfo(closeChunk=True)


flip_average()
