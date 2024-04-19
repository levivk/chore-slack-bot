#!/bin/bash

script_dir=$(dirname $(readlink -f "${BASH_SOURCE}"))
proj_dir=$( dirname ${script_dir} )
cd ${proj_dir}

# # build image
# docker build --tag chore-bot .  \
#     || exit
#
# # send image to server
# docker save chore-bot | gzip | pv | ssh oracle-vps 'gunzip | docker load'

./tools/sync_to_server.sh
ssh -t oracle-vps 'bash ./chore-bot/tools/run_docker.sh'
