#!/usr/bin/env -S uv run --script
#
# NEW: /home/joea/miniconda3/envs/aa2il/bin/python -u
# OLD: /usr/bin/python3 -u 
################################################################################
#
# Ham Satellite Orbit Prediction and Rig Control - Rev 1.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# Gui to show predicted passes for various OSCARs and command rig and rotor to
# follow a user selected satellite trajectory.
#
# Notes:
# - To get a list of operational OSCARs, can check at
#      https://www.amsat.org/status
#      https://www.ariss.org/current-status-of-iss-stations.html
#
#   The list of known satellites is stored in ft_tables.py.
#
# - The TLE data is in the file   nasa.txt    and is updated using
#   the   -update   switch.
# - The transponder data is from SatNogs
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
# - Installation of predict engine:  (They've added support for python3)
#   sudo apt-get install python3-dev
#   git clone https://github.com/nsat/pypredict.git
#   cd pypredict
#   sudo python3 setup.py install
#   cd ..
#
# - Other things we need:
#    - install python3-pip (pip3) and python3-setuptools
#    - pip3 install pyhamtools
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
URL2 = "~/Python/pySat/nasa.txt"                                 # Local copy

################################################################################

import sys
from pyhamtools.locator import locator_to_latlong

from widgets_qt import QTLIB
exec('from '+QTLIB+'.QtWidgets import QApplication')
exec('from '+QTLIB+' import QtCore')

import urllib.request, urllib.error, urllib.parse
import json
from dateutil import tz
from utilities import get_Host_Name_IP,error_trap

import rig_io.socket_io as socket_io
import os
import time
from datetime import timedelta,datetime
from collections import OrderedDict
from pprint import pprint

from params import PARAMS
from watchdog import WatchDog
from rig_control import RigControl
from sat_class import SATELLITE
from gui import SAT_GUI
from tcp_server import *
from latlon2maiden import *
from fileio import read_gps_coords
from meteor_showers import *

################################################################################

VERSION='1.0'

################################################################################

print('\n****************************************************************************')
print('\n   Satellite Pass Predicter and Rig Control v',VERSION,'beginning ...\n')
P=PARAMS()
print("P=")
pprint(vars(P))
print('\n\tPython version=',sys.version_info[0],'.',
      sys.version_info[1],'.',sys.version_info[2])
print('\tQT Version=',QtCore.qVersion(),'\n')

# Put up splash screen
P.app  = QApplication(sys.argv)
P.gui  = SAT_GUI(P)

# Test internet connection
print('Checking internet connection ...')
P.gui.status_bar.setText('Checking internet connection ...')
P.host_name,P.host_ip=get_Host_Name_IP()
print("\nHostname :  ", P.host_name)
print("IP : ", P.host_ip,'\n')
if P.host_ip=='127.0.0.1':
    P.INTERNET=False
    print('No internet connection')
    if P.UPDATE_TLE:
        print('Cant update TLE from internet!!!!')
        sys.exit(0)
else:
    P.INTERNET=True

# Open connection to rig
P.gui.status_bar.setText('Opening connection to rig ...')
P.sock = socket_io.open_rig_connection(P.connection,0,P.PORT,0,'SATELLITES',rig=P.rig)
if P.sock.rig_type=='Icom':
    P.sock.icom_defaults()
print('RIG:',P.sock.rig_type,P.sock.rig_type1,P.sock.rig_type2)
#sys.exit(0)

# Make sure rig is properly setup
if P.sock.rig_type2=='IC9700':

    # Pre-amp on, attenuator off
    P.sock.frontend(1,1,0)

    # Check computer time
    now = datetime.utcnow()
    print('\nnow=',now)

    # Check rig time
    d,t,z=P.sock.get_date_time(VERBOSITY=1)
    print('d=',d,'\tt=',t)
    utc = datetime.strptime(d+' '+t,'%Y%m%d %H%M%S')
    print('Rig date=',d,'\ttime=',t,'\tzone=',z,
          '\nRig utc=',utc)
    #sys.exit(0)

    delta = (now - utc).total_seconds()/60      # In minutes
    print('delta=',delta,'min.')

    if not P.INTERNET and delta<-1:
        
        # The RPi doesn't have a real-time clock so use rig time if
        # there is no internet
        arch=os.getenv('MACHTYPE')
        if arch=='aarch64':
            from_zone = tz.tzutc()             # Zulu
            to_zone = tz.tzlocal()             # Local
            utc = utc.replace(tzinfo=from_zone)
            rig = utc.astimezone(to_zone)

            rig_date=rig.date().strftime("%Y-%m-%d")
            rig_time=rig.time().strftime("%H:%M:%S")
            val = rig_date+' '+rig_time
            
            print('\nSetting system clock from rig to',val,'...') 
            cmd = 'sudo date --set="'+val+'" &'
            os.system("echo "+cmd)
            os.system(cmd)
            time.sleep(1)
            #sys.exit(0)

        else:
            print('\n*** pySAT: NEED SOME CODE TO SET COMPUTER TIME FROM RIG !!!! *** arch=',arch,'\n')
            sys.exit(0)

    elif abs(delta)>2:
        
        # We have an internet connection so we assume the RPi clock is set
        # Keep rig clock p to date also
        print('Setting rig time ...')
        P.sock.set_date_time(1)        
        #sys.exit(0)    
    
# Open connection to rotor
P.gui.status_bar.setText('Opening connection to rotor ...')
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

        # Test if rotor controller is turned on
        if P.sock2.connection=='DIRECT' or True:
            print('Testing rotor ...')
            pos=P.sock2.get_position()
            print('pos=',pos)
            if pos[0]==179. and pos[1]==0:
                pos2=[175,5]
                P.sock2.set_position(pos2)
                time.sleep(1)
                pos=P.sock2.get_position()
                print('pos=',pos)
                if pos[0]==179. and pos[1]==0:
                    print('\n*** Rotor not responding - make sure its plugged in and controller is turned on ***\n')
                    sys.exit(0)

# Open connection to SDR
if P.USE_SDR:
    print('Looking for the SDR ...')
    P.gui.status_bar.setText('Looking for SDR ...')
    P.sock3 = socket_io.open_rig_connection(P.SDR_CONNECTION,0,P.PORT3,0,'SATELLITES')
    if not P.sock3.active:
        print('*** No connection available to SDR ***')
        sys.exit(0)
    else:
        print(P.sock3.connection)
        print('SDR found!!\t',P.sock3.rig_type1,P.sock3.rig_type2)
        #sys.exit(0)

################################################################################
        
# Get my qth
if 'MY_ALT' not in P.SETTINGS and 'MY_ALT_FT' in P.SETTINGS:
    P.SETTINGS['MY_ALT'] = float(P.SETTINGS['MY_ALT_FT']) /3.084
if P.GPS:
    
    # Based on lat/long/alt from GPS
    [lat,lon,alt,gridsq]=read_gps_coords()
    print('loc=',[lat,lon,alt,gridsq])
    P.MY_GRID = latlon2maidenhead(lat,lon,12)
    
    P.SETTINGS['MY_LAT'] = lat        
    P.SETTINGS['MY_LON'] = lon
    P.SETTINGS['MY_ALT'] = alt        
    P.SETTINGS['MY_GRID'] = P.MY_GRID
    
elif 'MY_LAT' in P.SETTINGS and 'MY_LON' in P.SETTINGS:

    # Based on entered lat/lon
    lat = float( P.SETTINGS['MY_LAT'] )
    lon = float( P.SETTINGS['MY_LON'] )
    alt = float( P.SETTINGS['MY_ALT'] )
    P.MY_GRID = latlon2maidenhead(lat,lon,12)
    
else:

    # Based on grid square
    P.MY_GRID = P.SETTINGS['MY_GRID']
    lat, lon = maidenhead2latlon(P.MY_GRID)
    alt = float( P.SETTINGS['MY_ALT'] )
    P.SETTINGS['MY_LAT'] = lat        
    P.SETTINGS['MY_LON'] = lon
        
P.my_qth = (lat,-lon,alt)
print('My QTH:',P.MY_GRID,P.my_qth)
#sys.exit(0)

# There is a provision for looking at overlap with another grid square
if P.GRID2:
    lat2, lon2 = locator_to_latlong(P.GRID2)
    P.other_qth = (lat2,-lon2,0)
    print('Other QTH:',P.GRID2,P.other_qth)

################################################################################

# Function to fetch data from satnogs
def get_satnogs_json(url,outfile):
    print('GET SATNOSG: Fetching',outfile,'...')
    try:
        response = urllib.request.urlopen(url)
    except:
        error_trap('GET SATNOGS JSON: Unable to fetch satnogs data ---')
        return None
    txt = response.read().decode("utf-8")
    
    print('txt=',txt)
    print(type(txt),len(txt))

    fp=open(outfile,'w', encoding="utf-8")
    fp.write(txt)
    fp.close()

    obj=json.loads(txt)
    #print('obj=',obj)
    #for key in obj:
    #    print(key)

    return obj

# Function to grab all of the available satnogs info
def get_satnogs_info():
    
    # This is the root of where all the sat info is stored
    URL3="https://db.satnogs.org/api/"
    root=get_satnogs_json(URL3,'api.json')
    print('root=',root)
    print(root.keys())
    
    # This is the transponder data, i.e. transmitters.json
    for item in root.keys():
        URL4=URL3+item+'/'
        get_satnogs_json(URL4,item+'.json')


# Function to parse tle data
def parse_tle_data():
    item='tle'
    item='satellites'
    with open(item+'.json') as fp:
        objs = json.load(fp)
    print(type(objs),len(objs))
    #print('objs=',objs)

    for obj in objs:
        id=obj['norad_cat_id']
        if id in [25544,7530] or False:
            print(obj)
    
# Function to parse transmitter data
def parse_trsp_data():
    item='transmitters'
    with open(item+'.json') as fp:
        objs = json.load(fp)
    print('PARSE TRSP DATA:',type(objs),len(objs))
    #print('objs=',objs)

    path='trsp'
    if not os.path.exists(path):
        os.makedirs(path)

    ids=[]
    for obj in objs:
        id=obj['norad_cat_id']
        if id in [25544,7530] or True:
            if id not in ids:
                attr='w'
                ids.append(id)
            else:
                attr='a'
            fp=open(path+'/'+str(id)+'.trsp',attr)
            #print(obj)
            #print('\n['+obj['description']+']')
            fp.write('\n['+obj['description']+']\n')
            for item in ['uplink_low','uplink_high','downlink_low','downlink_high','mode','invert','baud']:
                val=obj[item]
                if type(val)==float:
                    val=int(val)
                if val:
                    tag=item.upper().replace('LINK','')
                    #print(tag+'='+str(val),type(val)==float)
                    fp.write(tag+'='+str(val)+'\n')
            fp.close()

    #print('PARSE TRSP DATA')
    #sys.exit(0)
    
    
# Get TLE data
print('Getting TLE data ...')
P.gui.status_bar.setText('Reading TLE data ...')
if False:
    # Use nasa.txt instead - old
    parse_tle_data()
    sys.exit(0)

if True:
    # Get timestamp of nasa.txt
    if P.PLATFORM=='Windows': 
        URL2=os.getcwd()+'/nasa.txt'                # Override for now
    fname=os.path.expanduser(URL2)
    print('URL2=',fname)
    if not os.path.isfile(fname) or not os.path.isdir('trsp'):
        print('nasa.txt and/or trsp/ not found - Need to update TLE data')
        P.UPDATE_TLE = True
    else:
        ti_c = os.path.getctime(fname)
        ti_m = os.path.getmtime(fname)
 
        # Converting the time in seconds to a timestamp
        c_ti = time.ctime(ti_c)
        m_ti = time.ctime(ti_m)
        print(f"{fname}\n was created at {c_ti} and last modified at {m_ti}")

        now = time.time()
        age=(now-ti_m)/(3600.)
        print(f'age= {age} hours')

        if age>24:
            print('Need to update TLE data')
            P.UPDATE_TLE = True
    
    #sys.exit(0)

if P.UPDATE_TLE and P.INTERNET:
    print('... Updating SatNogs data from Internet ...')
    P.gui.status_bar.setText('Retrieving SatNogs Data ...')
    get_satnogs_info()
    
    print('... Updating Transponder data  ...')
    parse_trsp_data()
    
    print('... Updating TLE data from Internet ...')
    if sys.version_info[0]==3:
        response = urllib.request.urlopen(URL1)
    else:
        response = urllib2.urlopen(URL1)
    html = response.read().decode("utf-8") 
    #print(html)
    #print( len(html) )
    
    fname=os.path.expanduser(URL2)
    fp=open(fname,'w')
    fp.write(html)
    fp.close()
    #sys.exit(0)
else:
    if P.PLATFORM=='Windows':
        url2="file:\\" + os.path.expanduser(URL2)
    else:
        url2="file://" + os.path.expanduser(URL2)
    print('url=',url2)
    if sys.version_info[0]==3:
        response = urllib.request.urlopen(url2)
    else:
        response = urllib2.urlopen(url2)
    html = response.read().decode("utf-8") 
#print( html)
#print( type(html))
if P.PLATFORM=='Windows':
    html=html.replace('\r','')
P.TLE=html.replace('\n\n','\n').split('\n')
#print('TLE=',P.TLE)
#sys.exit(0)
print(" ")

# Get meteor shower info also    
P.SHOWERS = get_meteor_showers()
    
# Open UDP client
if P.UDP_CLIENT:
    P.gui.status_bar.setText('Opening UDP client ...')
    for itry in range(5):
        try:
            print('Opening TCP client ...',itry)
            #P.udp_client = TCP_Client(P,None,KEYER_UDP_PORT,Client=True)
            P.udp_client = TCP_Server(P,None,KEYER_UDP_PORT,Server=False)
            print('... TCP Client Opened.')
            break
        except:
            error_trap('PYSAT Main - Error opening UDP Client - Try again in 2-seconds...')
            time.sleep(2)
    else:
        print('--- Unable to connect to UDP socket after 5-tries - giving :-(')
        sys.exit(0)

# Construct gui        
P.gui.status_bar.setText('Constructing GUI ...')
P.gui.construct_gui()
P.monitor = WatchDog(P,5)
P.ctrl = RigControl(P,1)

# Determine best sat to track right now
date = P.gui.date_changed()
sat,ttt=P.gui.find_next_transit([P.sat_name])
print('Here we go...')
if sat:
    P.gui.plot_sky_track(sat,ttt)

# Event loop
print('And away we go ...')
P.app.exec()

# Exit gracefully
print('Leaving app ...')
P.sock.split_mode(0)
sys.exit(0)
