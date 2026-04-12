
<#
    Show-Alert.ps1 — Ventana de mensaje simple para usar con tu programador de tareas

    USO BÁSICO
    -----------
    powershell.exe -ExecutionPolicy Bypass -File .\Show-Alert.ps1 "<mensaje>" [-Sound <None|Asterisk|Beep|Exclamation|Hand|Question>] [-Icon <None|Info|Information|Warning|Error|Question>] [-Attention <None|Blink|Flash>] [-BlinkSeconds <segundos>]

    PARÁMETROS
    ----------
    1) Mensaje (posicional, opcional):
       - Texto que se mostrará en la ventana. Si no se especifica, la ventana saldrá sin texto y con un único botón "Ok".

    2) -Sound (opcional): Reproduce un sonido del sistema cuando aparece la ventana.
       - Valores: None (por defecto), Asterisk, Beep, Exclamation, Hand, Question
       - Ejemplos de uso: -Sound Asterisk   |   -Sound Exclamation

    3) -Icon (opcional): Muestra un icono del sistema junto al texto.
       - Valores: None (por defecto), Info/Information, Warning, Error, Question
       - Nota: Info e Information son equivalentes.

    4) -Attention (opcional): Hace más visible la ventana/aviso.
       - Valores: None (por defecto), Blink, Flash
         * Blink: hace parpadear el color de fondo durante unos segundos (controlable con -BlinkSeconds).
         * Flash: hace parpadear la barra de título/tarea usando FlashWindowEx (hasta que la ventana reciba foco).
       - -BlinkSeconds <n>: duración aproximada del parpadeo de fondo cuando -Attention Blink (por defecto 6 s).

    5) Comportamiento por defecto si NO se pasa ningún argumento:
       - Sin texto, sin sonido, sin icono y un único botón "Ok" para cerrar.

    EJEMPLOS
    --------
    # Solo un mensaje informativo con sonido y parpadeo del fondo
    powershell.exe -ExecutionPolicy Bypass -File .\Show-Alert.ps1 "Respaldo completado" -Icon Info -Sound Asterisk -Attention Blink

    # Alerta de error con sonido y parpadeo de la barra de título
    powershell.exe -ExecutionPolicy Bypass -File .\Show-Alert.ps1 "Servidor no responde" -Icon Error -Sound Hand -Attention Flash

    # Ventana mínima: solo botón Ok
    powershell.exe -ExecutionPolicy Bypass -File .\Show-Alert.ps1

    NOTAS
    -----
    - La ventana se muestra "Siempre encima" (TopMost) para asegurar que aparezca sobre otros programas.
    - Este script usa .NET WinForms y no requiere dependencias externas.
    - Puedes llamarlo desde tu programador usando la ruta al .ps1 y añadiendo los argumentos deseados.
#>

param(
    [Parameter(Position=0)] [string]$Message = "",
    [ValidateSet('None','Asterisk','Beep','Exclamation','Hand','Question')] [string]$Sound = 'None',
    [ValidateSet('None','Info','Information','Warning','Error','Question')] [string]$Icon = 'None',
    [ValidateSet('None','Blink','Flash')] [string]$Attention = 'None',
    [int]$BlinkSeconds = 6
)

Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -AssemblyName System.Drawing | Out-Null

# Importar FlashWindowEx para efecto "Flash" en la barra de título/tarea
$flashSig = @"
using System;
using System.Runtime.InteropServices;
public static class WinFlash {
  [StructLayout(LayoutKind.Sequential)]
  public struct FLASHWINFO {
    public UInt32 cbSize;
    public IntPtr hwnd;
    public UInt32 dwFlags;
    public UInt32 uCount;
    public UInt32 dwTimeout;
  }
  [DllImport("user32")] public static extern bool FlashWindowEx(ref FLASHWINFO pwfi);
  public const UInt32 FLASHW_STOP = 0;
  public const UInt32 FLASHW_CAPTION = 1;
  public const UInt32 FLASHW_TRAY = 2;
  public const UInt32 FLASHW_ALL = 3;
  public const UInt32 FLASHW_TIMER = 4;
  public const UInt32 FLASHW_TIMERNOFG = 12;
}
"@
Add-Type -TypeDefinition $flashSig -ErrorAction SilentlyContinue | Out-Null

# Crear formulario
$form = New-Object System.Windows.Forms.Form
$form.Text = "Aviso"
$form.TopMost = $true
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.AutoSize = $true
$form.AutoSizeMode = 'GrowAndShrink'
$form.MinimizeBox = $false
$form.MaximizeBox = $false
$form.ShowInTaskbar = $true
$form.FormBorderStyle = 'FixedDialog'

# Contenedor principal
$root = New-Object System.Windows.Forms.TableLayoutPanel
$root.ColumnCount = 1
$root.RowCount = 2
$root.AutoSize = $true
$root.Padding = New-Object System.Windows.Forms.Padding(10)
$root.Dock = 'Fill'
$form.Controls.Add($root)

# Fila de contenido (icono + texto)
$content = New-Object System.Windows.Forms.TableLayoutPanel
$content.ColumnCount = 2
$content.RowCount = 1
$content.AutoSize = $true
$content.Dock = 'Top'
$content.Padding = New-Object System.Windows.Forms.Padding(4)
$root.Controls.Add($content)

# Icono (opcional)
$pic = $null
if ($Icon -ne 'None') {
    $pic = New-Object System.Windows.Forms.PictureBox
    $pic.SizeMode = 'CenterImage'
    $pic.Width = 40
    $pic.Height = 40
    switch ($Icon.ToLower()) {
        'info' { $pic.Image = [System.Drawing.SystemIcons]::Information.ToBitmap() }
        'information' { $pic.Image = [System.Drawing.SystemIcons]::Information.ToBitmap() }
        'warning' { $pic.Image = [System.Drawing.SystemIcons]::Warning.ToBitmap() }
        'error' { $pic.Image = [System.Drawing.SystemIcons]::Error.ToBitmap() }
        'question' { $pic.Image = [System.Drawing.SystemIcons]::Question.ToBitmap() }
        default { $pic.Image = $null }
    }
}

if ($pic -ne $null) { $content.Controls.Add($pic, 0, 0) }

# Texto del mensaje
$lbl = New-Object System.Windows.Forms.Label
$lbl.Text = $Message
$lbl.AutoSize = $true
$lbl.MaximumSize = New-Object System.Drawing.Size(600, 0)  # ajusta el ancho máximo
$lbl.Margin = New-Object System.Windows.Forms.Padding(8, 8, 8, 8)
$lbl.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$lbl.UseMnemonic = $false

if ($pic -ne $null) { $content.Controls.Add($lbl, 1, 0) } else { $content.Controls.Add($lbl, 0, 0) }

# Fila de botones
$buttonsPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$buttonsPanel.FlowDirection = 'RightToLeft'
$buttonsPanel.Dock = 'Fill'
$buttonsPanel.AutoSize = $true
$buttonsPanel.Padding = New-Object System.Windows.Forms.Padding(4)
$root.Controls.Add($buttonsPanel)

$okBtn = New-Object System.Windows.Forms.Button
$okBtn.Text = 'Ok'
$okBtn.AutoSize = $true
$okBtn.Add_Click({ $form.Close() })
$form.AcceptButton = $okBtn
$buttonsPanel.Controls.Add($okBtn)

# Atención visual
$defaultBack = $form.BackColor
$timer = $null
if ($Attention -eq 'Blink') {
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 400
    $elapsed = 0
    $timer.Add_Tick({
        if ($form.BackColor -eq $defaultBack) { $form.BackColor = [System.Drawing.Color]::FromArgb(255,255,200) } else { $form.BackColor = $defaultBack }
        $elapsed += $timer.Interval
        if ($elapsed -ge ($BlinkSeconds * 1000)) { $timer.Stop(); $form.BackColor = $defaultBack }
    })
}
elseif ($Attention -eq 'Flash' -and (Get-Command -Name Add-Type -ErrorAction SilentlyContinue)) {
    $form.Add_Shown({
        Start-Sleep -Milliseconds 50
        try {
            $h = $form.Handle
            $fi = New-Object WinFlash+FLASHWINFO
            $fi.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf([type] 'WinFlash+FLASHWINFO')
            $fi.hwnd = $h
            $fi.dwFlags = [uint32]12  # FLASHW_TIMERNOFG (tray + caption mientras no tiene foco)
            $fi.uCount = 0            # infinito hasta foco
            $fi.dwTimeout = 0
            [WinFlash]::FlashWindowEx([ref]$fi) | Out-Null
        } catch {}
    })
    $form.Add_Activated({
        try {
            $h = $form.Handle
            $fi = New-Object WinFlash+FLASHWINFO
            $fi.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf([type] 'WinFlash+FLASHWINFO')
            $fi.hwnd = $h
            $fi.dwFlags = [uint32]0   # STOP
            $fi.uCount = 0
            $fi.dwTimeout = 0
            [WinFlash]::FlashWindowEx([ref]$fi) | Out-Null
        } catch {}
    })
}

# Sonido del sistema
if ($Sound -ne 'None') {
    try {
        switch ($Sound) {
            'Asterisk'   { [System.Media.SystemSounds]::Asterisk.Play() }
            'Beep'       { [System.Media.SystemSounds]::Beep.Play() }
            'Exclamation'{ [System.Media.SystemSounds]::Exclamation.Play() }
            'Hand'       { [System.Media.SystemSounds]::Hand.Play() }
            'Question'   { [System.Media.SystemSounds]::Question.Play() }
        }
    } catch {}
}

# Iniciar efectos si corresponde
if ($timer) { $timer.Start() }

# Mostrar ventana (modal)
[void]$form.ShowDialog()

# Limpieza
if ($timer) { $timer.Dispose() }
$form.Dispose()
