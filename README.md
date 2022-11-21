# TDIC-Deliveries

![CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)

A simple script that takes a master delivery file and creates individual delivery documents with map and directions.

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

## Usage
### Usage Prerequisites
* Google Maps API key
* TDIC.csv (placed in `TDIC-Deliveries/`)

### TDIC.csv Prerequisites
The TDIC.csv files is expected to have the following columns. All rows without a unique ID in column 0 will be ignored.

0. ID
1. Confirmation
2. Last name
3. First name
4. Phone
5. Address
6. Apartment
7. City
8. State
9. Zip 	
10. Number of Meals	
11. Previous # Meals (unused) 
12. Notes 1	
13. Notes 2
14. Language	
15. Any Comments?

### Run

Inside the python virtual environment, run:
```sh
python3 tdic.py API_KEY
```
> replace API_KEY with your API key

To get the master PDF:
1. Navigate to `build/pdf/`
2. Press `command+A`
3. Right-click (two-finger click) and go to 'Quick Actions > Create PDF'
4. Name the new PDF

## Deactivate Virtual Environment
```sh
deactivate
```
