@echo off
echo %DATE% %TIME%
goto BUILD
echo.
echo Notes about how to run pySat on Windoze 10.
echo.
echo Make sure all references to "import predict" are turned off
echo and ignore any warnings when we try to install pypredict:
     pip install -r requirements
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
echo - Bombs if .satrc doesn't exist
echo - Need to fix location of /tmp/satellite.log for windoz
echo - Need to generate Moon.trsp & None.trsp if they don't exist

