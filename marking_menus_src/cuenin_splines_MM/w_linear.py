"""
Linear Tangent
Graph Editor: sets the in and out tangents of the selected keys to Linear.
"""
import maya.cmds as cmds


def linear_tangent():
    if not cmds.keyframe(q=True, selected=True, keyframeCount=True):
        cmds.warning("Select some keys in the Graph Editor first.")
        return
    cmds.keyTangent(edit=True, inTangentType="linear", outTangentType="linear")


linear_tangent()
