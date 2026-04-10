#!/usr/bin/env -S uv run --script
###############################################################################

# Script to analyze sat log data

###############################################################################

from fileio import read_csv_file
from datetime import datetime
import time
import sys
import numpy as np
import matplotlib.pyplot as plt

###############################################################################

sat='RS-44'
sat='AO-73'
#sat='ALL'
fname='satellites.log'
fname='satellites.log2'
fname='satellites.log3'

###############################################################################

def get_values(x,key,typ):
    print('GET VALUES: Extracting',key,'...')
    
    if typ=='seconds':
        
        vals=[d[key] for d in data];
        times=[]
        t0=None
        for tt in vals:
            #print(tt)
            if '.' in tt:
                fmt="%Y-%m-%d %H:%M:%S.%f"
            else:
                fmt="%Y-%m-%d %H:%M:%S"
            t=time.mktime(datetime.strptime(tt,fmt).timetuple())
            if not t0:
                t0=t
            times.append(t-t0)
        return times

    elif typ==bool:
        vals=[d[key]=='True' for d in data];
    else:
        vals=[typ(d[key]) for d in data];

    return np.array( vals )



def plot_setup(Title,Title2,xlab,ylab,ylab2):
    fig, ax = plt.subplots()
    ax2 = ax.twinx()

    fig.suptitle(Title)
    ax.set_title(Title2)
    ax.set_xlabel(xlab)
    ax.set_ylabel(ylab)
    ax2.set_ylabel(ylab2)
    #ax.legend(loc='lower left')
    #ax2.legend(loc='lower right')

    ax.grid(True)    
    
    return fig,ax,ax2

###############################################################################

data,hdr=read_csv_file(fname)
print('\nhdr=',hdr)
print('\ndata=',data[0])

keys=data[0].keys()
print('\nkeys=',keys,'\n')

times = get_values(data,'Time Stamp','seconds')
#print('Times=',time_stamps[0])
#print('times=',times[0:3])
#print('Start date/time =',times[0])
#print('End date/time   =',times[-1])

sat_name = get_values(data,'Selected',str)
print('Sat name=',sat_name)
Sat_Names=list(set(sat_name))
print('Sat names=',Sat_Names)

# Freq data
try:
    fdn1 = get_values(data,'dn1',float)*1e-6
    fdn2 = get_values(data,'dn2',float)*1e-6
    fup1 = get_values(data,'up1',float)*1e-6
    fup2 = get_values(data,'up2',float)*1e-6

    fdop1 = get_values(data,'fdop1',float)
    fdop2 = get_values(data,'fdop2',float)

    df    = get_values(data,'df',float)
    rit    = get_values(data,'RIT',float)
    xit    = get_values(data,'XIT',float)
except:
    pass

fup   = get_values(data,'fup',float)*1e-6
fdown = get_values(data,'fdown',float)*1e-6
#print('fup  =',fup[:10])
#print('fdown=',fdown[:10])

frqA = get_values(data,'frqA',float)*1e-6
frqB = get_values(data,'frqB',float)*1e-6
fdown = get_values(data,'fdown',float)*1e-6
#print(frqA)

# Rotor data
az = get_values(data,'az',float)
el = get_values(data,'el',float)
paz = get_values(data,'pos[0]',float)
pel = get_values(data,'pos[1]',float)
flipper=get_values(data,'flipper',bool)
#print('az  =',az[:10])
#print('paz  =',paz[:10])
#print('Flipper=',flipper)

engaged=get_values(data,'rig_engaged',bool)
#print('Engaged=',engaged)

if sat=='ALL':
    idx=range(len(el))
else:
    idx=np.where( np.logical_and(sat_name==sat,el>=0), )[0]
idx=idx[1:]
print(len(idx))

date1=data[idx[0]]['Time Stamp']
date2=data[idx[-1]]['Time Stamp']
print('Start Date/Time=',date1)
print('End   Date/Time=',date2)
#sys.exit(0)

###############################################################################

times2=np.take(times,idx)

# Tranpsonder up & down link freqs - these should be constant
# fdn1 and fdn2 are downlink passband edges and fup1 and fup2 are uplink edges
fig,ax,ax2 = plot_setup('Transponder Freqs for '+sat+' Pass','',
                        'Time','Down Link','Up Link')
fdn11=np.take(fdn1,idx)
fdn22=np.take(fdn2,idx)
fup11=np.take(fup1,idx)
fup22=np.take(fup2,idx)
ax.plot(times2, fdn11,color='red'   ,label='fdn1')
ax.plot(times2, fdn22,color='orange',label='fdn2')
ax2.plot(times2,fup11,color='blue'  ,linestyle=':',label='fup1')
ax2.plot(times2,fup22,color='cyan'  ,linestyle=':',label='fup2')
ax.legend(loc='center left')
ax2.legend(loc='center right')

ylim1=ax.get_ylim()
ylim2=ax2.get_ylim()
print('ylim=',ylim1,ylim2)
    
# Doppler shifts
fig,ax,ax2 = plot_setup('Doppler Shifts for '+sat+' Pass','',
                        'Time','Down Link','Up Link')
fdop11=np.take(fdop1,idx)
fdop22=np.take(fdop2,idx)
ax.plot(times2,  fdop11,color='red',   label='fdop1')
ax2.plot(times2, fdop22,color='orange',label='fdop2')
ax.legend(loc='upper left')
ax2.legend(loc='upper right')

# DF & R/XITs
# df = Shift from lower edge of transponder downlink window to where we are tuned to
# By default, we start out at the mid-point (center) of the passband
fig,ax,ax2 = plot_setup('DF for '+sat_name[idx[0]]+' Pass','',
                        'Time','Freq','')
df11=np.take(df,idx)
ax.plot(times2, df11,color='red',label='df')
ax.plot(times2, np.take(rit,idx),color='blue',label='RIT')
ax.plot(times2, np.take(xit,idx),color='orange',label='XIT')
ax.legend(loc='lower left')

# Freqs at transp - these two should mirror each other more or less
# fdwon = freq at sat = frq - rit - doppler
# fup   = corrsponding freq for uplink
fig,ax,ax2 = plot_setup('Freqs @ Transponder for '+sat+' Pass','',
                        'Time','Down Link','Up Link')
ax.plot(times2, np.take(fdown,idx),color='red',label='fdown')
ax2.plot(times2, np.take(fup,idx),color='orange',label='fup')

ax.plot(times2, np.take(fdn1,idx),color='red',linestyle='-.',label='fdn1')
ax.plot(times2, np.take(fdn2,idx),color='red',linestyle=':',label='fdn2')
ax2.plot(times2, np.take(fup1,idx),color='blue',linestyle='-.',label='fup1')
ax2.plot(times2, np.take(fup2,idx),color='blue',linestyle=':',label='fup2')

ax.legend(loc='upper left')
ax2.legend(loc='upper right')

ax.set_ylim(ylim1)
ax2.set_ylim(ylim2)

# VFO Freqs - Freqs at radio
fig,ax,ax2 = plot_setup('VFO Freqs for '+sat+' Pass','',
                        'Time','Down Link','Up Link')
ax.plot(times2, np.take(frqA,idx),color='red',label='VFO A')
ax2.plot(times2, np.take(frqB,idx),color='blue',label='VFO B')

ax.legend(loc='upper left')
ax2.legend(loc='upper right')

ax.set_ylim(ylim1)
ax2.set_ylim(ylim2)

# Rotor positioning
fig,ax,ax2 = plot_setup('Rotor Positioning for '+sat+' Pass',
                        'Starting at '+date1,
                        'Time','Az (deg)','El (deg)')
az2=np.take(az,idx)
paz2=np.take(paz,idx)
el2=np.take(el,idx)
pel2=np.take(pel,idx)

ax.plot(times2 , az2 ,color='red',label='Sat Az')
ax.plot(times2 , paz2,color='orange',label='Rotor Az')
ax2.plot(times2, el2 ,color='blue',label='Sat El')
ax2.plot(times2, pel2,color='cyan',label='Rotor El')
    
ax.legend(loc='lower left')
ax2.legend(loc='lower right')

with open('rotor.dat', 'wb') as fp:
    np.save(fp, times2)
    np.save(fp, az2)
    np.save(fp, paz2)
    np.save(fp, el2)
    np.save(fp, pel2)

print('az2  =',az2[:10])
print('paz2  =',paz2[:10])

# Simulator
MHz=1e-6
fmid=(fdn11[0]+fdn22[0]) / 2
df9 = fmid - fdn11[0]
print('Down passband=',fdn11[0],fdn22[0],'\tMid-point=',fmid,'\tdf=',df9,df11[0])
vfoA=fmid+fdop11*MHz

fmid2=fup22[0]-df9
print('Up passband=',fup11[0],fup22[0],'\tMid-point=',fmid2)
vfoB=fmid2+fdop22*MHz

fig,ax,ax2 = plot_setup('Expected VFO Freqs','',
                        'Time','Down Link','Up Link')
ax.plot(times2, vfoA,color='red',label='VFO A')
ax2.plot(times2, vfoB,color='blue',label='VFO B')
ax.legend(loc='upper left')
ax2.legend(loc='upper right')

#ax.set_ylim(ylim1)
#ax2.set_ylim(ylim2)

plt.show()
