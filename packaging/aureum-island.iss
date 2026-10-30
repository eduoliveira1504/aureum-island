; Instalador do Aureum Island (Inno Setup 6). Rode por scripts/build.py, que passa:
;   /DAppVersion=<versão do pyproject.toml>  /DSourceDir=dist\AureumIsland
;   /DOutputDir=dist  /DIconFile=build\aureum-island.ico
; Por usuário, sem admin. Ver docs/decisions/0011-empacotamento.md.

#ifndef AppVersion
  #error Rode por scripts/build.py (falta /DAppVersion)
#endif

#define AppName "Aureum Island"
#define AppExe "AureumIsland.exe"

[Setup]
; Nunca mude o AppId: é por ele que o Windows reconhece atualizações e o desinstalador.
AppId={{0E0A1B2E-8D21-429F-AF7B-214D7DC04890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Aureum
AppPublisherURL=https://eduoliveira1504.github.io/aureum-island/
AppSupportURL=https://github.com/eduoliveira1504/aureum-island/issues
AppUpdatesURL=https://github.com/eduoliveira1504/aureum-island/releases
VersionInfoVersion={#AppVersion}
; Por usuário: %LOCALAPPDATA%\Programs\Aureum Island, sem UAC.
PrivilegesRequired=lowest
DefaultDirName={userpf}\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; O mesmo mutex que o app cria (services/single_instance.py): o setup e o desinstalador
; pedem para fechar o app antes de mexer nos arquivos.
AppMutex=AureumIsland
CloseApplications=yes
RestartApplications=no
SourceDir={#SourceDir}
OutputDir={#OutputDir}
OutputBaseFilename=AureumIsland-Setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[InstallDelete]
; Atualização: tira os arquivos da versão anterior que esta não tem mais.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Iniciar o {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// A desinstalação apaga só o programa. O resto só sai se o usuário confirmar cada parte;
// em modo silencioso (/SUPPRESSMSGBOXES) a resposta é sempre Não. Quem apaga é o próprio
// app (AureumIsland.exe --uninstall-cleanup), que sabe onde fica cada coisa.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Args: String;
  ResultCode: Integer;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  Args := '';
  if SuppressibleMsgBox(
      'Remover também a opção "Iniciar com o Windows"?' + #13#10#13#10 +
      'Se escolher Não, a entrada continua em Aplicativos de inicialização e volta a ' +
      'funcionar se você instalar o app de novo.',
      mbConfirmation, MB_YESNO, IDNO) = IDYES then
    Args := Args + ' --autostart';
  if SuppressibleMsgBox(
      'Apagar os links de agenda (ICS) guardados no Gerenciador de Credenciais do Windows?',
      mbConfirmation, MB_YESNO, IDNO) = IDYES then
    Args := Args + ' --secrets';
  if SuppressibleMsgBox(
      'Apagar também seus dados (configurações, tarefas, água e eventos)?' + #13#10#13#10 +
      ExpandConstant('{userappdata}\{#AppName}') + #13#10#13#10 +
      'Se escolher Não, eles ficam guardados para quando você instalar de novo.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
    Args := Args + ' --data';
  if Args <> '' then
    Exec(ExpandConstant('{app}\{#AppExe}'), '--uninstall-cleanup' + Args, '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
