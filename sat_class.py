################################################################################
#
# sat_class.py - Rev 2.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
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

import os
import sys
if sys.platform == "win32":
    USE_PYPREDICT=False
if USE_PYPREDICT:
    import predict
from configparser import ConfigParser 
from collections import OrderedDict
import time
from datetime import timedelta,datetime, timezone
import ephem

from widgets_qt import QTLIB
exec('from '+QTLIB+'.QtWidgets import QMainWindow,QWidget,QGridLayout')

import numpy as np
from constants import *
from utilities import error_trap
from rig_io.ft_tables import CELESTIAL_BODY_LIST,METEOR_SHOWER_LIST

################################################################################

# Function to assemble TLE data for a particular satellite
def get_tle(TLE,sat):

    if not hasattr(get_tle,"TLE_SHOWN"):
        get_tle.TLE_SHOWN=False
    
    sat2=sat
    if sat=='CAS-6':
        sat2='TO-108'
    elif sat=='AO-7':
        sat2='AO-07'
    elif sat=='XW-3':
        sat2='XW 3'
    elif sat=='FS-3':
        sat2='Falconsat-3'
    elif 'TEVEL' in sat:
        sat2='Tevel'+sat[5:]
    if sat!=sat2:
        print('GET_TLE: Warning - name change for ',sat,' to ',sat2)

    try:
        idx  = TLE.index(sat2)
    except: 
        error_trap('GET TLE - Cant find TLE for sat='+sat)
        if not get_tle.TLE_SHOWN:
            print('TLE=',TLE)
            get_tle.TLE_SHOWN=True
        else:
            print('See previous trap msg for complete TLE')
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
    def __init__(self,isat,name,qth,date1,date2,TLE,SHOWERS):

        print('\n=====================================================================')
        print('SATELLITE CLASS: isat=',isat,'-\tSat:',name, \
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
        
        # Celestial and meteor showers are special since we don't use TLEs
        if name in CELESTIAL_BODY_LIST:
            self.meteor_shower(name,date1,date2)
            #self.fly_me_to_the_moon(date1,date2)
            return
        elif name in METEOR_SHOWER_LIST:
            self.meteor_shower(SHOWERS[name],date1,date2)
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
                return
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
        #NO_TRANSP=['Moon','Orbicraft-Zorkiy','IO-117']
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
        print('GET_TRANSPONDERS: fname=',fname)
        #sys.exit(0)

        # Read the transponder data for this sat
        config = ConfigParser() 
        print('GET_TRANSPONDERS: config.read=',config.read(fname)) 
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
            elif self.name=='IO-117':
                if 'MODE U PKT' in transp2:
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
        if self.name=='MoonDoggy':
            # Hack hack hack!
            [az,el,lat,lon,illum]   = self.current_moon_position()
            return [0,0,az,el,230e3,lat,lon,1]
        elif self.name in CELESTIAL_BODY_LIST+METEOR_SHOWER_LIST:
            # Hack hack hack!
            [az,el,lat,lon,illum]   = self.current_radiant_position()
            return [0,0,az,el,230e3,lat,lon,1]
        else:
            if USE_PYPREDICT:
                obs = predict.observe(self.tle, my_qth,now)
                obs1=self.observe(now)
                #print('Doppler:',obs['doppler'],obs1['doppler'])
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
        except: 
            # Trap any errors that occur - not sure why this happens with ephem
            # but seems to be an issue for passes well in the future
            error_trap('NEXT TRANSIT - Trapped Error')
            print('TLE=',tle0)
            print('t=',t,'\t',self.obs.date,'\n')
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

    # Function to compute moon lunation and phase
    def get_moon_phase(self,Date=None):
        print('Date=',Date)
        if Date==None:
            Date=datetime.utcnow()
        print('Date=',Date)
        Date = ephem.Date(Date)
        nnm = ephem.next_new_moon(Date)
        pnm = ephem.previous_new_moon(Date)
        
        # 0=new, 0.5=full, 1=new
        lunation = (Date-pnm)/(nnm-pnm)
        
        if lunation<0.1:
            phz='New Moon'
        elif lunation<0.25:
            phz='Waxing Crescent'
        elif lunation<0.5:
            phz='Waxing Half'
        elif lunation<0.75:
            phz='Waning Half'
        elif lunation<0.9:
            phz='Waning Crescent'
        else:
            phz='New Moon'
  
        return lunation,phz

    # Function to handle meteor showers
    def meteor_shower(self,shower,date1,date2):
        print('\nMETEOR_SHOWER: my_qth=',self.qth,'\ndate1=',date1,'\tdate2=',date2)

        # Create fixed body at radiant
        if shower=='Moon':
            self.radiant = ephem.Moon()
        elif shower=='Sun':
            self.radiant = ephem.Sun()
        else:
            self.radiant = ephem.FixedBody()
            ra = float( shower.RA )
            decl = float( shower.DE )
            print('\tRA=',ra,'\tdecl=',decl)
            self.radiant._ra  = ephem.degrees(ra*DEG2RAD)
            self.radiant._dec = ephem.degrees(decl*DEG2RAD)
            self.radiant._epoch = ephem.J2000
            #sys.exit(0)

        # Fake the transponders to use the weak signal portion of the 2m band
        # Not sure why I thought we needed to do this?
        #self.get_transponders()
        #print('Moon transp=',self.transponders)
                    
        # Loop over all the days requested
        Done=False
        self.obs.date=date1
        transits=[]
        while not Done:

            # Find next rise ...
            self.radiant.compute(self.obs)
            try:
                rise=self.obs.next_rising(self.radiant)
            except:
                rise=self.obs.date
            local1=ephem.localtime(rise)
            #print('\n',self.obs.date,'\nNext Mooon Rise:',rise,'\t',local1)
            #print('az/el=',moon.az,moon.alt)

            # ... and corresponding set ...
            self.obs.date=rise
            self.radiant.compute(self.obs)
            try:
                setting=self.obs.next_setting(self.radiant)
            except:
                setting=self.obs.date+1
            local2=ephem.localtime(setting)
            #print('Following moon setting:',setting,'\t',local2)
            #print('az/el=',moon.az,moon.alt)

            # Return everything in local time for plotting
            transits.append([local1,local2])
            #transits.append([rise.datetime(),setting.datetime()])

            # Get ready for next pass
            self.obs.date=setting
            if self.obs.date>ephem.Date(date2):
                Done=True        

        #print('Moon transits=',transits)

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

    # Function to return current radiantinfo
    def current_radiant_position(self):
        self.obs.date = datetime.utcnow()
        self.radiant.compute(self.obs)
        az=self.radiant.az
        el=self.radiant.alt
        if self.name=='Moon':
            illum=self.radiant.phase
        else:
            illum=0

        self.greenwich.date = self.obs.date
        self.radiant.compute(self.greenwich)
        lon = ( self.radiant.ra - self.greenwich.sidereal_time() )*RAD2DEG
        lat = ( self.radiant.dec )*RAD2DEG

        if False:
            print('Current Moon: date=',self.greenwich.date, \
                  '\n\taz=',az,'\tel=',el, \
                  '\n\tlat=',lat,'\t','lon=',lon,
                  '\nIllumination=',illum,'%')
        return [az*RAD2DEG, el*RAD2DEG, lat, lon, illum]
    
    # Function to compute moon track for a single pass
    def gen_radiant_track(self,t1,t2=None,dt=10.*MINS2DAYS,VERBOSITY=0):
        
        if VERBOSITY>0:
            print('\nGEN_RADIANT_TRACK: t1=',t1,'\tt2=',t2,'\tdt=',dt)
            print('obs=',self.obs)
            print('radiant=',self.radiant)
            print('t1a=',t1,type(t1),isinstance(t1,float))

        # Convert t1 (start time or time in the pass) to ephem datetime object
        if isinstance(t1,float):
            # Assume it local time and convert to utc
            #t1b = datetime.fromtimestamp(t1)
            #print('Local Time @ middle of pass =',t1b,type(t1b))
            t1 = datetime.fromtimestamp(t1,tz=timezone.utc)
            #print('UTC =',t1,type(t1))
        t1=ephem.Date(t1)
        if VERBOSITY>0:
            print('t1d=',t1,type(t1))

        # Check if t2 is given
        if t2:
        
            # Yes - Convert it (stop time) to ephem datetime object
            if isinstance(t2,float):
                # Assume it local time and convert to utc
                t2 = datetime.fromtimestamp(t2,tz=timezone.utc)
                t2 = datetime.fromtimestamp(t2)
            t2=ephem.Date(t2)

        else:

            # No - take t1 as some time in the past and find moon rise and set for the pass
            self.obs.date = t1
            self.radiant.compute(self.obs)

            try:
                rise=self.obs.previous_rising(self.radiant)
            except:
                rise=self.obs.date
            local1=ephem.localtime(rise)
            print('\nDate for Computation=',self.obs.date,'\nPrev Mooon Rise:',rise,'\t',local1)
            print('az/el=',self.radiant.az,self.radiant.alt)

            try:
                setting=self.obs.next_setting(self.radiant)
            except:
                setting=self.obs.date+1
            local2=ephem.localtime(setting)
            #print('Next Moon setting:',setting,'\t',local2)
            #print('az/el=',moon.az,moon.alt)
            
            t1=rise
            t2=setting
            #print('Rise=',t1,type(t1),local1,'\tSet=',t2,type(t2),local2)

        # Compute track
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
            self.radiant.compute(self.obs)

            local=ephem.localtime(t).timestamp()
            tt.append(local)
            az.append(self.radiant.az*RAD2DEG)
            el.append(self.radiant.alt*RAD2DEG)
            if VERBOSITY>0:
                print('Track: t=',self.obs.date,'\taz=',self.radiant.az,'\tel=',self.radiant.alt)
            
            t+=dt

        local1=local1.timestamp()
        local2=local2.timestamp()
        info=[rise,az[0],None,None,setting,az[-1]]
        transit=TRANSIT(info,tt,az,el,lats,lons,footprints)
        
        return transit

