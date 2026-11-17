"""
Copy Key Times
Graph Editor: remembers the frame numbers of all selected keys (across every
selected curve). Pair it with Paste Key Times.
The list is stored in an optionVar, so it survives between button presses
and Maya restarts.
"""
import maya.cmds as cmds

VAR = "animTools_copiedKeyTimes"


def copy_key_times():
    curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not curves:
        cmds.warning("Select some keys in the Graph Editor first.")
        return

    times = set()
    for crv in curves:
        for t in cmds.keyframe(crv, q=True, selected=True, timeChange=True) or []:
            times.add(round(t, 4))

    cmds.optionVar(clearArray=VAR)
    for t in sorted(times):
        cmds.optionVar(floatValueAppend=(VAR, t))

    print("Copied %d key time(s)." % len(times))


copy_key_times()
