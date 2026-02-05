#!/bin/bash
cd /home/ubuntu/dominion-api/DomVAEnergySch10
source ../venv/bin/activate
source ../.env

python3 dominion_energy_extractor_render.py >> ../logs/cron.log 2>&1
