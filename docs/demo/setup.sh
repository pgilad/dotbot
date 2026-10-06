# The VHS tapes in this directory source this file in bash. It puts Dotbot from
# this checkout on the PATH, and makes a temporary home directory with dotfiles,
# so that a recording doesn't change your home directory.
#
# Don't use ~ in this file: bash can keep the old home directory for ~ after
# HOME changes.

uv sync --quiet || return
export PATH="$PWD/.venv/bin:$PATH"

# the physical path, so that Dotbot shows the paths in the home directory as ~
demo_home=$(cd "$(mktemp -d)" && pwd -P) || return
export HOME="$demo_home"

mkdir -p "$HOME/.dotfiles/nvim"
cd "$HOME/.dotfiles" || return
git init --quiet
echo 'export EDITOR=nvim' > zshrc
printf '[user]\n\tname = Ada Lovelace\n' > gitconfig
echo 'vim.o.number = true' > nvim/init.lua
cat > install.conf.yaml << 'EOF'
- defaults:
    link:
      create: true  # make parent directories
      relink: true  # replace old symbolic links

- clean: ['~']  # remove dead links to your dotfiles

- link:
    ~/.zshrc: zshrc  # ~/.zshrc -> ~/.dotfiles/zshrc
    ~/.gitconfig: gitconfig
    ~/.config/nvim: nvim

- create:
    - ~/projects

- shell:
    - [git submodule update --init, Installing submodules]
EOF
