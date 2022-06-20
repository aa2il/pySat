#! /usr/bin/python3 -u
################################################################################
#
# sat_class.py - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Class containing individula satellite data
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

TRANSP_DATA = "~/.config/Gpredict/trsp"                          # Transponder data as parsed by gpredict
MIN_PEAK_EL  = 30       # Degrees, minimum elevation to identify overhead passes

################################################################################

import predict
import os
import sys
from configparser import ConfigParser 
from collections import OrderedDict
import time
from datetime import timedelta,datetime

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
    
    #tle  = TLE[idx]   + '\n'
    #tle += TLE[idx+1] + '\n' 
    #tle += TLE[idx+2] + '\n'
    
    tle = sat + '\n' \
        + TLE[idx+1] + '\n' \
        + TLE[idx+2] + '\n'

    #print('GET_TLE: tle=',tle)
    
    return tle

################################################################################

# Structure to contain data for a satellite
class SATELLITE:
    def __init__(self,isat,name,qth,tbefore,tafter,TLE):

        print('\nSATELLITE CLASS: isat=',isat,'-\tSat:',name, \
              '\ttb-ta:',tbefore,tafter,'\tqth:',qth)
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
        # by Gpredict - for this, we need the sat number
        print('GET_TRANSPONDERS: tle =',self.tle)
        tle2=self.tle.split()
        print('GET_TRANSPONDERS: tle2=',tle2)
        self.number=int( tle2[2][:-1] )
        print('GET_TRANSPONDERS: number=',self.number)
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
                if items['invert']=='true':
                    items['Inverting']=True

            # Find the main transponder
            if self.name=='ISS':
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

            
