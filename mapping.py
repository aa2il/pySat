################################################################################
#
# mappiong.py - Rev 2.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# Class containing for plotting map
#
################################################################################
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
################################################################################

from widgets_qt import QTLIB
exec('from '+QTLIB+'.QtWidgets import QMainWindow,QWidget,QGridLayout')

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.offsetbox import AnchoredText
import matplotlib.patches as mpatches
from matplotlib.image import imread

from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker
from shapely.geometry.polygon import Polygon
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from constants import DEG2RAD
from utilities import error_trap
#from rig_io.ft_tables import CELESTIAL_BODY_LIST,METEOR_SHOWER_LIST

################################################################################

class MAPPING(QMainWindow):
    def __init__(self,P,parent=None):
        super(MAPPING, self).__init__(parent)

        # Init
        self.P=P
        self.win  = QWidget()
        self.setCentralWidget(self.win)
        self.setWindowTitle('Satellite Track')
        self.grid = QGridLayout(self.win)

        self.fig  = Figure()
        self.canv = FigureCanvas(self.fig)
        self.grid.addWidget(self.canv,0,0)
        self.ax=None

        # Create figure centered on USA
        lon0=-75
        self.proj=ccrs.PlateCarree(central_longitude=lon0) 
        self.ax = self.fig.add_subplot(1, 1, 1, projection=self.proj)
        if False:
            # This doesn't work under pyinstaller ...
            self.ax.stock_img()
        else:
            # ... so we load image directly instead
            fname='../data/50-natural-earth-1-downsampled.png'
            print('fname=',fname)
            img = imread(fname)
            self.ax.imshow(img, origin='upper', transform=ccrs.PlateCarree(),
                      extent=[-180, 180, -90, 90])

        self.ax.set_aspect('auto')
        self.fig.tight_layout(pad=0)
            
        # Create a feature for States/Admin 1 regions at 1:50m from Natural Earth
        states_provinces = cfeature.NaturalEarthFeature(
            category='cultural',
            name='admin_1_states_provinces_lines',
            scale='50m',
            facecolor='none')

        # Add boundaries
        self.ax.add_feature(cfeature.LAND)
        self.ax.add_feature(cfeature.COASTLINE)
        self.ax.add_feature(cfeature.BORDERS)
        self.ax.add_feature(states_provinces, edgecolor='gray')
        
        self.show()
        self.canv.draw()
        self.blobs=[]

        # Make sure window has some size to it (problem if headless on RPi)
        qr = self.win.frameGeometry()
        w=qr.width()
        h=qr.height()
        print('qr=',qr,w,h)
        if w<400 or h<400:
            self.win.resize( max(400,w) , max(h,400) )
        #sys.exit(0)

    def ComputeSatTrack(self,Sat,tstart=None,npasses=1):
        if tstart==None:
            tstart = datetime.now()

        tle0=Sat.tle.split('\n')
        print('COMPUTE SAT TRACK: tle=',tle0)

        tle2=tle0[2].split()
        #inclination=float(tle2[2])
        revs=float(tle2[7])
        rev_mins=24.*60./revs
        print('rev per day=',revs,'\t',rev_mins)
        
        lons=[]
        lats=[]
        footprints=[]
        for m in range(0,int(npasses*rev_mins+2),1):
            dt = timedelta(minutes=m)
            t = time.mktime( (tstart+dt).timetuple() )
            
            if USE_PYPREDICT:
                obs = predict.observe(Sat.tle,self.P.my_qth,t)
            else:
                obs = Sat.observe(t)
                
            lon=obs['longitude']
            lat=obs['latitude']
            footprint=obs['footprint']

            # DEBUG
            if False:
                print(obs['orbit'],'\t',tstart+dt,'\t',lon,'\t',lat,
                      '\t',footprint)
                    
                obs1=Sat.observe(t)
                lon1=obs1['longitude']
                lat1=obs1['latitude']
                footprint1=obs1['footprint']
                print(obs1['orbit'],'\t',tstart+dt,'\t',lon1,'\t',lat1,
                          '\t',footprint1)
                print('*** COMPUTE SAT TRACK - DEBUG - EXITING ***')
                sys.exit(0)

            lons.append(lon)
            lats.append(lat)
            footprints.append(footprint)

        return lons,lats,footprints

    def transform_and_plot(self,lons,lats,style,clr=None):
        if np.isscalar(lons):
            lons = np.array( [lons] )
        if np.isscalar(lats):
            lats = np.array( [lats] )
        xx=[]
        yy=[]
        x_prev=np.nan
        phz=0
        for lon,lat in zip(lons,lats):
            x,y = self.proj.transform_point(lon,lat, ccrs.Geodetic())
            x+=phz
            dx=x-x_prev
            #print('XFORM and PLOT:\t',lon,'\t',lat,'\t',dx,'\t',x,'\t',y)
            if dx>120:
                phz-=360
                x-=360
            elif dx<-120:
                phz+=360
                x+=360
            xx.append(x)

            #yy.append(max(min(y,90),-90))
            yy.append(y)
            x_prev=x

        if not clr:
            clr=style[0]
        #p=self.ax.plot(xx,yy,style,color=clr,transform=self.proj)
        p=self.ax.plot(xx,yy,style,transform=self.proj)
        return p[0]
        
    def DrawSatTrack(self,name,lons,lats,ERASE=True,title=None):

        # Set title to sat name
        if title==None:
            title=name
        self.setWindowTitle(title)
        
        # Clear prior plots
        if ERASE:
            for line in self.ax.get_lines():
                #print('line=',line)
                line.remove()
            for p in self.blobs:
                #print('p=',line)
                try:
                    p.remove()
                except:
                    pass
            self.blobs=[]

        # Plot sat track
        self.transform_and_plot(-self.P.my_qth[1],self.P.my_qth[0],'mo')
        if name=='Moon':
            self.transform_and_plot(lons,lats,'bo')
            return
        elif name=='Sun':
            self.transform_and_plot(lons,lats,'yo')
            return
        self.transform_and_plot(lons,lats,'b-')
        self.transform_and_plot(lons[0],lats[0],'g*')
        self.transform_and_plot(lons[-1],lats[-1],'r*')

        self.canv.draw()
        return
    
        
    def DrawSatFootprint(self,name,lon0,lat0,footprint,ERASE=True):

        # Clear prior footprints
        if ERASE:
            for p in self.blobs:
                print(p)
                p.remove()
            self.blobs=[]

        # Add footprint "ellipse"
        #Latitude: 1 deg = 110.54 km
        #Longitude: 1 deg = 111.320*cos(latitude) km
        dy=0.5*footprint/110.54
        dx=0.5*footprint/(111.32*np.cos(lat0*DEG2RAD))

        #print('\nEllipse:',lon0,lat0,footprint)
        north_pole = lat0+dy>=80
        south_pole = lat0-dy<=-80
        phz=0
        #print('Poles:',lat0,dy,north_pole,south_pole)

        xx=[]
        yy=[]
        pgon=[]
        lon_prev=np.nan
        step=5
        for alpha in range(0,360+step,step):
            lat=lat0+dy*np.sin(alpha*DEG2RAD)
            dx=0.5*footprint/(111.32*np.cos(lat*DEG2RAD))
            lon=lon0 + dx*np.cos(alpha*DEG2RAD)
            
            x,y = self.proj.transform_point(lon,lat, ccrs.Geodetic())
            #print(alpha,'\t',dx,'\t',lon,'\t',lat,'\t',x,'\t',y)

            # Only keep valid points - near the poles, this can get squirrly
            if dx>0 and dx<180:
                x+=phz
                dlon=x-lon_prev
                if dlon>120:
                    if north_pole or south_pole:
                        if north_pole:
                            y0=90
                        else:
                            y0=-90
                        pgon.append((-180+phz,y))
                        #print(pgon[-1])
                        pgon.append((-180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((180+phz,y))
                        #print(pgon[-1])
                    else:
                        phz-=360
                        x-=360
                elif dlon<-120:
                    if north_pole or south_pole:
                        if north_pole:
                            y0=90
                        else:
                            y0=-90
                        pgon.append((180+phz,y))
                        #print(pgon[-1])
                        pgon.append((180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((-180+phz,y0))
                        #print(pgon[-1])
                        pgon.append((-180+phz,y))
                        #print(pgon[-1])
                    else:
                        phz+=360
                        x+=360
                        
                lon_prev=x
                #xx.append(lon)
                #yy.append(lat)
                #y=max(min(y,90),-90)
                pgon.append((x,y))
                
        #self.transform_and_plot(xx,yy,'g-')
        #self.transform_and_plot(xx[0],yy[0],'go')
        pgon=Polygon( tuple(pgon) )
        p=self.ax.add_geometries([pgon], crs=self.proj, facecolor='r',
                          edgecolor='red', alpha=0.3)
        self.blobs.append(p)

        p=self.transform_and_plot(lon0,lat0,'k*')
        self.blobs.append(p)
        
        self.canv.draw()
