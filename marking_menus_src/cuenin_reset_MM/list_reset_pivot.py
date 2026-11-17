"""
Reset Pivot
Puts the move/rotate manipulator pivot back where it belongs after you moved
it with D / Insert or a custom pivot. This is Maya's own pivot, the
non-animBot stand-in for animBot's Reset Temp Pivot.
"""
import maya.cmds as cmds

try:
    cmds.manipPivot(reset=True)
except Exception:
    import maya.mel as mel
    mel.eval("manipPivot -r")
