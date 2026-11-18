"""
Reset Selected Channels
Resets whatever channels are highlighted in the Channel Box to their default
values, on every selected object. Works for any attribute, custom ones on
rig controls included (an IK/FK switch goes back to its default, a "space"
enum back to its first value, etc.), and for shape / history / output
channels highlighted in the lower sections of the Channel Box.
Nothing highlighted? Every keyable channel of the selection is reset instead,
same as Reset Pose.
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
    cmds.undoInfo(openChunk=True, chunkName="resetSelectedChannels")
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


CB = "mainChannelBox"
SECTIONS = [  # (highlighted attributes flag, objects shown in that section flag)
    ("selectedMainAttributes", "mainObjectList"),
    ("selectedShapeAttributes", "shapeObjectList"),
    ("selectedHistoryAttributes", "historyObjectList"),
    ("selectedOutputAttributes", "outputObjectList"),
]

plugs = []
for attrs_flag, objs_flag in SECTIONS:
    attrs = cmds.channelBox(CB, q=True, **{attrs_flag: True}) or []
    objs = cmds.channelBox(CB, q=True, **{objs_flag: True}) or []
    plugs += ["%s.%s" % (o, a) for o in objs for a in attrs if cmds.attributeQuery(a, node=o, exists=True)]

if plugs:
    n = _reset(plugs)
    print("Reset Selected Channels: reset %d channel(s)." % n)
else:
    nodes = cmds.ls(selection=True) or []
    if not nodes:
        cmds.warning("Select objects, and optionally highlight channels in the Channel Box.")
    else:
        plugs = ["%s.%s" % (o, a) for o in nodes for a in (cmds.listAttr(o, keyable=True, unlocked=True) or [])]
        n = _reset(plugs)
        print("Reset Selected Channels: nothing highlighted, reset all %d keyable channel(s)." % n)
