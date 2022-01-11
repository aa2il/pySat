#########################################################################################
#
# loogging.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui for logging contacts to an adif file
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
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
from rig_io.ft_tables import SATELLITE_LIST
from collections import OrderedDict
import time
from fileio import write_adif_record

#########################################################################################

class LOGGING(QMainWindow):
    def __init__(self,P,parent=None):
        super(LOGGING, self).__init__(parent)

        # Init
        self.P=P
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('pySat Contact Logging')
        self.grid = QGridLayout(self.win)

        # Open log file
        self.LOG_FILE='sats_'+P.MY_GRID[0:4]+'.adif'
        self.fp = open(self.LOG_FILE,"a+")

        # Create generic qso
        qso = OrderedDict()
        keys=['CALL','NAME','QTH','BAND','BAND_RX','FREQ','FREQ_RX','MODE', \
              'MY_GRIDSQUARE','QSO_DATE_OFF','TIME_OFF','RST_RCVD','RST_SENT',\
              'SAT_NAME','PROP_MODE']
        for key in keys:
            qso[key]=''
        qso['PROP_MODE']='SAT'
        qso['MY_GRIDSQUARE']=P.MY_GRID[0:6]
        self.qso=qso

        # Put up boxes for generic QSO fields
        row=0
        col=0
        self.labs=[]
        self.eboxes=[]
        row0=row+1
        for key in keys:
            print('key=',key)
            
            lab = QLabel(key)
            self.grid.addWidget(lab,row,col,1,1)
            self.labs.append(lab)
                
            ebox = QLineEdit(self)
            self.eboxes.append(ebox)
            ebox.setText(qso[key])
            ebox.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
            self.grid.addWidget(ebox,row,col+1,1,1)
            
            row+=1
            if row>row0+16:
                row=row0
                col+=3
            
        # Buttons to complete or abandon the update
        row+=1
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

        
    def log_qso(self):
        print('Log_qso ...')
        self.show()
        P=self.P
        gui=P.gui
        
        # Init QSO fields
        qso=self.qso
        qso['CALL']=''
        qso['NAME']=''

        # Get transponder for the currently selected sat
        sat = gui.Satellites[gui.Selected]
        if sat.main:
            transp    = sat.transponders[sat.main]
            print('main=',sat.main)
            print('transp=',transp)
        else:
            print('Hmmmm - no transponder for this sat')
            sys.exit(0)        

        # Set fields that are determined by the sat
        qso['SAT_NAME']=gui.Selected

        mode=transp['mode']
        qso['MODE']=mode
        
        fdown = 0.5*(transp['fdn1']+transp['fdn2'])*1e-6
        qso['FREQ_RX']=round(fdown,3)
        band=str( P.sock.get_band(fdown) )
        if band[-1]!='m':
            band += 'm'
        qso['BAND_RX']=band

        fup   = 0.5*(transp['fup1']+transp['fup2'])*1e-6
        qso['FREQ']=round(fup,3)
        band=str( P.sock.get_band(fup) )
        if band[-1]!='m':
            band += 'm'
        qso['BAND']=band

        t = 0.5*(gui.transit.start +gui.transit.end)
        qso['TIME_OFF']=time.strftime('%H:%M:%S', time.gmtime(t))
        qso['QSO_DATE_OFF']=time.strftime('%Y%m%d', time.gmtime(t))

        print('qso=',qso)

        for key,ebox in zip(qso.keys(),self.eboxes):
            ebox.setText(str(qso[key]))
        
    # Function to update settings and write them to resource file
    def Update(self):
        print('Update ...')

        # Read any changes user made
        for key,ebox in zip(self.qso.keys(),self.eboxes):
            self.qso[key]=ebox.text()

        # Write out adif record
        write_adif_record(self.fp,self.qso,self.P,long=True)
        self.fp.flush()

        # Hide the sub-window
        self.hide()

    # Abandon the update, just close the sub-window
    def Cancel(self):
        print('Cancel ...')
        self.hide()
        
