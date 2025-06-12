#! /usr/bin/python3 -u
################################################################################
#
# WatchDog.py - Rev 1.0
# Copyright (C) 2021-5 by Joseph B. Attili, aa2il AT arrl DOT net
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

if True:
    # Dynamic importing - this works!
    from widgets_qt import QTLIB
    exec('from '+QTLIB+' import QtCore')
elif False:
    from PyQt6 import QtCore
elif False:
    from PySide6 import QtCore
else:
    from PyQt5 import QtCore
from datetime import timedelta,datetime

################################################################################

# Watch Dog Timer - Called every min minutes to monitor health of app
class WatchDog:
    def __init__(self,P,sec):

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.Monitor)
        msec=1000*sec
        self.timer.start(msec)
        self.P=P

    # Check health of app in here
    def Monitor(self):
        gui=self.P.gui
        print('WatchDog...',gui.date1)
        
        # Draw line showing current time
        if gui.now:
            gui.now.remove()
        now=datetime.now()
        #print('now=',now)
        tt=[now,now]
        yy=gui.ax.get_ylim()
        gui.now,=gui.ax.plot(tt,yy,'b--')

        # Trying to maintain date selection
        #gui.cal.setSelectedDate(gui.date1)
        #gui.cal.updateCell(gui.date1)
        gui.cal.repaint()
        
        gui.canv.draw()
