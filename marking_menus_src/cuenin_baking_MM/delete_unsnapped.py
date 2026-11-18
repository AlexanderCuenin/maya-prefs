"""
Delete Unsnapped
Deletes keys that sit between whole frames (subframe keys).
If you have keys selected, only those keys are checked.
If not, every key on the selected objects is checked.
"""
import maya.cmds as cmds

TOL = 1e-3  # how far from a whole frame still counts as snapped


def delete_unsnapped():
    sel_curves = cmds.keyframe(q=True, selected=True, name=True) or []
    use_selection = bool(sel_curves)
    if use_selection:
        curves = sel_curves
    else:
        sel = cmds.ls(selection=True)
        curves = (cmds.keyframe(sel, q=True, name=True) or []) if sel else []
    if not curves:
        cmds.warning("Select keys or objects with animation first.")
        return

    removed = 0
    cmds.undoInfo(openChunk=True, chunkName="deleteUnsnapped")
    try:
        for crv in set(curves):
            if use_selection:
                pool = cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []
            else:
                pool = cmds.keyframe(crv, q=True, timeChange=True) or []
            bad = [t for t in pool if abs(t - round(t)) > TOL]
            for t in bad:
                cmds.cutKey(crv, time=(t, t), clear=True)
            removed += len(bad)
    finally:
        cmds.undoInfo(closeChunk=True)

    print("Deleted %d unsnapped key(s)." % removed)


delete_unsnapped()
