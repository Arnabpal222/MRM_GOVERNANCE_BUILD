# Creates "MRM Governance MIS" (start) and "Stop MRM Governance MIS" shortcuts in THIS folder
# (A_Codes\AE_launcher), with app icons generated here. Nothing is written to the desktop. Run once:
#   powershell -ExecutionPolicy Bypass -File "A_Codes\AE_launcher\create_shortcuts.ps1"

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function New-AppIcon([string]$path, [string]$hexColour, [string]$label) {
    # 256x256 PNG drawn with System.Drawing, wrapped in a single-image .ico container.
    $size = 256
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = "AntiAlias"; $g.TextRenderingHint = "AntiAliasGridFit"
    $g.Clear([System.Drawing.Color]::Transparent)
    $bg = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#0E1118"))
    $accent = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml($hexColour))
    $gp = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = 48; $rect = New-Object System.Drawing.Rectangle 8, 8, 240, 240
    $gp.AddArc($rect.X, $rect.Y, $r, $r, 180, 90); $gp.AddArc($rect.Right - $r, $rect.Y, $r, $r, 270, 90)
    $gp.AddArc($rect.Right - $r, $rect.Bottom - $r, $r, $r, 0, 90); $gp.AddArc($rect.X, $rect.Bottom - $r, $r, $r, 90, 90)
    $gp.CloseFigure()
    $g.FillPath($bg, $gp)
    $g.FillRectangle($accent, 40, 196, 176, 14)
    $font = New-Object System.Drawing.Font "Segoe UI", 70, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
    $fmt = New-Object System.Drawing.StringFormat; $fmt.Alignment = "Center"; $fmt.LineAlignment = "Center"
    $g.DrawString($label, $font, $accent, (New-Object System.Drawing.RectangleF 0, 20, 256, 170), $fmt)
    $g.Dispose()
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
    $png = $ms.ToArray()
    $fs = [System.IO.File]::Create($path); $w = New-Object System.IO.BinaryWriter $fs
    $w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]1)           # ICONDIR: reserved, type=icon, count
    $w.Write([byte]0); $w.Write([byte]0); $w.Write([byte]0); $w.Write([byte]0) # 256x256, no palette
    $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$png.Length); $w.Write([uint32]22)
    $w.Write($png); $w.Close()
}

function New-Shortcut([string]$name, [string]$script, [string]$icon, [string]$description) {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut((Join-Path $PSScriptRoot "$name.lnk"))
    $lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = "$icon,0"
    $lnk.Description = $description
    $lnk.Save()
    Write-Host "Created shortcut: $(Join-Path $PSScriptRoot "$name.lnk")"
}

$startIcon = Join-Path $PSScriptRoot "mrm.ico"
$stopIcon  = Join-Path $PSScriptRoot "mrm_stop.ico"
New-AppIcon $startIcon "#8C9EFF" "MRM"
New-AppIcon $stopIcon  "#EC6A57" "STOP"
New-Shortcut "MRM Governance MIS" (Join-Path $PSScriptRoot "start_mrm.ps1") $startIcon "Start the Model Governance MIS and open it in the browser"
New-Shortcut "Stop MRM Governance MIS" (Join-Path $PSScriptRoot "stop_mrm.ps1") $stopIcon "Stop the Model Governance MIS"
