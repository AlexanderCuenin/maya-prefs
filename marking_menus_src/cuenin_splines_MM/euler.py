"""
Smart Euler Filter
Runs Maya's Euler filter on rotation curves only.

Curves come from the selected keys if there are any, otherwise from the
selected objects. For every node it finds, it grabs ALL THREE rotate curves
(X, Y, Z), because the filter needs the full set to work. Non-rotation curves
are skipped. Filters the whole curve, not just the selected keys.
"""
import maya.cmds as cmds

ROT_ATTRS = ("rotateX", "rotateY", "rotateZ", "rx", "ry", "rz")


def _scope_curves():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if curves:
        return curves
    sel = cmds.ls(selection=True)
    return (cmds.keyframe(sel, q=True, name=True) or []) if sel else []


def smart_euler_filter():
    curves = _scope_curves()
    if not curves:
        cmds.warning("Select keys or objects with animation first.")
        return

    nodes = set()
    for crv in set(curves):
        plugs = cmds.listConnections(crv + ".output", plugs=True, source=False, destination=True) or []
        for plug in plugs:
            node, attr = plug.split(".", 1)
            if attr in ROT_ATTRS:
                nodes.add(node)

    if not nodes:
        cmds.warning("No rotation curves found.")
        return

    count = 0
    cmds.undoInfo(openChunk=True, chunkName="smartEulerFilter")
    try:
        for node in nodes:
            rot_curves = []
            for axis in "XYZ":
                src = cmds.listConnections(node + ".rotate" + axis, source=True, destination=False) or []
                rot_curves += [c for c in src if cmds.nodeType(c).startswith("animCurve")]
            if rot_curves:
                cmds.filterCurve(*rot_curves, filter="euler")
                count += 1
    finally:
        cmds.undoInfo(closeChunk=True)

    print("Euler filtered rotation on %d node(s)." % count)


smart_euler_filter()
