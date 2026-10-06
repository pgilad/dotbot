# Records the dry run screenshot in the README. Run from the root of the
# repository:
#   vhs docs/demo/dry-run.tape

# VHS always records a GIF; only the screenshot is in the repository
Output "/tmp/dotbot-dry-run.gif"

Require bash
Require git
Require uv

Set Shell bash
Set FontSize 20
Set Width 1040
Set Height 350
Set Padding 28
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set WindowBarSize 40
Set TypingSpeed 0

Hide
Type `source docs/demo/setup.sh && echo '# old' > "$HOME/.zshrc" && clear` Enter
Wait
Show

Type "dotbot -c install.conf.yaml --dry-run" Enter
Wait
Sleep 500ms
Screenshot docs/demo/dry-run.png
Sleep 500ms
