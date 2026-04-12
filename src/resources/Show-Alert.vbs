
' Show-Alert.vbs — Mensaje simple (sin PowerShell) para usar en tu programador de tareas
'
' USO BÁSICO
' ----------
'   wscript Show-Alert.vbs "<mensaje>" [/icon:None|Info|Warning|Error|Question] [/sound:None|Asterisk|Beep|Exclamation|Hand|Question] [/attention:None|Blink] [/blinkseconds:N]
'
' PARÁMETROS
' ----------
' 1) <mensaje> (posicional, opcional):
'    Texto que se mostrará en la ventana. Si no se especifica, la ventana aparecerá sin texto y con un único botón "Ok".
'
' 2) /icon:   Icono del sistema a mostrar junto al texto. Valores: None (defecto), Info, Warning, Error, Question.
'    Nota: Algunos temas de Windows reproducen el sonido asociado al icono elegido. Si quieres silencio total, usa /icon:None.
'
' 3) /sound:  Sonido del sistema a reproducir al mostrar la ventana. Valores: None (defecto), Asterisk, Beep, Exclamation, Hand, Question.
'    - Limitación VBScript: no hay API directa para sonidos; si eliges Asterisk/Exclamation/Hand/Question
'      confía en el sonido que Windows suele asociar al icono equivalente. Para un pitido simple usa /sound:Beep.
'
' 4) /attention: Intensifica la visibilidad. Valores: None (defecto), Blink
'    - Blink: realiza varios pitidos breves antes de mostrar el mensaje (para llamar la atención). Duración ajustable con /blinkseconds.
'
' 5) /blinkseconds:N  Duración del parpadeo/atención en segundos cuando /attention:Blink (defecto: 6).
'
' COMPORTAMIENTO POR DEFECTO (sin argumentos)
' -------------------------------------------
' - Sin texto, sin icono, sin sonido. Solo aparece el botón "Ok" para cerrar.
'
' EJEMPLOS
' --------
'   wscript Show-Alert.vbs "Respaldo completado" /icon:Info /sound:Asterisk
'   wscript Show-Alert.vbs "Servidor no responde" /icon:Error /sound:Hand /attention:Blink /blinkseconds:4
'   wscript Show-Alert.vbs
'
Option Explicit

Dim args, msg, iconArg, soundArg, attArg, blinkSec
Set args = WScript.Arguments

msg = ""
iconArg = "None"
soundArg = "None"
attArg = "None"
blinkSec = 6

Dim i
For i = 0 To args.Count-1
  Dim a: a = args(i)
  If Left(LCase(a), 6) = "/icon:" Then
    iconArg = Mid(a, 7)
  ElseIf Left(LCase(a), 7) = "/sound:" Then
    soundArg = Mid(a, 8)
  ElseIf Left(LCase(a), 11) = "/attention:" Then
    attArg = Mid(a, 12)
  ElseIf Left(LCase(a), 14) = "/blinkseconds:" Then
    On Error Resume Next
    blinkSec = CInt(Mid(a, 15))
    If Err.Number <> 0 Then blinkSec = 6
    On Error GoTo 0
  Else
    ' Primer argumento no nombrado se toma como mensaje
    If msg = "" Then msg = a Else msg = msg & " " & a
  End If
Next

' NOTA: No redefinimos constantes vb* (vbOKOnly, vbInformation, etc.) porque ya existen en VBScript
'       y provocaría "Nombre redefinido" (código 800A0411).

' Mapear icono a flags de MsgBox
Dim iconFlag: iconFlag = 0
Select Case LCase(iconArg)
  Case "info", "information": iconFlag = vbInformation   ' 64
  Case "warning", "exclamation": iconFlag = vbExclamation ' 48
  Case "error", "critical": iconFlag = vbCritical         ' 16
  Case "question": iconFlag = vbQuestion                  ' 32
  Case Else: iconFlag = 0 ' None
End Select

' Atención previa (Blink = varios pitidos) antes de mostrar el mensaje
If LCase(attArg) = "blink" Then
  Dim tEnd: tEnd = Timer + blinkSec
  Do While Timer < tEnd
    Call MessageBeep()
    WScript.Sleep 350
  Loop
End If

' Sonido explícito si lo pide el usuario (Beep simple)
If LCase(soundArg) = "beep" Then
  Call MessageBeep()
End If

' Mostrar el mensaje siempre encima (SystemModal)
Dim flags: flags = vbOKOnly Or iconFlag Or vbSystemModal
Dim title: title = "Aviso"

' Mostrar MsgBox (si msg vacío, saldrá solo el botón Ok)
Call MsgBox(msg, flags, title)

'===== Funciones auxiliares =====
Sub MessageBeep()
  ' Llama al pitido por defecto del sistema usando rundll32 -> user32!MessageBeep
  Dim sh
  Set sh = CreateObject("WScript.Shell")
  On Error Resume Next
  sh.Run "rundll32 user32,MessageBeep", 0, False
  On Error GoTo 0
  Set sh = Nothing
End Sub
