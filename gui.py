################################################################################
#
# Satellite GUI - Rev 2.0
# Copyright (C) 2021-4 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui to show predicted passes for various OSCARs.
#
# Jan. 2023 - pypredict uses a lot of unix system calls and will not compile on
# windows ---> Migrating to pyemphem.
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

import requests
import sys
import functools
import webbrowser

import numpy as np
try:
    from PySide6.QtWidgets import *
    from PySide6 import QtCore
    from PySide6.QtGui import QIcon, QPixmap, QAction, QGuiApplication
    QT_VERSION=6
except ImportError:
    from PyQt5.QtWidgets import *
    from PyQt5 import QtCore
    from PyQt5.QtGui import QIcon, QPixmap
    QT_VERSION=5
from widgets_qt import *

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

import os
import time
from datetime import timedelta,datetime, timezone
from collections import OrderedDict

from params import PARAMS
from watchdog import WatchDog
from rig_control import RigControl
from sat_class import SATELLITE,MAPPING,USE_PYPREDICT
if USE_PYPREDICT:
    import predict

from settings_qt import *
from Logging import *
from rotor import *
from constants import *
from utilities import error_trap

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
        self.pos=[np.nan,np.nan]
        self.rit = 0
        self.xit = 0
        self.Ready=False
        self.SettingsWin=SETTINGS_GUI_QT(P)
        self.LoggingWin=LOGGING(P)
        self.MODES=['USB','CW','FM','LSB']
        self.ax=None
        self.event_type = None

        # Put up splash screen until we're ready
        self.splash=SPLASH_SCREEN(P.app,'splash.png')              # In util.py
        self.status_bar = self.splash.status_bar

    # Function that actually constructs the gui
    def construct_gui(self):
        P=self.P

        # Start by putting up the root window
        print('Init GUI ...',P.sock.rig_type2)
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('Satellite Pass Predictions by AA2IL - '+
                            P.sock.rig_type2)
        ##self.win.setMinimumSize(1200,600)

        # We use a simple grid to layout controls
        self.grid = QGridLayout(self.win)
        nrows=8
        ncols2=3
        ncols=9+2*ncols2

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

        # Set col width and don't allow calendar size to change width when we resize the window
        self.grid.setColumnStretch(col,1)
        sizePolicy = QSizePolicy( QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.cal.setSizePolicy(sizePolicy)
        print('Calendar: hint=',self.cal.sizeHint(),'\tsize=',self.cal.geometry())

        # The first 0canvas where we will put the graph with the pass times
        row=1
        col=0
        self.fig = Figure()
        self.canv = FigureCanvas(self.fig)
        self.grid.addWidget(self.canv,nrows,col,1,ncols)
        self.grid.setRowStretch(nrows,ncols)
        print('1st Canvas: hint=',self.canv.sizeHint(),'\tsize=',self.canv.geometry())

        # Allow canvas size to change when we resize the window
        # but make is always visible
        sizePolicy = QSizePolicy( QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        ##sizePolicy = QSizePolicy( QSizePolicy.Preferred, QSizePolicy.Preferred)
        ##sizePolicy = QSizePolicy( QSizePolicy.Preferred, QSizePolicy.Maximum)
        #self.canv.setSizePolicy(sizePolicy)
        
        # Attach mouse click to handler
        cid = self.canv.mpl_connect('button_press_event', self.MouseClick)

        # The second canvas is where we will plot sky track
        row=0
        self.fig2  = Figure()
        self.canv2 = FigureCanvas(self.fig2)
        self.grid.addWidget(self.canv2,row,ncols-1,nrows-1,1)
        ##self.canv2.setMinimumSize(200,200)
        ##self.canv2.setFixedSize(200,200)
        self.canv2.setFixedHeight(200)
        self.canv2.setMinimumWidth(210)    # was 210
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
        self.grid.setColumnStretch(ncols-1,1)
        sizePolicy = QSizePolicy( QSizePolicy.Fixed, QSizePolicy.Fixed)
        #sizePolicy = QSizePolicy( QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        #sizePolicy = QSizePolicy( QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.canv2.setSizePolicy(sizePolicy)
        print('2nd Canvas: hint=',self.canv2.sizeHint(),'\tsize=',self.canv2.geometry())

        # Fetch the currently selected date, this is a QDate object
        date = self.cal.selectedDate()
        print('date=',date)
        if QT_VERSION==6:
            date0 = date.toPython()
        else:
            date0 = date.toPyDate()
        print('date0=',date)
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
        self.grid.setColumnStretch(col,1)

        self.grid.setColumnStretch(col+1,1)
        print('Combo Box: hint=',self.StartTime_cb.sizeHint(),'\tsize=',self.StartTime_cb.geometry())

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
        self.grid.setColumnStretch(col,1)
        self.grid.setColumnStretch(col+1,1)
        print('Sat Name Label: hint=',self.SatName.sizeHint(),'\tsize=',self.SatName.geometry())
        
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
        self.grid.setColumnStretch(col,1)
        print('Tuning: hint=',self.txt1.sizeHint(),'\tsize=',self.txt1.geometry())

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
        self.txt10.setText("- RIT -")
        self.txt10.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt10,row,col,1,ncols2)
        self.grid.setColumnStretch(col,ncols2)
        print('RIT label: hint=',self.txt10.sizeHint(),'\tsize=',self.txt10.geometry())

        row+=1
        self.txt11 = QLineEdit(self)
        self.txt11.setText(str(self.rit))
        self.txt11.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt11,row,col,1,ncols2)
        print('RIT: hint=',self.txt11.sizeHint(),'\tsize=',self.txt11.geometry())

        f = self.txt11.font()
        f.setPointSize(10)
        self.txt11.setFont(f)
        
        """
            self.btn4.setStyleSheet('QPushButton { \
            background-color: red; \
            border :1px inset ; \
            border-radius: 5px; \
            border-color: gray; \
            font: bold 14px; \
            padding: 4px; \
            }')
        """

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarShadeButton')))
        btn.setToolTip('Click to increase RIT')
        btn.clicked.connect(self.RITup)
        self.grid.addWidget(btn,row,col,1,ncols2)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarUnshadeButton')))
        btn.setToolTip('Click to decrease RIT')
        btn.clicked.connect(self.RITdn)
        self.grid.addWidget(btn,row,col,1,ncols2)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_DialogCloseButton')))
        btn.setToolTip('Click to clear RIT')
        btn.clicked.connect(self.RITclear)
        self.grid.addWidget(btn,row,col,1,ncols2)
        
        row+=1
        self.txt15 = QLabel(self)
        self.txt15.setText(str('HEY!'))
        self.txt15.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt15,row,col,1,2*ncols2)

        # Panel to implement XIT
        row=0
        col+=ncols2
        self.txt12 = QLabel(self)
        self.txt12.setText("- XIT -")
        self.txt12.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt12,row,col,1,ncols2)
        self.grid.setColumnStretch(col,ncols2)
        print('XIT label: hint=',self.txt12.sizeHint(),'\tsize=',self.txt12.geometry())

        row+=1
        self.txt13 = QLineEdit(self)
        self.txt13.setText(str(self.xit))
        self.txt13.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.grid.addWidget(self.txt13,row,col,1,ncols2)
        print('XIT: hint=',self.txt13.sizeHint(),'\tsize=',self.txt13.geometry())

        f = self.txt13.font()
        f.setPointSize(10)
        self.txt13.setFont(f)
                
        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarShadeButton')))
        btn.setToolTip('Click to increase XIT')
        btn.clicked.connect(self.XITup)
        self.grid.addWidget(btn,row,col,1,ncols2)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_TitleBarUnshadeButton')))
        btn.setToolTip('Click to decrease XIT')
        btn.clicked.connect(self.XITdn)
        self.grid.addWidget(btn,row,col,1,ncols2)

        row+=1
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_DialogCloseButton')))
        btn.setToolTip('Click to clear XIT')
        btn.clicked.connect(self.XITclear)
        self.grid.addWidget(btn,row,col,1,ncols2)

        # Make sure all columns are adjusted when we resize the width of the window
        #for i in range(ncols):
        #    self.grid.columnconfigure(self.win, i, weight=1,uniform='twelve')

        # Status bar
        self.status_bar = StatusBar(self,nrows+1)
        
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
        self.MapWin=MAPPING(P)
        if P.SHOW_MAP:
            self.MapWin.show()
        else:
            self.MapWin.hide()
            
        if P.TEST_MODE:
            self.PlotWin=PLOTTING(P)
        
        # This doesn't seem to be working quite right - idea is to limit size of window
        print('Main Window: hint=',self.win.sizeHint(),'\tsize=',self.win.geometry())
        self.win.resize(self.win.sizeHint())
        print('Main Window: hint=',self.win.sizeHint(),'\tsize=',self.win.geometry())
        #self.win.resize(900,720)
        if QT_VERSION==6:
            screen = QGuiApplication.primaryScreen().size()
        else:
            screen = QDesktopWidget().screenGeometry()
        print('screen=',screen)
        #widget = self.geometry()
        #print('hint=',self.win.sizeHint())
        #self.setMainimumSize( widget.width() , widget.height() )    # Set minimum size of gui window
          
        #screen_resolution = P.app.desktop().screenGeometry()
        #width, height = screen_resolution.width(), screen_resolution.height()
        #print("Screen Res:",screen_resolution,width, height)

################################################################################
        
    # Capture 'x' in upper right corner so that we can shut down gracefully
    def closeEvent(self, event):
        print("()(()()()()()( User has clicked the red x on the main window ()()()()()))")

        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText("Really Quit?")
        msgBox.setWindowTitle("Really Quit")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        returnValue = msgBox.exec()
        if returnValue == QMessageBox.Cancel:
            #print('Cancel clicked')
            event.ignore()
        elif returnValue == QMessageBox.Ok:
            #print('OK clicked')
            event.accept()
        
            if self.P.TEST_MODE:
                self.PlotWin.close()
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
        self.status_bar.setText('Set rig mode to '+mode)
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
            
        except: 
            error_trap('GUI->RECENTER - Failure :-(')

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

        flipped=self.flipper
        if self.Selected:
            self.rig_engaged = not self.rig_engaged
        print('Rig Control is',self.rig_engaged)
        
        if not self.rig_engaged:

            # Manage button
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
            
        else:
            
            # Manage button
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

            # Check rotor and see if we need to re-calculate
            rotor_flipped(self)
            if flipped != self.flipper:
                ttt=self.Satellites[self.Selected].pass_times
                self.plot_sky_track(self.Selected,ttt)  # JBA - Try this -nope ttt undefined
            
            # Retune the rig
            self.ReCenter()

            # Plot sat track for current orbit on sat map
            if self.P.SHOW_MAP:
                self.plot_sat_map_track(self.P.satellite,0)
            
            # Put up a reminder for something that is not availabe via CAT
            if self.P.sock.rig_type2=='IC9700' and False:
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
        
################################################################################
        
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

        # This can get called b4 gui is ready - just ignore it
        if not self.Ready:
            print('WARNING - DATE CHANGED but GUI not ready!!!')
            return
        
        # Fetch the currently selected date, this is a QDate object
        date = self.cal.selectedDate()
        print('\n!!!!!!!!!!!!!!!!!!!!!!!!! Date Changed:',date)
        if QT_VERSION==6:
            date0 = date.toPython()
        else:
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
            error_trap('GUI->DATE CHANGED: Unable to clear gui entries ???')

################################################################################

    # Load satellite data
    def load_sat_data(self):

        print('\nLoad Sat Data - Computing orbits ...')
        print('Satellite List=',self.P.SATELLITE_LIST)
        
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

        #print('\nDraw passes - self.sats=',self.Satellites)
        self.ax = self.fig.add_subplot(111)

        # Loop over list of sats
        self.pass_times=[]
        for name in list(self.Satellites.keys()):
            print('Draw Passes - name=',name)
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

        if True:
            # Expand or shrink axis's width & height so we fill the canvas
            #self.fig.tight_layout(pad=0)
            ph1=.15
            ph2=.1
            pw1=.08
            pw2=.12
            box = self.ax.get_position()
            print('box=',box)
            self.ax.set_position([box.x0 - pw1*box.width,
                                  box.y0 - ph1*box.height,
                                  (1+pw1+pw2)*box.width,
                                  (1+ph1+ph2)*box.height])

            # Put a legend below current axis
            #self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -2*p),
            #               fancybox=True, shadow=True, ncol=5)

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
            Sat=self.Satellites[name]
            if name=='Moon' or not Sat.main:
                print('FIND NEXT TRANSIT: Hmmmm - no transponder for this sat - skipping')
                continue
            
            # Observe sat at current time
            now = time.mktime( datetime.now().timetuple() )
            print('FIND NEXT TRANSIT:',name,'\t',now)

            # Look at next transit for this sat
            try:
                if USE_PYPREDICT:
                    
                    p = predict.transits(Sat.tle, self.P.my_qth, ending_after=now)
                    transit = next(p)

                    # Debug
                    if False:
                        transit1 = Sat.next_transit(now)
                        
                        #print('Transit vars:\n', vars(transit))
                        #print('Transit1 vars:\n', vars(transit1))
                        dt=transit.start-transit1.start
                        print('Start times=',transit.start,transit1.start,dt)
                        
                        t0 = datetime.fromtimestamp(now,tz=timezone.utc)
                        t1 = datetime.fromtimestamp(transit.start,tz=timezone.utc)
                        t2 = datetime.fromtimestamp(transit.end,tz=timezone.utc)
                        t3 = datetime.fromtimestamp(transit1.start,tz=timezone.utc)
                        t4 = datetime.fromtimestamp(transit1.end,tz=timezone.utc)
                        print(t0,'\n',t1,t2,'\n',t3,t4)

                        if transit1.alt<=0:
                            print('Sat IS NOT visible',transit1.alt,transit1.dec)
                        else:
                            print('Sat IS visible',transit1.alt,transit1.dec,transit1.u)

                        if abs(dt)>60:
                            print('BIG mismatch!')
                            sys.exit(0)
                        
                else:
                    transit = Sat.next_transit(now)
                    
                # Keep track of next transit
                if transit.start<tnext:
                    best=name
                    tnext=transit.start
                    
            except: 
                error_trap('GUI->FIND NEXT TRANSIT: Failure for sat '+name)
                
        print(name,tnext)
        ttt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tnext))
        print('\nNext transit:',best,ttt,'\n')
        return [best,tnext]


    # Routine to plot sat map
    def plot_sat_map_track(self,Sat,iopt):

        if iopt==0:

            # Show full track
            if Sat.name=='Moon':
            
                # Donde estan la luna y el sol?
                [moon_az,moon_el,moon_lat,moon_lon,illum] = Sat.current_moon_position()
                [sun_az, sunn_el,sun_lat, sun_lon]  = Sat.current_sun_position()
                self.MapWin.DrawSatTrack(Sat.name,moon_lon,moon_lat,title='Current Position of Sun and Moon')
                self.MapWin.transform_and_plot(sun_lon,sun_lat,'o',clr='orange')
                #self.MapWin.setWindowTitle('Current Position of Sun and Moon')
                self.MapWin.canv.draw()
            
            else:

                # Plot sat track
                lons,lats,footprints = self.MapWin.ComputeSatTrack(Sat)
                self.MapWin.DrawSatTrack(Sat.name,lons,lats,'Current Position of '+Sat.name)
                self.MapWin.DrawSatFootprint(Sat.name,lons[0],lats[0],footprints[0])

        elif iopt==1:

            # Show footprint at mid-point of pass
            tmid = 0.5*(self.transit.start + self.transit.end)
            #print('tmid=',tmid,datetime.fromtimestamp(tmid))
            imid = int( len(self.track_lats)/2 )
            self.MapWin.DrawSatTrack(Sat.name,self.track_lons,self.track_lats,ERASE=True,title='Mid-Pass Position of '+Sat.name)
            for idx in [0,imid,-1]:
                self.MapWin.DrawSatFootprint(Sat.name,self.track_lons[idx],self.track_lats[idx],self.track_foot[idx],ERASE=False)
            
            
    # Routine to update track info
    def plot_sky_track(self,sat,ttt):
        print('PLOT SKY TRACK: sat=',sat,'\tttt=',ttt)
        self.Selected=sat
        self.New_Sat_Selection=True
        Sat = self.Satellites[sat]
        # print('### Plot Sky Track: flipper=',self.flipper)

        # Turn off rig tracking when we select a new sat
        self.rig_engaged = False
        self.rotor_engaged = False
        if self.btn2.isChecked():
            self.btn2.toggle()
        if self.btn4.isChecked():
            self.btn4.toggle()
        self.P.satellite = Sat

        # Plot sat track for current orbit on sat map
        if self.P.SHOW_MAP and sat=='Moon':
            print('================================================ MMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOONNNNNNNNNN =====')
            self.plot_sat_map_track(Sat,0)
            
        # The moon is special
        if sat=='Moon':
            
            # Generate a moon track
            self.transit = Sat.gen_moon_track(ttt,VERBOSITY=1)
            tt=self.transit.t
            az=self.transit.az
            el=self.transit.el

            # Indicate to use what he should see in the sky
            lunation,phz=Sat.get_moon_phase()
            print('lunation=',lunation,'\tphz=',phz)
            self.status_bar.setText('Moon Phase: '+phz)

        else:
            
            # Pull out info for this sat
            tle  = Sat.tle
        
            if USE_PYPREDICT:
                p = predict.transits(tle, self.P.my_qth, ending_after=ttt)
                self.transit = next(p)

                # Debug
                if False:
                    self.transit1 = Sat.next_transit(ttt)
                    tstart = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.transit.start))
                    tend   = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.transit.end))
            
                    tstart1 = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.transit1.start))
                    tend1   = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.transit1.end))
                    print('\n\nsat=',sat,'\tttt=',ttt)
                    print('Transit vars:', vars(self.transit) )
                    print('\nTransit Peak:',self.transit.peak())
                    print(("\n%s\t%s\t%s\tduration=%f\t%f" %
                           (sat,tstart,tend,self.transit.duration()/60.,
                            self.transit.peak()['elevation'])))
                    print('\nTransit Peak:',self.transit1.peak())
                    print(("\n%s\t%s\t%s\tduration=%f\t%f" %
                           (sat,tstart1,tend1,self.transit1.duration()/60.,
                            self.transit1.peak()['elevation'])))

                    t=self.transit.start
                    obs=predict.observe(tle, self.P.my_qth,at=t)
                    print('t=',t,'\tlat/lon=',obs['latitude'],obs['longitude'])
                    print('t=',self.transit1.t[0],'\tlat/lon=',self.transit1.lats[0],self.transit1.lons[0])
                    sys.exit(0)
                    
            else:
                self.transit = Sat.next_transit(ttt)
                
            if USE_PYPREDICT:
                
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

                # Debug
                if False:
                    #print('alt=',obs['altitude'],self.transit.peak()['elevation'])
                    #print('footprints=',footprints)
                    print('tt   =',tt[0],tt[-1])
                    print('tt1  =',self.transit1.t[0],self.transit1.t[-1])
                    print('lats =',lats)
                    print('lats1=',self.transit1.lats)
                    sys.exit(0)

            else:
                
                tt=self.transit.t
                az=self.transit.az
                el=self.transit.el
                lats=self.transit.lats
                lons=self.transit.lons
                footprints=self.transit.footprints

            # Show sat footprint at mid-point of pass on sat map
            if self.P.SHOW_MAP:
                self.track_lats  = np.array(lats)
                self.track_lons  = np.array(lons)
                self.track_foot  = np.array(footprints)
                #print('\nSHOWING MAP: start/end=',self.transit.start,self.transit.end)
                #print('lats=',self.track_lats)
                self.plot_sat_map_track(Sat,1)

        # Update GUI
        self.SatName.setText( sat )
        self.aos=self.transit.start
        self.los=self.transit.end
        #print('PLOT SKY TRACK: aos=',self.aos,type(self.aos),'\tlos=',self.los,type(self.los))
        self.AOS.setText( time.strftime('%H:%M:%S', time.localtime(self.aos) ))
        self.LOS.setText( time.strftime('%H:%M:%S', time.localtime(self.los) ))
        self.PeakEl.setText( '%6.1f deg.' % self.transit.peak()['elevation'] )
        srng=self.transit.peak()['slant_range']*KM2MILES
        self.SRng.setText( '%d miles' % srng)

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
            [az,el,lat,lon,illum] = Sat.current_moon_position()
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

        if pel==None or paz==None:
            print('*** WARNING *** RESOLVE POINTING - Unepected az/el value(s)',paz,pel)
            az90=0
            el90=0
        elif pel<=90:
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
        #print('PLOT_POSITION: az,el=',az,el,'\tpos=',pos)
        self.pos=pos

        # Plot current rotor position (the big magenta blob)
        if not np.isnan(pos[0]):
            az90,el90 = self.resolve_pointing(pos[0],pos[1])
            self.rot.set_data( [az90*RADIANS], [el90])

        # Plot sat position (the black star)
        self.sky.set_data( [(90.-az)*RADIANS], [90.-max(0.,el)] )

        # Plot Sun position also
        [sun_az,sun_el,lat,lon] = self.Satellites['Moon'].current_sun_position()
        #print('SUN:',sun_az,sun_el)
        if sun_el<-10:
            sun_az=np.nan
            sun_el=np.nan
        #print('SUN:',sun_az,sun_el)
        self.sun.set_data( [(90.-sun_az)*RADIANS], [90.-max(0.,sun_el)] )
        
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
        print('\n============================== MOUSE CLICK: New Sat Selected=',sat,isat,'========================================\n')

        xx = self.ax.get_xlim()
        # print('xx=',xx)
        t = self.date1 + timedelta(days=event.xdata - int(xx[0]) )
        tt = time.mktime(t.timetuple())
        print('\ttime=',t,tt)

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

        print(' ')

################################################################################
            
    # Callback to toggle no flipper
    def NoFlipperCB(self,state):
        self.P.NO_FLIPPER = not self.P.NO_FLIPPER
        print('Toggled NO FLIPPER ...',self.P.NO_FLIPPER,state)
    
    # Callback to toggle Showing Map
    def ShowMapCB(self,state):
        self.P.SHOW_MAP = not self.P.SHOW_MAP
        print('Toggled SHOW MAP ...',self.P.SHOW_MAP,state)
        if self.P.SHOW_MAP:
            self.MapWin.show()
        else:
            self.MapWin.hide()
    
    # Function to send the rotor home
    def RotorHome(self):
        print('Sending rotor home ...')
        self.P.sock2.set_position([0,0])

    # Function to open the AMSAT satellite status web page 
    def OpenAmsatWebPage(self):
        link = 'https://www.amsat.org/status'
        webbrowser.open(link, new=2)

        # Rovers are starting to post here
        link2 = 'https://hams.at'
        webbrowser.open(link2, new=2)
                    
################################################################################
        
    # Function to create menu bar
    def create_menu_bar(self):
        print('Creating Menubar ...')

        # The File Menu
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')

        settingsAct = QAction('&Settings...', self)
        settingsAct.setStatusTip('Settings Dialog')
        settingsAct.triggered.connect( self.SettingsWin.show )
        fileMenu.addAction(settingsAct)

        loggingAct = QAction('&Logging...', self)
        loggingAct.setStatusTip('Logging Dialog')
        loggingAct.triggered.connect( self.LoggingWin.log_qso )
        fileMenu.addAction(loggingAct)

        GetStatusAct = QAction('&Sat Status Page...', self)
        GetStatusAct.setStatusTip('Open AMSAT Web Page')
        GetStatusAct.triggered.connect( self.OpenAmsatWebPage )
        fileMenu.addAction(GetStatusAct)

        NoFlipperAct = QAction('&No Flipper', self, checkable=True)        
        NoFlipperAct.setStatusTip('No Flipper')
        NoFlipperAct.triggered.connect(self.NoFlipperCB)
        NoFlipperAct.setChecked(self.P.NO_FLIPPER)
        fileMenu.addAction(NoFlipperAct)
            
        ShowMapAct = QAction('&Show Map', self, checkable=True)        
        ShowMapAct.setStatusTip('Show Map')
        ShowMapAct.triggered.connect(self.ShowMapCB)
        ShowMapAct.setChecked(self.P.SHOW_MAP)
        fileMenu.addAction(ShowMapAct)
            
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

