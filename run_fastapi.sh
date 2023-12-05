#!/bin/bash
export UVICORN_PORT=8443
poetry run uvicorn app.main:app --reload
