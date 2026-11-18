"""
Reset All Xforms
Resets translate, rotate and scale of the selected objects to their defaults.
Locked channels and channels driven by constraints or expressions are skipped.
"""
import maya.cmds as cmds


def _settable(plug):
    """Skip locked channels and channels driven by something other than keys."""
    try:
        if cmds.getAttr(plug, lock=True):
            return False
    except Exception:
        return False
    src = cmds.listConnections(plug, source=True, destination=False, skipConversionNodes=True) or []
    return all(cmds.nodeType(s).startswith("animCurve") for s in src)


def _reset(plugs):
    """Set each node.attr to its default value. Returns how many changed."""
    done = 0
    cmds.undoInfo(openChunk=True, chunkName="resetTRS")
    try:
        for plug in plugs:
            node, attr = plug.split(".", 1)
            try:
                default = cmds.attributeQuery(attr, node=node, listDefault=True)
            except Exception:
                continue
            if not default or not _settable(plug):
                continue
            try:
                cmds.setAttr(plug, default[0])
                done += 1
            except Exception:
                pass  # string, matrix or other non-numeric channel
    finally:
        cmds.undoInfo(closeChunk=True)
    return done


CHANNELS = ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]

nodes = cmds.ls(selection=True, transforms=True) or []
if not nodes:
    cmds.warning("Select the controls to reset.")
else:
    n = _reset(["%s.%s" % (node, a) for node in nodes for a in CHANNELS])
    print("Reset All Xforms: reset %d channel(s) on %d object(s)." % (n, len(nodes)))
