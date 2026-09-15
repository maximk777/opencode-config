#!/bin/sh
set -e
mkdir -p repos
git clone -b main git@gitlab.example:demo/cards-front.git repos/cards-front
git clone -b main git@gitlab.example:demo/cards-bff.git repos/cards-bff
