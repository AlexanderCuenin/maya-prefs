"""
Flop Keys
Flops (mirrors in time, along X) your selected keys in the Graph Editor, per curve: the
first and last selected keys swap frames, and the selected keys in between
reverse order. Select two keys and they trade places in time. Each key keeps
its value, and its tangents are mirrored so that stretch plays backwards.

Only selected keys move. Unselected keys stay exactly where they are. If a
flopped key would land on a frame where an unselected key already sits, that
curve is skipped with a warning instead of overwriting the key.
One Ctrl+Z undoes the whole thing.
"""
import maya.cmds as cmds


def _q(crv, t, **flag):
    return cmds.keyTangent(crv, q=True, time=(t, t), **flag)[0]


def _flop_curve(crv, times):
    start, end = min(times), max(times)
    target = dict((t, start + end - t) for t in times)
    unselected = set(cmds.keyframe(crv, q=True, timeChange=True) or []) - set(times)
    clash = [target[t] for t in times if target[t] in unselected]
    if clash:
        cmds.warning("Flop Keys: skipped %s, an unselected key sits on frame %g."
                     % (crv, clash[0]))
        return False

    weighted = cmds.keyTangent(crv, q=True, weightedTangents=True)[0]
    info = {}
    for t in times:
        info[t] = {
            "inAngle": _q(crv, t, inAngle=True), "outAngle": _q(crv, t, outAngle=True),
            "inType": _q(crv, t, inTangentType=True), "outType": _q(crv, t, outTangentType=True),
            "lock": _q(crv, t, lock=True),
        }
        if weighted:
            info[t]["inWeight"] = _q(crv, t, inWeight=True)
            info[t]["outWeight"] = _q(crv, t, outWeight=True)
            info[t]["weightLock"] = _q(crv, t, weightLock=True)

    # Park the selected keys past the end of the curve, then drop each one on
    # its mirrored frame, so no key ever lands on another while moving.
    # option="over" lets a key travel past its neighbours; Maya's default
    # move refuses that ("Cannot move keys").
    last = max(cmds.keyframe(crv, q=True, timeChange=True))
    park = last - start + 1000.0
    for t in sorted(times, reverse=True):
        cmds.keyframe(crv, e=True, time=(t, t), timeChange=t + park,
                      absolute=True, option="over")
    for t in sorted(times, key=lambda x: target[x]):
        cmds.keyframe(crv, e=True, time=(t + park, t + park), timeChange=target[t],
                      absolute=True, option="over")

    # Mirror the tangents: what came in now goes out, and slopes flip sign.
    for t in times:
        nt, k = target[t], info[t]
        when = (nt, nt)
        cmds.keyTangent(crv, e=True, time=when, lock=False)
        if weighted:
            cmds.keyTangent(crv, e=True, time=when, weightLock=False)
        cmds.keyTangent(crv, e=True, time=when, inTangentType=k["outType"],
                        outTangentType=k["inType"])
        if k["outType"] == "fixed":
            cmds.keyTangent(crv, e=True, time=when, inAngle=-k["outAngle"])
        if k["inType"] == "fixed":
            cmds.keyTangent(crv, e=True, time=when, outAngle=-k["inAngle"])
        if weighted:
            cmds.keyTangent(crv, e=True, time=when, inWeight=k["outWeight"],
                            outWeight=k["inWeight"])
            cmds.keyTangent(crv, e=True, time=when, weightLock=k["weightLock"])
        cmds.keyTangent(crv, e=True, time=when, lock=k["lock"])
    return True


def flop_keys():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not curves:
        cmds.warning("Flop Keys: select some keys in the Graph Editor first.")
        return

    done = {}
    cmds.undoInfo(openChunk=True, chunkName="flopKeys")
    try:
        for crv in sorted(set(curves)):
            times = sorted(set(cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []))
            if len(times) >= 2 and _flop_curve(crv, times):
                done[crv] = [min(times) + max(times) - t for t in times]
        cmds.selectKey(clear=True)
        for crv, new_times in done.items():
            for t in new_times:
                cmds.selectKey(crv, add=True, keyframe=True, time=(t, t))
    finally:
        cmds.undoInfo(closeChunk=True)

    if done:
        print("Flop Keys: flopped selected keys on %d curve(s)." % len(done))
    else:
        cmds.warning("Flop Keys: select at least two keys on a curve.")


flop_keys()
