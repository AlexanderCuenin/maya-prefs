"""
Buffer Snap
Graph Editor: snapshots the current shape of the selected curves into Maya's
buffer curve, so you can edit and compare against the original.
Also turns on "Show Buffer Curves" in the Graph Editor.

Works on selected keys if there are any, otherwise on selected objects.

MODE = "store"  -> save a new buffer (default)
MODE = "swap"   -> swap the curve with its buffer (flip back to the old version)
"""
import maya.cmds as cmds

MODE = "store"


def buffer_snap():
    has_keys = cmds.keyframe(q=True, selected=True, keyframeCount=True)
    if not has_keys and not cmds.ls(selection=True):
        cmds.warning("Select some keys or objects first.")
        return

    if MODE == "swap":
        cmds.bufferCurve(animation="keysOrObjects", swap=True)
    else:
        cmds.bufferCurve(animation="keysOrObjects", overwrite=True)

    # make the buffer visible (editor name can differ, so don't die on it)
    try:
        cmds.animCurveEditor("graphEditor1GraphEd", edit=True, showBufferCurves="on")
    except RuntimeError:
        pass


buffer_snap()
