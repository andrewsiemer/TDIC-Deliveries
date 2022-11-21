#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Creates Delivery Handouts from Master Speadsheet"""

import sys
import requests
import csv
import textwrap
import os
import shutil

import secrets
import png
import pyqrcode
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import gray, black
import os

FILE_NAME = 'tdic'

# clean build dir if they do not exist
if os.path.exists('build'):
    shutil.rmtree("build")
os.makedirs('build')
os.makedirs('build/img')
os.makedirs('build/qr')
os.makedirs('build/pdf')

# current csv row data
data = {}

# Google Maps parameters
STATIC_BASE_URL = "https://maps.googleapis.com/maps/api/staticmap?"
if len(sys.argv) != 2:
    print("err: please provide google api key `python3 tdic.py uh2eih2id7as87d6as82hk2e`")
    sys.exit()
API_KEY = sys.argv[1]
ZOOM = 15 

# QR dode parameters
GOOGLE_BASE_URL = "https://www.google.com/maps/place/"
APPLE_BASE_URL = "https://maps.apple.com/?daddr="

# document version
VERSION = secrets.token_hex(3)

# open csv file
with open(FILE_NAME + '.csv', mode='r') as csv_file:
    with open(FILE_NAME + '-labels.csv', mode='w') as csv_out_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        csv_writer = csv.writer(csv_out_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            # read row of csv
            data.clear()

            if not row[0].isnumeric():  # ignore rows without IDß
                line_count += 1
            else:
                data['index'] = row[0]
                data['confirmation'] = str(row[1])
                data['last_name'] = str(row[2])
                data['first_name'] = str(row[3])
                data['phone'] = str(row[4])
                data['address'] = str(row[5])
                data['apartment'] = str(row[6])
                data['city'] = str(row[7])
                data['state'] = str(row[8])
                data['zip_code'] = str(row[9])
                data['meals'] = str(row[10])
                data['notes'] = str(row[12]) + str(row[13])
                data['language'] = str(row[14])
                data['comments'] = str(row[15])
                # print(data)

                # printed name format
                name = data['first_name'] + ' ' + data['last_name']

                # concatinate address for url
                location = data['address'].replace(" ", "+").split('Apt', 1)[0] + ',+' + data['city'].replace(" ", "+") + ',+' + data['state'].replace(" ", "+") + '+' + data['zip_code'] 
                # google static map api create link
                STATIC_URL = STATIC_BASE_URL + "center=" + location + "&zoom=" + str(ZOOM) + "&size=500x500&markers=" + location + "&key=" + API_KEY
                print(str(data['index']) + ': ' + STATIC_URL)
                response = requests.get(STATIC_URL)

                # write image as png file
                with open('build/img/' + str(data['index']) + '.png', 'wb') as file:
                    file.write(response.content)

                # create pdf for delivery
                canvas = Canvas('build/pdf/' + str(data['index']) + '.pdf')
                
                # starting locations on pdf for text formatting
                y1 = 270
                x1 = 50
                x11 = x1+65

                # pdf header
                canvas.setFont("Helvetica-Bold", 18)
                canvas.drawString(153, 800, "THANKSGIVING DAY IN THE CITY")
                canvas.setFont("Helvetica", 12)
                canvas.drawString(212, 780, "Memorial Road Church of Christ")

                # draw map
                canvas.drawInlineImage("build/img/" + str(data['index']) + ".png", x1, y1, 500, 500)
                y1 -= 20
                
                # draw QR code if valid address
                canvas.drawInlineImage("static/apple-maps.png", 364, 241, 75, 18)
                URL = APPLE_BASE_URL + location
                QR = pyqrcode.create(URL, error="L", version=5)
                QR.png('build/qr/apple-' + str(data['index']) + '.png', scale = 3)
                canvas.drawInlineImage("build/qr/apple-" + str(data['index']) + ".png", 362, 162, 80, 80)

                canvas.drawInlineImage("static/google-maps.png", 452, 240, 100, 24)
                URL = GOOGLE_BASE_URL + location
                QR = pyqrcode.create(URL, error="L", version=5)
                QR.png('build/qr/google-' + str(data['index']) + '.png', scale = 3)
                canvas.drawInlineImage("build/qr/google-" + str(data['index']) + ".png", 462, 162, 80, 80)

                # draw row data on pdf
                canvas.drawString(x1, y1, "Name:")
                canvas.drawString(x11, y1, name)
                y1 -= 20

                canvas.drawString(x1, y1, "Phone:")
                canvas.drawString(x11, y1, data['phone'])
                y1 -= 20

                # draw address with apartment number if necassary
                if data['apartment'] != '':
                    canvas.drawString(x1, y1, "Address:")
                    addr = data['address'].upper() + ", " + data['apartment'].upper()
                    canvas.drawString(x11, y1, addr)
                else:
                    canvas.drawString(x1, y1, "Address:")
                    addr = data['address'].upper()
                    canvas.drawString(x11, y1, addr)
                y1 -= 20

                addr2 = data['city'] + ', ' + data['state'] + ' ' + data['zip_code']
                canvas.drawString(x11, y1, addr2)
                y1 -= 20

                canvas.drawString(x1, y1, "Meals:")
                canvas.drawString(x11, y1, data['meals'])
                y1 -= 20

                if data['notes'] != '':
                    canvas.drawString(x1, y1, "Notes:") 
                    canvas.drawString(x11, y1, data['notes'])
                    y1 -= 20
                
                if data['language'] != '':
                    canvas.drawString(x1, y1, "Language:") 
                    canvas.drawString(x11, y1, data['language'])
                    y1 -= 20
                
                if data['comments'] != '':
                    canvas.drawString(x1, y1, "Comments:")
                    wrapper = textwrap.TextWrapper(width=85) 
                    word_list = wrapper.wrap(text=data['comments']) 
                    for i, element in enumerate(word_list): 
                        canvas.drawString(x11, y1, element)
                        y1 -= 20

                # draw meal count at top of pdf
                canvas.setFont("Helvetica", 50)
                canvas.rect(20, 20, 555, 65, fill=0)
                centered_str = 'BOX #' + data['index'] + ' - ' +  data['meals'] + ' MEALS'
                while (len(centered_str) < 19):
                    centered_str = ' ' + centered_str
                canvas.drawString(39, 34, centered_str)
                
                # draw version data
                canvas.setFont("Helvetica", 8)
                canvas.setFillColor(gray)
                canvas.drawString(20, 10, VERSION)

                # save canvas to file
                canvas.save()
                csv_writer.writerow(['# ' + data['index'], data['meals'] + ' MEALS', name + ' (' + data['phone'] + ')', addr + ' ' + addr2, ])
                
                # iterate to next line of csv
                line_count += 1

print('version: ' + VERSION)
