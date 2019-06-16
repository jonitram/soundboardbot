#!/bin/bash
python3.7 -m pip install -r requirements.txt
rm tokens.txt
touch tokens.txt
read -sp $'Please input your discord token:' d_token
echo $d_token >> tokens.txt
read -sp $'\nPlease input your youtube token:' y_token
echo $y_token >> tokens.txt
