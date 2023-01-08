#! /usr/bin/python3 -u
################################################################################
#
# Ham Satellite Orbit Prediction and Rig Control - Rev 1.0
# Copyright (C) 2021-3 by Joseph B. Attili, aa2il AT arrl DOT net
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
from PyQt5.QtWidgets import QApplication
import urllib.request, urllib.error, urllib.parse
import json
from dateutil import tz
from utilities import get_Host_Name_IP

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
#from tcp_client import *
from tcp_server import *
from latlon2maiden import *
from fileio import read_gps_coords

################################################################################

print('\n****************************************************************************')
print('\n   Satellite Pass Predicter and Rig Control beginning ...\n')
P=PARAMS()

# Test internet connection
print('Checking internet connection ...')
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
P.sock = socket_io.open_rig_connection(P.connection,0,P.PORT,0,'SATELLITES',rig=P.rig)
if P.sock.rig_type=='Icom':
    P.sock.icom_defaults()
print('RIG:',P.sock.rig_type,P.sock.rig_type1,P.sock.rig_type2)
    #sys.exit(0)

# Make sure rig is properly setup
if P.sock.rig_type2=='IC9700':

    # Pre-amp on, attenuator off
    P.sock.frontend(1,1,0)

    # Check rig time
    d,t,z=P.sock.get_date_time()
    utc = datetime.strptime(d+' '+t,'%Y%m%d %H%M%S')
    #utc = utc.replace(tzinfo=tz.tzutc())
    print('Rig date=',d,'\ttime=',t,'\tzone=',z,
          '\nRig utc=',utc)

    now = datetime.utcnow()
    #now = now.replace(tzinfo=tz.tzutc())
    print('now=',now)

    delta = (now - utc).total_seconds()/60      # In minutes
    print('delta=',delta)

    if delta>2.:
        print('Setting rig time ...')
        P.sock.set_date_time(1)        
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
if False:
    # Based on configured grid square
    lat,lon=maidenhead2latlon(P.MY_GRID)
    P.my_qth = (lat,-lon,0)
    print('Based on grid square: \tMy QTH:',P.MY_GRID,P.my_qth)
else:
    # Based on lat/long/alt from GPS
    if P.GPS:
        [lat,lon,alt,gridsq]=read_gps_coords()
        print('loc=',[lat,lon,alt,gridsq])
        P.MY_GRID = latlon2maidenhead(lat,lon,12)
        
        P.SETTINGS['MY_LAT'] = lat        
        P.SETTINGS['MY_LON'] = lon
        P.SETTINGS['MY_ALT'] = alt        
        P.SETTINGS['MY_GRID'] = P.MY_GRID        
    elif 1:
        lat = float( P.SETTINGS['MY_LAT'] )
        lon = float( P.SETTINGS['MY_LON'] )
        alt = float( P.SETTINGS['MY_ALT'] )
        P.MY_GRID = latlon2maidenhead(lat,lon,12)
    else:
        P.MY_GRID = 'DM37QG46ML'
        lat, lon = maidenhead2latlon(P.MY_GRID)
        alt=1654
        
    P.my_qth = (lat,-lon,alt)
    print('Based on GPS: \t\tMy QTH:',P.MY_GRID,P.my_qth)
    #sys.exit(0)

if False:
    # Experiment with various precisions - locator in pyhamtools doesn't
    # provide a whole lot of accuracy
    for n in [4,6,8,10,12]:
        gridsq=P.MY_GRID[:n]
        print(gridsq)
        lat, lon = locator_to_latlong(gridsq)
        my_qth = (lat,-lon,0)
        print('My QTH:',gridsq,my_qth)

    sys.exit(0)
    
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
    except Exception as e: 
        print(e)
        print('--- Unable to fetch satnogs data ---')
        return None
    txt = response.read().decode("utf-8")
    
    #print('txt=',txt)
    #print(type(txt),len(txt))
    
    fp=open(outfile,'w')
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
    print(type(objs),len(objs))
    #print('objs=',objs)

    ids=[]
    for obj in objs:
        id=obj['norad_cat_id']
        if id in [25544,7530] or True:
            if id not in ids:
                attr='w'
                ids.append(id)
            else:
                attr='a'
            fp=open('trsp/'+str(id)+'.trsp',attr)
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
    
    
# Get TLE data
print('Getting TLE data ...')
if False:
    # Use nasa.txt instead - old
    parse_tle_data()
    sys.exit(0)

if True:
    # Get timestamp of nasa.txt
    fname=os.path.expanduser(URL2)
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
    url2="file://" + os.path.expanduser(URL2)
    if sys.version_info[0]==3:
        response = urllib.request.urlopen(url2)
    else:
        response = urllib2.urlopen(url2)
    html = response.read().decode("utf-8") 
#print( html)
#print( type(html))
#P.TLE=html.split('\n')            # Old
#P.TLE = [line for line in html.split('\n') if len(line)>0]      # Overcome double \n
P.TLE=html.replace('\n\n','\n').split('\n')            # New
print('TLE=',P.TLE)
#sys.exit(0)
print(" ")

# Open UDP client
if P.UDP_CLIENT:
    for itry in range(5):
        try:
            print('Opening TCP client ...',itry)
            #P.udp_client = TCP_Client(P,None,KEYER_UDP_PORT,Client=True)
            P.udp_client = TCP_Server(P,None,KEYER_UDP_PORT,Server=False)
            print('... TCP Client Opened.')
            break
        except Exception as e: 
            print(e)
            time.sleep(2)
    else:
        print('--- Unable to connect to UDP socket - giving up ---')
        sys.exit(0)

# Put up gui        
P.app  = QApplication(sys.argv)
P.gui  = SAT_GUI(P)
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
P.app.exec_()

# Exit gracefully
print('Leaving app ...')
P.sock.split_mode(0)
sys.exit(0)

    
