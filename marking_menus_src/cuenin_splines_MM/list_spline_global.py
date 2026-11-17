"""
Set Auto Global
Sets the default tangent type for NEW keys to Auto (in and out).
Does not touch existing keys.
"""
import maya.cmds as cmds


def set_auto_global():
    cmds.keyTangent(g=True, inTangentType="auto", outTangentType="auto")
    cmds.inViewMessage(amg="Default tangents: <hl>Auto</hl>", pos="midCenter", fade=True)


set_auto_global()
