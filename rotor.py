################################################################################
#
# rotor.py - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Routines related to rotor positioning
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

import numpy as np
import sys
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

###############################################################################

THRESH=15
ROTOR_THRESH = 10       # Was 2 but rotor updates too quickly

###############################################################################

# Function to determine if we need the old flip-a-roo-ski
# I.e. does sky track cross the 180-deg boundary?
def flip_a_roo_old(self):    

    az=self.track_az
    el=self.track_el
    
    # First, check if the track transists into both the 2nd and 3rd quadrants
    quad2 = np.logical_and(az>90  , az<=180)
    quad3 = np.logical_and(az>180 , az<=270)
    self.cross180 = any(quad2) and any(quad3)

    # Initially assume that there is nothing to worry about
    self.flipper      = False
    self.quads12_only = False
    self.quads34_only = False
    
    # If we cross the 180-deg boundary, how far do we go?
    if self.cross180:
        
        min2=az[quad2].min()
        max3=az[quad3].max()
        max_el = el.max()
        print('Flip-a-roo:',min2,max3,max_el)

        # We need to flip if we cross the boundary significantly OR its a very high overhead pass
        # The very high overhead pass is something we can probably refine later but it should
        # constitue a very small number of passes so we'll just do this for now.
        if (max3>180+THRESH and min2<180-THRESH) or max_el>75:
            self.flipper = self.cross180
            if self.flipper:
                print("\n######### They call him Flipper Flipper Flipper-a-roo-ski ######")

    # If we cross the boundary but not by much, fix up track so rotor is never
    # commanded to cross boundary
    if self.cross180 and not self.flipper:

        # Probably need to address what happens in 1st & 4th quads as well, 
        # particularly for the very high overhead passes
        quad1 = np.logical_and(az>0  , az<=90)
        quad4 = np.logical_and(az>270 , az<=360)
        n1 = np.sum(quad1)
        n2 = np.sum(quad2)
        n3 = np.sum(quad3)
        n4 = np.sum(quad4)
        print('Quad counts:',n1,n2,n3,n4)

        # This would be the right thing to do but has no effect since track goes back to sat positions
        if False:
            if n2>n3:
                # Probably want to add 4th quad points as well
                idx=np.argwhere(quad3)
                vals=az[ quad3 ]
                az[quad3] = 178
                vals2=az[ quad3 ]
                print('Adjusting 3rd quadrant track points ...',idx,vals,vals2)
            elif n3>n2:
                # Probably want to add 1st quad points as well
                idx=np.argwhere(quad2)
                vals=az[ quad2 ]
                az[quad2] = 182
                vals2=az[ quad2 ]
                print('Adjusting 2nd quadrant track points ...',idx,vals,vals2)

        # Instead, just note what we need to do & take care of it later
        if n2>n3:
            self.quads12_only=True
        else:
            self.quads34_only=True


# Function to determine if we need the old flip-a-roo-ski
# I.e. does sky track cross the 180-deg boundary?
def flip_a_roo_new(self):

    az=self.track_az
    el=self.track_el

    # Compute quadrant each point is in
    quad1 = np.logical_and(az>0  , az<=90)
    quad2 = np.logical_and(az>90  , az<=180)
    quad3 = np.logical_and(az>180 , az<=270)
    quad4 = np.logical_and(az>270 , az<=360)

    n1 = np.sum(quad1)
    n2 = np.sum(quad2)
    n3 = np.sum(quad3)
    n4 = np.sum(quad4)
    print('Quad counts:',n1,n2,n3,n4)
    
    # First, check if the track transists into both the 2nd and 3rd quadrants
    # or into 1st and 4th quadrants
    self.cross0   = any(quad1) and any(quad4)
    self.cross180 = any(quad2) and any(quad3)

    # Initially assume that there is nothing to worry about
    #self.flipper      = False
    self.quads12_only = False
    self.quads34_only = False

    # If we don't cross a boundary, there' nothing to worry about
    print('FLIP_A_ROO: Current flip state=',self.flipper)
    #if not self.cross0 and not self.cross180:
    #print('FLIP_A_ROO: Can keep current flip state')
        
    # If we cross the 180-deg boundary and we're not yet flipped, how far do we go?
    if self.cross180 and not self.flipper:
        
        min2=az[quad2].min()
        max3=az[quad3].max()
        max_el = el.max()
        print('FLIP_A_ROO: Cross180 and not flipped:',min2,max3,max_el)

        # We need to flip if we cross the boundary significantly OR its a very high overhead pass
        # The very high overhead pass is something we can probably refine later but it should
        # constitue a very small number of passes so we'll just do this for now.
        if (max3>180+THRESH and min2<180-THRESH):     # or max_el>75:
            self.flipper = True
            if self.flipper:
                print("\n######### They call him Flipper Flipper Flipper-a-roo-ski ######")

        # If we don't cross the boundary by much, fix up track so rotor is never
        # commanded to cross boundary
        if not self.flipper:
            if n2>n3:
                self.quads12_only=True
            else:
                self.quads34_only=True

    # If we cross the 0-deg boundary and we're flipped, how far do we go?
    elif self.cross0 and self.flipper:
        
        min4=az[quad4].min()
        max1=az[quad1].max()
        max_el = el.max()
        print('FLIP_A_ROO: Croos 0 and flipped:',min4,max1,max_el)

        # We need to flip if we cross the boundary significantly OR its a very high overhead pass
        # The very high overhead pass is something we can probably refine later but it should
        # constitue a very small number of passes so we'll just do this for now.
        if (max1>THRESH and min4<360-THRESH):     # or max_el>75:
            self.flipper = False
            if self.flipper:
                print("\n######### They call him UNFlipper UNFlipper UNFlipper-a-roo-ski ######")

        # If we don't cross the boundary by much, fix up track so rotor is never
        # commanded to cross boundary
        if self.flipper:
            if n1>n4:
                self.quads12_only=True
            else:
                self.quads34_only=True

    else:
        print('FLIP_A_ROO: Can keep current flip state')


# Function to compute new position for the rotor
def rotor_positioning(gui,az,el,Force):

    #print('ROTOR_POSITIONING:',el,gui.event_type)
    if el>=0:
        # Sat is above the horizon ...
        # Limit az if we cross the boundary but don't want to flip
        if not gui.flipper:
            if gui.quads12_only and az>178:
                az=178
            elif gui.quads34_only and az<182:
                az=182
        else:
            if gui.quads12_only and (az<1 or az<360):
                az=1
            elif gui.quads34_only and (az>0 or az>360):
                az=359
        
        # ... and point to the calculated sat position
        new_pos=[az,el]

    else:
        # Sat is below the horizon so point to starting or ending point on track
        if gui.event_type==1:
            # Future event --> point to start
            new_pos=[gui.track_az[0] , 0]
        elif gui.event_type==-1:
            # Past event --> point to end
            new_pos=[gui.track_az[-1] , 0]
        else:
            # Indeterminant --> point to start
            #return False,[np.nan,np.nan],np.nan,np.nan,[np.nan,np.nan]
            new_pos=[gui.track_az[0] , 0]

    # Flip antenna if needed to avoid ambiquity at 180-deg
    if gui.flipper:
        #print('*** Need a Flip-a-roo-ski ***')
        if new_pos[0]<180:
            new_pos = [new_pos[0]+180. , 180.-new_pos[1]]
        else:
            new_pos = [new_pos[0]-180. , 180.-new_pos[1]]

    # Update rotor 
    rotor_updated=False
    if gui.P.sock2.active:
            
        # Current rotor position
        pos=gui.P.sock2.get_position()
        
        # Compute pointing error & adjust rotor if the error is large enough
        daz=pos[0]-new_pos[0]
        de =pos[1]-new_pos[1]
        #print('pos=',pos,'\taz/el=',az,el,'\tdaz/del=',daz,de, \
            #      '\n\tnew_pos=',new_pos)
        if abs(daz)>ROTOR_THRESH or abs(de)>ROTOR_THRESH:
            if gui.rig_engaged or gui.rotor_engaged or Force:
                gui.P.sock2.set_position(new_pos)
                rotor_updated=True
                
    else:
        pos=[np.nan,np.nan]
        daz=np.nan
        de=np.nan

    return rotor_updated,pos,daz,de,new_pos

        


class PLOTTING(QMainWindow):
    def __init__(self,P,parent=None):
        super(PLOTTING, self).__init__(parent)

        # Init
        self.P=P
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('pySat Plotting')
        self.grid = QGridLayout(self.win)

        #self.fig, self.ax = plt.subplots()

        self.fig  = Figure()
        self.canv = FigureCanvas(self.fig)
        self.grid.addWidget(self.canv,0,0)
        self.ax=None
        self.ax2=None
        
        #self.p1, = self.ax.plot([],[],'k')
        
        #self.hide()
        self.show()
        #self.ax.grid(True)    
        #plt.show()
        self.canv.draw()


    def plot_az_el(self,t,sat_az,sat_el,paz,pel):
        gui=self.P.gui
        
        print('\n$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ PLOT_AZ_EL $$$$$$$$$$$$$$$$$$$$$$$')
        print('\nCross180=',gui.cross180,gui.flipper,gui.event_type)
        print('Min,Max paz:',min(paz),max(paz))
        
        """
        print(t)
        print(az)
        print(el)
        print('paz=',paz)
        print('pel=',pel)
        """        

        # Convert rotor position to actual pointing position in the sky
        sky_az=0*np.array(paz)
        sky_el=0*np.array(pel)
        for i in range(len(paz)):
            az90,el90 = gui.resolve_pointing(paz[i],pel[i])
            sky_az[i]=90-az90
            sky_el[i]=90-el90
            
        #print('sky_az=',sky_az)
        
        if self.ax:
            self.ax.remove()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot(t, sat_az, color='red',label='Sat Az')
        self.ax.plot(t,paz, color='orange',label='Rotor Az')
        self.ax.plot(t,sky_az, 'o',color='yellow',label='Sky Az')
        self.ax.plot(t, len(t)*[180], color='magenta',linestyle='dashed',label='Boundary')
        self.ax.grid(True)    

        if self.ax2:
            self.ax2.remove()
        self.ax2 = self.ax.twinx()
        self.ax2.plot(t, sat_el, color='blue',label='Sat El')
        self.ax2.plot(t,pel, color='cyan',label='Rotor El')
        self.ax2.plot(t,sky_el, 'o',color='green',label='Sky El')

        self.ax.set_xlabel('Time (?)')
        self.ax.set_ylabel('Az (deg)')
        self.ax2.set_ylabel('El (deg)')
        self.fig.suptitle('Rotor Data')
        self.ax.legend(loc='lower left')
        self.ax2.legend(loc='lower right')
        
        self.canv.draw()


# Routine to simulate rotor commands over the course of a track to help
# developing better alg
def simulate_rotor(self):

    prev_az=np.nan
    paz=[]
    pel=[]
    for az,el in zip(self.track_az,self.track_el):
        rotor_updated,pos,daz,de,new_pos = \
            rotor_positioning(self,az,el,False)
        paz.append(new_pos[0])
        pel.append(new_pos[1])
        
        if np.isnan(prev_az):
            prev_az=new_pos[0]
        if False and abs(new_pos[0]-180)<10 and \
           ( (new_pos[0]>180 and prev_az<180) or \
             (new_pos[0]<180 and prev_az>180) ):
            #paz.append(-180)
            #pel.append(new_pos[1])
            paz[-1]=-180
        prev_az=new_pos[0]

    """
    print('Track t  =',self.track_t)
    print('Track Az =',self.track_az)
    print('Track El =',self.track_el)
    print('Rotor Az =',paz)
    print('Rotor El =',pel)
    """
        
    self.PlotWin.plot_az_el(self.track_t,self.track_az,self.track_el, \
                            paz,pel)

    if self.flipper:
        txt='Flipper'
    else:
        txt='Not flipped'
    print(txt)
    self.PlotWin.ax.set_title(txt)
    self.PlotWin.canv.draw()
    
        
