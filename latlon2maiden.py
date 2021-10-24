#!/usr/bin/python3
#########################################################################################
#
# latlon2maiden.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Routines for converting between lat/lon coordinates and maidenhead grid
# squares.  These convserions can be done to arbitrary precision, not just
# 4- or 6-characters like most readily available codes.  This helps
# to improve the accuracy of our Doppler shift projections.
#
############################################################################################
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
#########################################################################################

import sys

#########################################################################################

# Function to compute maidnhead grid square to apecified precision
# from lat & lon
def latlon2maidenhead(lat,lon,nchar):
    
    A=ord('A')       # Ascii 65

    if lon<-180 or lon>180:
        print('Longitude must be between +/-180 deg - lon=',lon,'\n')
        sys.exit(-1)
        
    if lat<-90 or lat>90:
        print('Latitude must be between +/-90 deg - lat=',lat,'\n')
        sys.exit(-1)

    # The coarsest (2-char) grids 20-deg x 10-deg "fields"
    a=divmod(lon+180,20)
    b=divmod(lat+90,10)
    gridsq=chr(A+int(a[0]))+chr(A+int(b[0]))  # Use quotient to get 1st two chars
    
    lon=a[1]/2         # Use remainder to deal with what is left
    lat=b[1]
    i=1                # No. 2-char groups so far

    # Iterate until we get the desired precision
    while 2*i<nchar:
        i+=1
        a=divmod(lon,1)     # Rinse & repeat
        b=divmod(lat,1)

        # Check if numeric or alpha field is next
        if i%2:
            # Next two chars are alpha
            gridsq+=chr(A+int(a[0]))+chr(A+int(b[0]))
            lon=10*a[1]
            lat=10*b[1]
        else:
            # Next two chars are numeric
            gridsq+=str(int(a[0]))+str(int(b[0]))
            lon=24*a[1]
            lat=24*b[1]

    return gridsq


# Routine to convert maidenhead grid square back to lat,lon
def maidenhead2latlon(gridsq):

    # Error checking
    if len(gridsq)%2:
        print('ERROR - length of grid square must be event - gridsq=',gridsq)
        sys.exit(-1)
    
    A=ord('A');                  # Ascii 65
    lonch = gridsq[0::2]         # Pull out chars related to longitude
    latch = gridsq[1::2]         # Pull out chars related to latitude

    # Convert lat and lon locators into lat & lon in degrees
    step=10*24                   # At the coursest level, there are 24 10-deg lat squares
                                 # There are 24 20-deg lon square - see below
    lon=-180                     # Offset for lon and lat
    lat=-90
    for i in range(len(lonch)):
        if i%2:
            # The odd chars are numbers 0-9
            x=int( lonch[i] )
            y=int( latch[i] )
            step/=10
        else:
            # The even chars are letters A-X
            x=ord( lonch[i] )-A
            y=ord( latch[i] )-A
            step/=24
        
        lon+=x*step*2              # Lon squares in deg. are twice as big as lat
        lat+=y*step
        #print(x,lon_step,lon)

    return lat,lon


################################################################################

# Test program
# latlon2maiden.py -116.797740833 32.982545833 12
# gives DM12OX45GT54
#
# Other direction should give something very close to what we started with

if __name__ == "__main__":

    print('\n****************************************************************************')
    print('\n   lat/lon to maidenhead converter eginning ...\n')
   
    lon=float(sys.argv[1])
    lat=float(sys.argv[2])

    if len(sys.argv)==4:
        nchar=int(sys.argv[3])
        if nchar<2 or nchar%2!=0:
            sys.stderr.write('No. characters must be even integer > 0\n')
            sys.exit(-1)
    else:
        nchar=6

    print('Input lat=',lat,'\tlon=',lon,'\tnchar=',nchar)
    gridsq=latlon2maidenhead(lat,lon,nchar)
    print('grid sq=',gridsq)

    print('\nReversing:')
    lat,lon=maidenhead2latlon(gridsq)
    print('lat=',lat)
    print('lon=',lon)


