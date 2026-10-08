' The silent front door: runs the launcher with no window at all. The
' desktop shortcut points here, so double-clicking opens nothing but the
' browser.
'
' conhost --headless, not a plain hidden run: on Windows 11 with Windows
' Terminal as the default terminal app, SW_HIDE on a console program is
' ignored and a terminal window pops anyway (verified on this machine).
' Invoking conhost directly bypasses the default-terminal delegation and
' --headless means the console genuinely has no window. The server itself
' runs under pythonw, which has no console for any terminal's closing to
' take down. Failures still surface: launch.ps1 -Quiet shows a message box.
Dim shell, here
Set shell = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
shell.Run "conhost.exe --headless powershell -NoProfile -ExecutionPolicy Bypass -File """ & _
    here & "launch.ps1"" -Quiet", 0, False
