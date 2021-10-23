#########################################################################################
#
# settings.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui for basic settings.
#
############################################################################################
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
#########################################################################################

import sys
import json
"""
if sys.version_info[0]==3:
    from tkinter import *
    import tkinter.font
else:
    from Tkinter import *
    import tkFont
"""
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
from rig_io.ft_tables import SATELLITE_LIST

#########################################################################################

class SETTINGS(QMainWindow):
    def __init__(self,P,parent=None):
        super(SETTINGS, self).__init__(parent)

        self.P=P

        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('Settings')
        self.grid = QGridLayout(self.win)

        row=0
        col=0
        self.gridsq = self.newEntry('My Grid:     ','MY_GRID',row,col)
        self.lat    = self.newEntry('Latitude:    ','MY_LAT' ,row+1,col)
        self.lon    = self.newEntry('Longitude:   ','MY_LON' ,row+2,col)
        self.alt    = self.newEntry('Altitude (m):','MY_ALT' ,row+3,col)

        row+=4
        lab = QLabel(self)
        lab.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        lab.setText('-----------')
        self.grid.addWidget(lab,row,col,1,1)

        row+=1
        lab = QLabel(self)
        lab.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        lab.setText('Known Satellites:')
        self.grid.addWidget(lab,row,col,1,1)

        self.cboxes=[]
        for sat in SATELLITE_LIST:
            row+=1
            cbox = QCheckBox(sat)
            self.grid.addWidget(cbox,row,col,1,1)
            self.cboxes.append(cbox)
            if sat in P.SATELLITE_LIST:
                cbox.setChecked(True)
        
        row+=1
        col=0
        button1 = QPushButton('OK')
        button1.setToolTip('Click to Update Settings')
        button1.clicked.connect(self.Update)
        self.grid.addWidget(button1,row,col,1,1)
        
        col+=1
        button2 = QPushButton('Cancel')
        button2.setToolTip('Click to Cancel')
        button2.clicked.connect(self.Cancel)
        self.grid.addWidget(button2,row,col,1,1)
        
        self.hide()


    def newEntry(self,label,item,row,col):
        lab = QLabel(self)
        lab.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        lab.setText(label)
        self.grid.addWidget(lab,row,col,1,1)

        box = QLineEdit(self)
        try:
            txt=str(self.P.SETTINGS[item])
        except:
            txt=''
        box.setText(txt)
        box.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(box,row,col+1,1,1)

        return box

    def Update(self):
        ACTIVE=[]
        for sat,cbox in zip(SATELLITE_LIST,self.cboxes):
            if cbox.isChecked():
                ACTIVE.append(sat)
        
        self.P.SETTINGS = {'MY_GRID': self.gridsq.text().upper() , \
                           'MY_LAT' : float(self.lat.text())      , \
                           'MY_LON' : float(self.lon.text())      , \
                           'MY_ALT' : float(self.alt.text())      , \
                           'ACTIVE' : ACTIVE  }

        self.P.SATELLITE_LIST=ACTIVE

        with open(self.P.RCFILE, "w") as outfile:
            json.dump(self.P.SETTINGS, outfile)
        
        self.hide()

    def Cancel(self):
        self.hide()
        
        
################################################################################
        
"""
# Tk version - surprisingly seemed to work b4 put up Qt window!
        
class SETTINGS():
    def __init__(self,root,P):
        self.P = P
        
        if root:
            self.win=Toplevel(root)
        else:
            self.win = Tk()
        self.win.title("Settings")

        row=0
        Label(self.win, text='My Grid:').grid(row=row, column=0)
        self.call = Entry(self.win)
        self.call.grid(row=row,column=1,sticky=E+W)
        #self.call.delete(0, END)
        try:
            self.call.insert(0,P.MY_GRID)
        except:
            pass

        row+=1
        button = Button(self.win, text="OK",command=self.Dismiss)
        button.grid(row=row,column=1,sticky=E+W)

        self.win.update()
        self.win.deiconify()

    def Dismiss(self):
        self.P.SETTINGS = {'MY_GRID' : self.call.get().upper()}
        
        with open(self.P.RCFILE, "w") as outfile:
            json.dump(self.P.SETTINGS, outfile)
        
        self.win.destroy()

        
"""
