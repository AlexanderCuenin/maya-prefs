"""
Redundant Keys
Deletes keys that do nothing: a key is redundant when its value matches both
neighbors and the tangents around it are flat, so removing it can't change the
curve shape. First and last keys on a curve are never deleted.

If you have keys selected, only those keys are checked.
If not, every key on the selected objects is checked.
"""
import maya.cmds as cmds

VALUE_TOL = 1e-4   # how close values must be to count as equal
ANGLE_TOL = 1e-3   # how close to zero a tangent angle must be to count as flat


def redundant_keys():
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
    cmds.undoInfo(openChunk=True, chunkName="redundantKeys")
    try:
        for crv in set(curves):
            times = cmds.keyframe(crv, q=True, timeChange=True) or []
            if len(times) < 3:
                continue
            vals = cmds.keyframe(crv, q=True, valueChange=True)
            in_ang = cmds.keyTangent(crv, q=True, inAngle=True)
            out_ang = cmds.keyTangent(crv, q=True, outAngle=True)

            selected = set()
            if use_selection:
                selected = set(round(t, 4) for t in
                               (cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []))

            to_delete = []
            for i in range(1, len(times) - 1):
                if use_selection and round(times[i], 4) not in selected:
                    continue
                if abs(vals[i] - vals[i - 1]) > VALUE_TOL or abs(vals[i] - vals[i + 1]) > VALUE_TOL:
                    continue
                flat = (
                    abs(out_ang[i - 1]) <= ANGLE_TOL
                    and abs(in_ang[i]) <= ANGLE_TOL
                    and abs(out_ang[i]) <= ANGLE_TOL
                    and abs(in_ang[i + 1]) <= ANGLE_TOL
                )
                if flat:
                    to_delete.append(times[i])

            for t in to_delete:
                cmds.cutKey(crv, time=(t, t), clear=True)
            removed += len(to_delete)
    finally:
        cmds.undoInfo(closeChunk=True)

    print("Deleted %d redundant key(s)." % removed)


redundant_keys()
