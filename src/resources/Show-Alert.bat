@echo off
:: Show-Alert.bat (v2.1) — Mensaje simple (sin PowerShell, sin MSHTA) para usar en tu programador de tareas
::
:: USO
::   Show-Alert.bat "<mensaje>" [/icon:None|Info|Warning|Error|Question] ^
::     [/sound:None|Asterisk|Beep|Exclamation|Hand|Question] ^
::     [/attention:None|Blink] [/blinkseconds:N]
::
:: NOTAS
:: - Por limitaciones de cmd.exe, si necesitas un signo % literal en el mensaje,
::   escribe dos:  %%   (así se verá como %).
:: - Para comillas dobles dentro del mensaje, no tienes que hacer nada: este script
::   ya las duplica antes de pasarlas al VBScript temporal.
::
setlocal EnableExtensions EnableDelayedExpansion

set "MSG="
set "ICON=None"
set "SOUND=None"
set "ATT=None"
set "BLINKSECS=6"

:parse
if "%~1"=="" goto parsed
for /f "tokens=1,2 delims=:" %%A in ("%~1") do (
  set "K=%%~A"
  set "V=%%~B"
)
if /i "!K!"=="/icon"        (set "ICON=!V!" & shift & goto parse)
if /i "!K!"=="/sound"       (set "SOUND=!V!" & shift & goto parse)
if /i "!K!"=="/attention"   (set "ATT=!V!" & shift & goto parse)
if /i "!K!"=="/blinkseconds" (set "BLINKSECS=!V!" & shift & goto parse)

:: Si no es argumento nombrado, acumular en mensaje
if defined MSG (set "MSG=!MSG! %~1") else set "MSG=%~1"
shift
goto parse

:parsed

:: Asegurar que BLINKSECS es numérico
for /f "tokens=*"%=% %%N in ("%BLINKSECS%") do set "BLINKSECS=%%N"
set "_num=%BLINKSECS:"="%"
set /a _test=_num 2>nul || set "BLINKSECS=6"

:: Mapear icono a flags de MsgBox
set /a FLAGS=0
set /a FLAGS+=4096 & rem vbSystemModal (siempre encima)
if /i "%ICON%"=="Info"         set /a FLAGS+=64
if /i "%ICON%"=="Information"  set /a FLAGS+=64
if /i "%ICON%"=="Warning"      set /a FLAGS+=48
if /i "%ICON%"=="Exclamation"  set /a FLAGS+=48
if /i "%ICON%"=="Error"        set /a FLAGS+=16
if /i "%ICON%"=="Critical"     set /a FLAGS+=16
if /i "%ICON%"=="Question"     set /a FLAGS+=32

:: Atención previa (Blink): serie de pitidos
if /i "%ATT%"=="Blink" (
  set /a COUNT=%BLINKSECS%*2
  for /L %%I in (1,1,!COUNT!) do (
    call :_beep
    >nul timeout /t 1 /nobreak
  )
)

:: Sonido explícito si lo pide el usuario
if /i "%SOUND%"=="Beep" call :_beep

:: Preparar mensaje: duplicar comillas dobles (para VBS)
set "TITLE=Aviso"
set "MSG_ESC=!MSG:"=""!"

:: Crear VBS temporal
set "TMPVBS=%TEMP%\show_alert_%RANDOM%%RANDOM%.vbs"
> "%TMPVBS%" echo Dim a: Set a = WScript.Arguments
>>"%TMPVBS%" echo Dim msg: If a.Count^>0 Then msg = a(0) Else msg = ""
>>"%TMPVBS%" echo Dim flags: If a.Count^>1 Then flags = CLng(a(1)) Else flags = 4096
>>"%TMPVBS%" echo Dim ttl: If a.Count^>2 Then ttl = a(2) Else ttl = "Aviso"
>>"%TMPVBS%" echo MsgBox msg, flags, ttl

:: Mostrar con interfaz gráfica (WScript), bloqueante hasta que se pulse Ok
wscript //nologo "%TMPVBS%" "!MSG_ESC!" "!FLAGS!" "%TITLE%"

:: Limpiar
if exist "%TMPVBS%" del /q "%TMPVBS%" >nul 2>&1

exit /b 0

:_beep
start "" /b rundll32 user32,MessageBeep
exit /b 0