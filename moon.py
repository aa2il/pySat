#! /usr/bin/python3 -u

# Script to play with moon tracking

# Try this library - it was already installed
#    https://rhodesmill.org/pyephem/index.html
#    pip3 install pyephem

# They suggest using  The Skyfield astronomy library  instead but this
# seems to work just fine for our purposes.  For future reference:
#    https://rhodesmill.org/skyfield/

# Need to read the docs but this looks like it will work!

##############################################################################

import ephem
from datetime import datetime, timedelta #, tzinfo
#import pytz

#UTC = pytz.utc

# Example from website - seems ok
mars = ephem.Mars()
boston = ephem.Observer()
boston.lat = '42.37'
boston.lon = '-71.03'
boston.date = '2007/10/02 00:50:22'
mars.compute(boston)
print( mars.az, mars.alt)

print(boston.next_rising(mars))
print(mars.az)         # degrees when printed
print(mars.az + 0.0)   # radians in math
print(boston.next_transit(mars))
print(mars.alt)        # degrees when printed
print(mars.alt + 0.0)  # radians in math

# Ok, let's try for SDG & the moon & today
qth = ephem.Observer()
qth.lat = '32.982545833'
qth.lon = '-116.797740833'
qth.elevation = 602.2
# qth.pressure = 0          # Turns off horizon refraction calcs
#now = datetime.utcnow().replace(tzinfo=UTC)   # Not sure why I do this?
now = datetime.utcnow()
qth.date=now              # Does this by default
local=ephem.localtime(ephem.Date(now))
print('\nCurrent time now=',now,'\tlocal=',local)

moon = ephem.Moon()
moon.compute(qth)
print('Current Moon: az=',moon.az,'\tel=',moon.alt)
rise=qth.next_rising(moon)
local=ephem.localtime(rise)
print('Next moon rising:',rise,'\t',local)
print('az/el=',moon.az,moon.alt)           

trans=qth.next_transit(moon)
local=ephem.localtime(trans)
print('Next moon transit:',trans,'\t',local)
print('az/el=',moon.az,moon.alt)

setting=qth.next_setting(moon)
local=ephem.localtime(setting)
print('Next moon setting:',setting,'\t',local)
print('az/el=',moon.az,moon.alt)

# # Here's how to progress over several moon rises
for i in range(5):
    qth.date=rise
    moon.compute(qth)
    rise=qth.next_rising(moon)
    local=ephem.localtime(rise)
    print('\nFollowing moon rising:',rise,'\t',local)
    print('az/el=',moon.az,moon.alt)

    qth.date=rise+1./24.
    moon.compute(qth)
    local=ephem.localtime(qth.date)
    print('An hour later:',qth.date,'\t',local)
    print('az/el=',moon.az,moon.alt)           
    
    setting=qth.next_setting(moon)
    local=ephem.localtime(setting)
    print('Following moon setting:',setting,'\t',local)
    print('az/el=',moon.az,moon.alt)

# For completeness, take a quick look at Old Sol
sun = ephem.Sun()
qth.date=now
sun.compute(qth)
print('\nCurrent Sun: az=',sun.az,'\tel=',sun.alt)

setting=qth.next_setting(sun)
local=ephem.localtime(setting)
print('Next sun setting:',setting,'\t',local)
print('az/el=',sun.az,sun.alt)

# A closer look at date/time objects
# Straight-forward how to manipulate both datetime and .Date objects
print('\nqth.date         =',qth.date)
print('now + 1 day      =',now + timedelta(days=1))
print('qth.date + 1 day =',qth.date + 1, ephem.Date(qth.date + 1))
print('qth.date + 1 day =',qth.date.datetime() + timedelta(days=1))
