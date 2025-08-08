################################################################################
#
# Params.py - Rev 1.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# Command line param parser for satellite predictions.
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

import os
from rig_io.ft_tables import SATELLITE_LIST,CONNECTIONS,SAT_RIGS
import argparse
from settings import read_settings
import datetime
import platform

################################################################################

# Structure to contain processing params
class PARAMS:
    def __init__(self):

        # Process command line args
        arg_proc = argparse.ArgumentParser()
        arg_proc.add_argument("-n", help="No. Days",type=int,default=10)
        arg_proc.add_argument('-update', action='store_true',\
                              help='Update TLE Data from Internet')
        arg_proc.add_argument("-grid", help="Grid Square",
                              type=str,default=None)
        arg_proc.add_argument("-rig", help="Connection Type",
                              type=str,default=["NONE"],nargs='+',
                              choices=CONNECTIONS+['NONE']+SAT_RIGS)
        arg_proc.add_argument("-port", help="Connection Port",
                              type=int,default=0)
        arg_proc.add_argument("-rotor", help="Rotor connection Type",
                              type=str,default="NONE",
                              choices=['HAMLIB','DIRECT','NONE'])
        arg_proc.add_argument("-port2", help="Rotor connection Port",
                              type=int,default=0)
        arg_proc.add_argument("-sat", help="Sat to Track",
                              type=str,default=None)
        arg_proc.add_argument("-grid2", help="Show passes covering another grid",
                              type=str,default=None)
        arg_proc.add_argument('-sdr', action='store_true',
                              help='Command SDR also')
        arg_proc.add_argument("-tstart", help="Start Time",
                              type=int,default=0)
        arg_proc.add_argument("-tend", help="End Time",
                              type=int,default=24)
        arg_proc.add_argument('-udp', action='store_true',
                              help='Start UDP client')
        arg_proc.add_argument('-gps', action='store_true',
                              help='Read GPS info from .gpsrc file')
        arg_proc.add_argument('-test', action='store_true',
                              help='Test Mode')
        arg_proc.add_argument('-map', action='store_true',
                              help='Show track Map')
        
        args = arg_proc.parse_args()
        self.NDAYS2     = args.n
        self.UPDATE_TLE = args.update
        if args.sat:
            self.sat_name  = args.sat.upper()
        else:
            self.sat_name  = None

        self.connection    = args.rig[0]
        if len(args.rig)>=2:
            self.rig       = args.rig[1]
        else:
            self.rig       = None
        self.PORT          = args.port
        self.UDP_CLIENT    = args.udp
        self.GPS           = args.gps
        self.TEST_MODE     = args.test
        self.SHOW_MAP      = args.map

        self.GRID2         = args.grid2
            
        self.ROTOR_CONNECTION = args.rotor
        self.PORT2            = args.port2
        if self.PORT2==0:
            if self.ROTOR_CONNECTION=='HAMLIB':
                self.PORT2==433
            elif self.ROTOR_CONNECTION=='DIRECT':
                self.PORT2==232

        self.USE_SDR          = args.sdr
        self.SDR_CONNECTION   = 'HAMLIB'
        self.PORT3            = 4575            # Needs to be same port SDR is listening on

        self.TSTART           = args.tstart
        if self.TSTART<0:
            now = datetime.datetime.now()
            self.TSTART       = now.hour
        self.TEND             = args.tend
        if self.TEND<0 or self.TEND>24:
            self.TEND         = 24

        self.NO_FLIPPER       = False
        self.PLATFORM=platform.system()
        
        # Read config file
        ATTR=['Call','Grid','Alt_ft']
        self.SETTINGS,self.RCFILE = read_settings('.satrc',attr=ATTR)
        """
        self.RCFILE=os.path.expanduser("~/.satrc")
        self.SETTINGS=None
        try:
            with open(self.RCFILE) as json_data_file:
                self.SETTINGS = json.load(json_data_file)
        except:
            print(self.RCFILE,' not found!\n')
            sys.exit(0)
        """
        
        self.MY_GRID    = args.grid
        if self.MY_GRID==None:
            try:
                self.MY_GRID = self.SETTINGS['MY_GRID']
            except:
                self.MY_GRID = 'DM12'
                
        try:
            self.SATELLITE_LIST = self.SETTINGS['ACTIVE']

            # There is a goofy legacy thing that I need to look into
            # that requires the first "sat" in the list be 'None'
            if 'None' not in self.SATELLITE_LIST:
                self.SATELLITE_LIST = ['None'] + self.SATELLITE_LIST
        except:
            self.SATELLITE_LIST = SATELLITE_LIST

        #print('PARAMS: SATELLITE LIST=',self.SATELLITE_LIST)
