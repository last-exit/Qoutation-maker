; Inno Setup script for the Quotation Engine Windows installer.
;
; Compile with:  ISCC.exe installer\quotation_engine.iss
; (or open this file in the Inno Setup IDE and press F9)
;
; Expects PyInstaller to have produced dist\QuotationEngine\ first - build_installer.bat
; does both steps in order.

#define MyAppName        "Quotation Engine"
#define MyAppVersion     "1.0.0"
#define MyAppPublisher   "Red Cube"
#define MyAppExeName     "QuotationEngine.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}

; This GUID identifies the application to Windows for upgrades and for the Add/Remove
; Programs entry. It was generated once. NEVER change it - a new GUID makes Windows treat
; the next build as a separate product, so the PM ends up with two installed copies and two
; uninstall entries. (The doubled leading brace is Inno's escape for a literal '{'.)
AppId={{C77163C5-4CCF-4107-82D6-946FD43435B8}

; {autopf} resolves to Program Files for an admin install and the per-user equivalent
; otherwise. Either way the install directory is treated as read-only at runtime: everything
; the app writes goes to %LOCALAPPDATA%\QuotationEngine (see paths.py).
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Ask for admin, but let the user drop to a per-user install from the dialog if they cannot
; elevate - a locked-down work laptop should not be a dead end.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; 'x64compatible' is the current identifier. Older examples show 'x64', which is deprecated.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

OutputDir=..\dist\installer
OutputBaseFilename=QuotationEngine-{#MyAppVersion}-Setup
SetupIconFile=..\assets\app.ico
WizardStyle=modern

; The payload is ~2 GB and is dominated by files that are already incompressible - the
; PyTorch DLLs, the OCR weights, the ONNX model. lzma2/max gets most of the available
; benefit. SolidCompression is deliberately off: it would force Setup to decompress
; everything up to a given file before it can extract it, which at this size costs more
; install time than it saves in download size.
Compression=lzma2/max
SolidCompression=no
; DiskSpanning is only required above 4,200,000,000 compressed bytes. We are under that,
; but not by a wide margin - check the output size if the bundle grows.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"

[Files]
; The whole PyInstaller one-folder output.
Source: "..\dist\QuotationEngine\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; The WebView2 bootstrapper, run below only if the runtime is missing. It is about 2 MB,
; which next to a 2 GB payload is free - and without WebView2 the app opens no window at all,
; which is a miserable thing to debug remotely.
Source: "redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; \
    Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Windows 11 ships WebView2. Most Windows 10 machines have it, but not all, and Microsoft's
; own guidance is to handle the gap rather than assume.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
    StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; \
    Check: WebView2Missing; Flags: waituntilterminated

; Finish-page "launch now" checkbox. skipifsilent keeps an unattended install from opening a
; window nobody is there to see.
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: postinstall nowait skipifsilent

[UninstallDelete]
; PyInstaller's bundle is removed by the uninstaller, but Python leaves __pycache__ folders
; behind inside it, which would otherwise strand the install directory.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Code]
{ Detects the WebView2 runtime by the registry value Microsoft documents for the purpose.
  Absent, empty, or 0.0.0.0 all mean "not installed". The GUID is the runtime's fixed
  product code, not something to regenerate. }
function WebView2Missing(): Boolean;
var
  Version: String;
begin
  Result := True;
  if RegQueryStringValue(HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Version) then
    if (Version <> '') and (Version <> '0.0.0.0') then
      Result := False;

  if Result then
    if RegQueryStringValue(HKCU,
        'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
        'pv', Version) then
      if (Version <> '') and (Version <> '0.0.0.0') then
        Result := False;
end;

{ The user's quotations, invoices, price corrections and product photos live in
  %LOCALAPPDATA%\QuotationEngine, which is deliberately outside {app} and is NOT removed
  here. Uninstalling a version of the software must never destroy the work done with it;
  reinstalling picks the same data back up. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    MsgBox('Your quotations, invoices and settings have been kept in:' + #13#10 + #13#10 +
           ExpandConstant('{localappdata}\QuotationEngine') + #13#10 + #13#10 +
           'Delete that folder by hand if you want to remove them too.',
           mbInformation, MB_OK);
end;
