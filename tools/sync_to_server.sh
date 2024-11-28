#!/bin/bash

script_dir=$( dirname $(readlink -f "${BASH_SOURCE}") )
proj_dir=$( dirname ${script_dir} )
cd ${proj_dir}

rsync -avz --exclude __pycache__ --exclude-from .gitignore --delete-excluded data src payloads tools Dockerfile keys.env requirements.txt oracle-vps:/home/ubuntu/chore-bot/
