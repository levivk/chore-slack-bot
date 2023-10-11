#!/bin/bash
rsync -avz --exclude __pycache__ --delete-excluded data src run_docker.sh Dockerfile keys.env requirements.txt oracle-vps:/home/ubuntu/chore-bot/
