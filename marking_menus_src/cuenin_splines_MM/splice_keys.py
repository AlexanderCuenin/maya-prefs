"""
Splice Keys
Adds a key at the current frame on the curves you're working on, without
changing the curve's shape. Like holding I in the Graph Editor, but in one go
at the time slider's position.

Which curves get a key:
  1. curves that have selected keys in the Graph Editor, or else
  2. curves highlighted in the Graph Editor's channel list, or else
  3. every animated channel on the selected objects.
Curves that already have a key on this frame are left alone.
The new keys end up selected, and one Ctrl+Z undoes the whole thing.
"""
import maya.cmds as cmds


def _target_curves():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if curves:
        return curves, "curves with selected keys"
    for ge in ("graphEditor1FromOutliner",):
        if cmds.selectionConnection(ge, exists=True):
            channels = cmds.selectionConnection(ge, q=True, object=True) or []
            curves = (cmds.keyframe(channels, q=True, name=True) or []) if channels else []
            if curves:
                return curves, "highlighted Graph Editor channels"
    sel = cmds.ls(selection=True) or []
    curves = (cmds.keyframe(sel, q=True, name=True) or []) if sel else []
    return curves, "animated channels on the selection"


def splice_keys():
    t = cmds.currentTime(q=True)
    curves, source = _target_curves()
    curves = sorted(set(curves))
    if not curves:
        cmds.warning("Splice Keys: select keys, curves or animated objects first.")
        return

    added, skipped = [], 0
    cmds.undoInfo(openChunk=True, chunkName="spliceKeys")
    try:
        for crv in curves:
            if cmds.keyframe(crv, q=True, time=(t, t), keyframeCount=True):
                skipped += 1
                continue
            try:
                cmds.setKeyframe(crv, insert=True, time=(t, t))
            except Exception:
                # fall back to keying the channel the curve drives
                plugs = cmds.listConnections(crv + ".output", plugs=True,
                                             source=False, destination=True) or []
                if not plugs:
                    continue
                cmds.setKeyframe(plugs[0], insert=True, time=(t, t))
            added.append(crv)
        if added:
            cmds.selectKey(clear=True)
            for crv in added:
                cmds.selectKey(crv, add=True, keyframe=True, time=(t, t))
    finally:
        cmds.undoInfo(closeChunk=True)

    print("Splice Keys: added %d key(s) at frame %g on %s (%d already had a key)."
          % (len(added), t, source, skipped))


splice_keys()
