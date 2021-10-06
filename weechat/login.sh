#!/bin/bash

function start_weechat()
{
    weechat
}

function start_tmux()
{
    if tmux has-session -t weechat 2>/dev/null; then
        tmux attach -t weechat
    else
        tmux new -s weechat "$0"
    fi
}

if test $TMUX; then
    start_weechat
else
    start_tmux
fi
