#! /usr/bin/python3 -u

# Routine to work on rotor positioning alg.

from fileio import read_csv_file
from datetime import datetime
import time
import numpy as np
import matplotlib.pyplot as plt
import sys

###############################################################################

THRESH=15

###############################################################################

# Function to determine if we need the old flip-a-roo-ski
# I.e. does sky track cross the 180-deg boundary?
def flip_a_roo(az,el):    

    quad2 = np.logical_and(az>90  , az<=180)
    quad3 = np.logical_and(az>180 , az<=270)
    cross180 = any(quad2) and any(quad3)

    min2=az[quad2].min()
    max3=az[quad3].max()
    max_el = el.max()

    if cross180 and (max3<180+THRESH or min2>180-THRESH):   # or max_el>90-THRESH):
        print("\n######### Probably don't need the old flip-a-roo-ski ##############")
        flipper = False
    else:
        flipper = cross180
        if flipper:
            print("\n######### They call him Flipper Flipper Flipper-a-roo-ski ######")

    print(min2,max3,cross180,flipper)
    #sys.exit(0)

    return cross180,flipper


# Function to take care of rotor flipping
#TBD


# Function to compute new position for the rotor
#az_prev=None
#el_prev=None
first_time=True
#rotor_az=None
#rotor_el=None
def rotor_positioning(az1,el1):
    global az_prev,el_prev,first_time
    global rotor_az,rotor_el

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

    # For diagnostic purposes, indicate when we've corssed the 180-deg boundary
    crossed = not first_time and not flipper and \
        ((new_az>180. and az_prev<=180.) or \
         (new_az<=180. and az_prev>180.))
    first_time=False

    az_prev=new_az
    el_prev=new_el

    #print(az1,new_az,daz)
    #print(az0,el0,new_az,new_el,crossed)
    return new_az,new_el,crossed
        

###############################################################################

with open('rotor.dat', 'rb') as fp:
    times2=np.load(fp)
    az=np.load(fp)
    paz=np.load(fp)
    el=np.load(fp)
    pel=np.load(fp)

# Does the sky track cross the 180-deg boundary?    
cross180,flipper = flip_a_roo(az,el)

# Simulate a pass and see what the alg would do
paz3=[]
pel3=[]
n=len(az)
for i in range(n):
    i2 = min(i+30,n-1)
    i2=i
    az1=az[i2]
    el1=el[i2]

    new_az,new_el,crossed=rotor_positioning(az1,el1)
    
    if not crossed:
        paz3.append(new_az)
    else:
        paz3[-1]=360
        paz3.append(0)
    pel3.append(new_el)

    #print(new_az,new_el)

fig, ax = plt.subplots()
ax2 = ax.twinx()

ax.plot(times2 , az ,color='red',label='Sat Az')
ax.plot(times2 , paz3,color='orange',label='Rotor Az')
ax2.plot(times2, el ,color='blue',label='Sat El')
ax2.plot(times2, pel3,color='cyan',label='Rotor El')

print('az  =',az[:10])
print('paz3  =',paz3[:10])
    
ax.set_xlabel('Time (?)')
ax.set_ylabel('Az (deg)')
ax2.set_ylabel('El (deg)')
#fig.suptitle('Rotor Data')
plt.title('Rotor Data')
ax.legend(loc='lower left')
ax2.legend(loc='lower right')

ax.grid(True)    
plt.show()
