#! /usr/bin/python3 -u

from fileio import read_csv_file
from datetime import datetime
import time
import numpy as np
import matplotlib.pyplot as plt

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

#sat='JO-97'
#fname='satellites.log_jo97_ao91'

sat='RS-44'
fname='satellites.log_rs44'
fname='satellites.log_rs44_2'
fname='satellites.log_rs44_3'

sat='CAS-4A'
fname='satellites.log_cas4a'

#sat='CAS-4B'
#fname='satellites.log_cas4b'

#sat='CAS-6'
#fname='satellites.log_cas6'

#sat='PO-101'
#fname='satellites.log_po101'

###############################################################################

data=read_csv_file(fname)

keys=data[0].keys()
print('\nkeys=',keys)
#print('\ndata=',data[0])

times = get_values(data,'Time Stamp','seconds')
#print('Times=',time_stamps[0])
#print('times=',times[0:3])

sat_name = get_values(data,'Selected',str)
#print(sat_name)

# Freq data
fdn1 = get_values(data,'dn1',float)*1e-6
fdn2 = get_values(data,'dn2',float)*1e-6
fup1 = get_values(data,'up1',float)*1e-6
fup2 = get_values(data,'up2',float)*1e-6

fdop1 = get_values(data,'fdop1',float)
fdop2 = get_values(data,'fdop2',float)

df    = get_values(data,'df',float)
rit    = get_values(data,'RIT',float)
xit    = get_values(data,'XIT',float)

fup   = get_values(data,'fup',float)*1e-6
fdown = get_values(data,'fdown',float)*1e-6
print('fup  =',fup[:10])
print('fdown=',fdown[:10])

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

###############################################################################

fig, ax = plt.subplots()
ax2 = ax.twinx()

if False:
    # Tranpsonder up & down link freqs
    ax.plot(np.take(times,idx), np.take(fdn1,idx),color='red')
    ax.plot(np.take(times,idx), np.take(fdn2,idx),color='orange')
    ax2.plot(np.take(times,idx), np.take(fup1,idx),color='blue')
    ax2.plot(np.take(times,idx), np.take(fup2,idx),color='cyan')

elif True:
    # Doppler shifts
    ax.plot(np.take(times,idx), np.take(fdop1,idx),color='red')
    ax2.plot(np.take(times,idx), np.take(fdop2,idx),color='orange')

elif False:
    # DF
    ax.plot(np.take(times,idx), np.take(df,idx),color='red')
    ax.plot(np.take(times,idx), np.take(rit,idx),color='blue')
    ax.plot(np.take(times,idx), np.take(xit,idx),color='orange')

elif True:
    # Freqs at transp
    ax.plot(np.take(times,idx), np.take(fdown,idx),color='red')
    ax2.plot(np.take(times,idx), np.take(fup,idx),color='orange')

elif True:
    # VFO Freqs
    ax.plot(np.take(times,idx), np.take(frqA,idx),color='red')
    #ax.plot(np.take(times,idx), np.take(fdown,idx),color='orange')
    ax2.plot(np.take(times,idx), np.take(frqB,idx),color='blue')
    #ax2.plot(np.take(times,idx), np.take(fup,idx),color='cyan')

else:
    ax.plot(np.take(times,idx), np.take(az,idx),color='red')
    ax.plot(np.take(times,idx), np.take(paz,idx),color='orange')
    ax2.plot(np.take(times,idx), np.take(el,idx),color='blue')
    ax2.plot(np.take(times,idx), np.take(pel,idx),color='cyan')

plt.show()
