#! /usr/bin/python3 -u
################################################################################
#
# Satellite orbit prediction - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui to show predicted passes for various OSCARs.
#
# Notes:
# - To get a list of operational OSCARs, can check at
#      https://ka7fvv.net/satellite.htm
#      https://www.amsat.org/status
#      https://www.ariss.org/current-status-of-iss-stations.html
#
#   The list of displayed sat is stored in ft_tables.py - This needs
#   to be moved to a config file.
#
# - The TLE data is in the file   nasa.txt    and is updated using
#   the   -update   switch.
# - The transponder data is from gpredict
#
# - When a new satellite is introduced, it may be difficult to get
#   Gpredict to recognize it.  To fix this:
#     1) Find the satellite in the nasa.txt file downloaded by this program
#     2) The second column in the TLE data contains the satellite number, e.g. 07530 for AO-7
#     3) Delete the corresponding .sat file in ~/.config/Gpredict/satdata
#     4) In Gpredict, update TLE data using LOCAL files - point to this directory
#     5) Gpredict seems to recognize .txt files which is why nasa.all
#        has been renamed to nasa.txt
#
# - Migrated to python3 & Qt5 - To get this this to work, had to
#    - fiddle with pypredict/predict.c - they changed the init of C functions
#      in python 3 - ugh!
#    - install python3-pip (pip3) and python3-setuptools
#    - pip3 install pyhamtools
#   In python3, there is a distinction between bytes and string so the
#   .decode(...)   below takes care of that.
#
# - Installation of predict engine:
#   Problem with this package - they changed the init module - ugh!
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
URL1 = "http://www.amsat.org/amsat/ftp/keps/current/nasa.all"    # AMSAT latest & greatest
URL2 = "~/Python/satellites/nasa.txt"                               # Local copy

################################################################################

import sys
from pyhamtools.locator import locator_to_latlong
from PyQt5.QtWidgets import QApplication
import urllib.request, urllib.error, urllib.parse

import rig_io.socket_io as socket_io
import os
import time
from datetime import timedelta,datetime
from collections import OrderedDict

from params import PARAMS
from watchdog import WatchDog
from rig_control import RigControl
from sat_class import SATELLITE
from gui import SAT_GUI
from rig_io.ft_tables import SATELLITE_LIST
from tcp_client import *

################################################################################

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
    print('*** No connection available to rotor ***')
    sys.exit(0)
else:
    print(P.sock2.active)
    print(P.sock2.connection)
    if P.sock2.active:
        print('Rotor found!!\t',
              P.sock2.rig_type1,P.sock2.rig_type2,P.sock2.connection)

        if P.sock2.connection=='DIRECT':
            print('Testing it ...')
            pos=P.sock2.get_position()
            print('pos=',pos)
            sys.exit(0)        

# Open connection to SDR
if P.USE_SDR:
    print('Looking for the SDR ...')
    P.sock3 = socket_io.open_rig_connection(P.SDR_CONNECTION,0,P.PORT3,0,'SATELLITES')
    if not P.sock3.active:
        print('*** No connection available to SDR ***')
        sys.exit(0)
    else:
        print(P.sock3.connection)
        print('SDR found!!\t',P.sock3.rig_type1,P.sock3.rig_type2)
        #sys.exit(0)
    
# Get my qth
lat, lon = locator_to_latlong(P.MY_GRID)
P.my_qth = (lat,-lon,0)
print('My QTH:',P.MY_GRID,P.my_qth)

if P.GRID2:
    lat2, lon2 = locator_to_latlong(P.GRID2)
    P.other_qth = (lat2,-lon2,0)
    print('Other QTH:',P.GRID2,P.other_qth)
    
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
P.TLE=html.split('\n')
if False:
    print('TLE=',TLE)
    sys.exit(0)
print(" ")

# Open UDP client
if P.UDP_CLIENT:
    try:
        print('Opening TCP client ...')
        P.udp_client = TCP_Client(None,7474)
        #worker = Thread(target=P.udp_client.Listener, args=(), name='UDP Server' )
        #worker.setDaemon(True)
        #worker.start()
        #P.THREADS.append(worker)
        print('... TCP Client Opened.')
    except Exception as e: 
        print(e)
        print('--- Unable to connect to UDP socket ---')
        sys.exit(0)        
                
P.app  = QApplication(sys.argv)
P.gui  = SAT_GUI(P)
P.monitor = WatchDog(P,5)
P.ctrl = RigControl(P,1)

# Determine best sat to track right now
date = P.gui.date_changed()
sat,ttt=P.gui.find_next_transit([P.sat_name])
P.gui.plot_sky_track(sat,ttt)

print('And away we go ...')
P.app.exec_()
print('Leaving app ...')
P.sock.split_mode(0)
sys.exit(0)

    
