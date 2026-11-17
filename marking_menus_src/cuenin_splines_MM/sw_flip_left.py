"""
Flip Left
Graph Editor: flips selected keys (value * -1) around the nearest key to the
LEFT of the selection. If there is no key outside the selection on the left,
it pivots on the leftmost selected key instead.
Works per curve. Tangents flip with the values.
"""
import maya.cmds as cmds


def flip_left():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not curves:
        cmds.warning("Select some keys in the Graph Editor first.")
        return

    cmds.undoInfo(openChunk=True, chunkName="flipLeft")
    try:
        for crv in curves:
            sel_times = cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []
            if not sel_times:
                continue

            first = min(sel_times)
            all_times = cmds.keyframe(crv, q=True, timeChange=True) or []

            # nearest key left of the selection, else the leftmost selected key
            left = [t for t in all_times if t < first - 1e-6]
            anchor_time = max(left) if left else first
            anchor = cmds.keyframe(
                crv, q=True, time=(anchor_time, anchor_time), valueChange=True
            )[0]

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


flip_left()
