#!/usr/bin/env python
# pylint: disable=unspecified-encoding,bare-except
"""TDIC Delivery Mapper"""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import shutil
import textwrap
import time
from datetime import datetime
from io import BytesIO

import pyqrcode
import requests
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.colors import gray
from reportlab.pdfgen.canvas import Canvas

# Google Maps parameters
API_BASE_URL = "https://maps.googleapis.com/maps/api/staticmap?"
ZOOM = 15

# QR dode parameters
GOOGLE_BASE_URL = "https://www.google.com/maps/place/"
APPLE_BASE_URL = "https://maps.apple.com/?daddr="

VERSION = hex(round(time.time() * 1000))[2:]

HCENTER = 300
RADIUS = 10

TERMINAL_WIDTH = 100
COL_WIDTH = 15


def format_phone_number(unformatted_number):
    # Remove any non-numeric characters
    digits_only = "".join(c for c in unformatted_number if c.isdigit())

    # Check if the remaining digits form a valid phone number
    if len(digits_only) == 10:
        # Format the number with dashes
        formatted_number = f"{digits_only[:3]}-{digits_only[3:6]}-{digits_only[6:]}"
        return formatted_number
    else:
        # Handle invalid phone numbers
        print(f"Error formatting phone number {unformatted_number}, skipping ...")
        return unformatted_number


def hash_dict(input_dict):
    # Convert the dictionary to a JSON string
    json_string = json.dumps(input_dict, sort_keys=True)

    # Create a hash object using hashlib and hash the JSON string
    hash_object = hashlib.sha256(json_string.encode())

    # Get the hexadecimal representation of the hash
    checksum_value = hash_object.hexdigest()

    return checksum_value


def combine_pdfs(input_dir, output_file):
    pdf_writer = PdfWriter()

    # Get a list of PDF files in the input directory
    pdf_files = [file for file in os.listdir(input_dir) if file.endswith(".pdf")]

    # Sort the files to maintain the order
    pdf_files.sort()

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_dir, pdf_file)

        with open(pdf_path, "rb") as pdf:
            pdf_reader = PdfReader(pdf)
            # Add each page to the writer object
            for page_num in range(len(pdf_reader.pages)):
                pdf_writer.add_page(pdf_reader.pages[page_num])

    # Write the combined PDF to the output file
    with open(output_file, "wb") as output_pdf:
        pdf_writer.write(output_pdf)


def main(args):
    with open(args.spreadsheet, mode="r") as in_file, open(
        args.spreadsheet.stem + "-labels.csv", mode="w"
    ) as out_file:
        csv_reader = csv.reader(in_file, delimiter=",")
        csv_writer = csv.writer(out_file, delimiter=",")

        for row in csv_reader:
            # read row of csv
            data = {}
            try:
                if not row[0].isnumeric():  # ignore rows without ID
                    raise RuntimeError()
            except:
                continue

            print(f" #{row[0].strip()} ".center(TERMINAL_WIDTH, "-"))

            data["index"] = row[0].strip()
            data["last_name"] = row[3].strip()
            data["first_name"] = row[4].strip()
            data["phone"] = row[5].strip()
            data["address"] = row[6].strip()
            data["apartment"] = row[7].strip()
            data["city"] = row[8].strip()
            data["state"] = row[9].strip()
            data["zip_code"] = row[10].strip()
            data["meals"] = row[11].strip()
            data["notes"] = row[15].strip()
            data["language"] = row[16].strip()
            data["comments"] = row[17].strip()

            if int(data["meals"]) <= 0:
                print(f"Meals <= 0, skipping ...")
                continue

            index = int(data["index"])

            # Hash dict unique checksum
            checksum = hash_dict(data)
            print(f'{"Checksum:".ljust(COL_WIDTH)} {checksum}')

            # printed name format
            name = (f'{data["first_name"]} {data["last_name"]}').title().strip()

            # create pdf for delivery
            canvas = Canvas(f'{args.build}/pdf/{data["index"]}.pdf')

            # starting locations on pdf for text formatting
            y1 = 280
            x1 = 50
            x11 = x1 + 65

            # pdf header
            canvas.setFont("Helvetica-Bold", 18)
            canvas.drawCentredString(
                HCENTER, 810, f"THANKSGIVING DAY IN THE CITY {datetime.now().year}"
            )
            canvas.setFont("Helvetica", 12)
            canvas.drawCentredString(HCENTER, 790, "Memorial Road Church of Christ")

            # handle address
            addr = f'{data["address"].upper()}, {data["apartment"]}'.upper()
            addr2 = f'{data["city"]}, {data["state"]} {data["zip_code"]}'.upper()

            if index >= 1000:
                row4 = "CATHOLIC CHARITIES"
            elif index >= 900 and index < 1000:
                row4 = "CAPITOL HILL"
            else:
                row4 = f"{addr.strip()} {addr2.strip()}"

            # draw image placeholder
            canvas.drawCentredString(HCENTER, y1 + 250, row4)

            if data["address"]:
                # concatinate address for url
                location = (
                    data["address"]
                    .replace(" ", "+")
                    .split("Apt", 1)[0]
                    .split("#", 1)[0]
                    + ",+"
                    + data["city"].replace(" ", "+")
                    + ",+"
                    + data["state"].replace(" ", "+")
                    + "+"
                    + data["zip_code"]
                )
                # google static map api create link
                api = (
                    API_BASE_URL
                    + "center="
                    + location
                    + "&zoom="
                    + str(ZOOM)
                    + "&size=500x500&markers="
                    + location
                    + "&key="
                    + args.api_token
                )
                print(f'{"MAPS API:".ljust(COL_WIDTH)} {api}')
                response = requests.get(api, timeout=3)

                img = Image.open(BytesIO(response.content)).convert("RGBA")
                img.save(f'{args.build}/img/{data["index"]}.png')

                # draw map
                canvas.drawInlineImage(img, x1, y1, 500, 500)

                # add rounded corners
                canvas.setStrokeColorRGB(1, 1, 1)
                canvas.setLineWidth(6)
                canvas.roundRect(x1 - 3, y1 - 3, 506, 506, 13)
                canvas.setLineWidth(1)
                canvas.setStrokeColorRGB(0, 0, 0)

                # draw QR code if valid address
                canvas.drawInlineImage("static/apple-maps.png", 364, 251, 75, 18)
                url = APPLE_BASE_URL + location
                print(f'{"APPLE MAPS:".ljust(COL_WIDTH)} {url}')
                qr = pyqrcode.create(url, error="L", version=5)
                qr.png(f'{args.build}/qr/apple-{data["index"]}.png', scale=3)
                canvas.drawInlineImage(
                    f'{args.build}/qr/apple-{data["index"]}.png', 362, 172, 80, 80
                )
                canvas.drawInlineImage("static/google-maps.png", 452, 250, 100, 24)
                url = GOOGLE_BASE_URL + location
                print(f'{"GOOGLE MAPS:".ljust(COL_WIDTH)} {url}')
                qr = pyqrcode.create(url, error="L", version=5)
                qr.png(f'{args.build}/qr/google-{data["index"]}.png', scale=3)
                canvas.drawInlineImage(
                    f'{args.build}/qr/google-{data["index"]}.png', 462, 172, 80, 80
                )

            # add map frame
            canvas.roundRect(x1, y1, 500, 500, RADIUS, fill=0)
            y1 -= 20

            # draw row data on pdf
            canvas.drawString(x1, y1, "Name:")
            canvas.drawString(x11, y1, name)
            y1 -= 20

            if data["phone"]:
                canvas.drawString(x1, y1, "Phone:")
                canvas.drawString(x11, y1, format_phone_number(data["phone"]))
                y1 -= 20

            # draw address with apartment number if necassary
            if data["address"]:
                if data["apartment"] != "":
                    canvas.drawString(x1, y1, "Address:")
                    canvas.drawString(x11, y1, addr)
                    y1 -= 20
                else:
                    canvas.drawString(x1, y1, "Address:")
                    addr = data["address"].upper()
                    canvas.drawString(x11, y1, addr)
                    y1 -= 20

                canvas.drawString(x11, y1, addr2)
                y1 -= 20

            canvas.drawString(x1, y1, "Meals:")
            canvas.drawString(x11, y1, data["meals"])
            y1 -= 20

            if data["notes"] != "":
                canvas.drawString(x1, y1, "Notes:")
                canvas.drawString(x11, y1, data["notes"])
                y1 -= 20

            if data["language"] != "":
                canvas.drawString(x1, y1, "Language:")
                canvas.drawString(x11, y1, data["language"])
                y1 -= 20

            if data["comments"] != "":
                canvas.drawString(x1, y1, "Comments:")
                wrapper = textwrap.TextWrapper(width=85)
                word_list = wrapper.wrap(text=data["comments"])
                for _, element in enumerate(word_list):
                    canvas.drawString(x11, y1, element)
                    y1 -= 20

            # draw meal count at top of pdf
            canvas.setFont("Helvetica", 50)
            canvas.roundRect(20, 20, 555, 65, RADIUS)
            centered_str = f'BOX #{data["index"]} - {data["meals"]} MEAL{"S" if int(data["meals"]) > 1 else ""}'
            canvas.drawCentredString(HCENTER, 34, centered_str)

            # draw version data
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(gray)
            canvas.drawCentredString(HCENTER, 10, f"{checksum} - {VERSION}")

            # save canvas to file
            canvas.save()

            label = [
                f'#{data["index"]}',
                f'{data["meals"]} MEAL{"S" if int(data["meals"]) > 1 else ""}',
                f'{name}{" (" + format_phone_number(data["phone"]) + ")" if data["phone"] else "" }',
                row4,
                checksum,
            ]
            print(f'{"Label:".ljust(COL_WIDTH)} {label}')
            csv_writer.writerow(label)

    pdf = args.output / f"{args.spreadsheet.stem}.pdf"
    print(" All done! ✨ 🍰 ✨ ".center(TERMINAL_WIDTH, "-"))
    print(f"Output: {pdf}")
    combine_pdfs(args.build / "pdf", pdf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TDIC Delivery Mapper")
    parser.add_argument("api_token", type=str, help="Google Maps API key")
    parser.add_argument(
        "--spreadsheet",
        default="tdic.csv",
        type=pathlib.Path,
        help="Spreadsheet to use. Default is tdic.csv",
    )
    parser.add_argument(
        "--build",
        default=pathlib.Path(__file__).parent / "build",
        type=pathlib.Path,
        help="Path to build directory. Default is __file__.parent/builds.",
    )
    parser.add_argument(
        "--output",
        default=pathlib.Path.cwd(),
        type=pathlib.Path,
        help="Path to output location. Default is cwd.",
    )

    args = parser.parse_args()

    if not args.spreadsheet.exists():
        raise FileNotFoundError(f"Path to '{args.spreadsheet}' does not exist")

    # clean build dir if they do not exist
    if os.path.exists(args.build):
        shutil.rmtree(args.build)
    for _dir in ["img", "qr", "pdf"]:
        os.makedirs(args.build / _dir)

    print(f"build id: {VERSION}")
    main(args)
