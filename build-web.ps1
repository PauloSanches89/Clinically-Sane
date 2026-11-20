# Vite cannot build from this folder because the path contains "#".
# Copy the frontend to a temporary path, build it, and copy dist back.
$ErrorActionPreference = "Stop"
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dst = Join-Path $env:TEMP "clinically-sane-web"
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
New-Item -ItemType Directory -Path $dst | Out-Null
robocopy (Join-Path $src "web") $dst /E /XD dist node_modules /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
Push-Location $dst
npm install
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location
$built = Join-Path $dst "dist"
$out = Join-Path $src "web\dist"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
robocopy $built $out /E /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { exit $LASTEXITCODE }
Write-Output "Built web/dist"
exit 0
