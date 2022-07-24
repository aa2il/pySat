#! /usr/bin/python3 -u
################################################################################
#
# sat_class.py - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
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
# Unfortunately, there are some differences in the terms used quantify the orbit
# of the moon vs those for artificial sats (e.g. alt vs el).  I'm sticking with the
# sat way of doing things.
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

################################################################################

import predict
import os
import sys
from configparser import ConfigParser 
from collections import OrderedDict
import time
from datetime import timedelta,datetime, timezone
import ephem
from math import pi

from PyQt5 import QtCore
from PyQt5.QtWidgets import *

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.offsetbox import AnchoredText
import matplotlib.patches as mpatches
#from cartopy.mpl.ticker import (LongitudeFormatter, LatitudeFormatter,
#                                LatitudeLocator, LongitudeLocator)

from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker
from shapely.geometry.polygon import Polygon
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

################################################################################

RAD2DEG=180./pi
MINS2DAYS=1./(24.*60.)
DEG2RAD=pi/180.

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
        
    idx  = TLE.index(sat2)
    
    tle = sat + '\n' \
        + TLE[idx+1] + '\n' \
        + TLE[idx+2] + '\n'

    if sat=='ISS':
        print('GET_TLE: sat=',sat,'\ntle=',tle)
        #sys.exit(0)
    
    return tle

################################################################################

# Structure compatible with what comes out of Predict for us in moon tracking
class TRANSIT:
    def __init__(self,start,end,t,az,el):

        self.start = start
        self.end   = end
        self.t     = t
        self.az    = az
        self.el    = el

    def peak(self):
        return {'elevation':0,'slant_range':0}

################################################################################

# Structure to contain data for a satellite
class SATELLITE:
    def __init__(self,isat,name,qth,date1,date2,TLE):

        print('\nSATELLITE CLASS: isat=',isat,'-\tSat:',name, \
              '\ttb-ta:',date1,date2,'\tqth:',qth)
        self.name = name
        self.isat = isat
        self.qth  = qth

        self.pass_times = []
        self.t = []
        self.y = []
        self.t2 = []
        self.y2 = []
        
        # The moon is special since we don't use TLEs
        if name=='Moon':
            self.fly_me_to_the_moon(date1,date2)
            return        

        # Predict transits of this (artificial) satellite over qth for the specified time span
        tafter  = time.mktime(date1.timetuple())
        tbefore = time.mktime(date2.timetuple())
        self.tle = get_tle(TLE,name)
        self.p   = predict.transits(self.tle, qth,
                                    ending_after=tafter, ending_before=tbefore)

        # Get transponder info for this sat
        self.get_transponders()
            
        # Look at the transits and determine times for visible sections
        tlast=0
        ts_old=None
        te_old=None
        while True:

            # Move through list of passes & break if we're done
            try:
                transit = next(self.p)
            except:
                break

            # Determine start & end times for this pass
            ts = datetime.fromtimestamp(transit.start)
            te = datetime.fromtimestamp(transit.end)
            #print('ts=',ts,'\tte=',te)

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
            if name in ['AO-07','FO-29']:
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

            elif name=='FO-29':
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
        self.main=None
        if self.name=='Moon':
            # There are no transponders but we fake till we make it
            self.number='Moon'
        else:
            print('GET_TRANSPONDERS: tle =',self.tle)
            tle2=self.tle.split()
            print('GET_TRANSPONDERS: tle2=',tle2)
            self.number=int( tle2[2][:-1] )
            print('GET_TRANSPONDERS: number=',self.number)

        fname = os.path.expanduser(TRANSP_DATA+'/'+str(self.number)+'.trsp')
        #print(fname)
        #sys.exit(0)

        # Read the transponder data for this sat
        config = ConfigParser() 
        print(config.read(fname)) 
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
            if self.name=='Moon':
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
            print('Hmmmmm - never found main transponder for this sat :-(')


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
            [az,el] = self.current_moon_position()
            return [0,0,az,el,230e3]
        else:
            obs = predict.observe(self.tle, my_qth,now)
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
        
        return [fdop1,fdop2,az,el,rng]

################################################################################

    """
    # Duplicate function - see current moon position below
    def get_moon_pos(self,date1):
        qth=self.qth_moon
        qth.date=date1
        self.moon.compute(qth)
        az=self.moon.az
        el=self.moon.alt
        print('MOON: Date=',date1,'\taz=',az,'\tel=',el)
        return az,el
    """
    
    # Function to handle moon passes
    def fly_me_to_the_moon(self,date1,date2):
        print('\nFLY_ME_TO_THE_MOON: my_qth=',self.qth,'\ndate1=',date1,'\tdate2=',date2)

        # The Moon
        moon = ephem.Moon()
        self.moon= moon

        # The Sun
        self.sun = ephem.Sun()

        # Greenwich
        self.greenwich = ephem.Observer()
        self.greenwich.lat = '0'
        self.greenwich.lon = '0'

        # Fake the transponders to use the weak signal portion of the 2m band
        self.get_transponders()
        print('Moon transp=',self.transponders)
        
        # Form location object
        qth = ephem.Observer()
        qth.lat = str( self.qth[0] )
        qth.lon = str( -self.qth[1] )
        qth.elevation = self.qth[2]
        #print('QTH=',qth)
        self.qth_moon=qth

        # Loop over all the days requested
        Done=False
        qth.date=date1
        transits=[]
        while not Done:

            # Find next moon rise ...
            moon.compute(qth)
            rise=qth.next_rising(moon)
            local1=ephem.localtime(rise)
            print('\n',qth.date,'\nNext Mooon Rise:',rise,'\t',local1)
            print('az/el=',moon.az,moon.alt)

            # ... and corresponding moon setting
            qth.date=rise
            moon.compute(qth)
            setting=qth.next_setting(moon)
            local2=ephem.localtime(setting)
            print('Following moon setting:',setting,'\t',local2)
            print('az/el=',moon.az,moon.alt)

            # Return everything in local time for plotting
            transits.append([local1,local2])
            #transits.append([rise.datetime(),setting.datetime()])

            # Get ready for next pass
            qth.date=setting
            if qth.date>ephem.Date(date2):
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


    # Get current moon lat and lon
    def get_moon_latlon(self):
        self.greenwich.date = datetime.utcnow()
        self.moon.compute(self.greenwich)
        lon = ( self.moon.ra - self.greenwich.sidereal_time() )*RAD2DEG
        lat = ( self.moon.dec )*RAD2DEG
        print('Moon lat & lon:',lat,lon)

        return [lat,lon]

    # Get current sun lat and lon
    def get_sun_latlon(self):
        self.greenwich.date = datetime.utcnow()
        self.sun.compute(self.greenwich)
        lon = ( self.sun.ra - self.greenwich.sidereal_time() )*RAD2DEG
        lat = ( self.sun.dec )*RAD2DEG
        print('Sun lat & lon:',lat,lon)

        return [lat,lon]

    # Function to return current moon info
    def current_moon_position(self):
        qth=self.qth_moon
        qth.date = datetime.utcnow()
        self.moon.compute(qth)
        print('Current Moon: az=',self.moon.az,'\tel=',self.moon.alt)

        return [self.moon.az*RAD2DEG , self.moon.alt*RAD2DEG]


    def current_sun_position(self):
        qth=self.qth_moon
        qth.date = datetime.utcnow()
        self.sun.compute(qth)
        print('Current Sun: az=',self.sun.az,'\tel=',self.sun.alt)

        return [self.sun.az*RAD2DEG , self.sun.alt*RAD2DEG]


    # Function to compute moon track for a single pass
    def gen_moon_track(self,t1,t2=None,dt=30.*MINS2DAYS,VERBOSITY=0):
        qth=self.qth_moon
        moon=self.moon
        
        if VERBOSITY>0:
            print('\nGEN_MOON_TRACK: t1=',t1,'\tt2=',t2,'\tdt=',dt)
            print('qth=',qth)
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
            qth.date = t1
            moon.compute(qth)
            
            rise=qth.previous_rising(moon)
            local1=ephem.localtime(rise)
            print('\nDate for Computation=',qth.date,'\nPrev Mooon Rise:',rise,'\t',local1)
            print('az/el=',moon.az,moon.alt)
            
            setting=qth.next_setting(moon)
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
        while not Done:
            if t>=t2:
                Done=True
                t=t2
            qth.date=t
            moon.compute(qth)

            tt.append(t)
            az.append(moon.az*RAD2DEG)
            el.append(moon.alt*RAD2DEG)
            if VERBOSITY>0:
                print('Track: t=',qth.date,'\taz=',moon.az,'\tel=',moon.alt)
            
            t+=dt

        local1=local1.timestamp()
        local2=local2.timestamp()
        transit=TRANSIT(local1,local2,tt,az,el)
        
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
        self.ax.stock_img()

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
        self.plots=[]
        

    def ComputeSatTrack(self,tle,tstart,npasses):
        print('COMPUTE SAT TRACK: tle=',tle)
        tle0=tle.split('\n')
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
            obs = predict.observe(tle,self.P.my_qth,t)

            lon=obs['longitude']
            lat=obs['latitude']
            footprint=obs['footprint']
            if 0:
                print(obs['orbit'],'\t',tstart+dt,'\t',lon,'\t',lat,
                      '\t',footprint)

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
            yy.append(y)
            x_prev=x

        if not clr:
            clr=style[0]
        self.ax.plot(xx,yy,style,color=clr,transform=self.proj)

    def DrawSatTrack(self,name,lons,lats,footprint):

        # Set title to sat name
        self.setWindowTitle('Current Position of '+name)
        
        # Clear prior plots
        for line in self.ax.get_lines():
            print(line)
            line.remove()
        for p in self.plots:
            p.remove()
        self.plots=[]

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
        
        # Add footprint "ellipse"
        #Latitude: 1 deg = 110.54 km
        #Longitude: 1 deg = 111.320*cos(latitude) km
        dy=0.5*footprint/110.54
        dx=0.5*footprint/(111.32*np.cos(lats[0]*DEG2RAD))

        print('\nEllipse:',lons[0],lats[0],footprint)
        north_pole = lats[0]+dy>=80
        south_pole = lats[0]-dy<=-80
        phz=0
        print('Poles:',lats[0],dy,north_pole,south_pole)

        xx=[]
        yy=[]
        pgon=[]
        lon_prev=np.nan
        step=5
        for alpha in range(0,360+step,step):
            lat=lats[0]+dy*np.sin(alpha*DEG2RAD)
            dx=0.5*footprint/(111.32*np.cos(lat*DEG2RAD))
            lon=lons[0]+dx*np.cos(alpha*DEG2RAD)
            
            x,y = self.proj.transform_point(lon,lat, ccrs.Geodetic())
            #print(lon,'\t',lat,'\t',x,'\t',y)

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
                        pgon.append((-180+phz,y0))
                        pgon.append((180+phz,y0))
                        pgon.append((180+phz,y))
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
                        pgon.append((180+phz,y0))
                        pgon.append((-180+phz,y0))
                        pgon.append((-180+phz,y))
                    else:
                        phz+=360
                        x+=360
                        
                lon_prev=x
                xx.append(lon)
                yy.append(lat)
                pgon.append((x,y))
                
        #self.transform_and_plot(xx,yy,'g-')
        #self.transform_and_plot(xx[0],yy[0],'go')
        pgon=Polygon( tuple(pgon) )
        p=self.ax.add_geometries([pgon], crs=self.proj, facecolor='r',
                          edgecolor='red', alpha=0.3)
        self.plots.append(p)
        
        self.canv.draw()
