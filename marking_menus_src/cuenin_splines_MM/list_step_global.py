"""
Set Step Global
Sets the default tangent type for NEW keys to Step (out) with a Flat in tangent.
Maya has no step on the in side, so Flat is used there. Change IN_TYPE if you
want something else. Does not touch existing keys.
"""
import maya.cmds as cmds

IN_TYPE = "flat"


def set_step_global():
    cmds.keyTangent(g=True, inTangentType=IN_TYPE, outTangentType="step")
    cmds.inViewMessage(amg="Default tangents: <hl>Step</hl>", pos="midCenter", fade=True)


set_step_global()
