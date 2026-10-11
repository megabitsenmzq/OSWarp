@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "CSC="
set "LANGVER=7.3"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
  for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -prerelease -find MSBuild\**\Bin\Roslyn\csc.exe`) do set "CSC=%%I"
)
if not defined CSC (
  if exist "%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" (
    set "CSC=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
  ) else (
    set "CSC=%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
  )
  set "LANGVER=5"
)
if not exist "%CSC%" (
  echo csc.exe was not found
  exit /b 1
)

call :build x64 OSWarp-x64.exe
if errorlevel 1 exit /b 1
if "%LANGVER%"=="5" (
  echo Built %CD%\OSWarp-x64.exe
  echo This compiler cannot build ARM64
  exit /b 0
)
call :build arm64 OSWarp-arm64.exe
if errorlevel 1 exit /b 1
echo Built %CD%\OSWarp-x64.exe
echo Built %CD%\OSWarp-arm64.exe
exit /b 0

:build
"%CSC%" /nologo /langversion:%LANGVER% /platform:%~1 /codepage:65001 /target:winexe /utf8output /win32manifest:app.manifest /win32icon:OSWarp.ico /out:"%~2" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Management.dll Program.cs Boot.cs Actions.cs Prompt.cs ListForm.cs Firmware.cs Config.cs
if errorlevel 1 exit /b 1
exit /b 0
