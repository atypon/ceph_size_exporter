#!/bin/bash

bash /usr/local/bin/toolbox.sh &
python /usr/local/bin/exporter.py &

wait