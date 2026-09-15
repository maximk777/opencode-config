#!/usr/bin/env bash
# One-shot macOS terminal setup: Homebrew, oh-my-zsh + plugins, starship, fzf, common
# dev CLI tools, opencode, and a clean generic ~/.zshrc with correct PATH.
# Contains no personal or work settings.
# Usage: sudo ./mac-shell-setup.sh [--dry-run]   (plain user run also works)
set -euo pipefail

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
say() { printf '\n== %s\n' "$1"; }
run() { printf '+ %s\n' "$*"; [ "$DRY" = 1 ] || "$@"; }
die() { printf 'setup: %s\n' "$1" >&2; exit 1; }

# --- resolve the console user: brew, oh-my-zsh and dotfiles must never run as root
REAL_USER="${SUDO_USER:-$(id -un)}"
[ "$(id -u)" -eq 0 ] && [ -z "${SUDO_USER:-}" ] && die "run with sudo as yourself, or without sudo (not as a root login shell)"
REAL_HOME="$(dscl . -read "/Users/$REAL_USER" NFSHomeDirectory | sed 's/^[^:]*: //')"
[ -n "$REAL_HOME" ] || die "cannot resolve home for $REAL_USER"
as_user() {
  if [ "$(id -u)" -eq 0 ]; then
    sudo -u "$REAL_USER" -H env HOME="$REAL_HOME" "$@"
  else
    "$@"
  fi
}

say "target: user $REAL_USER, home $REAL_HOME"

# --- Xcode command line tools (git, compilers); needs a GUI confirmation on fresh macs
if ! xcode-select -p >/dev/null 2>&1; then
  run xcode-select --install
  [ "$DRY" = 1 ] || { printf 'Confirm the Xcode CLT install dialog, then press Enter... '; read -r; }
  xcode-select -p >/dev/null 2>&1 || die "Xcode CLT not ready; rerun after the install finishes"
fi

# --- Homebrew (arm: /opt/homebrew, intel: /usr/local)
BREW="/opt/homebrew/bin/brew"
[ -x "$BREW" ] || BREW="/usr/local/bin/brew"
if [ ! -x "$BREW" ]; then
  say "installing Homebrew"
  run as_user /bin/bash -c "NONINTERACTIVE=1 \$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  [ -x "$BREW" ] || die "brew not found at $BREW after install"
fi
[ "$DRY" = 1 ] || as_user "$BREW" --version >/dev/null || die "brew at $BREW is not runnable as $REAL_USER"

# --- CLI tools (generic, open source)
say "brew formulae"
run as_user env HOMEBREW_NO_AUTO_UPDATE=1 "$BREW" install \
  starship fzf fd ripgrep jq yq wget tree htop ncdu tmux neovim lazygit gitui gh \
  direnv diff-so-fancy git-filter-repo

say "brew casks (nerd fonts for the prompt glyphs)"
run as_user env HOMEBREW_CASK_OPTS="--no-quarantine" "$BREW" install --cask \
  font-fira-code-nerd-font font-jetbrains-mono-nerd-font

# --- oh-my-zsh + the two custom plugins
say "oh-my-zsh"
if [ "$DRY" = 1 ] || [ ! -d "$REAL_HOME/.oh-my-zsh" ]; then
  run as_user env RUNZSH=no KEEP_ZSHRC=yes /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi
ZSH_CUSTOM="$REAL_HOME/.oh-my-zsh/custom"
for repo in zsh-autosuggestions zsh-syntax-highlighting; do
  if [ "$DRY" = 1 ] || [ ! -d "$ZSH_CUSTOM/plugins/$repo" ]; then
    run as_user git clone --depth=1 \
      "https://github.com/zsh-users/$repo.git" "$ZSH_CUSTOM/plugins/$repo"
  fi
done

# --- fzf key bindings and completions into ~/.fzf.zsh (the zshrc below sources it)
say "fzf integration"
BREW_PREFIX="${BREW%/bin/brew}"
FZF_INSTALLER="$BREW_PREFIX/opt/fzf/install"
if [ -x "$FZF_INSTALLER" ]; then
  run as_user "$FZF_INSTALLER" --key-bindings --completion --no-update-rc --no-bash --no-fish
else
  echo "fzf installer not found at $FZF_INSTALLER, skipping key bindings"
fi

# --- opencode
say "opencode"
if [ "$DRY" = 1 ] || [ ! -x "$REAL_HOME/.opencode/bin/opencode" ]; then
  run as_user /bin/bash -c "curl -fsSL https://opencode.ai/install | bash"
fi

# --- ~/.zshrc: generic, no personal settings; the old file is backed up
say "writing ~/.zshrc"
stamp="$(date +%Y%m%d%H%M%S)"
if [ "$DRY" = 0 ] && [ -f "$REAL_HOME/.zshrc" ]; then
  cp "$REAL_HOME/.zshrc" "$REAL_HOME/.zshrc.backup.$stamp"
fi
run as_user tee "$REAL_HOME/.zshrc" >/dev/null <<'ZSHRC'
# --- Homebrew (arm and intel) ---
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.opencode/bin:$PATH"

# opencode: enables the built-in websearch tool for agents
export OPENCODE_ENABLE_EXA=1

# --- oh-my-zsh ---
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"
plugins=(git zsh-autosuggestions zsh-syntax-highlighting)
source $ZSH/oh-my-zsh.sh

# extra completion paths: openspec (from ~/.config/opencode setup) and docker
[ -d "$HOME/.oh-my-zsh/custom/completions" ] && fpath=("$HOME/.oh-my-zsh/custom/completions" $fpath)
[ -d "$HOME/.docker/completions" ] && fpath=("$HOME/.docker/completions" $fpath)
autoload -Uz compinit
compinit

eval "$(starship init zsh)"
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

alias n='nvim'

# --- WezTerm shell integration ---
if [[ -n "$WEZTERM_PANE" || "$TERM_PROGRAM" == "WezTerm" ]]; then
  zmodload zsh/datetime 2>/dev/null

  __wezterm_set_user_var() {
    if hash base64 2>/dev/null; then
      printf "\033]1337;SetUserVar=%s=%s\007" "$1" "$(printf '%s' "$2" | base64)"
    fi
  }
  __wezterm_osc7() { printf "\033]7;file://%s%s\033\\" "$HOST" "$PWD"; }
  __wezterm_prompt_start() { printf "\033]133;A\007"; }
  __wezterm_prompt_end()   { printf "\033]133;B\007"; }

  typeset -g __wez_cmd_start=0
  typeset -g __wez_last_cmd=""
  __wez_preexec() { __wez_cmd_start=$EPOCHSECONDS; __wez_last_cmd="$1"; }
  __wez_precmd() {
    local dur=0
    if (( __wez_cmd_start > 0 )); then
      dur=$(( EPOCHSECONDS - __wez_cmd_start ))
      __wezterm_set_user_var "WEZTERM_CMD_DONE" "${dur}|${__wez_last_cmd}"
      __wez_cmd_start=0
    fi
    __wezterm_osc7
    __wezterm_prompt_start
  }
  autoload -Uz add-zsh-hook
  add-zsh-hook preexec __wez_preexec
  add-zsh-hook precmd  __wez_precmd
  PS1="%{$(__wezterm_prompt_end)%}$PS1"
fi

# --- opencode-setup keys: sourced from ~/.openviking/.env (created by bin/bootstrap
# of the ~/.config/opencode setup); the block is inert while that file is absent.
if [ -f "$HOME/.openviking/.env" ]; then
  export OPENVIKING_API_KEY="$(grep '^OPENVIKING_API_KEY=' "$HOME/.openviking/.env" 2>/dev/null | cut -d= -f2-)"
  export DEEPSEEK_API_KEY="$(grep '^DEEPSEEK_API_KEY=' "$HOME/.openviking/.env" 2>/dev/null | cut -d= -f2-)"
fi
ZSHRC

# --- starship prompt config (tokyo-night powerline, no secrets)
say "writing ~/.config/starship.toml"
if [ "$DRY" = 0 ] && [ -f "$REAL_HOME/.config/starship.toml" ]; then
  cp "$REAL_HOME/.config/starship.toml" "$REAL_HOME/.config/starship.toml.backup.$stamp"
fi
run as_user mkdir -p "$REAL_HOME/.config"
run as_user tee "$REAL_HOME/.config/starship.toml" >/dev/null <<'STARSHIP'
"$schema" = 'https://starship.rs/config-schema.json'

# Two-line prompt with a right-aligned "status bar" (time / git state)
add_newline = true
command_timeout = 2000

format = """
[](fg:#7aa2f7)\
$os\
$directory\
[](fg:#7aa2f7 bg:#3b4261)\
$git_branch\
$git_status\
[](fg:#3b4261)\
$fill\
$cmd_duration\
$nodejs$python$rust$golang\
$line_break\
$character"""

right_format = """$time"""

[fill]
symbol = ' '

[os]
disabled = false
style = 'bg:#7aa2f7 fg:#1a1b26'
format = '[ $symbol ]($style)'

[os.symbols]
Macos = ''

[directory]
style = 'bg:#7aa2f7 fg:#1a1b26'
format = '[ $path ]($style)'
truncation_length = 3
truncation_symbol = '…/'
read_only = ' '

[directory.substitutions]
'~/.config' = ' config'
'Documents' = ' Docs'
'Downloads' = ' DL'

[git_branch]
symbol = ''
style = 'bg:#3b4261 fg:#7aa2f7'
format = '[ $symbol $branch ]($style)'

[git_status]
style = 'bg:#3b4261 fg:#e0af68'
format = '[$all_status$ahead_behind ]($style)'
conflicted = '=${count} '
ahead = '⇡${count} '
behind = '⇣${count} '
diverged = '⇕⇡${ahead_count}⇣${behind_count} '
untracked = '?${count} '
stashed = '$${count} '
modified = '!${count} '
staged = '+${count} '
renamed = '»${count} '
deleted = '✘${count} '

[cmd_duration]
min_time = 500
style = 'fg:#f7768e'
format = '[  $duration ]($style)'

[nodejs]
symbol = ''
style = 'fg:#9ece6a'
format = '[ $symbol $version ]($style)'

[python]
symbol = ''
style = 'fg:#e0af68'
format = '[ $symbol $version ]($style)'

[rust]
symbol = ''
style = 'fg:#f7768e'
format = '[ $symbol $version ]($style)'

[golang]
symbol = ''
style = 'fg:#7dcfff'
format = '[ $symbol $version ]($style)'

[time]
disabled = false
time_format = '%H:%M:%S'
style = 'fg:#565f89'
format = '[  $time ]($style)'

[character]
success_symbol = '[❯](bold #9ece6a)'
error_symbol = '[❯](bold #f7768e)'
vimcmd_symbol = '[❮](bold #bb9af7)'
STARSHIP

# --- make zsh the login shell (root chsh works without a password prompt)
say "login shell"
if [ "$(dscl . -read "/Users/$REAL_USER" UserShell | sed 's/^[^:]*: //')" != "/bin/zsh" ]; then
  run chsh -s /bin/zsh "$REAL_USER"
fi

say "done"
echo "open a new terminal window; the old ~/.zshrc is backed up as .zshrc.backup.$stamp"
echo "for the agent setup on top of this, run bin/bootstrap of ~/.config/opencode"
