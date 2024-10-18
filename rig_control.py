#! /usr/bin/python3 -u
################################################################################
#
# RigControl.py - Rev 1.0
# Copyright (C) 2021-4 by Joseph B. Attili, aa2il AT arrl DOT net
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

import sys
import numpy as np
try:
    if True:
        from PyQt6 import QtCore
    else:
        from PySide6 import QtCore
except ImportError:
    from PyQt5 import QtCore
import time
from datetime import timedelta,datetime
from rig_io.ft_tables import SATELLITE_LIST
from rotor import *
from utilities import freq2band, error_trap

################################################################################

# Rig control called every sec seconds
class RigControl:
    def __init__(self,P,sec):

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.Updater)
        self.timer.start(1000*sec)
        self.P     = P
        self.gui   = P.gui
        self.frqA  = 0
        self.frqB  = 0
        self.fdown = None
        self.fdop1 = None
        self.fdop2 = None
        self.az    = None
        self.el    = None
        self.sat_map_cntr=0

        if P.PLATFORM=='Windows':
            tmpfile="satellites.log"
        else:
            tmpfile="/tmp/satellites.log"
        self.fp_log = open(tmpfile, "w")
        
        row=['Time Stamp','Source','Selected',
             'Inverting','dn1','dn2','up1','up2','Mode',
             'fup','fdown','df','fdop1','fdop2',
             'frqA','frqB','RIT','XIT',
             'az','el','pos[0]','pos[1]','new_pos[0]','new_pos[1]','daz','de',
             'flipper','rig_engaged','rotor_engaged','rotor_updated']
        for item in row:
            self.fp_log.write(str(item)+',')
        self.fp_log.write('\n')
        self.fp_log.flush()


    def Updater(self):
        P=self.P
        gui=P.gui
        #print('\nUPDATER ...')

        engaged = gui.rig_engaged or gui.rotor_engaged                 
        if (engaged or self.fdown==None) and gui.Selected:
        
            # Tune to middle of transponder BW if we've selected a new sat
            if gui.New_Sat_Selection:
                print('\nNew Sat Selected:',gui.Selected)
                P.satellite = gui.Satellites[gui.Selected]
                if P.satellite.main:
                    P.transp    = P.satellite.transponders[P.satellite.main]
                    print('main=',P.satellite.main)
                    print('transp=',P.transp)
                else:
                    print('RIG_CONTROL->UPDATER: Hmmmm - no transponder for this sat')
                    gui.New_Sat_Selection=False
                    return

                # Put rig into sat mode
                if P.sock.rig_type2=='FT991a':
                    print('Putting FT991a into SPLIT mode ...')
                    P.sock.split_mode(1)
                    self.vfos=['A','B']
                elif P.sock.rig_type2=='IC9700':
                    if P.satellite.name in ['Moon','IO-117']:
                        print('Putting IC9700 into Regular mode ...')
                        P.sock.sat_mode(0)
                        self.vfos=['A','B']
                    else:
                        print('Putting IC9700 into SAT mode ...')
                        P.sock.sat_mode(1)
                        self.vfos=['M','S']
                    self.check_ic9700_bands(P)
                elif P.sock.rig_type2=='pySDR':
                    self.vfos=['A']
                elif P.sock.rig_type2==None or P.sock.rig_type2=='None' \
                     or P.sock.rig_type2=='Dummy':
                    self.vfos=['A','B']
                else:
                    print('UPDATER: Unknown rig',P.sock.rig_type2,' - Aborting')
                    sys.exit(0)

                # Set proper mode on both VFOs
                if False:
                    mode=P.transp['mode']
                    self.set_rig_mode( mode )
                    gui.txt15.setText(mode)
                    if gui.mode_cb:
                        idx = gui.MODES.index( mode )
                        gui.mode_cb.setCurrentIndex(idx)
                else:
                    gui.ModeSelect()
                        
                # Set down link freq to center of transp passband - uplink will follow
                self.fdown = 0.5*(P.transp['fdn1']+P.transp['fdn2'])
                self.track_freqs(tag='Selection')
                
                gui.New_Sat_Selection=False

                # Tell keyer name of new sat
                if self.P.UDP_CLIENT:
                    self.P.udp_client.Send('Sat:'+gui.Selected)

                # Set XIT for this sat
                try:
                    OFFSETS=self.P.SETTINGS['OFFSETS']
                    gui.rit=OFFSETS[gui.Selected][0]
                    gui.xit=OFFSETS[gui.Selected][1]
                except:
                    error_trap('RIG CONTROL -> UPDATER: Unable to set RIT/XIT')
                    print('\tsat=',gui.Selected)
                    gui.rit=0
                    gui.xit=0
                gui.txt11.setText(str(gui.rit))
                gui.txt13.setText(str(gui.xit))

            else:

                # Check if op has spun main dial - if so, compute new downlink freq
                frq = int( P.sock.get_freq(VFO=self.vfos[0]) )
                #print('++++++++++++++++++++++++++--------------- frq=',frq,'\tfrqA=',self.frqA)
                if frq>0 and frq!=self.frqA:
                    #print('========================================================================')
                    #print('=============================== Rig freq change: old frq=',self.frqA,'\tnew frq=',frq)
                    #print('========================================================================')

                    # Compute new downlink freq at the sat
                    self.fdown = frq -gui.rit - self.fdop1

                    # Don't do anything until op stops spinning the dial
                    self.frqA = frq
                    nan=np.nan
                    self.save_diagnostics('Spin',nan,[nan,nan],[nan,nan],nan,nan,nan)
                    return

                # Update up and down link freqs - WAS 2 TABS IN
                self.track_freqs(tag='Update')
                
        else:
            self.track_freqs(tag='Update')

        # Update AOS/LOS indicator
        self.update_aos_los()

    # Routine to check VFO bands - the IC9700 is quirky if the bands are reversed
    def check_ic9700_bands(self,P):
        frq1 = int( P.sock.get_freq(VFO=self.vfos[0]) )
        #band1 = P.sock.get_band(1e-6*frq1)
        band1  = freq2band(1e-6*frq1)
        print('frq1=',frq1,band1)

        frq2 = P.transp['fdn1']
        #band2 = P.sock.get_band(1e-6*frq2)
        band2  = freq2band(1e-6*frq2)
        print('frq2=',frq2,band2)
        if band1!=band2:
            print('Flipping VFOs')
            P.sock.select_vfo('X')
                        
        
    # Routine to set rig mode on both VFOs
    def set_rig_mode(self,mode):
        P=self.P
        print('================== RIG_SET_MODE:',mode,self.vfos,P.transp['Inverting'],'================')
        
        if mode[0:2]=='CW':
            filter='Wide'
        else:
            filter=None
        P.sock.set_mode(mode,VFO=self.vfos[0],Filter=filter)
        if len(self.vfos)>1:
            if P.transp['Inverting']:
                if mode=='FM':
                    P.sock.set_mode('FM',VFO=self.vfos[1])
                elif mode=='USB':
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
    def track_freqs(self,Force=False,tag='Track'):
        P=self.P
        gui=self.gui
        #print('\nTRACK_FREQS: P.transp=',P.transp)
        
        # Compute uplink freq corresponding to downlink
        df = self.fdown - P.transp['fdn1']
        if P.transp['Inverting']:
            self.fup = P.transp['fup2'] - df
            #print('Inv:',P.transp['fup2'],df,self.fup)
        else:
            self.fup = P.transp['fup1'] + df
            #print('Non:',P.transp['fup1'],df,self.fup)
            
        # Compute Doppler shifts for up and down links
        [self.fdop1,self.fdop2,self.az,self.el,rng,lat,lon,footprint] = \
            P.satellite.Doppler_Shifts(self.fdown,self.fup,P.my_qth)

        # Set up and down link freqs
        if len(self.vfos)>1:
            self.frqB = int(self.fup+self.fdop2 + gui.xit)
            if gui.rig_engaged or Force:
                P.sock.set_freq(1e-3*self.frqB,VFO=self.vfos[1])

        # Compute downlink freq at rig = frq at sat + Doppler
        self.frqA = int(self.fdown+self.fdop1 + gui.rit)
        if gui.rig_engaged or Force:
            print('TRACK FREQS: VFO A=',self.frqA,'\tVFO B=',self.frqB)
            P.sock.set_freq(1e-3*self.frqA,VFO=self.vfos[0])
            if P.USE_SDR:
                #print('Setting SDR freq to:',1e-3*self.frqA)
                P.sock3.set_freq(1e-3*self.frqA)
        #print(self.frqA,self.frqB)

        # Form new rotor position
        try:
            rotor_updated,pos,daz,de,new_pos = \
                rotor_positioning(gui,self.az,self.el,Force)
        except:
            error_trap('RIG CONTROL -> TRACK_FREQS: Unable to update rotor position')
            print(self.az,self.el)
            pos=[nan,nan]

        # Update sky track & sat map
        gui.plot_position(self.az,self.el,pos)
        engaged = gui.rig_engaged or gui.rotor_engaged
        if self.P.SHOW_MAP and engaged:
            self.sat_map_cntr+=1
            if self.sat_map_cntr>=10:
                name = P.satellite.name
                print('\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ Updating footprint ...',name)
                self.sat_map_cntr=0
                gui.MapWin.DrawSatFootprint(name,lon,lat,footprint)
        
        # Toggle voice recorder (if available)
        if self.el>0:
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

        gui.SRng.setText( '%d miles' % rng )
        
        # Save log file to assist in further development
        self.save_diagnostics(tag,df,pos,new_pos,daz,de,rotor_updated)
        
        
    # Save log file to assist in further development
    def save_diagnostics(self,source,df,pos,new_pos,daz,de,rotor_updated):
        P=self.P
        gui=self.gui
        
        now = datetime.now()
        row=[now,source,gui.Selected,
             P.transp['Inverting'],P.transp['fdn1'],P.transp['fdn2'],
             P.transp['fup1'],P.transp['fup2'],P.transp['mode'],
             self.fup,self.fdown,df,self.fdop1,self.fdop2,
             self.frqA,self.frqB,gui.rit,gui.xit,
             self.az,self.el,pos[0],pos[1],new_pos[0],new_pos[1],daz,de,
             gui.flipper,gui.rig_engaged,gui.rotor_engaged,rotor_updated]
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
        #print('UPDATE AOS-LOS: Now=',now,type(now),
        #      '\taos=',gui.aos,type(gui.aos),
        #      '\tlos=',gui.los,type(gui.los))
        try:
            daos=gui.aos-now
            dlos=gui.los-now
            #print('UPDATE AOS-LOS: d-aos=',daos,'\td-los=',dlos)
        except:
            daos=0
            dlos=0
            #print('UPDATE AOS-LOS: Whooops!')
        
        if daos>0:
            gui.txt9.setText("AOS in\t"+self.hms(daos))
            gui.event_type = 1
        elif dlos>0:
            gui.txt9.setText("LOS in\t"+self.hms(dlos))
            gui.event_type = 0
        else:
            gui.txt9.setText("Past Event")
            gui.event_type = -1

        if False:
            screen = QDesktopWidget().screenGeometry()
            print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ screen=',screen)
            widget = gui.win.geometry()
            print('win=',widget)
            print('hint=',gui.win.sizeHint())

        
