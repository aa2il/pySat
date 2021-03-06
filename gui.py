#! /usr/bin/python3 -u
################################################################################
#
# Satellite GUI - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui to show predicted passes for various OSCARs.
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

NDAYS1 = 15
COLORS=['b','g','r','c','m','y','k',
        'dodgerblue','lime','orange','aqua','indigo','gold','gray',
        'navy','limegreen','tomato','cyan','purple','yellow','dimgray']

RIT_DELTA=100
XIT_DELTA=100

################################################################################

import predict
import requests
import sys
import functools
import webbrowser

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QPixmap

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

if sys.version_info[0]==3:
    import urllib.request, urllib.error, urllib.parse
else:
    import urllib2

import rig_io.socket_io as socket_io
import pytz

from pprint import pprint
import os
import time
from datetime import timedelta,datetime
from collections import OrderedDict

from params import PARAMS
from watchdog import WatchDog
from rig_control import RigControl
from sat_class import SATELLITE,MAPPING

from settings import *
from Logging import *
from rotor import *

################################################################################
        
# The GUI
class SAT_GUI(QMainWindow):

    def __init__(self,P,parent=None):
        super(SAT_GUI, self).__init__(parent)

        # Init
        self.P=P
        self.now=None
        self.sky=None
        self.rot=None
        self.Selected=None
        self.New_Sat_Selection=False
        self.flipper = False
        #self.cross180 = False
        self.pos=[np.nan,np.nan]
        self.rit = 0
        self.xit = 0
        self.Ready=False
        self.SettingsWin=SETTINGS(P)
        self.LoggingWin=LOGGING(P)
        self.MODES=['USB','CW','FM','LSB']
        self.ax=None
        self.event_type = None

        # Put up splash screen until we're ready
        self.splash = QSplashScreen(QPixmap('splash.png'))
        self.splash.show()
        time.sleep(.01)
        self.P.app.processEvents()
        
        # Start by putting up the root window
        print('Init GUI ...')
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('Satellite Pass Predictions by AA2IL')
        ##self.win.setMinimumSize(1200,600)

        # We use a simple grid to layout controls
        self.grid = QGridLayout(self.win)
        nrows=8
        ncols=13

        # Add menu bar
        row=0
        self.create_menu_bar()
        
        # Create a calendar widget and add it to our layout
        row=0
        col=0
        self.cal = QCalendarWidget()
        self.grid.addWidget(self.cal,row,col,nrows-1,1)
        self.cal.clicked.connect(self.date_changed)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)   # Delete week numbers
        self.cal.setGridVisible(True)

        # Don't allow calendar size to change when we resize the window
        if False:
            sizePolicy = QSizePolicy( QSizePolicy.Fixed,
                                      QSizePolicy.Fixed)
            self.cal.setSizePolicy(sizePolicy)

        # The Canvas where we will plot sky track
        self.fig2  = Figure()
        self.canv2 = FigureCanvas(self.fig2)
        self.grid.addWidget(self.canv2,row,ncols-1,nrows-1,1)
        #self.canv2.setMinimumSize(200,200)
        #self.canv2.setFixedSize(200,200)
        self.canv2.setFixedHeight(200)
        self.canv2.setMinimumWidth(210)
        #self.canv2.setGeometry(0,0,200,210)

        # Polar axis for sky track plot
        self.ax2 = self.fig2.add_subplot(111, projection='polar')
        self.ax2.set_rmax(90)
        self.ax2.set_yticks([0,30, 60, 90])          # Less radial ticks
        self.ax2.set_yticklabels(['90','60','30','0'])
        #self.ax2.set_rlabel_position(-22.5)  # Move radial labels away from plotted line
        self.ax2.grid(True)
        xtics = ['E','','N','','W','','S','']
        self.ax2.set_xticklabels(xtics) 

        # Allow canvas size to change when we resize the window
        # but make is always visible
        if False:
            sizePolicy = QSizePolicy( QSizePolicy.MinimumExpanding, 
                                      QSizePolicy.MinimumExpanding)
            sizePolicy = QSizePolicy( QSizePolicy.Preferred,
                                      QSizePolicy.Preferred)
            self.canv2.setSizePolicy(sizePolicy)

        # The Canvas where we will put the graph with the pass times
        row=1
        col=0
        self.fig = Figure()
        self.canv = FigureCanvas(self.fig)
        self.grid.addWidget(self.canv,nrows,col,1,ncols)

        # Allow canvas size to change when we resize the window
        # but make is always visible
        if False:
            sizePolicy = QSizePolicy( QSizePolicy.MinimumExpanding, 
                                      QSizePolicy.MinimumExpanding)
            sizePolicy = QSizePolicy( QSizePolicy.Preferred, 
                                      QSizePolicy.Preferred)
            #sizePolicy = QSizePolicy( QSizePolicy.Preferred, 
            #                          QSizePolicy.Maximum)
            self.canv.setSizePolicy(sizePolicy)
        self.grid.setRowStretch(nrows,10)

        # Attach mouse click to handler
        cid = self.canv.mpl_connect('button_press_event', self.MouseClick)

        # Fetch the currently selected date, this is a QDate object
        date = self.cal.selectedDate()
        date0 = date.toPyDate()
        self.date1 = datetime.strptime( date0.strftime("%Y%m%d"), "%Y%m%d") 
        
        # Load satellite data
        self.load_sat_data()
        
        # Plot passes
        self.draw_passes()

        # User selections
        row=0
        col+=1

        # Push buttons to go forwarnd and backward one day
        # These are disabled since I never seemed to use them
        if False:
            btn = QPushButton('')
            btn.setIcon(self.style().standardIcon(
                getattr(QStyle, 'SP_MediaSeekBackward')))
            btn.setToolTip('Click to regress 1 day')
            btn.clicked.connect(self.Regress)
            self.grid.addWidget(btn,row,col)

            btn = QPushButton('')
            btn.setIcon(self.style().standardIcon(
                getattr(QStyle, 'SP_MediaSeekForward')))
            btn.setToolTip('Click to advance 1 day')
            btn.clicked.connect(self.Advance)
            self.grid.addWidget(btn,row,col+1)
            row+=1

        # Combo-boxes to set start end end times of graph
        Times=[]
        for i in range(25):
            t = '%2.2d:00' % i
            Times.append(t)

        lb=QLabel("Start Time:")
        self.StartTime_cb = QComboBox()
        self.StartTime_cb.addItems(Times)
        self.StartTime_cb.currentIndexChanged.connect(self.date_changed)
        self.StartTime_cb.setCurrentIndex(P.TSTART)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.StartTime_cb,row,col+1)

        row+=1
        lb=QLabel("End Time:")
        self.EndTime_cb = QComboBox()
        self.EndTime_cb.addItems(Times)
        self.EndTime_cb.currentIndexChanged.connect(self.date_changed)
        self.EndTime_cb.setCurrentIndex(P.TEND)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.EndTime_cb,row,col+1)

        row+=1
        self.btn2 = QPushButton('Engage')
        self.btn2.setToolTip('Click to engange Rig Control')
        self.btn2.clicked.connect(self.ToggleRigControl)
        self.btn2.setCheckable(True)

        self.btn2.setStyleSheet('QPushButton { \
        background-color: limegreen; \
        border :1px outset ; \
        border-radius: 5px; \
        border-color: gray; \
        font: bold 14px; \
        padding: 4px; \
        }')
        
        self.grid.addWidget(self.btn2,row,col,1,2)
        self.rig_engaged=False

        row+=1
        self.btn3 = QPushButton('Re-Center')
        self.btn3.setToolTip('Click to Tune to Center of Transponder passband')
        self.btn3.clicked.connect(self.ReCenter)
        self.grid.addWidget(self.btn3,row,col,1,2)

        row+=1
        self.btn4 = QPushButton('Rotor')
        self.btn4.setToolTip('Click to engange Rotor Control')
        self.btn4.clicked.connect(self.ToggleRotorControl)
        self.btn4.setCheckable(True)

        self.btn4.setStyleSheet('QPushButton { \
        background-color: limegreen; \
        border :1px outset ; \
        border-radius: 5px; \
        border-color: gray; \
        font: bold 14px; \
        padding: 4px; \
        }')
        
        self.grid.addWidget(self.btn4,row,col,1,2)
        self.rotor_engaged=False

        # Add Mode selector - this is in the menubar now
        if False:
            row+=1
            self.mode_cb = QComboBox()
            self.mode_cb.addItems(self.MODES)
            self.mode_cb.currentIndexChanged.connect(self.ModeSelect)
            self.grid.addWidget(self.mode_cb,row,col,1,2)
        else:
            self.mode_cb = None

        # Buttons to quickly select CW & Phone
        row+=1
        self.CWbtn = QPushButton('CW')
        self.CWbtn.setToolTip('Click to select CW')
        self.CWbtn.clicked.connect( functools.partial( self.ModeSelect,mode='CW' ))
        self.grid.addWidget(self.CWbtn,row,col,1,1)
        self.CWbtn.setCheckable(True)
            
        self.PHbtn = QPushButton('Phone')
        self.PHbtn.setToolTip('Click to select Phone')
        self.PHbtn.clicked.connect( functools.partial( self.ModeSelect,mode='Phone' ))
        self.grid.addWidget(self.PHbtn,row,col+1,1,1)
        self.PHbtn.setCheckable(True)
            
        # Panel to put the pass details when the user clicks on a pass
        row=0
        col+=2
        lb=QLabel("Satellite:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.SatName = QLabel('---')
        self.SatName.setAlignment(QtCore.Qt.AlignCenter)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.SatName,row,col+1)
        
        row+=1
        lb=QLabel("AOS:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.AOS = QLabel('---')
        self.AOS.setAlignment(QtCore.Qt.AlignCenter)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.AOS,row,col+1)
        
        row+=1
        lb=QLabel("LOS:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.LOS = QLabel('---')
        self.LOS.setAlignment(QtCore.Qt.AlignCenter)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.LOS,row,col+1)

        row+=1
        lb=QLabel("Peak El:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.PeakEl = QLabel('---')
        self.PeakEl.setAlignment(QtCore.Qt.AlignCenter)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.PeakEl,row,col+1)
                
        row+=1
        lb=QLabel("Slant Rng:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.SRng = QLabel('---')
        self.SRng.setAlignment(QtCore.Qt.AlignCenter)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.SRng,row,col+1)

        row+=1
        self.txt9 = QLabel(self)
        self.txt9.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.txt9.setText("Hey!")
        self.grid.addWidget(self.txt9,row,col,1,2)

        # Panel to display tuning info
        row=0
        col+=2
        lb=QLabel("Downlink:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        #self.txt1 = QLineEdit(self)
        self.txt1 = QLabel(self)
        self.txt1.setText("Hey!")
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.txt1,row,col+1,1,2)

        row+=1
        lb=QLabel("Uplink:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        #self.txt2 = QLineEdit(self)
        self.txt2 = QLabel(self)
        self.txt2.setText("Hey!")
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.txt2,row,col+1,1,2)

        row+=1
        lb=QLabel("VFO A:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.txt3 = QLabel(self)
        self.txt3.setText("Hey!")
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.txt3,row,col+1,1,2)

        row+=1
        lb=QLabel("VFO B:")
        lb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.txt4 = QLabel(self)
        self.txt4.setText("Hey!")
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.txt4,row,col+1,1,2)

        row+=1
        self.txt5 = QLabel(self)
        self.txt5.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.txt5.setText("Hey!")
        self.grid.addWidget(self.txt5,row,col)

        self.txt6 = QLabel(self)
        self.txt6.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.txt6.setText("Hey!")
        self.grid.addWidget(self.txt6,row,col+1)

        row+=1
        self.txt7 = QLabel(self)
        self.txt7.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.txt7.setText("Hey!")
        self.grid.addWidget(self.txt7,row,col,1,3)

        # Panel to implement RIT
        row=0
        col+=3
        self.txt10 = QLabel(self)
        #self.txt10.setText(str(self.rit))
        self.txt10.setText("- RIT -")
        self.txt10.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt10,row,col,1,2)

        row+=1
        self.txt11 = QLineEdit(self)
        self.txt11.setText(str(self.rit))
        self.txt11.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt11,row,col,1,2)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarShadeButton')))
#            getattr(QStyle, 'SP_ArrowUp')))
        btn.setToolTip('Click to increase RIT')
        btn.clicked.connect(self.RITup)
        self.grid.addWidget(btn,row,col)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarUnshadeButton')))
#            getattr(QStyle, 'SP_ArrowDown')))
        btn.setToolTip('Click to decrease RIT')
        btn.clicked.connect(self.RITdn)
        self.grid.addWidget(btn,row,col)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_DialogCloseButton')))
        btn.setToolTip('Click to clear RIT')
        btn.clicked.connect(self.RITclear)
        self.grid.addWidget(btn,row,col)
        
        row+=1
        self.txt15 = QLabel(self)
        self.txt15.setText(str('HEY!'))
        self.txt15.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt15,row,col,1,4)

        # Panel to implement XIT
        row=0
        col+=2
        self.txt12 = QLabel(self)
        #self.txt12.setText(str(self.xit))
        self.txt12.setText("- XIT -")
        self.txt12.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt12,row,col,1,2)

        row+=1
        self.txt13 = QLineEdit(self)
        self.txt13.setText(str(self.xit))
        self.txt13.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt13,row,col,1,2)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarShadeButton')))
        btn.setToolTip('Click to increase XIT')
        btn.clicked.connect(self.XITup)
        self.grid.addWidget(btn,row,col)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarUnshadeButton')))
        btn.setToolTip('Click to decrease XIT')
        btn.clicked.connect(self.XITdn)
        self.grid.addWidget(btn,row,col)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_DialogCloseButton')))
        btn.setToolTip('Click to clear XIT')
        btn.clicked.connect(self.XITclear)
        self.grid.addWidget(btn,row,col)

        # Let's roll!
        self.show()
        self.Ready=True
        self.splash.destroy()
        
        # Check if we have a valid set of settings
        self.LoggingWin.hide()
        if not P.SETTINGS:
            self.SettingsWin.show()
            print('\n*** Need to re-start ***\n')
            self.Ready=False
            #return
            #sys.exit(0)

        # Put up plotting windows
        if P.TEST_MODE:
            self.PlotWin=PLOTTING(P)
        if P.SHOW_MAP:
            self.MapWin=MAPPING(P)
        
        # This doesn't seem to be working quite right - idea is to limit size of window
        #self.win.resize(size_hint)
        #self.win.resize(900,720)
        #screen = QDesktopWidget().screenGeometry()
        #print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ screen=',screen)
        #widget = self.geometry()
        #print('win=',widget)
        #print('hint=',self.win.sizeHint())
        #self.setMainimumSize( widget.width() , widget.height() )    # Set minimum size of gui window
          
        #screen_resolution = P.app.desktop().screenGeometry()
        #width, height = screen_resolution.width(), screen_resolution.height()
        #print("Screen Res:",screen_resolution,width, height)

        
    # Capture 'x' in upper right corner so that we can shut down gracefully
    def closeEvent(self, event):
        print("()(()()()()()( User has clicked the red x on the main window ()()()()()))")
        if self.P.TEST_MODE:
            self.PlotWin.close()
        event.accept()
        qApp.quit()
        

    # Function to set rig mode
    def ModeSelect(self,mode=None):
        #print('MODE SELECT:',mode)
        #if self.mode_cb and (not mode or type(mode)==int):
        #    mode = self.mode_cb.currentText()
        if not mode or mode=='Phone':
            mode=self.P.transp['mode']
        print('MODE SELECT: mode=',mode)
        self.P.ctrl.set_rig_mode( mode )

        self.txt15.setText(mode)
        if self.statusBar:
            self.statusBar.showMessage('Set rig mode to '+mode)
        if self.mode_cb:
            idx = self.MODES.index( mode )
            self.mode_cb.setCurrentIndex(idx)

        if mode=='CW':
            self.CWbtn.setChecked(True)
            self.PHbtn.setChecked(False)
        else:
            self.CWbtn.setChecked(False)
            self.PHbtn.setChecked(True)
            
        return mode
        
    # Function to re-tune to center of transponder passband
    def ReCenter(self):
        P=self.P
        gui=self.P.gui
        ctrl=self.P.ctrl
        
        # Set down link freq to center of transp passband - uplink will follow
        try:
            if P.sock.rig_type2=='IC9700':
                ctrl.check_ic9700_bands(P)
            
            ctrl.fdown = 0.5*(P.transp['fdn1']+P.transp['fdn2'])
            ctrl.track_freqs(True,tag='Re-Center')

            # Also reset mode
            mode=self.ModeSelect()
            print('================== ReCenter: downlink=',ctrl.fdown,
                  '\tmde=',mode)
            return

            # This isn't effective until we actually select the sat 
            mode=P.transp['mode']
            ctrl.set_rig_mode( mode )
            print('================== ReCenter: downlink=',ctrl.fdown,
                  '\tmde=',mode)
            print('transp=',P.transp)

            idx = gui.MODES.index( mode )
            gui.mode_cb.setCurrentIndex(idx)
            
        except Exception as e: 
            print('================== ReCenter - Failure')
            print(e)



    # Function to engage/disengange rig control
    def ToggleRotorControl(self):
        if self.Selected:
            self.rotor_engaged = not self.rotor_engaged
        print('Rotor Control is',self.rotor_engaged)

        if self.rotor_engaged:
            self.btn4.setStyleSheet('QPushButton { \
            background-color: red; \
            border :1px inset ; \
            border-radius: 5px; \
            border-color: gray; \
            font: bold 14px; \
            padding: 4px; \
            }')
            #self.btn4.setText('Dis-Engage')

        else:
            self.btn4.setStyleSheet('QPushButton { \
            background-color: limegreen; \
            border :1px outset ; \
            border-radius: 5px; \
            border-color: gray; \
            font: bold 14px; \
            padding: 4px; \
            }')
            #self.btn4.setText('Engage')
            
            
    # Function to engage/disengange rig control
    def ToggleRigControl(self):
        if self.Selected:
            self.rig_engaged = not self.rig_engaged
        print('Rig Control is',self.rig_engaged)

        if self.rig_engaged:
            self.btn2.setStyleSheet('QPushButton { \
            background-color: red; \
            border :1px inset ; \
            border-radius: 5px; \
            border-color: gray; \
            font: bold 14px; \
            padding: 4px; \
            }')
            self.btn2.setText('Dis-Engage')
            self.P.sock.split_mode(1)

            # Retune the rig
            self.ReCenter()

        else:
            self.btn2.setStyleSheet('QPushButton { \
            background-color: limegreen; \
            border :1px outset ; \
            border-radius: 5px; \
            border-color: gray; \
            font: bold 14px; \
            padding: 4px; \
            }')
            self.btn2.setText('Engage')
            self.P.sock.split_mode(0)
            
        # Put up a reminder for something that is not availabe via CAT
        if self.rig_engaged and self.P.sock.rig_type2=='IC9700' and False:
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Information)
            msgBox.setText("Be sure REVERSE mode is set !!!\n\nKeep RF GAIN Centered !!!")
            msgBox.setWindowTitle("IC9700 Operation")
            msgBox.setStandardButtons(QMessageBox.Ok)
            #msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            #msgBox.buttonClicked.connect(msgButtonClick)
        
            returnValue = msgBox.exec()
            if returnValue == QMessageBox.Ok:
                print('OK clicked')

        
    # Function to increase RIT
    def RITup(self):
        self.rit += RIT_DELTA
        print('\nRITup:',self.rit)
        self.txt11.setText(str(self.rit))
        #self.P.ctrl.track_freqs(True,tag='RIT-UP')
        
    def RITdn(self):
        self.rit -= RIT_DELTA
        print('\nRITdn:',self.rit)
        self.txt11.setText(str(self.rit))
        #self.P.ctrl.track_freqs(True,tag='RIT-DN')
        
    def RITclear(self):
        print('\nRITclear:')
        self.rit = 0
        self.txt11.setText(str(self.rit))
        #self.P.ctrl.track_freqs(True,tag='RIT-CLR')
        
    # Function to increase XIT
    def XITup(self):
        self.xit += XIT_DELTA
        print('\nXITup:',self.xit)
        self.txt13.setText(str(self.xit))
        #self.P.ctrl.track_freqs(True,tag='XIT-UP')
        
    def XITdn(self):
        self.xit -= XIT_DELTA
        print('\nXITdn:',self.xit)
        self.txt13.setText(str(self.xit))
        #self.P.ctrl.track_freqs(True,tag='XIT-DN')
        
    def XITclear(self):
        print('\nXITclear:')
        self.xit = 0
        self.txt13.setText(str(self.xit))
        #self.P.ctrl.track_freqs(True,tag='XIT-CLR')
        
    # Function to advance in time
    def Advance(self):
        print('\nAdvance:',self.date1)
        self.date1 += timedelta(days=1)
        print(self.date1)
        self.UpdateMap()
        
    # Function to regress in time
    def Regress(self):
        print('\nRegress:',self.date1) 
        self.date1 -= timedelta(days=1)
        print(self.date1)
        self.UpdateMap()

    # Handler called when the date selection has changed
    def date_changed(self):
        #print('Date Changed:')

        # Fetch the currently selected date, this is a QDate object
        date = self.cal.selectedDate()
        date0 = date.toPyDate()
        self.date1 = datetime.strptime( date0.strftime("%Y%m%d"), "%Y%m%d")
        
        self.UpdateMap()

        # Clear pass info
        try:
            self.SatName.setText('---')
            self.AOS.setText('---')
            self.LOS.setText('---')
            self.PeakEl.setText('---')
            self.SRng.setText('---')
        except:
            pass


    # Load satellite data
    def load_sat_data(self):

        print('\nLoad Sat Data - Computing orbits ...')
        print(self.P.SATELLITE_LIST)
        
        # Set time limits
        date1   = datetime.now() - timedelta(days=NDAYS1)
        date2   = date1 + timedelta(days=self.P.NDAYS2+NDAYS1)

        # Reflect these onto the calendar
        self.start_date = date1
        self.end_date   = date2
        self.cal.setMinimumDate(self.start_date)
        self.cal.setMaximumDate(self.end_date)
        
        # Loop over list of sats
        self.Satellites = OrderedDict()
        if self.P.GRID2:
            self.Satellites2 = OrderedDict()
        self.pass_times=[]
        for isat in range(1,len(self.P.SATELLITE_LIST) ):
            name=self.P.SATELLITE_LIST[isat]
            self.Satellites[name]=SATELLITE(isat,name,self.P.my_qth,
                                            date1,date2,self.P.TLE)
            if self.P.GRID2:
                self.Satellites2[name]=SATELLITE(isat,name,self.P.other_qth,
                                            date1,date2,self.P.TLE)
                sat2=self.Satellites2[name]

        
    # Plot passes for all sats
    def draw_passes(self):

        print('\nDraw passes - self.sats=',self.Satellites)
        self.ax = self.fig.add_subplot(111)
        #self.fig.tight_layout(pad=0)

        # Loop over list of sats
        self.pass_times=[]
        for name in list(self.Satellites.keys()):
            print('\nDraw Passes - name=',name)
            Sat=self.Satellites[name]
            
            # Plot passes for this sat
            c = COLORS[ (Sat.isat-1) % len(COLORS) ]
            self.pass_times.append(np.array( Sat.pass_times ))
            self.ax.plot(Sat.t,Sat.y,'-',label=name,linewidth=8,color=c)
            c2='w'
            self.ax.plot(Sat.t2,Sat.y2,'*',color=c2,markersize=12)

            if self.P.GRID2:
                Sat2=self.Satellites2[name]
                c3='k'
                self.ax.plot(Sat2.t,Sat2.y,'-',label=name,linewidth=4,color=c3)

        # Beautify the x-labels
        self.fig.autofmt_xdate()
        myFmt = mdates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_formatter(myFmt)
        self.ax.set_xlim(self.date1,self.date1+timedelta(hours=24))

        #self.ax.set_xlabel('Local Time', fontsize=16)
        #self.ax.set_ylabel('Satellite', fontsize=16)

        # Fix-up vertical axis
        self.ax.grid(True)
        nsats = len(self.P.SATELLITE_LIST)-1
        self.ax.set_ylim(1-.1,nsats+.1)
        self.ax.set_yticks(range(1,nsats+1))
        self.ax.set_yticklabels(self.P.SATELLITE_LIST[1:])
        self.ax.invert_yaxis()

        if False:
            # Shrink current axis's height by 20% on the bottom
            p=.1
            box = self.ax.get_position()
            self.ax.set_position([box.x0, box.y0 + box.height * p,
                                  box.width, box.height * (1-p)])

            # Put a legend below current axis
            self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -2*p),
                           fancybox=True, shadow=True, ncol=5)

        # Re-draw the canvas
        self.canv.draw()


    # Function to draw spots on the map
    def UpdateMap(self):
        #print('UpdateMap...')
        if not self.Ready:
            return

        # Draw line showing current time
        if self.now:
            self.now.remove()
        now=datetime.now()
        #print('now=',now)
        tt=[now,now]
        yy=self.ax.get_ylim()
        self.now,=self.ax.plot(tt,yy,'b--')
                
        t = self.StartTime_cb.currentText().split(':')
        t1 = int( t[0] )
        t = self.EndTime_cb.currentText().split(':')
        t2 = int( t[0] )
        date2 = self.date1 + timedelta(hours=t2)
        date1 = self.date1 + timedelta(hours=t1)
        #print 't1,t2=',t1,t2
        
        # Update Gui
        self.ax.set_xlim(date1,date2)
        DATE = self.date1.strftime('%m/%d/%y')
        grd=self.P.MY_GRID
        if len(grd)>6:
            grd=grd[:6]
        self.ax.set_title('Satellite Passes over '+grd+' for '+DATE+ '(Local Time)')
        self.canv.draw()

        self.cal.setSelectedDate(self.date1)

        
    # Function to find next transit at current time
    def find_next_transit(self,sat_names=None):
        
        # Loop over list of sats
        tnext=1e38
        if sat_names[0]==None:
            sat_names=list(self.Satellites.keys())
        for name in sat_names:
            print('\nFind best:',name)
            Sat=self.Satellites[name]
            if name=='Moon' or not Sat.main:
                print('FIND NEXT TRANSIT: Hmmmm - no transponder for this sat - skipping')
                continue
            
            # Observe sat at current time
            now = time.mktime( datetime.now().timetuple() )
            if False:
                obs = predict.observe(Sat.tle, self.P.my_qth,now)
                print('\tobs=',obs)
                print(' ')
                #print(now,obs.start,obs.end)

            # Look at next transit for this sat
            try:
                p = predict.transits(Sat.tle, self.P.my_qth, ending_after=now)
                transit = next(p)
                print('Transit vars:', vars(transit) )

                # Keep track of next transit
                if transit.start<tnext:
                    best=name
                    tnext=transit.start
                    
            except Exception as e: 
                print('================== Predict Failure for sat',name)
                print(e)
                best=None
                tnext=None

        ttt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tnext))
        print('\nNext transit:',best,ttt,'\n')
        return [best,tnext]


    # Routine to update track info
    def plot_sky_track(self,sat,ttt):
        print('PLOT SKY TRACK: sat=',sat,'\tttt=',ttt)
        self.Selected=sat
        self.New_Sat_Selection=True
        Sat = self.Satellites[sat]
        # print('### Plot Sky Track: flipper=',self.flipper)

        if self.P.SHOW_MAP and True:
            if sat=='Moon':
                # Donde esta la luna?
                [moon_az,moon_el,moon_lat,moon_lon] = Sat.current_moon_position()
                [sun_az, sunn_el,sun_lat, sun_lon]  = Sat.current_sun_position()
                self.MapWin.DrawSatTrack(Sat.name,moon_lon,moon_lat)
                self.MapWin.transform_and_plot(sun_lon,sun_lat,'o',clr='orange')
                self.MapWin.setWindowTitle('Current Position of Sun and Moon')
                self.MapWin.canv.draw()
            else:
                lons,lats,footprints = self.MapWin.ComputeSatTrack(Sat.tle)
                self.MapWin.DrawSatTrack(Sat.name,lons,lats)
                self.MapWin.DrawSatFootprint(Sat.name,lons[0],lats[0],footprints[0])
                #self.MapWin.transform_and_plot([lons[0]],[lats[0]],'ko')

        # Turn off rig tracking when we select a new sat
        self.rig_engaged = False
        self.rotor_engaged = False
        if self.btn2.isChecked():
            self.btn2.toggle()
        if self.btn4.isChecked():
            self.btn4.toggle()
        self.P.satellite = Sat         ### JBA - not sure about this????

        # The moon is special
        if sat=='Moon':
            
            # Generate a moon track
            self.transit = Sat.gen_moon_track(ttt,VERBOSITY=1)
            tt=self.transit.t
            az=self.transit.az
            el=self.transit.el

        else:
            
            # Pull out info for this sat
            tle  = Sat.tle
        
            p = predict.transits(tle, self.P.my_qth, ending_after=ttt)
            self.transit = next(p)
            #print('Transit vars:', vars(transit) )
            tstart = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.transit.start))
            tend   = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.transit.end))
            print(("%s\t%s\t%f\t%f" %
                   (tstart,tend,self.transit.duration()/60., self.transit.peak()['elevation'])))
            print('Transit Peak:',self.transit.peak())
    
            # Assemble data for sky track
            t=self.transit.start
            tt=[]
            az=[]
            el=[]
            lats=[]
            lons=[]
            footprints=[]
            while t<self.transit.end:
                obs=predict.observe(tle, self.P.my_qth,at=t)
                #print('obs=',obs)
                tt.append(t)
                az.append(obs['azimuth'])
                el.append(obs['elevation'])
                lats.append(obs['latitude'])
                lons.append(obs['longitude'])
                footprints.append(obs['footprint'])
                t+=10

            if self.P.SHOW_MAP and False:
                # Show footprint at mid-point of pass
                tmid = 0.5*(self.transit.start + self.transit.end)
                #obs=predict.observe(tle, self.P.my_qth,at=tmid)
                #lat = obs['latitude']
                #lon = obs['longitude']
                #footprint = obs['footprint']
                idx = int( len(lats)/2 )
                print('\nHEY:',Sat.name,tmid,lats[idx],lons[idx],footprints[idx],'-----------=====================\n')
                self.MapWin.DrawSatTrack(Sat.name,lons,lats,ERASE=False)
                self.MapWin.DrawSatFootprint(Sat.name,lons[idx],lats[idx],footprints[idx])

        # Update GUI
        self.SatName.setText( sat )
        self.aos=self.transit.start
        self.los=self.transit.end
        #print('PLOT SKY TRACK: aos=',self.aos,type(self.aos),'\tlos=',self.los,type(self.los))
        self.AOS.setText( time.strftime('%H:%M:%S', time.localtime(self.aos) ))
        self.LOS.setText( time.strftime('%H:%M:%S', time.localtime(self.los) ))
        self.PeakEl.setText( '%6.1f deg.' % self.transit.peak()['elevation'] )
        self.SRng.setText( '%d miles' % self.transit.peak()['slant_range'] )

        # Save data for rotor tracking
        self.track_t  = np.array(tt)
        self.track_az = np.array(az)
        self.track_el = np.array(el)

        if self.P.TEST_MODE and False:
            print('SKY_TRACK: Track t  =',self.track_t)
            print('SKY_TRACK: Track Az =',self.track_az)
            print('SKY_TRACK: Track El =',self.track_el)

        # Determine if we need to flip the antenna to avoid crossing 180-deg
        print('PLOT_SKY_TRACK: Current flip state=',self.flipper,self.pos)
        flip_a_roo(self)

        # Convert data to polar format & plot it
        # Note that track_az & track_el might have been modified so we go back to
        # the orig data for plotting purposes.
        RADIANS=np.pi/180.
        az=(90.-np.array(az))*RADIANS
        r=90.-np.array(el)
    
        self.ax2.clear()
        self.ax2.plot(az, r)
        self.ax2.plot(az[0], r[0],'go')
        self.ax2.plot(az[-1], r[-1],'ro')
        
        self.rot, = self.ax2.plot(0,0,'mo')
        self.sky, = self.ax2.plot(0,0,'ko')
        self.sun, = self.ax2.plot(np.nan,np.nan,'o',color='orange')
        self.ax2.set_rmax(90)

        if sat=='Moon':
            [az,el,lat,lon] = Sat.current_moon_position()
        else:
            [fdop1,fdop2,az,el,rng,lat,lon,footprint] = \
                Sat.Doppler_Shifts(0,0,self.P.my_qth)
        self.plot_position(az,el)

        # JBA - WARNING - what are they talking about? set_xtick
        # UserWarning: FixedFormatter should only be used together with FixedLocator

        xtics = ['E','','N','','W','','S','']
        self.ax2.set_xticklabels(xtics) 
        self.ax2.set_yticks([30, 60, 90])          # Less radial ticks
        self.ax2.set_yticklabels(3*[''])          # Less radial ticks
        
        self.canv2.draw()


    # Function to convert rotor position to actual pointing position in the sky
    def resolve_pointing(self,paz,pel):

        if pel<=90:
            az90 = 90.-paz
            el90 = 90.-max(0.,pel)
        else:
            if paz<180:
                az90 = -90.-paz
            else:
                az90 = 270.-paz
            el90 = 90.-max(0.,180-pel)

        return az90,el90
        
    
    # Plot sat and rotor position
    def plot_position(self,az=np.nan,el=np.nan,pos=[np.nan,np.nan]):
        RADIANS=np.pi/180.
        #print('\nPLOT_POSITION: az,el=',az,el,'\tflipper=',self.flipper)

        P=self.P
        if P.sock2.active:
            pos=P.sock2.get_position()
        else:
            pos=[np.nan,np.nan]
        print('PLOT_POSITION: az,el=',az,el,'\tpos=',pos)
        self.pos=pos

        # Plot current rotor position (the big magenta blob)
        if pos[0]!=np.nan:
            az90,el90 = self.resolve_pointing(pos[0],pos[1])
            self.rot.set_data( (az90)*RADIANS, el90)

        # Plot sat position (the black star)
        self.sky.set_data( (90.-az)*RADIANS, 90.-max(0.,el) )

        # Plot Sun position also
        [sun_az,sun_el,lat,lon] = self.Satellites['Moon'].current_sun_position()
        print('SUN:',sun_az,sun_el)
        if sun_el<-10:
            sun_az=np.nan
            sun_el=np.nan
        print('SUN:',sun_az,sun_el)
        self.sun.set_data( (90.-sun_az)*RADIANS, 90.-max(0.,sun_el) )
        
        self.canv2.draw()
        return
    
    
    # Mouse click handler
    def MouseClick(self,event):
    
        if event.xdata==None or event.ydata==None:
            print('Mouse click - bad params\n\tbutton:',event.button)
            print('\tx,y:',event.x, event.y)
            print('\txdat,ydat:',event.xdata, event.ydata)
            return

        # print(('\n%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
        #       ('double' if event.dblclick else 'single', event.button,
        #        event.x, event.y, event.xdata, event.ydata)))

        # Decode sat name and time
        isat = int( round( event.ydata ) )
        sat = self.P.SATELLITE_LIST[isat]
        print('\nMOUSE CLICK - Sat=',sat,isat)

        xx = self.ax.get_xlim()
        # print('xx=',xx)
        t = self.date1 + timedelta(days=event.xdata - int(xx[0]) )
        tt = time.mktime(t.timetuple())
        # print('t=',t,tt)

        # Find closest pass to this time
        pass_times = self.pass_times[isat-1]
        #print pass_times
        dt = abs( pass_times - tt )
        idx = np.argmin(dt)
        ttt = pass_times[idx]
        # print('idx=',idx,'\tttt=',ttt)

        # Plot sky track
        self.plot_sky_track(sat,ttt)

        # Rotor diagnostics/alg development
        if self.P.TEST_MODE:
            #print('\nTEST_MODE:',self.cross180,self.flipper,self.event_type)
            simulate_rotor(self)

    # Function to send the rotor home
    def RotorHome(self):
        print('Sending rotor home ...')
        self.P.sock2.set_position([0,0])

    # Function to open the AMSAT satellite status web page 
    def OpenAmsatWebPage(self):
        link = 'https://www.amsat.org/status'
        webbrowser.open(link, new=2)
                    
    # Function to create menu bar
    def create_menu_bar(self):
        print('Creating Menubar ...')

        # The status bar is a nice concept but takes up too much room for now
        #self.statusBar=self.statusBar()
        self.statusBar=None
        menubar = self.menuBar()

        # The File Menu
        fileMenu = menubar.addMenu('&File')

        settingsAct = QAction('&Settings...', self)
        settingsAct.setStatusTip('Settings Dialog')
        settingsAct.triggered.connect( self.SettingsWin.show )
        fileMenu.addAction(settingsAct)

        loggingAct = QAction('&Logging...', self)
        loggingAct.setStatusTip('Logging Dialog')
        loggingAct.triggered.connect( self.LoggingWin.log_qso )
        fileMenu.addAction(loggingAct)

        GetStatusAct = QAction('&Satellite Status...', self)
        GetStatusAct.setStatusTip('Open AMSAT Web Page')
        GetStatusAct.triggered.connect( self.OpenAmsatWebPage )
        fileMenu.addAction(GetStatusAct)

        exitAct = QAction('&Exit', self)
        #exitAct.setShortcut('Ctrl+Q')
        exitAct.setStatusTip('Exit Application')
        exitAct.triggered.connect(qApp.quit)
        fileMenu.addAction(exitAct)

        # The Mode Menu
        modeMenu = menubar.addMenu('&Mode')
        for m in self.MODES:
            Act = QAction('&'+m, self)
            Act.setStatusTip('Set uplink mode to '+m)
            Act.triggered.connect( functools.partial( self.ModeSelect,mode=m ))
            modeMenu.addAction(Act)

        # Rotor Menu
        rotorMenu = menubar.addMenu('&Rotor')
        Act = QAction('&Rotor Home', self)
        Act.setStatusTip('Send Rotor to (0,0)')
        Act.triggered.connect( functools.partial( self.RotorHome ))
        rotorMenu.addAction(Act)





        
