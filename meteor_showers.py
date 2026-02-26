################################################################################
#
# meteor_showers.py - Rev 2.0
# Copyright (C) 2025-6 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# Code relating containing meteor showers.
#
# For now, approximate radiant RA and Decl data is used for the individual
# showers.  # These apparently change slightly as the earth progresses through
# a shower but this should be adequate for our purposes.
# The data are from the file
#      IMO_Working_Meteor_Shower_List.xml
# which was downloaded from
#      https://www.imo.net/members/imo_showers/working_shower_list
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

import os
import xmltodict,xml.dom.minidom
from collections import OrderedDict
from rig_io.ft_tables import METEOR_SHOWER_LIST

################################################################################

class Meteor_Shower:
    def __init__(self, **shower_data):
        self.__dict__.update(shower_data)

def get_meteor_showers():

    SHOWERS=OrderedDict()
    fname='~/Python/pySat/IMO_Working_Meteor_Shower_List.xml'
    METEOR_FILE=os.path.expanduser(fname)

    with open(METEOR_FILE,'r') as f:
        xml_string = f.read()

    if False:
        # Re-format XML data so its easier to read
        temp = xml.dom.minidom.parseString(xml_string)
        pretty_xml = temp.toprettyxml()
        print(pretty_xml)

        with open(METEOR_FILE,'w',encoding="utf-8") as f:
            f.write(pretty_xml)
        
    METEOR_SHOWERS = xmltodict.parse(xml_string)
    #print(METEOR_SHOWERS)
    keys=list( METEOR_SHOWERS )
    print('GET METEOR SHOWERS: keys=',keys)
    #print(keys[0])
    
    SHOWERS1 = METEOR_SHOWERS[keys[0]]
    #print(SHOWERS1)
    keys1 = list( SHOWERS1 )
    print('GET METEOR SHOWERS: keys1=',keys1)
    #print(keys1[0])

    SHOWERS2 = SHOWERS1[keys1[0]]
    if False:
        print(SHOWERS2)
        print(SHOWERS2[0])
        print(len(SHOWERS2))

    #return SHOWERS2

    for shower in SHOWERS2:
        #print(shower)
        code=shower['IAU_code']        
        name=shower['name']        
        peak=shower['peak']        
        start=shower['start']        
        stop=shower['end']        
        SHOWERS[code] = Meteor_Shower(**shower)
        if code in METEOR_SHOWER_LIST:
            print(code,'\t',start,'-',stop,'\t',name)
    #print(SHOWERS)

    return SHOWERS
    
"""
def get_shower_data(SHOWERS,name):
    for shower in SHOWERS:
        #print(shower)
        if shower['name']==name:
            #return shower
            return Meteor_Shower(**shower)
"""

