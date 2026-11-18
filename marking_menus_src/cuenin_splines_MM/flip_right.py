"""
Flip Right
Graph Editor: flips selected keys (value * -1) around the nearest key to the
RIGHT of the selection. If there is no key outside the selection on the right,
it pivots on the rightmost selected key instead.
Works per curve. Tangents flip with the values.
"""
import maya.cmds as cmds


def flip_right():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not curves:
        cmds.warning("Select some keys in the Graph Editor first.")
        return

    cmds.undoInfo(openChunk=True, chunkName="flipRight")
    try:
        for crv in curves:
            sel_times = cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []
            if not sel_times:
                continue

            last = max(sel_times)
            all_times = cmds.keyframe(crv, q=True, timeChange=True) or []

            # nearest key right of the selection, else the rightmost selected key
            right = [t for t in all_times if t > last + 1e-6]
            anchor_time = min(right) if right else last
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


flip_right()
