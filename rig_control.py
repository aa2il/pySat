#! /usr/bin/python3 -u
################################################################################
#
# RigControl.py - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Rig Control class for satellite predictions.
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

ROTOR_THRESH = 10       # Was 2 but rotor updates too quickly

################################################################################

import sys
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
import time
from datetime import timedelta,datetime

################################################################################

# Rig control called every sec seconds
class RigControl:
    def __init__(self,P,sec):

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.Updater)
        self.timer.start(1000*sec)
        self.P=P
        self.gui=P.gui
        self.frqA=0
        self.fdown = None
        
        self.fp_log = open("/tmp/satellites.log", "w")
        row=['Time Stamp','Selected',
             'fup','fdown','df','fdop1','fdop2',
             'frqA','frqB',
             'az','el','pos[0]','pos[1]','new_pos[0]','new_pos[1]','daz','de',
             'flipper','rig_engaged','rotor_updated']
        for item in row:
            self.fp_log.write(str(item)+',')
        self.fp_log.write('\n')
        self.fp_log.flush()


    def Updater(self):
        P=self.P
        gui=P.gui
        
        if False:
            print('RIG CONTROL UPDATER: Rig  =',P.sock.rig_type1,P.sock.rig_type2)
            if P.sock2.active:
                print('RIG CONTROL UPDATER: Rotor=',P.sock2.rig_type1,P.sock2.rig_type2)
        
        if (gui.rig_engaged or self.fdown==None) and gui.Selected:
        #if gui.rig_engaged and gui.Selected:
        #if gui.Selected:
        
            # Tune to middle of transponder BW if we've selected a new sat
            if gui.New_Sat_Selection:
                print('\nNew Sat Selected:',gui.Selected)
                P.satellite = gui.Satellites[gui.Selected]
                P.transp    = P.satellite.transponders[P.satellite.main]
                print('main=',P.satellite.main)
                print('transp=',P.transp)

                # Put rig into sat mode
                if P.sock.rig_type2=='FT991a':
                    print('Putting FT991a into SPLIT mode ...')
                    P.sock.split_mode(1)
                    self.vfos=['A','B']
                elif P.sock.rig_type2=='IC9700':
                    print('Putting IC9700 into SAT mode ...')
                    P.sock.sat_mode(1)
                    self.vfos=['M','S']
                elif P.sock.rig_type2=='pySDR':
                    self.vfos=['A']
                elif P.sock.rig_type2==None or P.sock.rig_type2=='Dummy':
                    self.vfos=['A','B']
                else:
                    print('UPDATER: Unknown rig',P.sock.rig_type2,' - Aborting')
                    sys.exit(0)

                # Check VFO bands - the IC9700 is quirky if the bands are reversed
                if P.sock.rig_type2=='IC9700':
                    frq1 = int( P.sock.get_freq(VFO=self.vfos[0]) )
                    band1 = P.sock.get_band(1e-6*frq1)
                    print('frq1=',frq1,band1)
                    #frq2 = int( P.sock.get_freq(VFO=self.vfos[1]) )
                    frq2 = P.transp['fdn1']
                    band2 = P.sock.get_band(1e-6*frq2)
                    print('frq2=',frq2,band2)
                    if band1!=band2:
                        print('Flipping VFOs')
                        P.sock.select_vfo('X')
                    #sys.exit(0)
                        
                # Set proper mode on both VFOs
                self.set_rig_mode( P.transp['mode'] )
                idx = gui.MODES.index( P.transp['mode'] )
                gui.mode_cb.setCurrentIndex(idx)
                    
                # Set down link freq to center of transp passband - uplink will follow
                self.fdown = 0.5*(P.transp['fdn1']+P.transp['fdn2'])
                self.track_freqs()
                
                gui.New_Sat_Selection=False

                # Tell keyer name of new sat
                if self.P.UDP_CLIENT:
                    self.P.udp_client.Send('Sat:'+gui.Selected)
            
            else:

                # Check if op has spun main dial - if so, compute new downlink freq
                frq = int( P.sock.get_freq(VFO=self.vfos[0]) )
                if frq>0 and frq!=self.frqA:
                    #print('========================================================================')
                    #print('=============================== Rig freq change: old frq=',self.frqA,'\tnew frq=',frq)
                    #print('========================================================================')
                    self.fdown = frq - self.fdop1

                    # Don't do anything until op stops spinning the dial
                    self.frqA = frq
                    if gui.rit!=0:
                        return

                # Update up and down link freqs 
                self.track_freqs()

        # Update AOS/LOS indicator
        self.update_aos_los()

    # Routine to set rig mode on both VFOs
    def set_rig_mode(self,mode):
        P=self.P
        
        if mode[0:2]=='CW':
            filter='Wide'
        else:
            filter=None
        P.sock.set_mode(mode,VFO=self.vfos[0],Filter=filter)
        if len(self.vfos)>1:
            if P.transp['Inverting']:
                if mode=='USB':
                    P.sock.set_mode('LSB',VFO=self.vfos[1])
                elif mode=='LSB':
                    P.sock.set_mode('USB',VFO=self.vfos[1])
                elif mode=='CW':
                    P.sock.set_mode('CW-R',VFO=self.vfos[1],Filter=filter)
                elif mode=='CW-R':
                    P.sock.set_mode('CW',VFO=self.vfos[1],Filter=filter)
            else:
                P.sock.set_mode(mode,VFO=self.vfos[1],Filter=filter)

                
    # Function to set up & downlink freqs on rig
    def track_freqs(self,Force=False):
        P=self.P
        gui=self.gui
        
        # Compute uplink freq corresponding to downlink
        df = self.fdown - P.transp['fdn1']
        if P.transp['Inverting']:
            self.fup = P.transp['fup2'] - df
            #print('Inv:',P.transp['fup2'],df,self.fup)
        else:
            self.fup = P.transp['fup1'] + df
            #print('Non:',P.transp['fup1'],df,self.fup)
        #print('fdown=',self.fdown,'\tdf=',df,'\tfup=',self.fup, \
        #'\tInv=', P.transp['Inverting'])
            
        # Compute Doppler shifts for up and down links
        [self.fdop1,fdop2,az,el] = P.satellite.Doppler_Shifts(self.fdown,self.fup,P.my_qth)
        #print('TRACK_FREQS:',int(self.fdown),int(self.fdop1),
        #      int(self.fup),int(fdop2),'\t',int(az),int(el))

        # Set up and down link freqs
        if len(self.vfos)>1:
            self.frqB = int(self.fup+fdop2 + gui.xit)
            if gui.rig_engaged or Force:
                P.sock.set_freq(1e-3*self.frqB,VFO=self.vfos[1])
                
        self.frqA = int(self.fdown+self.fdop1 + gui.rit)
        if gui.rig_engaged or Force:
            P.sock.set_freq(1e-3*self.frqA,VFO=self.vfos[0])
            if P.USE_SDR:
                #print('Setting SDR freq to:',1e-3*self.frqA)
                P.sock3.set_freq(1e-3*self.frqA)
        #print(self.frqA,self.frqB)

        # Form new rotor position
        if el>=0:
            # Sat is above the horizon so point to calculated sat position
            new_pos=[az,el]
        else:
            # Sat is below the horizon so point to starting point on track
            new_pos=[gui.track_az[0] , 0]

        # Flip antenna if needed to avoid ambiquity at 180-deg
        if gui.flipper:
            print('*** Need a Flip-a-roo-ski ***')
            if new_pos[0]<180:
                new_pos = [new_pos[0]+180. , 180.-new_pos[1]]
            else:
                new_pos = [new_pos[0]-180. , 180.-new_pos[1]]

        # Update rotor 
        rotor_updated=False
        if P.sock2.active:
            
            # Current rotor position
            pos=P.sock2.get_position()

            # Compute pointing error & adjust rotor if the error is large enough
            daz=pos[0]-new_pos[0]
            de =pos[1]-new_pos[1]
            #print('pos=',pos,'\taz/el=',az,el,'\tdaz/del=',daz,de, \
            #      '\n\tnew_pos=',new_pos)
            if abs(daz)>ROTOR_THRESH or abs(de)>ROTOR_THRESH:
                if gui.rig_engaged or Force:
                    P.sock2.set_position(new_pos)
                    rotor_updated=True
                
        else:
            pos=[np.nan,np.nan]
            daz=np.nan
            de=np.nan

        # Update sky track
        gui.plot_position(az,el,pos)

        # Toggle voice recorder (if available)
        visible = el>0
        if visible:
            #print('=== ',gui.Selected,' is VISIBLE ===',az,el)
            on_off=P.sock.recorder(True)
        else:
            #print('=== ',gui.Selected,' is BELOW THE HORIZON ===',az,el)
            on_off=P.sock.recorder(False)
        #print('=== buf=',on_off)
            
        # Update gui
        gui.txt1.setText("{:,}".format(int(self.fdown)))
        gui.txt2.setText("{:,}".format(int(self.fup)))
        gui.txt3.setText("{:,}".format(int(self.frqA)))
        gui.txt4.setText("{:,}".format(int(self.frqB)))

        gui.txt5.setText("Az: {: 3d}".format(int(new_pos[0])))
        gui.txt6.setText("El: {: 3d}".format(int(new_pos[1])))
        if gui.flipper:
            gui.txt7.setText('Flip-a-roo-ski!')
        else:
            gui.txt7.setText('Not flipped')
        #self.update_aos_los()

        # Save log file to assist in further development
        now = datetime.now()
        #print('NOW=',now)
        row=[now,gui.Selected,
             self.fup,self.fdown,df,self.fdop1,fdop2,
             self.frqA,self.frqB,
             az,el,pos[0],pos[1],new_pos[0],new_pos[1],daz,de,
             gui.flipper,gui.rig_engaged,rotor_updated]
        for item in row:
            self.fp_log.write(str(item)+',')
        self.fp_log.write('\n')
        self.fp_log.flush()



    def hms(self,dt):

        hrs  = int( dt/3600. )
        dt2  = dt-3600*hrs
        mins = int( dt2/60. )
        secs = int( dt2-60*mins )

        txt = "{:02d}:{:02d}:{:02d}".format(hrs,mins,secs)
        #print(dt,dt2,dt3,'\t',hrs,mins,secs,'\t',txt)
        
        return txt
        

    # Function to update portion of gui related to AOS/LOS
    def update_aos_los(self):
        gui=self.P.gui
        
        now = time.mktime( datetime.now().timetuple() )
        #print('now=',now,'\taos=',gui.aos,'\tlos=',gui.los)
        daos=gui.aos-now
        dlos=gui.los-now
        #print('d-aos=',daos,'\td-los=',dlos)
        
        if daos>0:
            gui.txt9.setText("AOS in\t"+self.hms(daos))
        elif dlos>0:
            gui.txt9.setText("LOS in\t"+self.hms(dlos))
        else:
            gui.txt9.setText("Past Event")

        if False:
            screen = QDesktopWidget().screenGeometry()
            print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ screen=',screen)
            widget = gui.win.geometry()
            print('win=',widget)
            print('hint=',gui.win.sizeHint())

        
