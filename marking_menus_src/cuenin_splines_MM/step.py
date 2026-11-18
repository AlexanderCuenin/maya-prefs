"""
Step Tangent
Graph Editor: sets the OUT tangent of the selected keys to Step.
In tangents are left alone, since Maya only steps on the out side.
"""
import maya.cmds as cmds


def step_tangent():
    if not cmds.keyframe(q=True, selected=True, keyframeCount=True):
        cmds.warning("Select some keys in the Graph Editor first.")
        return
    cmds.keyTangent(edit=True, outTangentType="step")


step_tangent()
