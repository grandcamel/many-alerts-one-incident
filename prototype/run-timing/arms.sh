#!/bin/bash
# PROTOTYPE — throwaway. The four arms, one after another so wall time is honest.
set -u
cd "$(dirname "$0")"
python3 measure.py run opus5-high    --model claude-opus-5    --budget 3 --wait 900
python3 measure.py run opus5-xhigh   --model claude-opus-5    --effort xhigh --budget 3 --wait 900
python3 measure.py run opus5-medium  --model claude-opus-5    --effort medium --budget 3 --wait 900
python3 measure.py run fable51-high  --model claude-fable-5-1 --budget 3 --wait 900
python3 measure.py report
