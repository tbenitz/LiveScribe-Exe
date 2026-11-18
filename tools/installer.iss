[Setup]
AppId=LiveScribe.Local.Windows
AppName=LiveScribe
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\LiveScribe
DefaultGroupName=LiveScribe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=LiveScribe-Setup-x64-Offline
SetupIconFile=..\build\livescribe.ico
UninstallDisplayIcon={app}\LiveScribe.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\LiveScribe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LiveScribe"; Filename: "{app}\LiveScribe.exe"

[Run]
Filename: "{app}\LiveScribe.exe"; Description: "Open LiveScribe and start microphone transcription"; Flags: postinstall nowait skipifsilent unchecked
