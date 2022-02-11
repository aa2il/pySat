#! /usr/bin/python3 -u

from fileio import read_csv_file
from datetime import datetime
import time
import sys
import numpy as np
import matplotlib.pyplot as plt

###############################################################################

# Freq tracking problems - resolved
#sat='JO-97'
#fname='satellites.log_jo97_ao91'

#sat='RS-44'
#fname='satellites.log_rs44'
#fname='satellites.log_rs44_2'
#fname='satellites.log_rs44_3'

# Problem with flipper
#sat='AO-7'
#fname='satellites.log_ao7'                 # Screwy start - starts in 2nd quad close to boundary and moves to 3rd - new alg fixes

#sat='SO-50'
#fname='satellites.log_so50'                 # Screwy start - starts in 3rd quad close to boundary and moves to 2nd - new alg fixes

#sat='JO-97'                                # Screwy end 1st->2nd->3rd quads - new alg makes worse!!!!
#fname='satellites.log_jo97'
#fname='satellites.log_jo97_2'             # Bad start - new alg should fix

#sat='AO-91'                                # Screwy start - 2nd->3rd->4th  - new alg fixes
#fname='satellites.log_ao91'

sat='CAS-4A'
fname='satellites.log_cas4a'

#sat='CAS-4B'
#fname='satellites.log_cas4b'               # High overhead pass the really doesn't need the flipper - not sure what to do when this happens

#sat='CAS-6'
#fname='satellites.log_cas6'

#sat='PO-101'                               # igh overhead pass that lipper ent nuts
#fname='satellites.log_po101'

###############################################################################

def get_values(x,key,typ):
    if typ=='seconds':
        vals=[d[key] for d in data];
        times=[]
        t0=None
        for t in vals:
            t=time.mktime(datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f").timetuple())
            if not t0:
                t0=t
            times.append(t-t0)
        return times

    elif typ==bool:
        vals=[d[key]=='True' for d in data];
    else:
        vals=[typ(d[key]) for d in data];

    return np.array( vals )

###############################################################################

data,hdr=read_csv_file(fname)
#print('\ndata=',data[0])

keys=data[0].keys()
print('\nkeys=',keys,'\n')

times = get_values(data,'Time Stamp','seconds')
#print('Times=',time_stamps[0])
#print('times=',times[0:3])
#print('Start date/time =',times[0])
#print('End date/time   =',times[-1])

sat_name = get_values(data,'Selected',str)
print('Sat name=',sat_name)

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

#mask=np.array( sat_name=='JO-97' )
#print('mask=',mask)
#print(times[mask])

#print('sat_name=',sat_name)
#print('el=',el)

idx=np.where( np.logical_and(sat_name==sat,el>=0), )[0]
idx=idx[1:]
print(len(idx))
#delete( idx[0] )
#print('idx=',idx)
#print(np.take(times,idx))

#B = ind[sat_name[ind]=='JO-97']
#B = [sat_name[ind]=='JO-97']
#print(B)

date1=data[idx[0]]['Time Stamp']
date2=data[idx[-1]]['Time Stamp']
print('Start Date/Time=',date1)
print('End   Date/Time=',date2)
#sys.exit(0)

###############################################################################

fig, ax = plt.subplots()
ax2 = ax.twinx()
#fig, (ax1, ax2) = plt.subplots(1, 2, sharex=True, sharey=True)

times2=np.take(times,idx)

if False:
    # Tranpsonder up & down link freqs
    ax.plot(np.take(times,idx), np.take(fdn1,idx),color='red')
    ax.plot(np.take(times,idx), np.take(fdn2,idx),color='orange')
    ax2.plot(np.take(times,idx), np.take(fup1,idx),color='blue')
    ax2.plot(np.take(times,idx), np.take(fup2,idx),color='cyan')

elif False:
    # Doppler shifts
    ax.plot(np.take(times,idx), np.take(fdop1,idx),color='red')
    ax2.plot(np.take(times,idx), np.take(fdop2,idx),color='orange')

elif False:
    # DF
    ax.plot(np.take(times,idx), np.take(df,idx),color='red')
    ax.plot(np.take(times,idx), np.take(rit,idx),color='blue')
    ax.plot(np.take(times,idx), np.take(xit,idx),color='orange')

elif False:
    # Freqs at transp
    ax.plot(np.take(times,idx), np.take(fdown,idx),color='red')
    ax2.plot(np.take(times,idx), np.take(fup,idx),color='orange')

elif False:
    # VFO Freqs
    ax.plot(np.take(times,idx), np.take(frqA,idx),color='red')
    #ax.plot(np.take(times,idx), np.take(fdown,idx),color='orange')
    ax2.plot(np.take(times,idx), np.take(frqB,idx),color='blue')
    #ax2.plot(np.take(times,idx), np.take(fup,idx),color='cyan')

else:
    # Rotor positioning
    az2=np.take(az,idx)
    paz2=np.take(paz,idx)
    el2=np.take(el,idx)
    pel2=np.take(pel,idx)
    ax.plot(times2 , az2 ,color='red',label='Sat Az')
    ax.plot(times2 , paz2,color='orange',label='Rotor Az')
    ax2.plot(times2, el2 ,color='blue',label='Sat El')
    ax2.plot(times2, pel2,color='cyan',label='Rotor El')
    
    ax.set_xlabel('Time (?)')
    ax.set_ylabel('Az (deg)')
    ax2.set_ylabel('El (deg)')
    fig.suptitle('Rotor Data - For '+sat_name[idx[0]]+' Pass')
    ax.set_title('Starting at '+date1)
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
        
    
ax.grid(True)    
plt.show()
