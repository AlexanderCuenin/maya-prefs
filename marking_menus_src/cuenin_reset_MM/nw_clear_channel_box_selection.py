"""
Clear Channel Box Selection
Un-highlights all channels in the Channel Box (the selection itself stays).
"""
import maya.cmds as cmds

cmds.channelBox("mainChannelBox", edit=True, select="")
