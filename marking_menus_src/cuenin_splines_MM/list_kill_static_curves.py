"""
Static Anim Curves
Deletes animation curves that don't actually animate (every key has the same
value). The attribute keeps its value, it just loses the curve.

If you have keys selected, only those curves are checked.
If not, every curve on the selected objects is checked.
Driven key curves (set driven key) are skipped.
"""
import maya.cmds as cmds

TOL = 1e-5  # max value spread that still counts as static


def static_anim_curves():
    sel_curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if sel_curves:
        curves = sel_curves
    else:
        sel = cmds.ls(selection=True)
        curves = (cmds.keyframe(sel, q=True, name=True) or []) if sel else []

    if not curves:
        cmds.warning("Select keys or objects with animation first.")
        return

    deleted = 0
    cmds.undoInfo(openChunk=True, chunkName="staticAnimCurves")
    try:
        for crv in set(curves):
            if not cmds.objExists(crv):
                continue
            # skip set driven keys
            if cmds.listConnections(crv + ".input", source=True, destination=False):
                continue
            vals = cmds.keyframe(crv, q=True, valueChange=True) or []
            if vals and (max(vals) - min(vals)) < TOL:
                cmds.delete(crv)
                deleted += 1
    finally:
        cmds.undoInfo(closeChunk=True)

    print("Deleted %d static curve(s)." % deleted)


static_anim_curves()
