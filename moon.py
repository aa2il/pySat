#! /usr/bin/python3 -u

# Script to play with moon tracking.  I don't think we need this anymore but
# will keep it around for posterity.

# Try this library - it was already installed
#    https://rhodesmill.org/pyephem/index.html
#    pip3 install pyephem

# They suggest using  The Skyfield astronomy library  instead but this
# seems to work just fine for our purposes.  For future reference:
#    https://rhodesmill.org/skyfield/

##############################################################################

import sys
from math import pi
import ephem
from datetime import datetime, timedelta, timezone,date

RAD2DEG=180./pi
MINS2DAYS=1./(24.*60.)

#import datetime
from typing import List, Tuple

##############################################################################


# Function to compute moon lunation and phase
def get_moon_phase(date):
  Date = ephem.Date(date)
  nnm = ephem.next_new_moon(Date)
  pnm = ephem.previous_new_moon(Date)

  # 0=new, 0.5=full, 1=new
  lunation = (Date-pnm)/(nnm-pnm)

  if lunation<0.1:
    phz='New Moon'
  elif lunation<0.25:
    phz='Waxing Crescent'
  elif lunation<0.5:
    phz='Waxing Half'
  elif lunation<0.75:
    phz='Waning Half'
  elif lunation<0.9:
    phz='Waning Crescent'
  else:
    phz='New Moon'
  
  return lunation,phz

def get_phase_on_day(year: int, month: int, day: int):
  """Returns a floating-point number from 0-1. where 0=new, 0.5=full, 1=new"""
  #Ephem stores its date numbers as floating points, which the following uses
  #to conveniently extract the percent time between one new moon and the next
  #This corresponds (somewhat roughly) to the phase of the moon.

  #Use Year, Month, Day as arguments
  Date = ephem.Date(date(year,month,day))

  nnm = ephem.next_new_moon(Date)
  pnm = ephem.previous_new_moon(Date)

  lunation = (Date-pnm)/(nnm-pnm)

  #Note that there is a ephem.Moon().phase() command, but this returns the
  #percentage of the moon which is illuminated. This is not really what we want.

  return lunation

def get_moons_in_year(year: int) -> List[Tuple[ephem.Date, str]]:
  """Returns a list of the full and new moons in a year. The list contains tuples
of either the form (DATE,'full') or the form (DATE,'new')"""
  moons=[]

  Date=ephem.Date(date(year,1,1))
  while Date.datetime().year==year:
    Date=ephem.next_full_moon(Date)
    moons.append( (Date,'full') )

  while Date.datetime().year==year:
    Date=ephem.next_new_moon(date)
    moons.append( (Date,'new') )

  #Note that previous_first_quarter_moon() and previous_last_quarter_moon()
  #are also methods

  moons.sort(key=lambda x: x[0])

  return moons

print('\nFirst test 1/1/2013:')
print(get_phase_on_day(2013,1,1))

print(get_moons_in_year(2013))

print('\nSecond test - today')
now = datetime.utcnow()
print('now=',now)
print(get_phase_on_day(now.year,now.month,now.day))
print(get_moon_phase(now))

print(get_moons_in_year(now.year))

moon = ephem.Moon()
qth = ephem.Observer()
qth.lat = '32.982545833'
qth.lon = '-116.797740833'
qth.elevation = 602.2
now = datetime.utcnow()
qth.date=now              # Does this by default
moon.compute(qth)
print('\nCurrent Moon: az=',moon.az,'\tel=',moon.alt)
phz=moon.phase
print('nphz=',phz)

sys.exit(0)

##############################################################################

#if __name__ == "__main__":

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

# Here's how to progress over several moon rises
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

# Generate a track
dt=30.*MINS2DAYS                # Every half hour, expressed as days
qth.date=now
moon.compute(qth)
t=qth.next_rising(moon)
qth.date=t
moon.compute(qth)
setting=qth.next_setting(moon)
print('\n',t,setting)
qth.pressure = 0          # Turns off horizon refraction calcs
Done=False
while not Done:
    if t>=setting:
        Done=True
        t=setting
    qth.date=t
    moon.compute(qth)    
    print('Track: t=',qth.date,'\taz=',moon.az,moon.az*RAD2DEG,'\tel=',moon.alt,moon.alt*RAD2DEG)
    t+=dt
        
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

