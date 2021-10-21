#! /usr/bin/python3 -u

from fileio import read_csv_file
from datetime import datetime
import time
import numpy as np
import matplotlib.pyplot as plt
 

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


 
fname='satellites.log_jo97_ao91'

data=read_csv_file(fname)

keys=data[0].keys()
print('\nkeys=',keys)
print('\ndata=',data[0])

times = get_values(data,'Time Stamp','seconds')
#print('Times=',time_stamps[0])
print('times=',times[0:3])

sat_name = get_values(data,'Selected',str)
#print(sat_name)

frqA = get_values(data,'frqA',float)*1e-6
frqB = get_values(data,'frqB',float)*1e-6
fdown = get_values(data,'fdown',float)*1e-6
#print(frqA)

engaged=get_values(data,'rig_engaged',bool)
print(engaged)

#mask=np.array( sat_name=='JO-97' )
#print('mask=',mask)
#print(times[mask])

idx=np.where( sat_name=='JO-97', )[0]
#print(idx)
#print(np.take(times,idx))

#B = ind[sat_name[ind]=='JO-97']
#B = [sat_name[ind]=='JO-97']
#print(B)

fig, ax = plt.subplots()
ax2 = ax.twinx()

ax.plot(np.take(times,idx), np.take(frqA,idx),color='red')
ax.plot(np.take(times,idx), np.take(fdown,idx),color='orange')

ax2.plot(np.take(times,idx), np.take(frqB,idx),color='blue')
plt.show()
