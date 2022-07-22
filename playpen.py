#! /usr/bin/python3 -u
################################################################################

import predict
from latlon2maiden import *
import time
from datetime import timedelta,datetime, timezone
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.offsetbox import AnchoredText
import matplotlib.patches as mpatches
#from cartopy.mpl.ticker import (LongitudeFormatter, LatitudeFormatter,
#                                LatitudeLocator, LongitudeLocator)

from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker

from shapely.geometry.polygon import Polygon

################################################################################

grid='DM12ox'
lat,lon=maidenhead2latlon(grid)
my_qth = (lat,-lon,.3048*2000)
print('Based on grid square: \tMy QTH:',grid,'\t',my_qth)
#sys.exit(0)

tle="""ISS (ZARYA)
1 25544U 98067A   22202.89296957  .00009899  00000-0  18066-3 0  9992
2 25544  51.6421 164.6862 0005724  27.8461  82.9663 15.50079132350566"""
tle9 = """0 LEMUR 1
1 40044U 14033AL  15013.74135905  .00002013  00000-0  31503-3 0  6119
2 40044 097.9584 269.2923 0059425 258.2447 101.2095 14.72707190 30443"""

print(tle)
tle0=tle.split('\n')
print(tle0)
tle2=tle0[2].split()
print(tle2)
inclination=float(tle2[2])
print('inclination=',inclination)
revs=float(tle2[7])
rev_mins=24.*60./revs
print('rev per day=',revs,'\t',rev_mins)

#sys.exit(0)

def ComputeSatTrack(tstart,npasses):
    lons=[]
    lats=[]
    footprints=[]
    for m in range(0,int(npasses*rev_mins+2),1):
        dt = timedelta(minutes=m)
        t = time.mktime( (tstart+dt).timetuple() )
        obs = predict.observe(tle,my_qth,t)
        if m==0:
            print(obs)
        lon=obs['longitude']
        lat=obs['latitude']
        footprint=obs['footprint']
        print(obs['orbit'],'\t',tstart+dt,'\t',lon,'\t',lat,
              '\t',footprint)
        lons.append(lon)
        lats.append(lat)
        footprints.append(footprint)

    return lons,lats,footprints

def transform_and_plot(ax,proj,lons,lats,style):
    if np.isscalar(lons):
        lons = np.array( [lons] )
    if np.isscalar(lats):
        lats = np.array( [lats] )
    xx=[]
    yy=[]
    x_prev=np.nan
    for lon,lat in zip(lons,lats):
        x,y = proj.transform_point(lon,lat, ccrs.Geodetic())
        dx=x-x_prev
        #print(dx)
        if np.abs(dx)>120:
            xx.append(np.nan)
            yy.append(np.nan)
        xx.append(x)
        yy.append(y)
        x_prev=x
    ax.plot(xx,yy,style, transform=proj)
    #print('xx=',xx)


def DrawSatTrack(my_qth,lons,lats,footprint):

    # Create figure centered on USA
    fig = plt.figure()
    lon0=-75
    proj=ccrs.PlateCarree(central_longitude=lon0) 
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.stock_img()

    # Playing with axes
    if 0:
        gl = ax.gridlines(crs=proj, draw_labels=True,
                          linewidth=2, color='gray', alpha=0.5, linestyle='--')
        gl.xlabels_top = False
        #gl.ylabels_left = False
        gl.ylabels_right = False
        #gl.xlines = False
        #gl.xlocator = mticker.FixedLocator([-179,-120,-60, 0, 60, 120, 180])
        gl.xformatter = LONGITUDE_FORMATTER
        gl.yformatter = LATITUDE_FORMATTER
        gl.xlabel_style = {'size': 15, 'color': 'gray'}
        gl.xlabel_style = {'size': 15, 'color': 'gray'}
    elif 0:
        ax.set_xticks([-180,-120, -60, 0, 60, 120, 180], crs=proj)
        ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=proj)
        lon_formatter = LONGITUDE_FORMATTER #(zero_direction_label=True)
        lat_formatter = LATITUDE_FORMATTER  #()
        ax.xaxis.set_major_formatter(lon_formatter)
        ax.yaxis.set_major_formatter(lat_formatter)
        gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False,
                          linewidth=2, color='gray', alpha=0.5, linestyle='--')
    else:
        ax.set_aspect('auto')
        fig.tight_layout(pad=0)

    # Create a feature for States/Admin 1 regions at 1:50m from Natural Earth
    states_provinces = cfeature.NaturalEarthFeature(
        category='cultural',
        name='admin_1_states_provinces_lines',
        scale='50m',
        facecolor='none')

    # Add boundaries
    ax.add_feature(cfeature.LAND)
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS)
    ax.add_feature(states_provinces, edgecolor='gray')

    # Plot sat track
    transform_and_plot(ax,proj,-my_qth[1],my_qth[0],'mo')
    transform_and_plot(ax,proj,lons,lats,'b-')
    transform_and_plot(ax,proj,lons[0],lats[0],'g*')
    transform_and_plot(ax,proj,lons[-1],lats[-1],'r*')
    print(lons[0],lats[0])
    print(ax.get_extent())
    print(ax.axis())

    # Add circle
    #Latitude: 1 deg = 110.54 km
    #Longitude: 1 deg = 111.320*cos(latitude) km
    DEG2RAD=np.pi/180.
    dy=0.5*footprint/110.54
    dx=0.5*footprint/(111.32*np.cos(lats[0]*DEG2RAD))
    print(footprint,dy,dx)

    if 0:
        r=0.5*(dy+dx)
        print('footprint=',footprint,dxlat,dxlon,r)
        ax.add_patch(mpatches.Circle(xy=[lons[0], lats[0]], radius=r,
                                     color='red', \
                                     alpha=0.3, transform=ccrs.Geodetic(),
                                     zorder=30))
    else:
        xx=[]
        yy=[]
        pgon=[]
        for alpha in range(0,360,5):
            lat=lats[0]+dy*np.sin(alpha*DEG2RAD) 
            dx=0.5*footprint/(111.32*np.cos(lat*DEG2RAD))
            lon=lons[0]+dx*np.cos(alpha*DEG2RAD)
            
            x,y = proj.transform_point(lon,lat, ccrs.Geodetic())
            #x=lon
            #y=lat
            xx.append(lon)
            yy.append(lat)
            pgon.append((x,y))
        transform_and_plot(ax,proj,xx,yy,'g-')
        pgon=Polygon( tuple(pgon) )
        #print(pgon)
        #print(yy)
        #ax.add_geometries([pgon], crs=ccrs.Geodetic(), facecolor='red',
        ax.add_geometries([pgon], crs=proj, facecolor='r',
                          edgecolor='red', alpha=0.3)

    plt.show()
    

if __name__ == '__main__':
    now = datetime.now()
    print('now=',now)
    lons,lats,footprints,=ComputeSatTrack(now,1)
    DrawSatTrack(my_qth,lons,lats,footprints[0])

