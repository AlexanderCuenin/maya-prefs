"""
Flat Tangent
Graph Editor: sets the in and out tangents of the selected keys to Flat.
"""
import maya.cmds as cmds


def flat_tangent():
    if not cmds.keyframe(q=True, selected=True, keyframeCount=True):
        cmds.warning("Select some keys in the Graph Editor first.")
        return
    cmds.keyTangent(edit=True, inTangentType="flat", outTangentType="flat")


flat_tangent()
