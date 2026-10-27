; Inno Setup script for Naukri Profile Bot. Build with build.ps1 (it runs PyInstaller first).

#define MyAppName "Naukri Profile Bot"
#define MyAppExeName "NaukriProfileBot.exe"
#define MyAppURL "https://github.com/Acronikhil/Naukri_bot"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{7C3E2F4A-9B1D-4E6A-8F2C-5D0A1B3C9E77}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Nikhil Dubey
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
; Per-user install: no administrator rights needed.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\NaukriProfileBot
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
InfoAfterFile=after_install.txt
OutputDir=..\dist
OutputBaseFilename=NaukriProfileBot-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\NaukriProfileBot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Remove the Windows scheduled task before the files are deleted.
Filename: "{app}\{#MyAppExeName}"; Parameters: "--uninstall"; RunOnceId: "RemoveScheduledTask"; Flags: runhidden waituntilterminated

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\NaukriProfileBot');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox('Also delete your settings, activity log and saved Naukri login?',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
