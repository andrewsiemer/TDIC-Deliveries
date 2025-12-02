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
import uuid
from datetime import datetime
from io import BytesIO

import pyqrcode
import requests
from natsort import natsorted
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.colors import gray
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

# Google Maps parameters
API_BASE_URL = "https://maps.googleapis.com/maps/api/staticmap"
ZOOM = 15

# QR dode parameters
GOOGLE_BASE_URL = "https://www.google.com/maps/place/"
APPLE_BASE_URL = "https://maps.apple.com/?daddr="

START_ADDRESS = "2221 E Memorial Rd, Edmond, OK 73013"

VERSION = uuid.uuid4()

HCENTER = 300
RADIUS = 10

TERMINAL_WIDTH = 100
COL_WIDTH = 15


def format_phone_number(number):
    """
    Format the phone number to be in the format XXX-XXX-XXXX.
    """

    if len(digits := "".join(c for c in number if c.isdigit())) != 10:
        raise ValueError(f"Error formatting phone number {number}, skipping ...")

    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def hash_dict(input_dict):
    """
    Hash the dictionary to a unique checksum.
    """
    return hashlib.sha256(json.dumps(input_dict, sort_keys=True).encode()).hexdigest()


def combine_pdfs(input_dir, output_file):
    """
    Combine the PDF files in the input directory into a single PDF file.
    """
    pdf_writer = PdfWriter()
    for pdf_file in natsorted(
        [file for file in os.listdir(input_dir) if file.endswith(".pdf")]
    ):
        pdf_path = os.path.join(input_dir, pdf_file)

        with open(pdf_path, "rb") as pdf:
            pdf_reader = PdfReader(pdf)
            # Add each page to the writer object
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

    # Write the combined PDF to the output file
    with open(output_file, "wb") as output_pdf:
        pdf_writer.write(output_pdf)


def main(args):
    """
    Main function to process the spreadsheet and create the delivery documents.
    """
    with open(args.spreadsheet, mode="r", encoding="latin-1") as in_file:
        csv_reader = csv.reader(in_file, delimiter=",")

        for row in csv_reader:

            # read row of csv
            data = {}

            # Skip if IDs are specified and this ID is not in the list
            if not row[0].isnumeric() or (args.ids and row[0].strip() not in args.ids):
                continue

            print(f" #{row[0].strip()} ".center(TERMINAL_WIDTH, "-"))

            data["index"] = row[0].strip()
            data["last_name"] = row[2].strip()
            data["first_name"] = row[3].strip()
            data["phone"] = row[4].strip()
            data["address"] = row[5].strip()
            data["apartment"] = row[6].strip()
            data["city"] = row[7].strip()
            data["state"] = row[8].strip()
            data["zip_code"] = row[9].strip()
            data["meals"] = row[10].strip()
            data["boxes"] = row[11].strip()
            data["language"] = row[12].strip()
            data["comments"] = row[13].strip()

            if not data.get("meals") or int(data["meals"]) <= 0:
                print("Meals missing or invalid, skipping ...")
                continue

            # Default boxes to 1 if not specified or invalid
            try:
                num_boxes = int(data["boxes"]) if data.get("boxes") else 1
                if num_boxes <= 0:
                    num_boxes = 1
            except ValueError:
                num_boxes = 1

            index = int(data["index"])

            # Hash dict unique checksum
            checksum = hash_dict(data)
            print(f'{"Checksum:".ljust(COL_WIDTH)} {checksum}')

            # printed name format
            name = (f'{data["first_name"]} {data["last_name"]}').title().strip()

            # create pdf for delivery - standard US Letter size (8.5" x 11")
            canvas = Canvas(f'{args.build}/pdf/{data["index"]}.pdf', pagesize=letter)

            # starting locations on pdf for text formatting
            # Map dimensions: 4:3 aspect ratio
            map_width = 500
            map_height = 375
            y1 = 343  # Moved up by 3
            x1 = 50

            # pdf header
            canvas.setFont("Helvetica-Bold", 18)
            canvas.drawCentredString(
                HCENTER, 753, f"THANKSGIVING DAY IN THE CITY {datetime.now().year}"
            )
            canvas.setFont("Helvetica", 12)
            canvas.drawCentredString(HCENTER, 733, "Memorial Road Church of Christ")

            # handle address
            addr = f'{data["address"].upper()}, {data["apartment"]}'.upper()
            addr2 = f'{data["city"]}, {data["state"]} {data["zip_code"]}'.upper()

            row4 = f"{addr.strip()} {addr2.strip()}"

            # draw image placeholder
            canvas.drawCentredString(HCENTER, y1 + map_height / 2, row4)

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
                # google static map api create link for main map (4:3 aspect ratio)
                api = (
                    f"{API_BASE_URL}?center={location}&zoom={ZOOM}&size=666x500&"
                    f"markers={location}&key={args.api_token}"
                )
                print(f'{"MAPS API:".ljust(COL_WIDTH)} {api}')
                response = requests.get(api, timeout=10)
                response.raise_for_status()

                img = Image.open(BytesIO(response.content)).convert("RGBA")
                img.save(f'{args.build}/img/{data["index"]}.png')

                # draw main map with 4:3 aspect ratio
                canvas.drawInlineImage(img, x1, y1, map_width, map_height)

                # Create route overview map (zoomed out with path, 4:3 aspect ratio)
                start_location = START_ADDRESS.replace(" ", "+")
                route_api = (
                    f"{API_BASE_URL}?size=600x450&"
                    f"markers=color:green|label:S|{start_location}&"
                    f"markers=color:red|label:D|{location}&"
                    f"path=color:0x0000ffff|weight:3|{start_location}|{location}&"
                    f"key={args.api_token}"
                )
                print(f'{"ROUTE API:".ljust(COL_WIDTH)} {route_api}')
                route_response = requests.get(route_api, timeout=10)
                route_response.raise_for_status()

                route_img = Image.open(BytesIO(route_response.content)).convert("RGBA")
                route_img.save(f'{args.build}/img/{data["index"]}-route.png')

                # add rounded corners to main map
                canvas.setStrokeColorRGB(1, 1, 1)
                canvas.setLineWidth(6)
                canvas.roundRect(x1 - 3, y1 - 3, map_width + 6, map_height + 6, 13)
                canvas.setLineWidth(1)
                canvas.setStrokeColorRGB(0, 0, 0)

                # Draw smaller route map overlaid in bottom right corner (4:3 aspect ratio)
                # Position: bottom right of main map with some padding
                overlay_width = 150
                overlay_height = int(overlay_width * 3 / 4)  # 4:3 ratio = 112.5
                overlay_x = (
                    x1 + map_width - overlay_width - 10
                )  # 10px padding from right edge
                overlay_y = y1 + 10  # 10px padding from bottom edge

                canvas.drawInlineImage(
                    route_img, overlay_x, overlay_y, overlay_width, overlay_height
                )

                # Add rounded border around overlay map to complement main map
                canvas.setStrokeColorRGB(1, 1, 1)
                canvas.setLineWidth(4)
                canvas.roundRect(
                    overlay_x - 2,
                    overlay_y - 2,
                    overlay_width + 4,
                    overlay_height + 4,
                    8,
                )
                canvas.setLineWidth(1)
                canvas.setStrokeColorRGB(0, 0, 0)
                canvas.roundRect(overlay_x, overlay_y, overlay_width, overlay_height, 6)

                # Generate QR codes for use in instructions section below
                url = APPLE_BASE_URL + location
                print(f'{"APPLE MAPS:".ljust(COL_WIDTH)} {url}')
                qr = pyqrcode.create(url, error="L", version=6)
                qr.png(f'{args.build}/qr/apple-{data["index"]}.png', scale=3)

                url = GOOGLE_BASE_URL + location
                print(f'{"GOOGLE MAPS:".ljust(COL_WIDTH)} {url}')
                qr = pyqrcode.create(url, error="L", version=6)
                qr.png(f'{args.build}/qr/google-{data["index"]}.png', scale=3)

            # add map frame
            canvas.roundRect(x1, y1, map_width, map_height, RADIUS, fill=0)

            # Two-column layout below the map
            y1 -= 30  # Space below map
            col_width = (map_width - 20) / 2  # Two equal columns with 20px gap
            left_col_x = x1
            right_col_x = x1 + col_width + 20

            # LEFT COLUMN - DELIVERY INSTRUCTIONS
            canvas.setFont("Helvetica-Bold", 14)
            canvas.drawString(left_col_x, y1, "DELIVERY INSTRUCTIONS")

            instructions_y = y1 - 25
            canvas.setFont("Helvetica", 9)

            # Numbered delivery steps with text wrapping
            instructions = [
                f"1. Pick up {num_boxes} box{'es' if num_boxes > 1 else ''}{' and international events handout' if data.get('language') else ''}.",  # pylint: disable=line-too-long
                "2. Scan one of the QR codes below to get directions.",
                "3. Call the recipient to let them know you're on the way.",
                f"4. Deliver the box(es) to the recipient's address and wish them a Happy Thanksgiving from {'MRCC' if index > 699 or index < 400 else 'Forest Park'}. If no one answers, leave on doorstep.",  # pylint: disable=line-too-long
                "5. Delivery issues? Call Jason Davis 405-706-9563.",
            ]

            # Wrap and draw each instruction
            wrapper = textwrap.TextWrapper(width=57)  # Fits left column width
            for instruction in instructions:
                lines = wrapper.wrap(text=instruction)
                for i, line in enumerate(lines):
                    # First line gets the full text, subsequent lines are indented
                    if i == 0:
                        canvas.drawString(left_col_x, instructions_y, line)
                    else:
                        canvas.drawString(left_col_x + 11, instructions_y, line)
                    instructions_y -= 15  # Increased line spacing

            # Add QR codes in left column
            if data["address"]:
                instructions_y -= 12

                # Apple Maps QR
                canvas.drawInlineImage(
                    "static/apple-maps.png",
                    left_col_x + 30,
                    instructions_y - 5,
                    60,
                    14,
                )
                qr_y = instructions_y - 65
                canvas.drawInlineImage(
                    f'{args.build}/qr/apple-{data["index"]}.png',
                    left_col_x + 30,
                    qr_y,
                    60,
                    60,
                )

                # Google Maps QR
                canvas.drawInlineImage(
                    "static/google-maps.png",
                    left_col_x + 111,
                    instructions_y - 5,
                    80,
                    19,
                )
                canvas.drawInlineImage(
                    f'{args.build}/qr/google-{data["index"]}.png',
                    left_col_x + 120,
                    qr_y,
                    60,
                    60,
                )

            # RIGHT COLUMN - DELIVERY INFORMATION
            canvas.setFont("Helvetica-Bold", 14)
            canvas.drawString(right_col_x, y1, "DELIVERY INFORMATION")

            info_y = y1 - 25
            canvas.setFont("Helvetica-Bold", 10)
            label_offset = 60

            # Name
            canvas.drawString(right_col_x, info_y, "Name:")
            canvas.setFont("Helvetica", 10)
            canvas.drawString(right_col_x + label_offset, info_y, name)
            info_y -= 18

            # Phone
            if data["phone"]:
                canvas.setFont("Helvetica-Bold", 10)
                canvas.drawString(right_col_x, info_y, "Phone:")
                canvas.setFont("Helvetica", 10)

                try:
                    formatted_phone = format_phone_number(data["phone"])
                except ValueError:
                    print(
                        f"Error formatting phone number {data['phone']}, skipping ..."
                    )
                    formatted_phone = data["phone"].strip()

                canvas.drawString(
                    right_col_x + label_offset,
                    info_y,
                    formatted_phone,
                )
                info_y -= 18

            # Address
            if data["address"]:
                canvas.setFont("Helvetica-Bold", 10)
                canvas.drawString(right_col_x, info_y, "Address:")
                canvas.setFont("Helvetica", 10)

                if data["apartment"] != "":
                    canvas.drawString(right_col_x + label_offset, info_y, addr)
                else:
                    addr = data["address"].upper()
                    canvas.drawString(right_col_x + label_offset, info_y, addr)
                info_y -= 15
                canvas.drawString(right_col_x + label_offset, info_y, addr2)
                info_y -= 18

            # Meals (with box count in parentheses if multiple boxes)
            canvas.setFont("Helvetica-Bold", 10)
            canvas.drawString(right_col_x, info_y, "Meals:")
            canvas.setFont("Helvetica", 10)
            meals_text = (
                f'{data["meals"]} ({num_boxes} box{"es" if num_boxes > 1 else ""})'
            )
            canvas.drawString(right_col_x + label_offset, info_y, meals_text)
            info_y -= 18

            # Comments
            if data["comments"] != "":
                canvas.setFont("Helvetica-Bold", 10)
                canvas.drawString(right_col_x, info_y, "Comments:")
                canvas.setFont("Helvetica", 10)
                wrapper = textwrap.TextWrapper(width=40)  # Narrower for column
                word_list = wrapper.wrap(text=data["comments"])
                for i, element in enumerate(word_list):
                    if i == 0:
                        # First line on same line as "Comments:"
                        canvas.drawString(right_col_x + label_offset, info_y, element)
                        info_y -= 12
                    else:
                        # Subsequent lines below
                        canvas.drawString(right_col_x + label_offset, info_y, element)
                        info_y -= 12

            # Three boxes at bottom: ID (grey), Language, Box Count
            box_y = 33  # Starting y position (moved up by 3)
            id_box_height = 60
            box_gap = 10

            # Calculate widths for three boxes
            id_box_width = 120
            language_box_width = 190
            box_count_width = (
                map_width - id_box_width - language_box_width - (2 * box_gap)
            )

            # FIRST BOX (left) - ID number in grey
            id_box_x = x1  # Align with map

            # Draw grey border
            canvas.setStrokeColorRGB(0.5, 0.5, 0.5)  # Grey border
            canvas.setLineWidth(1)
            canvas.roundRect(id_box_x, box_y, id_box_width, id_box_height, RADIUS)

            # Draw "For Admin purposes only" text in small grey at top (15px padding from top)
            canvas.setFillColorRGB(0.5, 0.5, 0.5)  # Grey text
            canvas.setFont("Helvetica", 9)
            small_text_y = box_y + id_box_height - 17  # 15px from top
            canvas.drawCentredString(
                id_box_x + id_box_width / 2,
                small_text_y,
                "For Admin purposes only",
            )

            # Draw ID text in grey (centered below small text)
            canvas.setFont("Helvetica", 32)
            large_text_y = box_y + 11  # Lower position for better balance
            canvas.drawCentredString(
                id_box_x + id_box_width / 2,
                large_text_y,
                f"#{index}",
            )

            # Reset stroke and fill color to black
            canvas.setStrokeColorRGB(0, 0, 0)
            canvas.setFillColorRGB(0, 0, 0)
            canvas.setLineWidth(1)

            # SECOND BOX (middle) - Language
            language_box_x = id_box_x + id_box_width + box_gap
            canvas.roundRect(
                language_box_x, box_y, language_box_width, id_box_height, RADIUS
            )

            # Draw "The recipient speaks" text at top
            canvas.setFont("Helvetica", 9)
            canvas.drawCentredString(
                language_box_x + language_box_width / 2,
                small_text_y,
                "The recipient speaks",
            )

            # Draw language (default to ENGLISH if not specified)
            canvas.setFont("Helvetica", 32)
            language_text = data["language"] if data["language"] else "ENGLISH"
            canvas.drawCentredString(
                language_box_x + language_box_width / 2,
                large_text_y,
                language_text,
            )

            # THIRD BOX (right) - Box count
            box_count_x = language_box_x + language_box_width + box_gap
            canvas.roundRect(box_count_x, box_y, box_count_width, id_box_height, RADIUS)

            # Draw "For this delivery, you will need" text at top (15px padding from top)
            canvas.setFont("Helvetica", 9)
            small_text_y = box_y + id_box_height - 17  # 15px from top
            canvas.drawCentredString(
                box_count_x + box_count_width / 2,
                small_text_y,
                "For this delivery, you will need",
            )

            # Draw box count (centered below small text)
            canvas.setFont("Helvetica", 32)
            large_text_y = box_y + 11  # Lower position for better balance
            box_str = f'{num_boxes} BOX{"ES" if num_boxes > 1 else ""}'
            canvas.drawCentredString(
                box_count_x + box_count_width / 2,
                large_text_y,
                box_str,
            )

            # draw Build data
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(gray)
            canvas.drawCentredString(
                HCENTER, 21, f"Checksum: {checksum} - Build: {VERSION}"
            )

            # save canvas to file
            canvas.save()

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
        default=pathlib.Path.cwd() / "build",
        type=pathlib.Path,
        help="Path to build directory. Default is cwd/builds.",
    )
    parser.add_argument(
        "--output",
        default=pathlib.Path.cwd(),
        type=pathlib.Path,
        help="Path to output location. Default is cwd.",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        type=str,
        help="List of IDs to process (e.g., --ids 100 101 102). If not specified, processes all entries.",  # pylint: disable=line-too-long
    )

    args = parser.parse_args()

    if not args.output.exists():
        raise FileNotFoundError(f"Path to '{args.output}' does not exist")

    if not args.spreadsheet.exists():
        raise FileNotFoundError(f"Path to '{args.spreadsheet}' does not exist")

    # clean build dir if they do not exist
    if os.path.exists(args.build):
        shutil.rmtree(args.build)
    for _dir in ["img", "qr", "pdf"]:
        os.makedirs(args.build / _dir)

    print(f"build id: {VERSION}")
    main(args)
