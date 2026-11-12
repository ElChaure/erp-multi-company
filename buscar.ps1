<#
.SYNOPSIS
    Busca un string dentro de los archivos de un proyecto, excluyendo
    carpetas ruidosas (venv, node_modules, .git, __pycache__, etc.).

.PARAMETER Terminos
    Uno o varios strings a buscar. Ej: -Terminos "Dashboard","Catalogos"

.PARAMETER Ruta
    Carpeta raíz. Default: D:\proyecto_dj

.PARAMETER Extensiones
    Filtro por extensión. Ej: -Extensiones .py,.html,.js,.tsx
    Si se omite, busca en todas.

.PARAMETER CaseSensitive
    Si está presente, diferencia mayúsculas/minúsculas.

.PARAMETER Contexto
    Muestra N líneas antes y después del match. Default: 0

.EXAMPLE
    .\buscar.ps1 -Terminos "Dashboard","Catalogos"

.EXAMPLE
    .\buscar.ps1 -Terminos "total_empleados" -Extensiones .py,.html -Contexto 2
#>

param(
    [Parameter(Mandatory = $true)]
    [string[]]$Terminos,

    [string]$Ruta = "D:\proyecto_dj",

    [string[]]$Extensiones = @(),

    [switch]$CaseSensitive,

    [int]$Contexto = 0
)

# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════

$ErrorActionPreference = "SilentlyContinue"

# Carpetas a excluir (nombres, no rutas completas)
$ExcluirCarpetas = @(
    'venv', '.venv', 'env', '.env',
    'node_modules', '.next', 'dist', 'build',
    '__pycache__', '.git', '.idea', '.vscode',
    'migrations', 'staticfiles', 'media',
    '.pytest_cache', '.mypy_cache', 'htmlcov',
    'coverage', '.tox', 'eggs', '*.egg-info'
)

# Extensiones a excluir siempre (binarios, locks)
$ExcluirExtensiones = @(
    '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
    '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg',
    '.pdf', '.zip', '.tar', '.gz', '.7z', '.rar',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.lock', '.map', '.min.js', '.min.css'
)

# ═══════════════════════════════════════════════════════════
#  VALIDACIONES
# ═══════════════════════════════════════════════════════════

if (-not (Test-Path $Ruta)) {
    Write-Host "❌ La ruta no existe: $Ruta" -ForegroundColor Red
    exit 1
}

$Ruta = (Resolve-Path $Ruta).Path

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " 🔍  Búsqueda en proyecto" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " Ruta:        $Ruta"
Write-Host " Términos:    $($Terminos -join ', ')"
if ($Extensiones.Count -gt 0) {
    Write-Host " Extensiones: $($Extensiones -join ', ')"
} else {
    Write-Host " Extensiones: (todas)"
}
Write-Host " Case:        $(if ($CaseSensitive) { 'sensible' } else { 'insensible' })"
Write-Host " Contexto:    $Contexto líneas"
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ═══════════════════════════════════════════════════════════
#  RECOLECTAR ARCHIVOS
# ═══════════════════════════════════════════════════════════

$archivos = Get-ChildItem -Path $Ruta -Recurse -File -Force |
    Where-Object {
        $rutaRelativa = $_.FullName.Substring($Ruta.Length)

        # Excluir por carpeta
        $enCarpetaExcluida = $false
        foreach ($carpeta in $ExcluirCarpetas) {
            $patron = [regex]::Escape("\$carpeta\")
            if ($rutaRelativa -match $patron -or $rutaRelativa -match "\\$([regex]::Escape($carpeta))$") {
                $enCarpetaExcluida = $true
                break
            }
        }
        if ($enCarpetaExcluida) { return $false }

        # Excluir por extensión
        if ($ExcluirExtensiones -contains $_.Extension.ToLower()) {
            return $false
        }

        # Filtrar por extensiones solicitadas
        if ($Extensiones.Count -gt 0) {
            if ($Extensiones -notcontains $_.Extension.ToLower()) {
                return $false
            }
        }

        return $true
    }

Write-Host "📁 Archivos a revisar: $($archivos.Count)" -ForegroundColor Yellow
Write-Host ""

# ═══════════════════════════════════════════════════════════
#  BUSCAR
# ═══════════════════════════════════════════════════════════

$totalMatches = 0
$archivosConMatch = 0

foreach ($archivo in $archivos) {
    $lineas = Get-Content -Path $archivo.FullName -ErrorAction SilentlyContinue
    if (-not $lineas) { continue }

    $rutaCorta = $archivo.FullName.Substring($Ruta.Length + 1)

    for ($i = 0; $i -lt $lineas.Count; $i++) {
        $linea = $lineas[$i]

        foreach ($termino in $Terminos) {
            $match = if ($CaseSensitive) {
                $linea -cmatch [regex]::Escape($termino)
            } else {
                $linea -imatch [regex]::Escape($termino)
            }

            if ($match) {
                if ($totalMatches -eq 0 -or $archivosConMatch -eq 0) {
                    # Imprimir cabecera del archivo la primera vez
                }

                if (-not $script:archivosMostrados -or -not $script:archivosMostrados.Contains($archivo.FullName)) {
                    if (-not $script:archivosMostrados) { $script:archivosMostrados = @{} }
                    $script:archivosMostrados[$archivo.FullName] = $true
                    $archivosConMatch++
                    Write-Host ""
                    Write-Host "📄 $rutaCorta" -ForegroundColor Green
                    Write-Host ("─" * 70) -ForegroundColor DarkGray
                }

                $numLinea = $i + 1

                # Contexto previo
                if ($Contexto -gt 0) {
                    $desde = [Math]::Max(0, $i - $Contexto)
                    for ($j = $desde; $j -lt $i; $j++) {
                        Write-Host ("  {0,4} │ {1}" -f ($j + 1), $lineas[$j]) -ForegroundColor DarkGray
                    }
                }

                # Línea con match (resaltar término)
                $lineaResaltada = $linea
                if (-not $CaseSensitive) {
                    $lineaResaltada = $linea -ireplace "($([regex]::Escape($termino)))", ">>$1<<"
                } else {
                    $lineaResaltada = $linea -creplace "($([regex]::Escape($termino)))", ">>$1<<"
                }
                Write-Host ("  {0,4} │ {1}" -f $numLinea, $lineaResaltada) -ForegroundColor White

                # Contexto posterior
                if ($Contexto -gt 0) {
                    $hasta = [Math]::Min($lineas.Count - 1, $i + $Contexto)
                    for ($j = $i + 1; $j -le $hasta; $j++) {
                        Write-Host ("  {0,4} │ {1}" -f ($j + 1), $lineas[$j]) -ForegroundColor DarkGray
                    }
                }

                $totalMatches++
                break  # evitar duplicar si dos términos coinciden en la misma línea
            }
        }
    }
}

# ═══════════════════════════════════════════════════════════
#  RESUMEN
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " 📊  Resumen" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " Archivos revisados:     $($archivos.Count)"
Write-Host " Archivos con matches:   $archivosConMatch" -ForegroundColor Green
Write-Host " Total de coincidencias: $totalMatches" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""