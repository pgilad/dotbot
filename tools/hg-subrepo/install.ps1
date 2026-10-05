$ErrorActionPreference = "Stop"

$CONFIG = "install.conf.yaml"
$DOTBOT_DIR = "dotbot"

$DOTBOT_BIN = "bin/dotbot.ps1"
$BASEDIR = $PSScriptRoot

Set-Location $BASEDIR

git -C $DOTBOT_DIR submodule update --init --recursive
& $(Join-Path $BASEDIR -ChildPath $DOTBOT_DIR | Join-Path -ChildPath $DOTBOT_BIN) -d $BASEDIR -c $CONFIG @Args
exit $LASTEXITCODE
