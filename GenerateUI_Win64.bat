@echo off

SET pyuicpath="C:\Anaconda\Library\bin\pyuic5"
#SET pyuicpath="C:\Users\Alex\.conda\envs\movement\Library\bin\pyuic5"

echo Running pyuic5...

%PYUICPATH% ui\deftui.ui -o ui\deftui_ui.py

echo Done.
pause