################################################################################
#
# RigControl.py - Rev 1.0
# Copyright (C) 2021-6 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
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

import sys,os
import numpy as np
from widgets_qt import QTLIB
exec('from '+QTLIB+' import QtCore')
exec('from '+QTLIB+'.QtWidgets import QMessageBox')
import time
from datetime import timedelta,datetime
from rig_io.ft_tables import SATELLITE_LIST,SAT_PL_TONES
from rotor import *
from utilities import freq2band, error_trap
import rig_io.socket_io as socket_io

################################################################################

# Function to open connection to rig
def connect_to_rig(P):
    P.gui.status_bar.setText('Opening connection to rig ...')
    Done=False
    while not Done:
        P.sock = socket_io.open_rig_connection(P.connection,0,P.PORT,0,'SATELLITES',rig=P.rig)
        if P.rig!=None and (P.sock==None or not P.sock.powered_up):
            print('Ooops! - No rig connection')
            print('\tpowered_up=',P.sock.powered_up,'\tconnection=',P.connection,'\trig=',P.rig)

            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Icon.Information)
            msgBox.setText("Rig Not Responding!!!\n\nClick OK to POWER UP and try again ...")
            msgBox.setWindowTitle("Rig Not Responding")
            msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

            returnValue = msgBox.exec()
            if returnValue == QMessageBox.StandardButton.Ok:
                print('OK clicked ...')
                #P.sock.power_switch(1,VERBOSITY=1)
                cmd='~/Python/findRig/findRig.py -rig DIRECT IC9700 -SWITCH 1'
                os.system(cmd)

            elif returnValue == QMessageBox.StandardButton.Cancel:
                print('Cancel clicked - quitting app')
                sys.exit(0)
        else:
            Done=True    

    if P.sock.rig_type=='Icom':
        P.sock.icom_defaults()
    print('RIG: type=',P.sock.rig_type,'\ttype1=',P.sock.rig_type1,'\ttype2=',P.sock.rig_type2)
    #sys.exit(0)

    # Make sure rig is properly setup
    if P.sock.rig_type2=='IC9700':

        # Regular (non-Sat) mode
        P.sock.sat_mode(0,VERBOSITY=1)
        P.SAT_MODE = False
                        
        # Pre-amp on, attenuator off, mic gain=70%, RIT=0
        P.sock.frontend(1,1,0)
        #P.sock.mic_setting('SSB',1,lvl=70)     ### PROBLEM FOR HAMLIB - NEED CODE !!!!
        P.sock.mic_settings(gain=70,mode='SSB',VERBOSITY=1)
        for vfo in ['A','B']:
            P.sock.rit(0,0,VFO=vfo)

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
        self.vfos=['A','B']

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


    def Updater(self,VERBOSITY=1):
        P=self.P
        gui=P.gui
        if VERBOSITY>0:
            print('\nRIG CONTROL UPDATER ...')

        if P.USE_LOCK:
            acq=gui.rigLock.acquire(timeout=0.5)
            if not acq:
                error_trap('UPDATER: Unable to acquire lock - giving up :-(')
                return None                
            
        need_update=gui.refresh.isSet()
        if need_update:
            print('UPDATER: Needs an update!   Selected=',gui.Selected,
                  '\tNew Selection=',gui.New_Sat_Selection)
            gui.refresh.clear()

        engaged = gui.rig_engaged or gui.rotor_engaged                 
        if (need_update or engaged or self.fdown==None) and gui.Selected:

            # Tune to middle of transponder BW if we've selected a new sat
            if gui.New_Sat_Selection:
                print('\nNew Sat Selected:',gui.Selected)
                gui.setFocus()
                P.satellite = gui.Satellites[gui.Selected]
                if P.SSTV and hasattr(P.satellite,'sstv') and gui.Selected=='ISS':
                    P.transp       = P.satellite.transponders[P.satellite.sstv]
                    P.SIMPLEX = True
                    print('UPDATER: sstv  =',P.satellite.sstv)
                    print('UPDATER: transp=',P.transp)
                elif P.EME and gui.Selected=='Moon':
                    P.transp       = P.satellite.transponders['Mode V']
                    P.SIMPLEX = True
                    print('UPDATER: transponders  =',P.satellite.transponders)
                    print('UPDATER: transp=',P.transp)
                elif P.satellite.main:
                    P.transp       = P.satellite.transponders[P.satellite.main]
                    P.SIMPLEX = False
                    print('UPDATER: main=',P.satellite.main)
                    print('UPDATER: transp=',P.transp)
                else:
                    print('RIG_CONTROL->UPDATER: Hmmmm - no transponder for this sat')
                    P.SIMPLEX=False
                    gui.New_Sat_Selection=False
                    return

                # Put rig into sat mode
                if P.sock.rig_type2=='FT991a':
                    print('Putting FT991a into SPLIT mode ...')
                    P.sock.split_mode(1,VERBOSITY=1)
                    P.SAT_MODE = True
                    self.vfos=['A','B']
                elif P.sock.rig_type2=='IC9700':
                    if P.satellite.name in ['Moon','IO-117'] or P.SIMPLEX:
                        print('Putting IC9700 into Regular (non-SAT) mode ...')
                        P.sock.sat_mode(0,VERBOSITY=1)
                        P.SAT_MODE = False
                        self.vfos=['A','B']
                    else:
                        print('Putting IC9700 into SAT mode ...')
                        P.sock.sat_mode(1,VERBOSITY=1)
                        P.SAT_MODE = True
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
                mode = gui.ModeSelect(USE_LOCK=False)
                
                # Set PL Tone for FM sats
                if mode=='FM':
                    name = P.satellite.name
                    print('UPDATER: FM Sat ',name,'\tmode=',mode,
                          '\ttones=',SAT_PL_TONES)
                    if name in SAT_PL_TONES:
                        tone = SAT_PL_TONES[name]
                        print('UPDATER: FM Sat ',name,' - Setting PL Tone to ',tone,' Hz')
                        P.sock.set_PLtone(tone,VERBOSITY=1)

                        tone2=P.sock.get_PLtone(VERBOSITY=1)
                        print('\tread back=',tone2,' Hz')
                        gui.status_bar.setText('PL Tone = '+str(tone2)+' Hz',APPEND=True)
                        
                # Set downlink freq to center of transp passband - uplink will follow
                self.fdown = 0.5*(P.transp['fdn1']+P.transp['fdn2'])
                self.track_freqs(tag='Selection')

                gui.New_Sat_Selection=False

                # Tell keyer name of new sat
                if self.P.UDP_CLIENT:
                    self.P.udp_client.Send('Sat:'+gui.Selected)

                # Set RIT & XIT for this sat
                try:
                    OFFSETS=self.P.SETTINGS['OFFSETS']
                    print('\toffsets=',OFFSETS,'\tSelected=',gui.Selected)
                    #print('\toffsets=',OFFSETS[gui.Selected])
                    if gui.Selected in OFFSETS and len(OFFSETS[gui.Selected])>0:
                        gui.rit=OFFSETS[gui.Selected][0]
                        gui.xit=OFFSETS[gui.Selected][1]
                    else:
                        gui.rit=0
                        gui.xit=0
                except:
                    error_trap('RIG CONTROL->UPDATER: Unable to set RIT/XIT')
                    print('\tsat=',gui.Selected)
                    print('\tOFFSETS=',OFFSETS)
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
                    self.fdown = frq - gui.rit - self.fdop1

                    # Don't do anything until op stops spinning the dial
                    self.frqA = frq
                    nan=np.nan
                    self.save_diagnostics('Spin',nan,[nan,nan],[nan,nan],nan,nan,nan)
                    return

                # Update up and down link freqs - WAS 2 TABS IN
                self.track_freqs(tag='Update')
                
        else:
            self.track_freqs(tag='Update')

        # Update AOS/LOS indicator and other gui items that may have changed
        self.update_aos_los()
        self.P.SatModeAct.setChecked(self.P.SAT_MODE)
        
        if P.USE_LOCK:
            gui.rigLock.release()

    # Routine to check VFO bands - the IC9700 is quirky if the bands are reversed
    def check_ic9700_bands(self,P):
        print('CHECK IC9700 BANDS: transp=',P.transp,'\tsimplex=',P.SIMPLEX)
        frq1 = int( P.sock.get_freq(VFO=self.vfos[0]) )
        #band1 = P.sock.get_band(1e-6*frq1)
        band1  = freq2band(1e-6*frq1)
        print('frq1=',frq1,band1)
        
        if P.transp:
            frq2 = P.transp['fdn1']
            band2  = freq2band(1e-6*frq2)
            print('frq2=',frq2,band2)
            if band1!=band2:
                print('Flipping VFOs')
                P.sock.select_vfo('X')
                        
        
    # Routine to set rig mode on both VFOs
    def set_rig_mode(self,mode,bw=None):
        P=self.P
        print('=== RIG_SET_MODE: mode=',mode,'\tbw=',bw,'\tvfos=',self.vfos,
              '\tinverting=',P.transp['Inverting'],'===')

        if mode=='SSTV':
            mode='FM'
        if bw==None:
            filter='Wide'
        else:
            filter=bw
            
        P.sock.set_mode(mode,VFO=self.vfos[0],Filter=filter,VERBOSITY=1)
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

        print('================== RIG_SET_MODE Done ================================')
                
    # Function to set up & downlink freqs on rig
    def track_freqs(self,Force=False,tag='Track'):
        P=self.P
        gui=self.gui
        print('\nTRACK_FREQS: P.transp=',P.transp)
        if P.transp==None:
            print('\nTRACK_FREQS: No transponder!')
            return
        
        # Compute uplink freq corresponding to downlink
        try:
            df = self.fdown - P.transp['fdn1']
            if P.transp['fup1']==0:
                self.fup = 0
            elif P.transp['Inverting']:
                self.fup = P.transp['fup2'] - df
                #print('Inv:',P.transp['fup2'],df,self.fup)
            else:
                self.fup = P.transp['fup1'] + df
                #print('Non:',P.transp['fup1'],df,self.fup)
        except:
            error_trap('RIG CONTROL -> TRACK FREQS - Whoops!')
            print('\tsat=',gui.Selected)
            return
            
            
        # Compute Doppler shifts for up and down links
        [self.fdop1,self.fdop2,self.az,self.el,rng,lat,lon,footprint] = \
            P.satellite.Doppler_Shifts(self.fdown,self.fup,P.my_qth)

        # Set up link freq
        if len(self.vfos)>1 and self.fup>0:
            self.frqB = int(self.fup+self.fdop2 + gui.xit)
            if gui.rig_engaged or Force:
                P.sock.set_freq(1e-3*self.frqB,VFO=self.vfos[1],VERBOSITY=0)

        # Compute downlink freq at rig = frq at sat + Doppler
        self.frqA = int(self.fdown+self.fdop1 + gui.rit)
        if gui.rig_engaged or Force:
            print('\nTRACK FREQS: VFO A=',self.frqA,'\tVFO B=',self.frqB)
            P.sock.set_freq(1e-3*self.frqA,VFO=self.vfos[0],VERBOSITY=0)
            if P.USE_SDR:
                #print('Setting SDR freq to:',1e-3*self.frqA)
                P.sock3.set_freq(1e-3*self.frqA)
        #print(self.frqA,self.frqB)

        # Form new rotor position
        if 1:
            rotor_updated,pos,daz,de,new_pos = \
                rotor_positioning(gui,self.az,self.el,Force)
        """
        try:
        except:
            error_trap('RIG CONTROL -> TRACK_FREQS: Unable to update rotor position')
            print(self.az,self.el)
            rotor_updated=False
            pos=[np.nan,np.nan]
            new_pos=[np.nan,np.nan]
            daz=np.nan
            de=np.nan
        """
        
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
        self.update_rotor_angles(new_pos)
        """
        if not np.isnan(new_pos[0]):
            gui.txt5.setText("Az: {: 3d}".format(int(new_pos[0])))
        else:
            gui.txt6.setText("El: {: f}".format(new_pos[0]))
        if not np.isnan(new_pos[1]):
            gui.txt6.setText("El: {: 3d}".format(int(new_pos[1])))
        else:
            gui.txt6.setText("El: {: f}".format(new_pos[1]))
        if gui.flipper:
            gui.txt7.setText('Flip-a-roo-ski!')
        else:
            gui.txt7.setText('Not flipped')
        #self.update_aos_los()
        """

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
        P=self.P
        gui=P.gui
        
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

            if P.FOLLOW:
                print('UPDATE AOS-LOS: End of current pass, setting up for next pass for',P.sat_name,'...')
                sat,ttt=P.gui.find_next_transit([P.sat_name])
                print('\tsat=',sat)
                if sat:
                    P.gui.plot_sky_track(sat,ttt)
                    gui.refresh.set()
            else:
                gui.ToggleRigControl(junk=None,ENGAGED=False)
            

        if False:
            screen = QDesktopWidget().screenGeometry()
            print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ screen=',screen)
            widget = gui.win.geometry()
            print('win=',widget)
            print('hint=',gui.win.sizeHint())

        
    # Function to convert rotor position to actual pointing position in the sky (rel. to North)
    def update_rotor_angles(self,pos):

        gui=self.P.gui

        # Start out assuming not flipped and all is ok
        paz=pos[0]
        pel=pos[1]
        
        if pel==None or paz==None or np.isnan(paz) or np.isnan(pel):
            print('*** WARNING *** UPDATE ROTOR ANGLES - Unepected az/el value(s)',paz,pel)
            paz=0
            pel=0
        elif pel>90:
            # Ant is flipped - unwind actual pointing angles
            pel=180-pel
            paz=(paz+180) % 360
            if paz>180:
                paz-=360

        gui.txt5.setText("Az: {: 3d}".format(int(paz)))
        gui.txt6.setText("El: {: 3d}".format(int(pel)))
        print('\nUPDATE ROTOR ANGLES: flipper=',gui.flipper,
              '\n\tpos      =',pos,
              '\n\tresolved =',paz,pel,'\n')

        if gui.flipper:
            gui.txt7.setText('Flip-a-roo-ski!')
        else:
            gui.txt7.setText('Not flipped')
        #self.update_aos_los()
