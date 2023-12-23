#!/usr/bin/env bash

root_dir=$(dirname $(readlink -f "${BASH_SOURCE}"))
docker build --tag chore-bot .  \
    || exit

docker stop chore-bot-1
docker rm chore-bot-1
docker run -itd --env-file "$root_dir/keys.env" -p 8082:3000 -v /opt/chore-bot-data:/app/data --log-driver journald --restart unless-stopped --name chore-bot-1 chore-bot
