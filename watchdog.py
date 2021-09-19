#! /usr/bin/python3 -u
################################################################################
#
# WatchDog.py - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Watchdog timer for satellite predictions.
#
################################################################################
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
################################################################################

from PyQt5 import QtCore
from datetime import timedelta,datetime

################################################################################

# Watch Dog Timer - Called every min minutes to monitor health of app
class WatchDog:
    def __init__(self,P,min):

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.Monitor)
        msec=min*60*1000
        self.timer.start(msec)
        self.gui=P.gui

    # Check health of app in here
    def Monitor(self):
        print('WatchDog...')
        
        # Draw line showing current time
        gui=self.gui
        if gui.now:
            gui.now.remove()
        now=datetime.now()
        #print('now=',now)
        tt=[now,now]
        yy=gui.ax.get_ylim()
        gui.now,=self.gui.ax.plot(tt,yy,'b--')
        gui.canv.draw()
