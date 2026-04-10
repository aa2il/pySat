#! /usr/bin/python3 -u

# Script to explore reading json files

import urllib.request, urllib.error, urllib.parse
import json
import sys

URL3="https://db.satnogs.org/api/"
response = urllib.request.urlopen(URL3)

txt = response.read().decode("utf-8")
print('txt=',txt)

root=json.loads(txt)

print('root=',root)
print('root keys=',root.keys())

#sys.exit(0)

# This is the transponder data, i.e. transmitters.json
for item in ['modes']:    # root.keys():
    print('item=',item)
    URL4=URL3+item+'/'
    print('URL=',URL4)

    response = urllib.request.urlopen(URL4)

    txt = response.read().decode("utf-8")
    print('txt=',txt)

    obj=json.loads(txt)
    print('obj=',obj)

    pretty_obj = json.dumps(obj, indent=4)
    print('pretty obj=',pretty_obj)
    

sys.exit(0)

fname='../modes.json'
with open(fname) as json_data_file:
    data = json.load(json_data_file)

print(data)
pretty_data = json.dumps(data, indent=4)
print(pretty_data)
print(len(data))
