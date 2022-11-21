# TDIC-Deliveries

![CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)

## Installation (macOS)
### Install Prerequisites
* Python 3
* Python3-pip
* Python3-venv
* Git

### Create Virtual Environment
Then create a virtual environment in the `TDIC-Deliveries/` directory with:
```sh
python3 -m venv TDIC-Deliveries/
```

### Activate Virtual Environment
```sh
cd TDIC-Deliveries/
source bin/activate
```

### Update PIP
```sh
python3 -m pip install --upgrade pip
```

### Install PIP Requirements
Install all requirements at once using:
```sh
pip3 install -r requirements.txt
``` 

## Run
### Run Prerequisites
* Google Maps API key
* TDIC.csv (placed in `TDIC-Deliveries/`)

Inside the python virtual environment, run:
```sh
python3 tdic.py API_KEY
```
*** replace API_KEY with your API key

To get master PDF:
1. Navigate to `build/pdf/`
2. Press `command+A`
3. Right-click (two-finger click) and go to 'Quick Actions > Create PDF'
4. Name the new PDF

## Deactivate Virtual Environment
```sh
deactivate
```