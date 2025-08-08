#########################################################################################
#
# settings.py - Rev. 1.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
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
from widgets_qt import QTLIB
exec('from '+QTLIB+'.QtWidgets import QMainWindow,QWidget,QGridLayout,QLabel,QLineEdit,QCheckBox,QPushButton')
exec('from '+QTLIB+' import QtCore')
from rig_io.ft_tables import SATELLITE_LIST,CELESTIAL_BODY_LIST,METEOR_SHOWER_LIST

#########################################################################################

class SETTINGS_GUI_QT(QMainWindow):
    def __init__(self,P,parent=None):
        super(SETTINGS_GUI_QT, self).__init__(parent)

        # Init
        self.P=P
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('pySat Settings')
        self.grid = QGridLayout(self.win)
        self.ALL_OBJECTS = SATELLITE_LIST + CELESTIAL_BODY_LIST + METEOR_SHOWER_LIST

        # Boxes to hold geographic info (i.e. gps data)
        row=0
        col=0
        labels=['My Call:','My Grid:','Latitude:','Longitude:','Altitude (m):']
        self.items=['MY_CALL','MY_GRID','MY_LAT','MY_LON','MY_ALT']
        self.eboxes=[] 
        for label,item in zip(labels,self.items):
            
            lab = QLabel(self)
            lab.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
            lab.setText(label)
            self.grid.addWidget(lab,row,col,1,1)

            ebox = QLineEdit(self)
            try:
                txt=str(self.P.SETTINGS[item])
            except:
                txt=''
            ebox.setText(txt)
            ebox.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.grid.addWidget(ebox,row,col+1,1,1)
            
            self.eboxes.append(ebox)            
            row+=1

        if False:
            row+=1
            lab = QLabel(self)
            lab.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
            lab.setText('Known Satellites:')
            self.grid.addWidget(lab,row,col,1,1)

        # List of available satellites, whether we want them & tuning offsets
        self.cboxes=[]
        self.eboxes1=[]
        self.eboxes2=[]
        isat=0
        if 'OFFSETS' in self.P.SETTINGS:
            OFFSETS=self.P.SETTINGS['OFFSETS']
        else:
            OFFSETS=None
        row0=row+1
        for sat in self.ALL_OBJECTS:
            row+=1
            if row>row0+16:
                row=row0
                col+=4

            # Separater for next section
            if sat in [SATELLITE_LIST[0],CELESTIAL_BODY_LIST[0],METEOR_SHOWER_LIST[0]]:
                lab = QLabel(self)
                lab.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if sat==SATELLITE_LIST[0]:
                    txt='----- Known Satellites: ----- \tTX Offset\rRX Offset'
                elif sat==CELESTIAL_BODY_LIST[0]:
                    txt='----- Celestial Bodies: -----'
                else:
                    txt='----- Meteor Shower: --------'
                lab.setText(txt)
                self.grid.addWidget(lab,row,col,1,1)
                row+=1

            # Checkbox to indicate if we want to use this object
            cbox = QCheckBox(sat)
            self.grid.addWidget(cbox,row,col,1,1)
            self.cboxes.append(cbox)
            if sat!='None' and sat in P.SATELLITE_LIST:
                cbox.setChecked(True)

            # Entry boxes for TX and RX offsets
            if sat in SATELLITE_LIST:
                ebox = QLineEdit(self)
                self.eboxes1.append(ebox)
                try:
                    txt=str(OFFSETS[sat][0])
                except:
                    txt="0"
                ebox.setText(txt)
                ebox.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.grid.addWidget(ebox,row,col+1,1,1)
            
                ebox = QLineEdit(self)
                self.eboxes2.append(ebox)
                try:
                    txt=str(OFFSETS[sat][1])
                except:
                    txt="0"
                ebox.setText(txt)
                ebox.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.grid.addWidget(ebox,row,col+2,1,1)
            else:
                self.eboxes1.append(None)
                self.eboxes2.append(None)
            
            isat+=1
                
        # Buttons to complete or abandon the update
        row+=2
        col+=1
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

    # Function to update settings and write them to resource file
    def Update(self):

        # Collect things related to the list of sats
        ACTIVE=['None']
        OFFSETS={}
        for sat,cbox,ebox1,ebox2 in zip(self.ALL_OBJECTS,self.cboxes,self.eboxes1,self.eboxes2):
            print('SETTINGS UPDATE: sat=',sat)
            if sat!='None':
                if ebox1:
                    OFFSETS[sat] = [int(ebox1.text()) , int(ebox2.text())]
                else:
                    OFFSETS[sat] = []
                if cbox.isChecked():
                    ACTIVE.append(sat)

        # Bundle all into a common structure
        self.P.SETTINGS = {}
        for item,ebox in zip(self.items,self.eboxes):
            self.P.SETTINGS[item]=ebox.text()
        self.P.SETTINGS['ACTIVE']=ACTIVE
        self.P.SETTINGS['OFFSETS']=OFFSETS
        self.P.SATELLITE_LIST=ACTIVE
        
        # Write out the resource file
        with open(self.P.RCFILE, "w") as outfile:
            json.dump(self.P.SETTINGS, outfile)

        # Hide the sub-window
        self.hide()

    # Abaondon the update, just close the sub-window
    def Cancel(self):
        self.hide()
        
