@echo off
echo %DATE% %TIME%
goto BUILD
echo.
echo Notes about how to run pySat on Windoze 10.
echo.
echo !!!!!!!!!!!!!! WORK IN PROGRESS !!!!!!!!!!!!!!!!!
echo.
echo Need the following Python libraries:
echo.
     pip install pyephem
echo.
echo To run the script under python:
echo.
     pySat.py
:BUILD
echo.
echo To compile - takes a long time:
echo.
     pyinstaller --onefile pySat.py
echo.
echo To run compiled version - works under linux and windoz:
echo.
      dist\pySat.exe
echo.
echo KNOWN ISSUESL
echo - Haven't tested rig control yet
echo - Bombs is .satrc doesn't exist
echo - Need to fix location of /tmp/satellite.log for windoz
echo - Need to generate Moon.trsp & None.trsp if they don't exists

