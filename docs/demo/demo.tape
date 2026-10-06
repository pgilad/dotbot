# Records the demo in the README. Run from the root of the repository:
#   vhs docs/demo/demo.tape

Output docs/demo/demo.gif

Require bash
Require git
Require uv

Set Shell bash
Set FontSize 20
Set Width 1040
Set Height 600
Set Padding 28
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set WindowBarSize 40
Set TypingSpeed 45ms

Hide
Type "source docs/demo/setup.sh && clear" Enter
Wait
Show

Sleep 500ms
Type "cat install.conf.yaml" Sleep 400ms Enter
Sleep 4s

Ctrl+L
Type "dotbot -c install.conf.yaml" Sleep 400ms Enter
Wait
Sleep 3s

Type "dotbot -c install.conf.yaml  # safe to run again" Sleep 400ms Enter
Wait
Sleep 4s
