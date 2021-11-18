# Routines related to rotor positioning

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
def flip_a_roo(self):    

    az=self.track_az
    el=self.track_el
    
    # First, see if the track transists into both the 2nd and 3rd quadrants
    quad2 = np.logical_and(az>90  , az<=180)
    quad3 = np.logical_and(az>180 , az<=270)
    self.cross180 = any(quad2) and any(quad3)

    # Initially assume that there othing to worry about
    self.flipper = False
    
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
    # commanded to croos boundary
    if self.cross180 and not self.flipper and True:

        # Probably need to address what happens in 1st & 5th quads as well, particularly for
        # the very high overhead passes
        quad1 = np.logical_and(az>0  , az<=90)
        quad4 = np.logical_and(az>270 , az<=360)
        n1 = np.sum(quad1)
        n2 = np.sum(quad2)
        n3 = np.sum(quad3)
        n4 = np.sum(quad4)
        print('Quad counts:',n1,n2,n3,n4)

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



# Function to compute new position for the rotor
def rotor_positioning_old(gui,az,el,Force):

    #print('ROTOR_POSITIONING_OLD:',el,gui.event_type)
    if el>=0:
        # Sat is above the horizon so point to calculated sat position
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
        print('*** Need a Flip-a-roo-ski ***')
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

        


# Function to compute new position for the rotor
def rotor_positioning_new(self,az1,el1):

    first_time = self.first_time
    az_prev    = self.az_prev
    el_prev    = self.el_prev
    rotor_az   = self.rotor_az
    rotor_el   = self.rotor_el

    # Test various possibilities
    if first_time:
        #print('First time - az1=',az1,first_time)
        # Start of track - check if we'll be crossing the 180-deg boundary
        # w/o the flipper
        if cross180 and not flipper:
            # Yep - if we're starting close to the boundary, limit the motion of the
            # rotor to the other side of the boundary
            if az1>180 and az1<180+THRESH:
                # Starting in Third Quadrant but close to line - keep rotor in Second Quardant
                new_az=179.
            elif az1<180 and az1>180-THRESH:
                # Starting in Second Quadrant but close to line - keep rotor in Third Quardant
                new_az=181.
            else:
                new_az=az1
            new_el=el1

        else:
            # Not crossing boundary w/o the flipper - nothing special to worry about
            new_az=az1
            new_el=el1

        # Set rotor position - make adjustments if flipped
        if flipper:
            rotor_az = (new_az+180) % 360
            rotor_el = 180-new_el
        else:
            rotor_az = new_az
            rotor_el = new_el

    else:

        # Compute difference between where sat is and rotor is pointed
        if rotor_el>90:
            daz=np.abs( az1-((rotor_az+180) % 360) )
            de =np.abs( el1-(180-rotor_el) )
        else:
            daz=np.abs( az1-rotor_az )
            de =np.abs( el1-rotor_el )

            
        if daz>THRESH or de>THRESH:
            # We're  in the middle of a track and need to make an adjustment

            # Check if track crosses boundary but we're not flipped
            if cross180 and not flipper:
                # Yep - limit motion of rotor when boundary is crossed
                #if el1>90-THRESH:
                   # High overhead pass
                if az1<az_prev and az1>180 and az1<180+THRESH:
                    # Moving from Second Quadrant to Third - keep rotor in Second Quardant
                    new_az=179.
                elif az1>az_prev and az1<180 and az1>180-THRESH:
                    # Moving from Third Quadrant to Second - keep rotor in Third Quardant
                    new_az=181.
                else:
                    # Nothing to see here, just a normal update
                    new_az=az1
            else:
                # Nothing to see here, just a normal update 
                new_az=az1
            new_el=el1

            # Set rotor position - make adjustments if flipped
            if flipper:
                rotor_az = (new_az+180) % 360
                rotor_el = 180-new_el
            else:
                rotor_az = new_az
                rotor_el = new_el
            
        else:
            # Point error is small - nothing special to do right now
            new_az = az_prev
            new_el = el_prev

    # For diagnostic purposes, indicate when we've crossed the 180-deg boundary
    crossed = not first_time and not flipper and \
        ((new_az>180. and az_prev<=180.) or \
         (new_az<=180. and az_prev>180.))
    first_time=False

    az_prev=new_az
    el_prev=new_el

    #print(az1,new_az,daz)
    #print(az0,el0,new_az,new_el,crossed)
    return new_az,new_el,crossed
        




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


    def plot_az_el(self,t,az,el,paz,pel):
        gui=self.P.gui
        
        print('\n$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ PLOT_AZ_EL $$$$$$$$$$$$$$$$$$$$$$$')
        print('\nCross180=',gui.cross180,gui.flipper,gui.event_type)
        print('Min,Max paz:',min(paz),max(paz))
        
        """
        print(t)
        print(az)
        print(el)
        print(paz)
        print(pel)
        """
        
        if self.ax:
            self.ax.remove()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot(t, az, color='red',label='Sat Az')
        self.ax.plot(t,paz, color='orange',label='Rotor Az')
        self.ax.grid(True)    

        if self.ax2:
            self.ax2.remove()
        self.ax2 = self.ax.twinx()
        self.ax2.plot(t, el, color='blue',label='Sat El')
        self.ax2.plot(t,pel, color='cyan',label='Rotor El')

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
            rotor_positioning_old(self,az,el,False)
        paz.append(new_pos[0])
        pel.append(new_pos[1])
        
        if np.isnan(prev_az):
            prev_az=new_pos[0]
        if abs(new_pos[0]-180)<10 and \
           ( (new_pos[0]>180 and prev_az<180) or \
             (new_pos[0]<180 and prev_az>180) ):
            #paz.append(-180)
            #pel.append(new_pos[1])
            paz[-1]=-180
        prev_az=new_pos[0]
        
            
    self.PlotWin.plot_az_el(self.track_t,self.track_az,self.track_el, \
                            paz,pel)
        

        
