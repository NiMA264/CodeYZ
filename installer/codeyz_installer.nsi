!include "MUI2.nsh"

Name "CodeYZ"
OutFile "codeyz-installer.exe"
InstallDir "$PROGRAMFILES\CodeYZ"
RequestExecutionLevel admin

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File "..\dist\codeyz.exe"
  File "..\run.ps1"
  File "..\README.md"
  CreateDirectory "$SMPROGRAMS\CodeYZ"
  CreateShortcut "$SMPROGRAMS\CodeYZ\CodeYZ.lnk" "$INSTDIR\codeyz.exe"
  CreateShortcut "$DESKTOP\CodeYZ.lnk" "$INSTDIR\codeyz.exe"
SectionEnd
