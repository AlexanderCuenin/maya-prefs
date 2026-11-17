"""
Reset Pose
Resets every keyable channel of the selected objects to its default value:
translate, rotate, scale, and custom attributes on rig controls.
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
    cmds.undoInfo(openChunk=True, chunkName="resetPose")
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


nodes = cmds.ls(selection=True) or []
if not nodes:
    cmds.warning("Select the controls to reset.")
else:
    plugs = ["%s.%s" % (o, a) for o in nodes for a in (cmds.listAttr(o, keyable=True, unlocked=True) or [])]
    n = _reset(plugs)
    print("Reset Pose: reset %d channel(s) on %d object(s)." % (n, len(nodes)))
