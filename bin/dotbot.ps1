# This script finds a Python 3.14+ binary and uses it to run Dotbot, passing
# along all of the command line arguments. If there is no Python 3.14+ on the
# PATH, it uses uv to find or download one, and if uv is not installed, it first
# downloads a pinned version of uv (verifying its checksum) into the cache
# directory.

# Windows PowerShell 5.1 turns the stderr output of native commands into errors
# when it is redirected, so the "Stop" preference of the caller cannot be used
$ErrorActionPreference = "Continue"

$UV_VERSION = "0.12.21"
$DOTBOT = Join-Path $PSScriptRoot -ChildPath "dotbot"

function Stop-Dotbot($Message) {
    [Console]::Error.WriteLine("error: $Message")
    exit 1
}

foreach ($PYTHON in ('python', 'python3')) {
    # Python redirects to Microsoft Store in Windows 10 when not installed
    if (Get-Command $PYTHON -ErrorAction SilentlyContinue) {
        & $PYTHON -c "import sys; sys.exit(sys.version_info < (3, 14))" 2>$null
        if ($LASTEXITCODE -eq 0) {
            & $PYTHON $DOTBOT @Args
            exit $LASTEXITCODE
        }
    }
}

$UV = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UV) {
    $CACHE_DIR = Join-Path $(if ($env:XDG_CACHE_HOME) { $env:XDG_CACHE_HOME } else { $env:LOCALAPPDATA }) -ChildPath "dotbot"
    $UV_DIR = Join-Path $CACHE_DIR -ChildPath "uv-$UV_VERSION"
    $UV = Join-Path $UV_DIR -ChildPath "uv.exe"
    if (-not (Test-Path $UV)) {
        $ARCH = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
        switch ($ARCH) {
            "AMD64" { $TARGET = "x86_64-pc-windows-msvc"; $SHA256 = "5d223efa0bf00208c3853246af09420419dfbd352536aa6bb8163d6170e23890" }
            "ARM64" { $TARGET = "aarch64-pc-windows-msvc"; $SHA256 = "93ed53b94e9cec000cacdfd18ca67bc4cb2b6a5f5ec041edd7f2a3dae365ce79" }
            default { Stop-Dotbot "cannot find Python 3.14+ or uv; install one of them" }
        }
        $URL = "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$TARGET.zip"
        [Console]::Error.WriteLine("Cannot find Python 3.14+ or uv; downloading uv $UV_VERSION to $UV_DIR")
        $TMP = Join-Path $CACHE_DIR -ChildPath "tmp.$([System.IO.Path]::GetRandomFileName())"
        $ZIP = Join-Path $TMP -ChildPath "uv.zip"
        try {
            New-Item -ItemType Directory -Path $TMP -Force -ErrorAction Stop | Out-Null
            # Windows PowerShell 5.1 does not enable TLS 1.2 by default on older systems
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $ProgressPreference = "SilentlyContinue"
            Invoke-WebRequest -Uri $URL -OutFile $ZIP -UseBasicParsing -ErrorAction Stop
            if ((Get-FileHash -Path $ZIP -Algorithm SHA256).Hash -ne $SHA256) {
                Stop-Dotbot "checksum mismatch for $URL"
            }
            Expand-Archive -Path $ZIP -DestinationPath (Join-Path $TMP -ChildPath "uv") -ErrorAction Stop
            if (Test-Path $UV_DIR) { Remove-Item -Recurse -Force $UV_DIR }
            Move-Item -Path (Join-Path $TMP -ChildPath "uv") -Destination $UV_DIR -ErrorAction Stop
        } catch {
            Stop-Dotbot "cannot download $URL`n$_"
        } finally {
            if (Test-Path $TMP) { Remove-Item -Recurse -Force $TMP }
        }
    }
}

$PYTHON = & $UV python find --no-project ">=3.14" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $UV python install --no-bin 3.14
    if ($LASTEXITCODE -eq 0) { $PYTHON = & $UV python find --no-project ">=3.14" }
    if ($LASTEXITCODE -ne 0) { Stop-Dotbot "cannot find or install Python 3.14+" }
}
& $PYTHON $DOTBOT @Args
exit $LASTEXITCODE
