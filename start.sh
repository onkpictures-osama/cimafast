#!/bin/bash
set -a
source /srv/cimafast/.env
set +a
cd /srv/cimafast
/srv/cimafast/venv/bin/streamlit run app.py
