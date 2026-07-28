; ============================================================
; AIMScribe Agent - Windows installer
;
; Produces AIMScribeSetup.exe: one file for hospital IT to run on a doctor PC.
; No PowerShell, no execution policy, no command-line arguments.
;
; What the administrator is asked for:
;   * the enrolment token for that doctor
;   * the backend URL and the CMED origin, pre-filled with the defaults below
;
; Everything else - the per-install API key, the directory permissions, the
; logon task, the pinned public keys - happens without being asked, because
; every one of those was a step someone could get wrong twenty-nine times.
;
; Build:  ISCC.exe installer.iss
; ============================================================

#define AppName        "AIMScribe Agent"
#define AppVersion     "2.0.0"
#define AppPublisher   "AIMS LAB"
#define AppExe         "AIMScribe_Agent.exe"

; Defaults offered on the configuration page. Override per site.
#define DefaultBackend "https://aimscribe-backend-render.onrender.com"
#define DefaultOrigin  "https://aim-scribe-exe.vercel.app"

[Setup]
AppId={{8F3A2C41-6E5B-4D77-9A18-3C7E5B2D9F04}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\AIMScribe
DefaultGroupName=AIMScribe
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=AIMScribeSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Program files and the machine-wide data directory both need administrator
; rights, and the logon task is registered for the machine.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
; A clinical PC should be told what it is running.
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=AIMScribe consultation recording agent

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\AIMScribe_Agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Public halves only. Identical on every PC and carrying no secret, which is
; why they can ship in the installer instead of being copied by hand.
Source: "keys\cmed_grant_pub.pem";      DestDir: "{commonappdata}\AIMScribe\keys"; Flags: ignoreversion
Source: "keys\aimslab_receipt_pub.pem"; DestDir: "{commonappdata}\AIMScribe\keys"; Flags: ignoreversion

[Dirs]
; The agent writes audio and logs as the signed-in doctor, so Users need Modify
; here - but only here. It cannot alter its own program files.
Name: "{commonappdata}\AIMScribe";        Permissions: users-modify
Name: "{commonappdata}\AIMScribe\spool";  Permissions: users-modify
Name: "{commonappdata}\AIMScribe\logs";   Permissions: users-modify
Name: "{commonappdata}\AIMScribe\state";  Permissions: users-modify
Name: "{commonappdata}\AIMScribe\keys";   Permissions: users-modify

[Icons]
Name: "{group}\AIMScribe Agent"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start AIMScribe now"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""AIMScribe Agent"" /F"; \
    Flags: runhidden; RunOnceId: "RemoveTask"
Filename: "taskkill.exe"; Parameters: "/IM {#AppExe} /F"; \
    Flags: runhidden; RunOnceId: "StopAgent"

[Code]
var
  ConfigPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ConfigPage := CreateInputQueryPage(wpSelectDir,
    'AIMScribe Configuration',
    'Which backend, and which doctor is this PC for?',
    'The enrolment token names the doctor and hospital this machine records for.' + #13#10 +
    'Obtain one per PC from the AIMScribe administrator.');

  ConfigPage.Add('Backend URL:', False);
  ConfigPage.Add('CMED web address:', False);
  ConfigPage.Add('Enrolment token:', False);

  ConfigPage.Values[0] := '{#DefaultBackend}';
  ConfigPage.Values[1] := '{#DefaultOrigin}';
  ConfigPage.Values[2] := '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ConfigPage.ID then
  begin
    if Trim(ConfigPage.Values[0]) = '' then
    begin
      MsgBox('A backend URL is required.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Trim(ConfigPage.Values[1]) = '' then
    begin
      MsgBox('The CMED web address is required. The agent refuses connections' + #13#10 +
             'from any other origin, so recording cannot start without it.',
             mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Trim(ConfigPage.Values[2]) = '' then
    begin
      // Allowed, because a machine may be enrolled later - but say plainly
      // what it means rather than letting it be discovered at the bedside.
      if MsgBox('No enrolment token was entered.' + #13#10 + #13#10 +
                'AIMScribe will install and start, but will refuse to record ' +
                'until this PC is enrolled. Continue anyway?',
                mbConfirmation, MB_YESNO) = IDNO then
        Result := False;
    end;
  end;
end;

{ A local API key, unique per install. Not security-critical on its own - the
  listener is bound to 127.0.0.1 and every recording still needs a signed grant
  - but a shared key across thirty machines would be one stolen value away from
  driving all of them. }
function NewApiKey(): String;
var
  I: Integer;
  Alphabet: String;
begin
  Alphabet := 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  Result := '';
  for I := 1 to 44 do
    Result := Result + Copy(Alphabet, Random(Length(Alphabet)) + 1, 1);
end;

procedure WriteEnvFile();
var
  Env: TStringList;
  DataDir: String;
begin
  DataDir := ExpandConstant('{commonappdata}\AIMScribe');
  Env := TStringList.Create;
  try
    Env.Add('# Written by AIMScribeSetup. Do not edit by hand.');
    Env.Add('AIMS_BACKEND_URL=' + Trim(ConfigPage.Values[0]));
    Env.Add('# Protocol 2. The v1 prefix serves the transcription API and has');
    Env.Add('# none of the enrolment or session endpoints.');
    Env.Add('AIMS_BACKEND_API_PREFIX=/api/v2');
    Env.Add('');
    Env.Add('AIMS_SAMPLE_RATE=44100');
    Env.Add('AIMS_CHANNELS=1');
    Env.Add('AIMS_SAMPLE_WIDTH=2');
    Env.Add('AIMS_FRAMES_PER_BUFFER=2048');
    Env.Add('');
    Env.Add('AIMS_SEGMENT_MIN_SECONDS=170');
    Env.Add('AIMS_SEGMENT_MAX_SECONDS=190');
    Env.Add('');
    Env.Add('AIMS_SPOOL_DIR=' + DataDir + '\spool');
    Env.Add('# 40 GB is about three weeks of backend downtime at 44.1 kHz.');
    Env.Add('AIMS_SPOOL_MAX_BYTES=42949672960');
    Env.Add('# Receipted audio is kept this long as a safety net before deletion.');
    Env.Add('AIMS_PURGE_GRACE_HOURS=24');
    Env.Add('');
    Env.Add('AIMS_BIND_HOST=127.0.0.1');
    Env.Add('AIMS_BIND_PORT=5050');
    Env.Add('# Exact origins only. The agent refuses the WebSocket handshake from');
    Env.Add('# anything else, which is what stops a random page recording.');
    Env.Add('AIMS_ALLOWED_ORIGINS=' + Trim(ConfigPage.Values[1]));
    Env.Add('AIMS_ALLOWED_HOSTS=localhost:5050,127.0.0.1:5050,[::1]:5050');
    Env.Add('AIMS_LOCAL_API_KEY=' + NewApiKey());
    Env.Add('AIMS_REQUIRE_GRANT=true');
    Env.Add('AIMS_ENABLE_DOCS=false');
    Env.Add('');
    Env.Add('AIMS_GRANT_ISSUER=cmed');
    Env.Add('AIMS_GRANT_AUDIENCE=aimscribe-recorder');
    Env.Add('');
    Env.Add('AIMS_HEARTBEAT_SECONDS=30');
    Env.Add('AIMS_LOG_LEVEL=INFO');
    Env.Add('AIMS_REDACT_LOGS=true');
    Env.Add('# Never true on a clinical PC: private keys would sit unprotected.');
    Env.Add('AIMS_ALLOW_PLAINTEXT_KEYSTORE=false');
    Env.SaveToFile(ExpandConstant('{app}\.env'));
  finally
    Env.Free;
  end;
end;

procedure StageEnrollmentToken();
var
  Token: TStringList;
begin
  if Trim(ConfigPage.Values[2]) = '' then Exit;
  Token := TStringList.Create;
  try
    Token.Add(Trim(ConfigPage.Values[2]));
    Token.SaveToFile(ExpandConstant('{commonappdata}\AIMScribe\state\enrollment.token'));
  finally
    Token.Free;
  end;
end;

procedure RegisterLogonTask();
var
  ResultCode: Integer;
  Cmd: String;
begin
  { A logon task, not a service. Audio capture needs the user's session: a
    session 0 service has no default audio endpoint and would record silence.
    /RL HIGHEST so it can read its own configuration under Program Files. }
  Exec('schtasks.exe', '/Delete /TN "AIMScribe Agent" /F', '',
       SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Cmd := '/Create /TN "AIMScribe Agent" /TR "\"' + ExpandConstant('{app}\{#AppExe}') +
         '\"" /SC ONLOGON /RL HIGHEST /F';
  if not Exec('schtasks.exe', Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    MsgBox('Could not register the startup task. AIMScribe will not start ' +
           'automatically at logon; start it from the Start menu.',
           mbError, MB_OK);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Reinstalling or upgrading over a running agent leaves its files locked, and
  // Setup reports only "file in use". Stop it first: this is the upgrade path
  // for every machine in the fleet, not just a convenience today.
  Result := '';

  Exec('schtasks.exe', '/End /TN "AIMScribe Agent"', '',
       SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/IM "{#AppExe}" /F', '',
       SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Give Windows a moment to release the handles before Setup copies over them.
  Sleep(2000);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteEnvFile();
    StageEnrollmentToken();
    RegisterLogonTask();
  end;
end;

procedure InitializeUninstallProgressForm();
begin
  // Audio and configuration under ProgramData are deliberately left behind.
  // A consultation that has not yet reached the archive exists only there, and
  // an uninstall must not be the thing that destroys it.
end;
