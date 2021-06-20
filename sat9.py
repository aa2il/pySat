#! /usr/bin/python3
################################################################################
#
# Satellite orbit prediction - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui to show predicted passes for various OSCARs.
#
# Notes:
# - To get a list of operation OSCARs, can check at
#      https://ka7fvv.net/satellite.htm   and     https://www.amsat.org/status
#   The list of displayed sat is stored in ft_tables.py - This needs to be moved to a config file!
#
# - The TLE data is in the file nasa.txt and is updated using the -update switch.
# - The transponder data is from gpredict
#
# - When a new satellite is introduced, it may be difficult to get Gpredict to recognize it.
#   To fix this:
#     1) Find the satellite in the nasa.txt file downloaded by this program
#     2) The second column in the TLE data contains the satellite number, e.g. 07530 for AO-7
#     3) Delete the corresponding .sat file in ~/.config/Gpredict/satdata
#     4) In Gpredict, update TLE data using LOCAL files - point to this directory
#     5) Gpredict seems to recognize .txt files which is why nasa.all has been renamed to nasa.txt
#
# - Migrated to python3 & Qt5 - To get this this to work, had to
#    - fiddle with pypredict/predict.c - they changed the init of C functions in python 3
#    - install python3-pip (pip3) and python3-setuptools
#    - pip3 install pyhamtools
#   In python3, there is a distinction between bytes and string so the .decode(...)
#   below takes care of that
#
# - Installation of predict engine:
#   Problem is with this package - they changed the init module - ugh!
#   sudo apt-get install python-dev
#   git clone https://github.com/nsat/pypredict.git
#   cd pypredict
#   sudo python3 setup.py install
#   cd ..
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

# User params - most of these are now available as command line args
NDAYS1 = 15
URL1 = "http://www.amsat.org/amsat/ftp/keps/current/nasa.all"    # AMSAT latest & greatest
URL2 = "~/Python/predict/nasa.txt"                               # Local copy
TRANSP_DATA = "~/.config/Gpredict/trsp"                          # Transponder data as parsed by gpredict

ROTOR_THRESH=10       # Was 2
MIN_PEAK_EL=30       # Degrees, min. elevation to identify overhead passes

COLORS=['b','g','r','c','m','y','k',
        'dodgerblue','lime','orange','aqua','indigo','gold','gray',
        'navy','limegreen','tomato','cyan','purple','yellow','dimgray']

################################################################################

import predict
from pyhamtools.locator import locator_to_latlong
import requests
import time
import sys
from datetime import timedelta,datetime
from collections import OrderedDict

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtWidgets import *

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

if sys.version_info[0]==3:
    import urllib.request, urllib.error, urllib.parse
else:
    import urllib2

import rig_io.socket_io as socket_io
from rig_io.ft_tables import SATELLITE_LIST,CONNECTIONS,SAT_RIGS
import pytz
import argparse

from pprint import pprint
import os
from configparser import ConfigParser 
 
################################################################################

# Structure to contain processing params
class PARAMS:
    def __init__(self):

        # Process command line args
        arg_proc = argparse.ArgumentParser()
        arg_proc.add_argument("-n", help="No. Days",type=int,default=30)
        arg_proc.add_argument('-update', action='store_true',help='Update TLE Data from Internet')
        arg_proc.add_argument("-grid", help="Grid Square",
                              type=str,default="DM12ox")

        arg_proc.add_argument("-rig", help="Connection Type",
                              type=str,default=["ANY"],nargs='+',
                              choices=CONNECTIONS+['NONE']+SAT_RIGS)
        arg_proc.add_argument("-port", help="Connection Port",
                              type=int,default=0)
        arg_proc.add_argument("-rotor", help="Rotor connection Type",
                      type=str,default="NONE",
                      choices=['HAMLIB','NONE'])
        arg_proc.add_argument("-port2", help="Rotor onnection Port",
                              type=int,default=0)
        
        args = arg_proc.parse_args()
        self.NDAYS2     = args.n
        self.UPDATE_TLE = args.update
        self.MY_GRID    = args.grid

        self.connection    = args.rig[0]
        if len(args.rig)>=2:
            self.rig       = args.rig[1]
        else:
            self.rig       = None
        self.PORT          = args.port
            
        self.ROTOR_CONNECTION = args.rotor
        self.PORT2            = args.port2
        
################################################################################

# Mouse click handler
def MouseClick(event):
    self = gui
    
    if event.xdata==None or event.ydata==None:
        print('Mouse click - bad params\n\tbutton:',event.button)
        print('\tx,y:',event.x, event.y)
        print('\txdat,ydat:',event.xdata, event.ydata)
        return

    print(('\n%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
          ('double' if event.dblclick else 'single', event.button,
           event.x, event.y, event.xdata, event.ydata)))

    # Decode sat name and time
    isat = int( round( event.ydata ) )
    sat = SATELLITE_LIST[isat]
    print('sat:',isat,sat)

    xx = self.ax.get_xlim()
    print('xx=',xx)
    t = self.date1 + timedelta(days=event.xdata - int(xx[0]) )
    tt = time.mktime(t.timetuple())
    print('t=',t,tt)

    # Find closest pass to this time
    pass_times = self.pass_times[isat-1]
    #print pass_times
    dt = abs( pass_times - tt )
    idx = np.argmin(dt)
    ttt = pass_times[idx]
    print(idx,ttt)

    # Plot sky track
    plot_sky_track(self,sat,ttt)

    
# Routine to update track info
def plot_sky_track(self,sat,ttt):

    self.Selected=sat
    self.New_Selection=True
    
    # Pull out info for this sat
    tle  = self.Satellites[sat].tle
        
    p = predict.transits(tle, my_qth, ending_after=ttt)
    #print p
    transit = next(p)
    #print('Transit vars:', vars(transit) )
    tstart = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(transit.start))
    tend   = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(transit.end))
    print(("%s\t%s\t%f\t%f" %
          (tstart,tend,transit.duration()/60., transit.peak()['elevation'])))
    print('Transit Peak:',transit.peak())
    
    # Update GUI
    self.SatName.setText( sat )
    self.AOS.setText( time.strftime('%H:%M:%S', time.localtime(transit.start) ))
    self.LOS.setText( time.strftime('%H:%M:%S', time.localtime(transit.end)   ))
    self.PeakEl.setText( '%6.1f deg.' % transit.peak()['elevation'] )
    self.SRng.setText( '%d miles' % transit.peak()['slant_range'] )

    # Plot sky track
    t=transit.start
    az=[]
    el=[]
    while t<transit.end:
        obs=predict.observe(tle, my_qth,at=t)
        #print('obs=',obs)
        #tt.append(t)
        az.append(obs['azimuth'])
        el.append(obs['elevation'])
        t+=10

    # Save data for rotor tracking
    self.track_az=np.array(az)
    self.track_el=np.array(el)
    quad2 = np.logical_and(self.track_az>90 , self.track_az<180)
    quad3 = np.logical_and(self.track_az>180 , self.track_az<270)
    self.flipper = any(quad2) and any(quad3)

    #print('az=',az)
    #print('el=',el)

    RADIANS=np.pi/180.
    az=(90-self.track_az)*RADIANS
    r=90.-self.track_el
    
    self.ax2.clear()
    self.ax2.plot(az, r)
    self.ax2.plot(az[0], r[0],'go')
    self.ax2.plot(az[-1], r[-1],'ro')    
    self.sky, = self.ax2.plot(0,0,'k*')
    self.ax2.set_rmax(90)
    #xtics = np.roll( np.arange(0,360,45) ,2 )
    #xtics = ['E','NE','N','NW','W','SW','S','SE']
    xtics = ['E','','N','','W','','S','']
    #print('xtics=',xtics)
    self.ax2.set_xticklabels(xtics) 
    self.ax2.set_yticks([30, 60, 90])          # Less radial ticks
    self.ax2.set_yticklabels(3*[''])          # Less radial ticks

    self.canv2.draw()


def plot_position(self,az,el):

    print('PLOT_POSITION:',az,el)

    RADIANS=np.pi/180.
    #if not self.sky:
    #    self.sky, = self.ax2.plot((90.-az)*RADIANS, 90.-el,'kx')
    #else:
    self.sky.set_data( (90.-az)*RADIANS, 90.-el)
    self.canv2.draw()
    return
    
    
# Function to assemble TLE data for a particular satellite
def get_tle(TLE,sat):
    if sat=='CAS-6':
        sat='TO-108'
        print('GET_TLE: Warning - name change for TO-107 to CAS-6')
    idx  = TLE.index(sat)
    tle  = TLE[idx]   + '\n'
    tle += TLE[idx+1] + '\n' 
    tle += TLE[idx+2] + '\n'

    return tle

################################################################################

# Structure to contain data for a satellite
class SATELLITE:
    def __init__(self,isat,name,qth,tbefore,tafter):

        print('\n',isat,' - Sat:',name)
        #print(tafter,tbefore)
        self.name = name
        self.isat = isat
        self.qth  = qth

        # Predict transits of this satellite over qth for the specified time span
        self.tle = get_tle(TLE,name)
        self.p   = predict.transits(self.tle, qth,
                                    ending_after=tafter, ending_before=tbefore)

        # Get transponder info for this sat
        self.get_transponders()
            
        # Look at the transits and determine times for visible sections
        self.pass_times = []
        self.t = []
        self.y = []
        self.t2 = []
        self.y2 = []
        tlast=0
        while True:

            # Move through list of passes & break if we're done
            try:
                transit = next(self.p)
            except:
                break

            # Determine start & end times for this pass
            ts = datetime.fromtimestamp(transit.start)
            te = datetime.fromtimestamp(transit.end)

            # There is a bug somewhere for AO-7 that gets stuck in an infinite loop - kludge to avoid problem
            if name=='AO-07':
                #print(transit.start,transit.end,tlast)
                #print(ts,te,datetime.fromtimestamp(tafter),datetime.fromtimestamp(tbefore))
                if tlast>=transit.end:
                    #print('Unexpected result at',ts,'- giving up')
                    #break
                    print('*** Unexpected result at',ts,'- bumping by 1 hour ...')
                    date99   = ts + timedelta(hours=1)
                    print(date99)
                    tafter2  = time.mktime(date99.timetuple())
                    self.p   = predict.transits(self.tle, qth,
                                                ending_after=tafter2, ending_before=tbefore)
                    continue
                else:
                    tlast=transit.end

            # Add this pass to list of plotting vars
            self.t.append(ts)
            self.y.append(None)
            self.t.append(ts)
            self.y.append(isat)
            self.t.append(te)
            self.y.append(isat)
            self.t.append(te)
            self.y.append(None)

            # Identify passes that are well above the horizon
            if transit.peak()['elevation'] >= MIN_PEAK_EL:
                #print transit.start,transit.end 
                tmid = datetime.fromtimestamp(
                    0.5*( transit.start+transit.end ) )
                self.t2.append( tmid )
                self.y2.append(isat)

            self.pass_times.append( 0.5*(transit.start+transit.end) )


    # Function to read list of transponders for this sat 
    def get_transponders(self):

        # We use the transponder data that has already been parsed
        # by Gpredict - for this, we need the sat number
        tle2=self.tle.split()
        #print('tle =',self.tle)
        #print('tle2=',tle2)
        self.number=int( tle2[2][:-1] )
        #print(self.number)
        self.main=None

        fname = os.path.expanduser(TRANSP_DATA+'/'+str(self.number)+'.trsp')
        #print(fname)

        # Read the Gpredict transponder data for this sat
        config = ConfigParser() 
        print(config.read(fname)) 
        self.transponders = OrderedDict()
        for transp in config.sections():

            # Get details for this transponder
            items=dict( config.items(transp) )
            #print(items)
            items['fdn1']=int( items['down_low'] )
            if 'down_high' in items:
                items['fdn2']=int( items['down_high'] )
            else:
                items['fdn2']=items['fdn1']

            # Make sure we have all the info we'll want later on
            if 'up_low' in items:
                items['fup1']=int( items['up_low'] )
            else:
                items['fup1']=0
            if 'up_high' in items:
                items['fup2']=int( items['up_high'] )
            else:
                items['fup2']=items['fup1']

            items['Inverting']=False
            if 'invert' in items:
                if items['invert']=='true':
                    items['Inverting']=True
            if items['Inverting'] and False:
                tmp=items['fup2']
                items['fup2']=items['fup1']
                items['fup1']=tmp                

            # Find the main transponder
            transp2=transp.upper()
            if ('PE0SAT' in transp2) or ('L/V' in transp2):
                flagged=''
            elif ('FM VOICE' in transp2) or ('MODE U/V (B) LIN' == transp2) or \
                 ('MODE U/V LINEAR' == transp2) or ('MODE V/U FM' == transp2) or \
                 ('TRANSPONDER' in transp2) or ('TRANSPODER' in transp2):
                if not self.main:
                    self.main=transp
                    flagged='*****'
                else:
                    print('************ WARNING - Multiple Transponders fit criteria - skipping ***************')
            else:
                flagged=''
            
            print('Transponder:',transp,flagged)
            print(items)
            print(items['mode'])
            self.transponders[transp] = items
            
            #sys.exit(0)


    # Function to compute current Doppler shifts for a specific sat
    # Also returns az and el info for rotor control
    def Doppler_Shifts(self,fdown,fup):
        # obs.doppler is the Doppler shift for 100-MHz:
        # doppler100=-100.0e06*((sat_range_rate*1000.0)/299792458.0) = f*rdot/c
        # So to get Doppler shift @ fc (MHz):
        # fdop = doppler100*fc/100e6

        # Observe sat at current time
        now = time.mktime( datetime.now().timetuple() )
        obs = predict.observe(self.tle, my_qth,now)
        print('\nobs=',obs,'\n')
        
        dop100  = obs['doppler']          # Shift for f=100 MHz
        fdop1 =  1e-8*dop100*fdown        # Downlink
        fdop2 = -1e-8*dop100*fup          # Uplink gets tuned in the opposite direction

        az = obs['azimuth']
        el = obs['elevation']
        
        return [fdop1,fdop2,az,el]

            
################################################################################

# The GUI
class SAT_GUI(QMainWindow):

    def __init__(self,parent=None):
        super(SAT_GUI, self).__init__(parent)

        # Init
        self.now=None
        self.sky=None
        self.Selected=None
        self.New_Selection=False
        
        # Start by putting up the root window
        print('Init GUI ...')
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('Satellite Pass Predictions by AA2IL')

        # We use a simple grid to layout controls
        self.grid = QGridLayout(self.win)
        nrows=7
        ncols=6

        # Create a calendar widget and add it to our layout
        row=0
        col=0
        self.cal = QCalendarWidget()
        self.grid.addWidget(self.cal,row,col,nrows-1,1)
        self.cal.clicked.connect(self.date_changed)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)   # Delete week numbers
     
        # Don't allow calendar size to change when we resize the window
        sizePolicy = QSizePolicy( QSizePolicy.Fixed,
                                  QSizePolicy.Fixed)
        self.cal.setSizePolicy(sizePolicy)

        # The Canvas where we will plot sky track
        self.fig2  = Figure()
        self.canv2 = FigureCanvas(self.fig2)
        self.grid.addWidget(self.canv2,row,ncols-1,nrows-1,1)

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
        #self.canv2.setSizePolicy(sizePolicy)

        # The Canvas where we will put the map
        row=1
        col=0
        self.fig = Figure()
        self.canv = FigureCanvas(self.fig)
        self.grid.addWidget(self.canv,nrows,col,1,ncols)

        # Allow canvas size to change when we resize the window
        # but make is always visible
        sizePolicy = QSizePolicy( QSizePolicy.MinimumExpanding, 
                                  QSizePolicy.MinimumExpanding)
        self.canv.setSizePolicy(sizePolicy)

        # Attach mouse click to handler
        cid = self.canv.mpl_connect('button_press_event', MouseClick)

        # Fetch the currently selected date, this is a QDate object
        date = self.cal.selectedDate()
        date0 = date.toPyDate()
        self.date1 = datetime.strptime( date0.strftime("%Y%m%d"), "%Y%m%d") 
        
        # Load satellite data
        self.load_sat_data()
        #print self.Satellites
        
        # Plot passes
        self.draw_passes()

        # User selections
        row=0
        col+=1
        #btn = QToolButton()
        #btn.setArrowType(QtCore.Qt.LeftArrow)
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_MediaSeekBackward')))
        btn.setToolTip('Click to regress 1 day')
        btn.clicked.connect(self.Regress)
        self.grid.addWidget(btn,row,col)

        #btn = QToolButton()
        #btn.setArrowType(QtCore.Qt.RightArrow)
        btn = QPushButton('')
        btn.setIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_MediaSeekForward')))
        btn.setToolTip('Click to advance 1 day')
        btn.clicked.connect(self.Advance)
        self.grid.addWidget(btn,row,col+1)

        row+=1
        Times=[]
        for i in range(25):
            t = '%2.2d:00' % i
            Times.append(t)

        lb=QLabel("Start Time:")
        self.StartTime_cb = QComboBox()
        self.StartTime_cb.addItems(Times)
        self.StartTime_cb.currentIndexChanged.connect(self.date_changed)
        self.StartTime_cb.setCurrentIndex(0)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.StartTime_cb,row,col+1)

        row+=1
        lb=QLabel("End Time:")
        self.EndTime_cb = QComboBox()
        self.EndTime_cb.addItems(Times)
        self.EndTime_cb.currentIndexChanged.connect(self.date_changed)
        self.EndTime_cb.setCurrentIndex(len(Times)-1)
        self.grid.addWidget(lb,row,col)
        self.grid.addWidget(self.EndTime_cb,row,col+1)

        # Place to put the pass details when the user clicks on a pass
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
        self.btn2 = QPushButton('Track')
        self.btn2.setToolTip('Click to engange Rig Control')
        self.btn2.clicked.connect(self.ToggleRigControl)
        self.btn2.setCheckable(True)
        self.grid.addWidget(self.btn2,row,col,1,2)
        self.rig_ctrl=False
        
        # Let's roll!
        self.show()

        
        
    # Function to engage/disengange rig control
    def ToggleRigControl(self):
        if self.Selected:
            self.rig_ctrl = not self.rig_ctrl
        print('Rig Control is',self.rig_ctrl)

        # Put up a reminder for something that is not availabe via CAT
        if self.rig_ctrl and P.sock.rig_type2=='IC9700':
            #msgBox = QMessageBox('Reminder!')
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

        print('Date Changed:')

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

        print('Computing orbits ...')
        
        # Set time limits
        date1   = datetime.now() - timedelta(days=NDAYS1)
        tafter  = time.mktime(date1.timetuple())
        date2   = date1 + timedelta(days=P.NDAYS2+NDAYS1)
        tbefore = time.mktime(date2.timetuple())
        
        # Loop over list of sats
        self.Satellites = OrderedDict()
        self.pass_times=[]
        for isat in range(1,len(SATELLITE_LIST) ):
            name=SATELLITE_LIST[isat]
            self.Satellites[name]=SATELLITE(isat,name,my_qth,tbefore,tafter)

        #print(self.Satellites)
        #sys.exit(0)

        
    # Plot passes for all sats
    def draw_passes(self):

        print('Draw passes...')
        self.ax = self.fig.add_subplot(111)
        #self.fig.tight_layout(pad=0)

        # Loop over list of sats
        self.pass_times=[]
        for name in list(self.Satellites.keys()):
            print(name)
            Sat=self.Satellites[name]

            # Plot passes for this sat
            c = COLORS[ (Sat.isat-1) % len(COLORS) ]
            self.pass_times.append(np.array( Sat.pass_times ))
            self.ax.plot(Sat.t,Sat.y,'-',label=name,linewidth=8,color=c)
            c2='w'
            self.ax.plot(Sat.t2,Sat.y2,'*',color=c2,markersize=12)

        # Beautify the x-labels
        self.fig.autofmt_xdate()
        myFmt = mdates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_formatter(myFmt)
        self.ax.set_xlim(self.date1,self.date1+timedelta(hours=24))

        self.ax.set_xlabel('Local Time', fontsize=18)
        self.ax.set_ylabel('Satellite', fontsize=16)

        # Fix-up vertical axis
        self.ax.grid()
        nsats = len(SATELLITE_LIST)-1
        self.ax.set_ylim(1-.1,nsats+.1)
        self.ax.set_yticks(range(1,nsats+1))
        self.ax.set_yticklabels(SATELLITE_LIST[1:])
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

        # Fiddling
        if False:
            print('-----------------------------')
            locs, labels = plt.yticks()
            print(locs)
            print(labels)
            plt.yticks(np.arange(6), ('Tom', 'Dick', 'Harry', 'Sally', 'Sue','Joe'))
        if False:
            print('-----------------------------')
            print(self.ax.get_yticklabels())
            print(SATELLITE_LIST[1:])
            self.ax.set_yticklabels(SATELLITE_LIST)
        
        # Re-draw the canvas
        self.canv.draw()


    # Function to draw spots on the map
    def UpdateMap(self):
        print('UpdateMap...')

        # Draw line showing current time
        if self.now:
            self.now.remove()
        now=datetime.now()
        print('now=',now)
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
        self.ax.set_title('Satellite Passes over '+P.MY_GRID+' for '+DATE)
        self.canv.draw()

        self.cal.setSelectedDate(self.date1)

        
    # Function to find next transit at current time
    def find_next_transit(self):
        
        # Loop over list of sats
        tnext=1e38
        for name in list(self.Satellites.keys()):
            print('\nFind best:',name)
            Sat=self.Satellites[name]
            
            # Observe sat at current time
            now = time.mktime( datetime.now().timetuple() )
            #obs = predict.observe(Sat.tle, my_qth,now)
            #print('\tobs=',obs)

            # Look at next transit for this sat
            p = predict.transits(Sat.tle, my_qth, ending_after=now)
            transit = next(p)
            print('Transit vars:', vars(transit) )

            # Keep track of next transit
            if transit.start<tnext:
                best=name
                tnext=transit.start

        ttt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tnext))
        print('\nNext transit:',best,ttt,'\n')
        return [best,tnext]

        
################################################################################

# Watch Dog Timer - Called every min minutes to monitor health of app
class WatchDog:
    def __init__(self,gui,min):

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.Monitor)
        msec=min*60*1000
        self.timer.start(msec)
        self.gui=gui

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

################################################################################

# Rig control called every sec seconds
class RigControl:
    def __init__(self,P,gui,sec):

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.Updater)
        self.timer.start(1000*sec)
        self.P=P
        self.gui=gui

    def Updater(self):
        P=self.P
        if False:
            print('RIG CONTROL UPDATER: Rig  =',P.sock.rig_type1,P.sock.rig_type2)
            if P.sock2.active:
                print('RIG CONTROL UPDATER: Rotor=',P.sock2.rig_type1,P.sock2.rig_type2)
        
        if gui.rig_ctrl and gui.Selected:

            # Tune to middle of transponder BW if we've selected a new sat
            if gui.New_Selection:
                print('New Sat Selected:',gui.Selected)
                self.satellite = gui.Satellites[gui.Selected]
                self.transp    = self.satellite.transponders[self.satellite.main]
                print('main=',self.satellite.main)
                print('transp=',self.transp)

                # Put rig into sat mode
                if P.sock.rig_type2=='FT991a':
                    print('Putting FT991a into SPLIT mode ...')
                    P.sock.split_mode(1)
                    self.vfos=['A','B']
                elif P.sock.rig_type2=='IC9700':
                    print('Putting IC9700 into SAT mode ...')
                    P.sock.sat_mode(1)
                    self.vfos=['M','S']
                else:
                    print('UPDATER: Unknown rig',P.sock.rig_type2)
                    sys.exit(0)

                # Check VFO bands - the IC9700 is quirky if the bands are reversed
                if P.sock.rig_type2=='IC9700':
                    frq1 = int( P.sock.get_freq(VFO=self.vfos[0]) )
                    band1 = P.sock.get_band(1e-6*frq1)
                    print('frq1=',frq1,band1)
                    #frq2 = int( P.sock.get_freq(VFO=self.vfos[1]) )
                    frq2=self.transp['fdn1']
                    band2 = P.sock.get_band(1e-6*frq2)
                    print('frq2=',frq2,band2)
                    if band1!=band2:
                        print('Flipping VFOs')
                        P.sock.select_vfo('X')
                    #sys.exit(0)
                        
                # Set proper mode on both VFOs
                mode=self.transp['mode']
                P.sock.set_mode(mode,VFO=self.vfos[0])
                if self.transp['Inverting']:
                    if mode=='USB':
                        P.sock.set_mode('LSB',VFO=self.vfos[1])
                    else:
                        P.sock.set_mode('USB',VFO=self.vfos[1])
                else:
                    P.sock.set_mode(mode,VFO=self.vfos[1])

                # Set down link freq to center of transp passband - uplink will follow
                self.fdown = 0.5*(self.transp['fdn1']+self.transp['fdn2'])
                self.track_freqs()
                
                gui.New_Selection=False

            else:

                # Check if op has spun main dial - if so, compute new downlink freq
                frq = int( P.sock.get_freq(VFO=self.vfos[0]) )
                if frq!=self.frqA:
                    print('Rig freq change:',self.frqA,frq)
                    self.fdown = frq - self.fdop1

                    # Don't do anything until op stops spinning the dial
                    if True:
                        self.frqA = frq
                        return

                # Update up and down link freqs 
                self.track_freqs()
                

    # Function to set up & downlink freqs on rig
    def track_freqs(self):
        P=self.P
        gui=self.gui
        
        # Compute uplink freq corresponding to downlink
        df = self.fdown - self.transp['fdn1']
        if self.transp['Inverting']:
            self.fup = self.transp['fup2'] - df
            #print('Inv:',self.transp['fup2'],df,self.fup)
        else:
            self.fup = self.transp['fup1'] + df
            #print('Non:',self.transp['fup1'],df,self.fup)
        #print('fdown=',self.fdown,'\tdf=',df,'\tfup=',self.fup, \
        #'\tInv=', self.transp['Inverting'])
            
        # Compute Doppler shifts for up and down links
        [self.fdop1,fdop2,az,el] = self.satellite.Doppler_Shifts(self.fdown,self.fup)
        print('TRACK_FREQS:',int(self.fdown),int(self.fdop1),
              int(self.fup),int(fdop2),'\t',int(az),int(el))

        # Set up and down link freqs
        self.frqB = int(self.fup+fdop2)
        P.sock.set_freq(1e-3*self.frqB,VFO=self.vfos[1])
        self.frqA = int(self.fdown+self.fdop1)
        P.sock.set_freq(1e-3*self.frqA,VFO=self.vfos[0])
        #print(self.frqA,self.frqB)

        # Check rotor - need some work here:
        # - Not tested at all
        # - check entire transit &
        # flip antenna if needed to avoid ambiquity at 180-deg
        #print('az=',gui.track_az,gui.flipper)
        if P.sock2.active:
            pos=P.sock2.get_position()
            if el<0:
                az=gui.track_az[0]
                el=0

            if gui.flipper:
                print('*** NEED a Flip-a-roo-ski ***')
                #az=az-180
                #el=180-el
                
            daz=pos[0]-az
            de=pos[1]-el
            
            print('pos=',pos,az,el,'\t',daz,de)

            if abs(daz)>ROTOR_THRESH or abs(de)>ROTOR_THRESH:
                P.sock2.set_position([int(az),int(el)])

        # Update sky track
        plot_position(gui,az,el)
            
            
################################################################################

# If the program is run directly or passed as an argument to the python
# interpreter then create a Calendar instance and show it
if __name__ == "__main__":

    print('\n****************************************************************************')
    print('\n   Satellite Pass Predicter beginning ...\n')
    P=PARAMS()

    # Open connection to rig
    P.sock = socket_io.open_rig_connection(P.connection,0,P.PORT,0,'SATELLITES',rig=P.rig)
    if P.sock.rig_type=='Icom':
        P.sock.icom_defaults()
    #sys.exit(0)
    
    # Open connection to rotor
    P.sock2 = socket_io.open_rig_connection(P.ROTOR_CONNECTION,0,P.PORT2,0,'ROTOR')
    if not P.sock2.active and P.sock2.connection!='NONE':
    #if not P.sock2.active or P.sock2.connection=='NONE':
        print('*** No connection available to rotor ***')
        sys.exit(0)
    else:
        print(P.sock2.active)
        print(P.sock2.connection)
        if P.sock2.active:
            print('Rotor found!!\t',P.sock2.rig_type1,P.sock2.rig_type2)

    # Get my qth
    lat, lon = locator_to_latlong(P.MY_GRID)
    my_qth = (lat,-lon,0)
    print('My QTH:',P.MY_GRID,my_qth)
    
    # Get TLE data
    print('Getting TLE data ...')
    if P.UPDATE_TLE:
        print('... Updating TLE data from Internet ...')
        if sys.version_info[0]==3:
            response = urllib.request.urlopen(URL1)
        else:
            response = urllib2.urlopen(URL1)
        html = response.read().decode("utf-8") 
        #print html
        #print len(html)
        fp=open('nasa.txt','w')
        fp.write(html)
        fp.close()
        #sys.exit(0)
    else:
        url2="file://" + os.path.expanduser(URL2)
        if sys.version_info[0]==3:
            response = urllib.request.urlopen(url2)
        else:
            response = urllib2.urlopen(url2)
        html = response.read().decode("utf-8") 
    #print( html)
    #print( type(html))
    TLE=html.split('\n')
    if False:
        print('TLE=',TLE)
        sys.exit(0)
    print(" ")

    app  = QApplication(sys.argv)
    gui  = SAT_GUI()
    monitor = WatchDog(gui,5)
    if True:
        rig_ctrl = RigControl(P,gui,1)
    
    date = gui.date_changed()

    # Determine best sat to track right now
    sat,ttt=gui.find_next_transit()
    plot_sky_track(gui,sat,ttt)
    
    print('And away we go ...')
    sys.exit(app.exec_())
    
