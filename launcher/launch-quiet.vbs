' The silent front door: runs the launcher with no window at all. The
' desktop shortcut points here, so double-clicking opens nothing but the
' browser. Window style 0 hides the PowerShell console reliably where
' -WindowStyle flags do not, and the server itself runs under pythonw,
' which has no console for any terminal's closing to take down.
' Failures still surface: launch.ps1 -Quiet shows a message box.
Dim shell, here
Set shell = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
shell.Run "powershell -NoProfile -ExecutionPolicy Bypass -File """ & _
    here & "launch.ps1"" -Quiet", 0, False
