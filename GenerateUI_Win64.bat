@echo off

SET pyuicpath="C:\Anaconda\Library\bin\pyuic5"
REM SET pyuicpath="C:\Users\Alex\.conda\envs\road-defect-types\Library\bin\pyuic5"

echo Running pyuic5...

call %PYUICPATH% ui\deftui.ui -o ui\deftui_ui.py
call %PYUICPATH% ui\deftui_imgpreview.ui -o ui\deftui_imgpreview_ui.py

echo Done.
pause