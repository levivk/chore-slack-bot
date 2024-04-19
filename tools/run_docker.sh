#!/usr/bin/env bash

script_dir=$(dirname $(readlink -f "${BASH_SOURCE}"))
proj_dir=$( dirname ${script_dir} )
cd ${proj_dir}

docker build --tag chore-bot .  \
    || exit

docker stop chore-bot-1
docker rm chore-bot-bkp
docker rename chore-bot-1 chore-bot-bkp
docker run -itd --env-file "$proj_dir/keys.env" -p 8081:3000 -v /opt/chore-bot-data:/app/data --log-driver journald --restart unless-stopped --name chore-bot-1 chore-bot
