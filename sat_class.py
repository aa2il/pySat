#! /usr/bin/python3 -u
################################################################################
#
# sat_class.py - Rev 2.0
# Copyright (C) 2021-3 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Class containing individula satellite data
#
# Even though the moon is a satellite of the earth, the TLE way of doing things
# doesn't work.  Instead, we use this library - it was already installed
#    https://rhodesmill.org/pyephem/index.html
#    pip3 install pyephem
#
# They suggest using  The Skyfield astronomy library  instead but pyephem
# seems to work just fine for our purposes.  For future reference:
#    https://rhodesmill.org/skyfield/
#
# Unfortunately, there are some differences in the terms used quantify the
# orbit of the moon vs those for artificial sats (e.g. alt vs el).
# I'm sticking with the sat way of doing things.
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

#TRANSP_DATA = "~/.config/Gpredict/trsp"   # Transponder data as parsed by gpredict
TRANSP_DATA = "~/Python/pySat/trsp"       # Transponder data
MIN_PEAK_EL  = 30                         # Degrees, min. elevation to identify overhead passes
USE_PYPREDICT=False
USE_PYPREDICT=True
SUN_UPDATE_INTERVAL = 10*60               # Only update every ten minutes

################################################################################

if USE_PYPREDICT:
    import predict
    
import os
import sys
from configparser import ConfigParser 
from collections import OrderedDict
import time
from datetime import timedelta,datetime, timezone
import ephem
#from math import pi

from PyQt5 import QtCore
from PyQt5.QtWidgets import *

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.offsetbox import AnchoredText
import matplotlib.patches as mpatches
from matplotlib.image import imread

from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker
from shapely.geometry.polygon import Polygon
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from constants import *

################################################################################

# Function to assemble TLE data for a particular satellite
def get_tle(TLE,sat):
    sat2=sat
    if sat=='CAS-6':
        sat2='TO-108'
        print('GET_TLE: Warning - name change for TO-107 to CAS-6')
    elif sat=='AO-7':
        sat2='AO-07'
        print('GET_TLE: Warning - name change for AO-7 to AO-07')
    elif sat=='XW-3':
        sat2='XW 3'
        print('GET_TLE: Warning - name change for XW-3 to XW 3')
    elif sat=='FS-3':
        sat2='Falconsat-3'
        print('GET_TLE: Warning - name change for FS-3 to Falconsat-3')

    try:
        idx  = TLE.index(sat2)
    except Exception as e: 
        print('\n*** TRAPPED ERROR in GET_TLE ***')
        print( str(e) )
        print('TLE=',TLE)
        #sys.exit(0)
        return None

    tle = sat + '\n' \
        + TLE[idx+1] + '\n' \
        + TLE[idx+2] + '\n'

    if sat=='ISS':
        print('GET_TLE: sat=',sat,'\ntle=',tle)
        #sys.exit(0)
    
    return tle

################################################################################

# Structure compatible with what comes out of Predict
class TRANSIT:
    def __init__(self,info,t,az,el,lats,lons,footprints):

        # info:
        # 0  Rise time
        # 1  Rise azimuth
        # 2  Maximum altitude time
        # 3  Maximum altitude
        # 4  Set time
        # 5  Set azimuth
        
        self.start = ephem.localtime(info[0]).timestamp()
        self.end   = ephem.localtime(info[4]).timestamp()
        
        self.t     = t
        self.az    = az
        self.el    = el

        if info[3]==None:
            self.max_el = 0
        else:
            self.max_el = info[3]*RAD2DEG

        self.lats  = lats
        self.lons  = lons
        self.footprints  = footprints

    def duration(self):
        return self.end-self.start
    
    def peak(self):
        return {'elevation':self.max_el,'slant_range':0}

################################################################################

# Structure to contain data for a satellite
class SATELLITE:
    def __init__(self,isat,name,qth,date1,date2,TLE):

        print('\nSATELLITE CLASS: isat=',isat,'-\tSat:',name, \
              '\ttb-ta:',date1,date2,'\tqth:',qth)
        self.name = name
        self.isat = isat
        self.qth  = qth

        self.main=None
        self.pass_times = []
        self.t = []
        self.y = []
        self.t2 = []
        self.y2 = []
        self.last_update = time.time() - SUN_UPDATE_INTERVAL
        
        # Greenwich
        self.greenwich = ephem.Observer()
        self.greenwich.lat = '0'
        self.greenwich.lon = '0'
        
        # Form location object
        self.obs = ephem.Observer()
        self.obs.lat = str( self.qth[0] )
        self.obs.lon = str( -self.qth[1] )
        self.obs.elevation = self.qth[2]
        self.obs.pressure=0
        
        # The moon is special since we don't use TLEs
        if name=='Moon':
            self.fly_me_to_the_moon(date1,date2)
            return

        # Predict transits of this (artificial) satellite over qth for the specified time span
        tafter  = time.mktime(date1.timetuple())
        tbefore = time.mktime(date2.timetuple())
        self.tle = get_tle(TLE,name)
        if not self.tle:
            return
        tle0=self.tle.split('\n')
        self.sat = ephem.readtle(tle0[0],tle0[1],tle0[2])
        if USE_PYPREDICT:
            self.p   = predict.transits(self.tle, qth,
                                        ending_after=tafter, ending_before=tbefore)

        # Get transponder info for this sat
        self.get_transponders()
            
        # Look at the transits and determine times for visible sections
        tlast=0
        ts_old=None
        te_old=None
        npasses=0
        while True:

            # Move through list of passes & break if we're done
            if USE_PYPREDICT:
                try:
                    transit = next(self.p)
                except:
                    break

            else:
                transit = self.next_transit(tafter)
                #print('HEY:',tafter,tbefore,transit.start,transit.end)
                
                if transit==None or transit.start>tbefore:
                    break
                else:
                    tafter=transit.end+1

            # Determine start & end times for this pass
            ts = datetime.fromtimestamp(transit.start)
            te = datetime.fromtimestamp(transit.end)
            npasses+=1
            #print('Pass=',npasses,'\tts=',ts,'\tte=',te)
            if npasses>1000:
                print('Too many passes!')
                sys.exit(0)

            # AO-7 seems to have a problem with getting stuck in infinite loops
            # Avoid this
            if te_old and te<te_old:
                print('ts_old=',ts_old,'\tte_old=',te_old)
                print('ts    =',ts,    '\tte    =',te)
                print('Hmmm - we seem to be going backwards here !!!')
                break
                sys.exit(0)
            else:
                ts_old=ts
                te_old=te

            # There are bug somewhere for a few sats that gets stuck in an infinite loop - kludge to avoid problem
            if name in ['AO-07','FO-29'] and USE_PYPREDICT:
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

            elif name=='FO-29' and USE_PYPREDICT:
                print('HEY!!')
                #print(transit.start,transit.end,transit.end-transit.start,tlast)
                #print(ts,te,datetime.fromtimestamp(tafter),datetime.fromtimestamp(tbefore))
            

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
        # For this, we need the sat number
        NO_TRANSP=['Moon','Orbicraft-Zorkiy']
        if self.name in NO_TRANSP:
            # There are no transponders but we fake till we make it
            self.number=self.name
        else:
            print('GET_TRANSPONDERS: tle =',self.tle)
            tle2=self.tle.split()
            print('GET_TRANSPONDERS: tle2=',tle2)
            self.number=int( tle2[2][:-1] )
            print('GET_TRANSPONDERS: number=',self.number)

        fname = os.path.expanduser(TRANSP_DATA+'/'+str(self.number)+'.trsp')
        print('fname=',fname)
        #sys.exit(0)

        # Read the transponder data for this sat
        config = ConfigParser() 
        print('config.read=',config.read(fname)) 
        self.transponders = OrderedDict()
        for transp in config.sections():

            # Get details for this transponder
            items=dict( config.items(transp) )
            if self.name=='HO-113':
                print('\nitems=',items)
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

            # Decipher info about this transponder
            transp2=transp.upper()
            print('name=',self.name,'\ttransp2=',transp2)
            items['Inverting']=False
            if self.name=='HO-113' and 'MODE V/U' in transp2:
                items['Inverting']=True
            if 'invert' in items:
                if items['invert'].lower()=='true':
                    items['Inverting']=True

            # Find the main transponder
            if self.name in NO_TRANSP:
                if 'MODE V' in transp2:
                    self.main=transp
                    flagged='*****'
                else:
                    flagged=''
            elif self.name=='ISS':
                if 'VOICE REPEATER' in transp2:
                    self.main=transp
                    flagged='*****'
                else:
                    flagged=''
            elif ('PE0SAT' in transp2) or ('L/V' in transp2) or ('U/V CW' in transp):
                print('*** Skipping',transp)
                flagged=''
            elif ('FM VOICE' in transp2) or ('FM TRANSCEIVER' in transp2) or \
                 ('MODE U/V (B) LIN' == transp2) or \
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
            print('items=',items)
            print('mode=',items['mode'])
            self.transponders[transp] = items
            
            #sys.exit(0)

        if not self.main:
            print('Hmmmmm - never found main transponder for this sat :-(',self.name)
            if not self.name in NO_TRANSP:
                sys.exit(0)

    # Function to compute current Doppler shifts for a specific sat
    # Also returns az and el info for rotor control
    def Doppler_Shifts(self,fdown,fup,my_qth):
        # obs.doppler is the Doppler shift for 100-MHz:
        # doppler100=-100.0e06*((sat_range_rate*1000.0)/299792458.0) = f*rdot/c
        # So to get Doppler shift @ fc (MHz):
        # fdop = doppler100*fc/100e6

        # Observe sat at current time
        now = time.mktime( datetime.now().timetuple() )
        if self.name=='Moon':
            # Hack hack hack!
            [az,el,lat,lon]   = self.current_moon_position()
            return [0,0,az,el,230e3,lat,lon,1]
        else:
            if USE_PYPREDICT:
                obs = predict.observe(self.tle, my_qth,now)

                if True:
                    obs1=self.observe(now)
                    print('Doppler:',obs['doppler'],obs1['doppler'])
                    #sys.exit(0)

            else:
                obs=self.observe(now)
                
        if False:
            print('\nobs=',obs,'\n')

        # Compute Doppler shifts
        dop100  = obs['doppler']          # Shift for f=100 MHz
        fdop1 =  1e-8*dop100*fdown        # Downlink
        fdop2 = -1e-8*dop100*fup          # Uplink gets tuned in the opposite direction

        # Return the sat position also
        az = obs['azimuth']
        el = obs['elevation']
        rng = obs['slant_range']
        lon = obs['longitude']
        lat = obs['latitude']
        footprint = obs['footprint']
        
        return [fdop1,fdop2,az,el,rng,lat,lon,footprint]

################################################################################

    # Function to observe satellite at a given time
    def observe(self,t):

        # Compute dat mechanics at thime t
        self.obs.date = datetime.fromtimestamp(t,tz=timezone.utc)
        self.sat.compute(self.obs)

        # These calcs came from pawing through pypredict C code
        xkmper=6.378137E3
        sat_alt= 1e-3*self.sat.elevation
        fk = 12756.33*np.arccos(xkmper/(xkmper+sat_alt));

        # Compute Doppler shift for a 100-MHz signal
        rdot = self.sat.range_velocity
        f=100e6
        c=299792458.
        dop100 = -rdot*f/c

        # Bundle it all together
        d = dict(longitude   = self.sat.sublong*RAD2DEG,  \
                 latitude    = self.sat.sublat*RAD2DEG,   \
                 azimuth     = self.sat.az*RAD2DEG,       \
                 elevation   = self.sat.alt*RAD2DEG,      \
                 footprint   = fk,                        \
                 orbit       = self.sat.orbit,            \
                 slant_range = self.sat.range*0.001,     \
                 doppler     = dop100)

        return d
        

    # Function to find next transit of a satellite after time t
    def next_transit(self,t):
        if USE_PYPREDICT:
            p = predict.transits(self.tle,self.qth,ending_after=t)
            transit0 = next(p)
            print('NEXT TRANSIT: Transit0 vars:\n', vars(transit0),
                  '\nstart=',transit0.start,'\t',type(transit0) )
            return transit0

        # Compute sat info at time t
        tle0=self.tle.split('\n')
        sat = ephem.readtle(tle0[0],tle0[1],tle0[2])
        self.obs.date = datetime.fromtimestamp(t,tz=timezone.utc)
        #print('time=',self.obs.date,datetime.utcnow())
        sat.compute(self.obs)

        # Back up in time if we're in the middle of a pass
        if sat.alt>0 and True:
            print('Sat IS currently visible')
            self.obs.date = datetime.fromtimestamp(t-30*60,tz=timezone.utc)
            sat.compute(self.obs)

        # Get info for the next transit
        try:
            info=self.obs.next_pass(sat)
        except Exception as e:
            # Trap any errors that occur - not sure why this happens with ephem
            # but seems to be an issue for passes well in the future
            print('\n*** TRAPPED ERROR in NEXT_TRANSIT ***')
            print( str(e) )
            print('TLE=',tle0)
            print('t=',t,'\t',self.obs.date,'\n')
            #sys.exit(0)
            return None

        # Compute track - need to rip this mess out & use observe!
        rise = info[0]
        setting = info[4]
        t =rise
        dt=(setting-rise)/20.
        tt=[]
        az=[]
        el=[]
        lats=[]
        lons=[]
        footprints=[]
        while t<setting:
            self.obs.date=t
            sat.compute(self.obs)

            local=ephem.localtime(t).timestamp()
            tt.append(local)
            az.append(sat.az*RAD2DEG)
            el.append(sat.alt*RAD2DEG)

            lon = sat.sublong*RAD2DEG    # ( sat.ra - self.greenwich.sidereal_time() )*RAD2DEG
            lat = sat.sublat*RAD2DEG     #( sat.dec )*RAD2DEG
            lats.append(lat)
            lons.append(lon)
            #print('Track: t=',self.obs.date,'\taz=',sat.az,'\tel=',sat.alt,'\tlat=',lat,'\tlon=',lon)

            # These calcs came from pawing through pypredict C code
            xkmper=6.378137E3
            sat_alt= 1e-3*sat.elevation
            footprint = 12756.33*np.arccos(xkmper/(xkmper+sat_alt));
            footprints.append(footprint)
            
            t+=dt

        transit=TRANSIT(info,tt,az,el,lats,lons,footprints)
        transit.elevation=sat.elevation
        transit.alt=sat.alt
        transit.dec=sat.dec
        ###transit.u=ephem.unrefract(self.obs.pressure, self.obs.temperature, sat.alt)
        
        #print('NEXT TRANSIT: Transit vars:\n', vars(transit),
        #      '\nstart=',transit.start,'\t',type(transit) )
        #print('long=',sat.sublong,'\tlat=',sat.sublat,'\televation=',sat.elevation)
        #print('alt=',sat.alt,'\tdec=',sat.dec,'\trange=',sat.range,sat.a_dec,sat.g_dec,sat.a_ra,sat.g_ra,sat.ra)
        #print('rise=',rise+0.,'\tsetting=',setting+0.,'\t',setting-rise)
        #print('tt=',tt)
        #print('transit.t=',transit.t)
        #print('range=',sat.range,sat.radius)
        #sys.exit(0)
        
        return transit
        
    # Function to handle moon passes
    def fly_me_to_the_moon(self,date1,date2):
        print('\nFLY_ME_TO_THE_MOON: my_qth=',self.qth,'\ndate1=',date1,'\tdate2=',date2)

        # The Moon
        moon = ephem.Moon()
        self.moon= moon

        # The Sun
        self.sun = ephem.Sun()

        # Fake the transponders to use the weak signal portion of the 2m band
        self.get_transponders()
        print('Moon transp=',self.transponders)
        
        # Form location object
        #qth = ephem.Observer()
        #qth.lat = str( self.qth[0] )
        #qth.lon = str( -self.qth[1] )
        #qth.elevation = self.qth[2]
        #print('QTH=',qth)
        #self.qth_moon=self.obs

        # Loop over all the days requested
        Done=False
        self.obs.date=date1
        transits=[]
        while not Done:

            # Find next moon rise ...
            moon.compute(self.obs)
            rise=self.obs.next_rising(moon)
            local1=ephem.localtime(rise)
            print('\n',self.obs.date,'\nNext Mooon Rise:',rise,'\t',local1)
            print('az/el=',moon.az,moon.alt)

            # ... and corresponding moon setting
            self.obs.date=rise
            moon.compute(self.obs)
            setting=self.obs.next_setting(moon)
            local2=ephem.localtime(setting)
            print('Following moon setting:',setting,'\t',local2)
            print('az/el=',moon.az,moon.alt)

            # Return everything in local time for plotting
            transits.append([local1,local2])
            #transits.append([rise.datetime(),setting.datetime()])

            # Get ready for next pass
            self.obs.date=setting
            if self.obs.date>ephem.Date(date2):
                Done=True        

        print('Moon transits=',transits)

        # Assemble graphing data from the transits
        isat=self.isat
        for transit in transits:
            ts=transit[0]
            te=transit[1]
                
            self.t.append(ts)
            self.y.append(None)
            self.t.append(ts)
            self.y.append(isat)
            self.t.append(te)
            self.y.append(isat)
            self.t.append(te)
            self.y.append(None)

            tmid = ts + 0.5*(te-ts)
            self.t2.append( tmid )
            self.y2.append(isat)
                
            self.pass_times.append( time.mktime(tmid.timetuple()) )
                
        return transits

    # Function to return current moon info
    def current_moon_position(self):
        self.obs.date = datetime.utcnow()
        self.moon.compute(self.obs)
        az=self.moon.az
        el=self.moon.alt

        self.greenwich.date = self.obs.date
        self.moon.compute(self.greenwich)
        lon = ( self.moon.ra - self.greenwich.sidereal_time() )*RAD2DEG
        lat = ( self.moon.dec )*RAD2DEG
        
        print('Current Moon: date=',self.greenwich.date, \
              '\n\taz=',az,'\tel=',el, \
              '\n\tlat=',lat,'\t','lon=',lon)
        return [az*RAD2DEG, el*RAD2DEG, lat, lon]

    # Function to return current sun info
    def current_sun_position(self):

        now=time.time()
        dt = now - self.last_update
        if dt>=SUN_UPDATE_INTERVAL:
            self.last_update=now
        
            self.obs.date = datetime.utcnow()
            self.sun.compute(self.obs)
            az=self.sun.az
            el=self.sun.alt
            
            self.greenwich.date = self.obs.date
            self.sun.compute(self.greenwich)
            lon = ( self.sun.ra - self.greenwich.sidereal_time() )*RAD2DEG
            lat = ( self.sun.dec )*RAD2DEG

            print('Current Sun: date=',self.greenwich.date, \
                  '\n\taz=',az,'\tel=',el, \
                  '\n\tlat=',lat,'\t','lon=',lon,'\tdt=',dt)

            self.sun_pos = [az*RAD2DEG, el*RAD2DEG, lat, lon]
            
        return self.sun_pos


    # Function to compute moon track for a single pass
    def gen_moon_track(self,t1,t2=None,dt=30.*MINS2DAYS,VERBOSITY=0):
        moon=self.moon
        
        if VERBOSITY>0:
            print('\nGEN_MOON_TRACK: t1=',t1,'\tt2=',t2,'\tdt=',dt)
            print('obs=',self.obs)
            print('moon=',moon)
            print('t1a=',t1,type(t1),isinstance(t1,float))

        # Convert t1 (start time or time in the pass) to ephem datetime object
        if isinstance(t1,float):
            # Assume it local time and convert to utc
            #t1b = datetime.fromtimestamp(t1)
            #print('Local Time @ middle of pass =',t1b,type(t1b))
            t1 = datetime.fromtimestamp(t1,tz=timezone.utc)
            #print('UTC =',t1,type(t1))
        t1=ephem.Date(t1)
        #print('t1d=',t1,type(t1))

        # Check if t2 is given
        if t2:
        
            # Yes - Convert it (stop time) to ephem datetime object
            if isinstance(t2,float):
                # Assume it local time and convert to utc
                t2 = datetime.fromtimestamp(t2,tz=timezone.utc)
                t2 = datetime.fromtimestamp(t2)
            t2=ephem.Date(t2)

        else:

            # No - take t1 as some time in the pass and find moon rise and set for the pass
            self.obs.date = t1
            moon.compute(self.obs)
            
            rise=self.obs.previous_rising(moon)
            local1=ephem.localtime(rise)
            print('\nDate for Computation=',self.obs.date,'\nPrev Mooon Rise:',rise,'\t',local1)
            print('az/el=',moon.az,moon.alt)
            
            setting=self.obs.next_setting(moon)
            local2=ephem.localtime(setting)
            print('Next moon setting:',setting,'\t',local2)
            print('az/el=',moon.az,moon.alt)
            
            t1=rise
            t2=setting
            #print('Rise=',t1,type(t1),local1,'\tSet=',t2,type(t2),local2)

        # Compute moon track
        t=t1
        Done=False
        tt=[]
        az=[]
        el=[]
        lats=[]
        lons=[]
        footprints=[]
        while not Done:
            if t>=t2:
                Done=True
                t=t2
            self.obs.date=t
            moon.compute(self.obs)

            tt.append(t)
            az.append(moon.az*RAD2DEG)
            el.append(moon.alt*RAD2DEG)
            if VERBOSITY>0:
                print('Track: t=',self.obs.date,'\taz=',moon.az,'\tel=',moon.alt)
            
            t+=dt

        local1=local1.timestamp()
        local2=local2.timestamp()
        info=[rise,az[0],None,None,setting,az[-1]]
        transit=TRANSIT(info,tt,az,el,lats,lons,footprints)
        
        return transit

    
################################################################################

class MAPPING(QMainWindow):
    def __init__(self,P,parent=None):
        super(MAPPING, self).__init__(parent)

        # Init
        self.P=P
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('Satellite Track')
        self.grid = QGridLayout(self.win)

        self.fig  = Figure()
        self.canv = FigureCanvas(self.fig)
        self.grid.addWidget(self.canv,0,0)
        self.ax=None

        # Create figure centered on USA
        lon0=-75
        self.proj=ccrs.PlateCarree(central_longitude=lon0) 
        self.ax = self.fig.add_subplot(1, 1, 1, projection=self.proj)
        if False:
            # This doesn't work under pyinstaller ...
            self.ax.stock_img()
        else:
            # ... so we load image directly instead
            fname='../data/50-natural-earth-1-downsampled.png'
            print('fname=',fname)
            img = imread(fname)
            self.ax.imshow(img, origin='upper', transform=ccrs.PlateCarree(),
                      extent=[-180, 180, -90, 90])

        self.ax.set_aspect('auto')
        self.fig.tight_layout(pad=0)
            
        # Create a feature for States/Admin 1 regions at 1:50m from Natural Earth
        states_provinces = cfeature.NaturalEarthFeature(
            category='cultural',
            name='admin_1_states_provinces_lines',
            scale='50m',
            facecolor='none')

        # Add boundaries
        self.ax.add_feature(cfeature.LAND)
        self.ax.add_feature(cfeature.COASTLINE)
        self.ax.add_feature(cfeature.BORDERS)
        self.ax.add_feature(states_provinces, edgecolor='gray')
        
        self.show()
        self.canv.draw()
        self.blobs=[]
        

    def ComputeSatTrack(self,Sat,tstart=None,npasses=1):
        if tstart==None:
            tstart = datetime.now()

        tle0=Sat.tle.split('\n')
        print('COMPUTE SAT TRACK: tle=',tle0)

        tle2=tle0[2].split()
        #inclination=float(tle2[2])
        revs=float(tle2[7])
        rev_mins=24.*60./revs
        print('rev per day=',revs,'\t',rev_mins)
        
        lons=[]
        lats=[]
        footprints=[]
        for m in range(0,int(npasses*rev_mins+2),1):
            dt = timedelta(minutes=m)
            t = time.mktime( (tstart+dt).timetuple() )
            
            if USE_PYPREDICT:
                obs = predict.observe(Sat.tle,self.P.my_qth,t)
            else:
                obs = Sat.observe(t)
                
            lon=obs['longitude']
            lat=obs['latitude']
            footprint=obs['footprint']

            # DEBUG
            if False:
                print(obs['orbit'],'\t',tstart+dt,'\t',lon,'\t',lat,
                      '\t',footprint)
                    
                obs1=Sat.observe(t)
                lon1=obs1['longitude']
                lat1=obs1['latitude']
                footprint1=obs1['footprint']
                print(obs1['orbit'],'\t',tstart+dt,'\t',lon1,'\t',lat1,
                          '\t',footprint1)
                print('*** COMPUTE SAT TRACK - DEBUG - EXITING ***')
                sys.exit(0)

            lons.append(lon)
            lats.append(lat)
            footprints.append(footprint)

        return lons,lats,footprints

    def transform_and_plot(self,lons,lats,style,clr=None):
        if np.isscalar(lons):
            lons = np.array( [lons] )
        if np.isscalar(lats):
            lats = np.array( [lats] )
        xx=[]
        yy=[]
        x_prev=np.nan
        phz=0
        for lon,lat in zip(lons,lats):
            x,y = self.proj.transform_point(lon,lat, ccrs.Geodetic())
            x+=phz
            dx=x-x_prev
            #print('XFORM and PLOT:\t',lon,'\t',lat,'\t',dx,'\t',x,'\t',y)
            if dx>120:
                phz-=360
                x-=360
            elif dx<-120:
                phz+=360
                x+=360
            xx.append(x)

            #yy.append(max(min(y,90),-90))
            yy.append(y)
            x_prev=x

        if not clr:
            clr=style[0]
        #p=self.ax.plot(xx,yy,style,color=clr,transform=self.proj)
        p=self.ax.plot(xx,yy,style,transform=self.proj)
        return p[0]
        
    def DrawSatTrack(self,name,lons,lats,ERASE=True,title=None):

        # Set title to sat name
        if title==None:
            title=name
        self.setWindowTitle(title)
        
        # Clear prior plots
        if ERASE:
            for line in self.ax.get_lines():
                #print('line=',line)
                line.remove()
            for p in self.blobs:
                #print('p=',line)
                try:
                    p.remove()
                except:
                    pass
            self.blobs=[]

        # Plot sat track
        self.transform_and_plot(-self.P.my_qth[1],self.P.my_qth[0],'mo')
        if name=='Moon':
            self.transform_and_plot(lons,lats,'bo')
            return
        elif name=='Sun':
            self.transform_and_plot(lons,lats,'yo')
            return
        self.transform_and_plot(lons,lats,'b-')
        self.transform_and_plot(lons[0],lats[0],'g*')
        self.transform_and_plot(lons[-1],lats[-1],'r*')

        self.canv.draw()
        return
    
        
    def DrawSatFootprint(self,name,lon0,lat0,footprint,ERASE=True):

        # Clear prior footprints
        if ERASE:
            for p in self.blobs:
                print(p)
                p.remove()
            self.blobs=[]

        # Add footprint "ellipse"
        #Latitude: 1 deg = 110.54 km
        #Longitude: 1 deg = 111.320*cos(latitude) km
        dy=0.5*footprint/110.54
        dx=0.5*footprint/(111.32*np.cos(lat0*DEG2RAD))

        print('\nEllipse:',lon0,lat0,footprint)
        north_pole = lat0+dy>=80
        south_pole = lat0-dy<=-80
        phz=0
        print('Poles:',lat0,dy,north_pole,south_pole)

        xx=[]
        yy=[]
        pgon=[]
        lon_prev=np.nan
        step=5
        for alpha in range(0,360+step,step):
            lat=lat0+dy*np.sin(alpha*DEG2RAD)
            dx=0.5*footprint/(111.32*np.cos(lat*DEG2RAD))
            lon=lon0 + dx*np.cos(alpha*DEG2RAD)
            
            x,y = self.proj.transform_point(lon,lat, ccrs.Geodetic())
            #print(alpha,'\t',dx,'\t',lon,'\t',lat,'\t',x,'\t',y)

            # Only keep valid points - near the poles, this can get squirrly
            if dx>0 and dx<180:
                x+=phz
                dlon=x-lon_prev
                if dlon>120:
                    if north_pole or south_pole:
                        if north_pole:
                            y0=90
                        else:
                            y0=-90
                        pgon.append((-180+phz,y))
                        #print(pgon[-1])
                        pgon.append((-180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((180+phz,y))
                        #print(pgon[-1])
                    else:
                        phz-=360
                        x-=360
                elif dlon<-120:
                    if north_pole or south_pole:
                        if north_pole:
                            y0=90
                        else:
                            y0=-90
                        pgon.append((180+phz,y))
                        #print(pgon[-1])
                        pgon.append((180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((-180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((-180+phz,y))
                        #print(pgon[-1])
                    else:
                        phz+=360
                        x+=360
                        
                lon_prev=x
                #xx.append(lon)
                #yy.append(lat)
                #y=max(min(y,90),-90)
                pgon.append((x,y))
                
        #self.transform_and_plot(xx,yy,'g-')
        #self.transform_and_plot(xx[0],yy[0],'go')
        pgon=Polygon( tuple(pgon) )
        p=self.ax.add_geometries([pgon], crs=self.proj, facecolor='r',
                          edgecolor='red', alpha=0.3)
        self.blobs.append(p)

        p=self.transform_and_plot(lon0,lat0,'k*')
        self.blobs.append(p)
        
        self.canv.draw()
