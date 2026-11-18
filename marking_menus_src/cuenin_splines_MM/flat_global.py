"""
Set Flat Global
Sets the default tangent type for NEW keys to Flat (in and out).
Does not touch existing keys.
"""
import maya.cmds as cmds


def set_flat_global():
    cmds.keyTangent(g=True, inTangentType="flat", outTangentType="flat")
    cmds.inViewMessage(amg="Default tangents: <hl>Flat</hl>", pos="midCenter", fade=True)


set_flat_global()
