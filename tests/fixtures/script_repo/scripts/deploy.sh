#!/bin/bash
# Deploy script

source ./scripts/common.sh
. ./scripts/helpers.sh

APP_ENV="${APP_ENV:-production}"

deploy() {
    echo "Deploying to $APP_ENV"
}

deploy
