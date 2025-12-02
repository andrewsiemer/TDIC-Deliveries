#!/usr/bin/env python
"""Draw a high-resolution map with routes for each delivery group"""
import argparse
import csv
import pathlib
from io import BytesIO

import requests
from PIL import Image

# Google Maps API parameters
API_BASE_URL = "https://maps.googleapis.com/maps/api/staticmap"

# Colors for different delivery groups
COLORS = [
    "red",
    "blue",
    "green",
    "yellow",
    "purple",
    "orange",
    "pink",
    "brown",
    "gray",
    "cyan",
    "magenta",
    "lime",
    "navy",
    "teal",
    "olive",
    "maroon",
    "aqua",
    "fuchsia",
    "silver",
    "black",
]


def get_color_hex(color_name):
    """Convert color name to hex code (without #)"""
    color_map = {
        "red": "FF0000",
        "blue": "0000FF",
        "green": "00FF00",
        "yellow": "FFFF00",
        "purple": "800080",
        "orange": "FFA500",
        "pink": "FFC0CB",
        "brown": "A52A2A",
        "gray": "808080",
        "cyan": "00FFFF",
        "magenta": "FF00FF",
        "lime": "00FF00",
        "navy": "000080",
        "teal": "008080",
        "olive": "808000",
        "maroon": "800000",
        "aqua": "00FFFF",
        "fuchsia": "FF00FF",
        "silver": "C0C0C0",
        "black": "000000",
    }
    return color_map.get(color_name, "FF0000")


def create_route_map(deliveries_by_group, api_key, output_path):
    """Create map with paths and markers for single deliveries"""
    print(f"Creating route map with {len(deliveries_by_group)} groups...")

    # Build paths and markers
    path_params = []
    marker_params = []

    for group_idx, (group_id, deliveries) in enumerate(
        sorted(deliveries_by_group.items())
    ):
        color = COLORS[group_idx % len(COLORS)]
        hex_color = get_color_hex(color)

        if len(deliveries) == 1:
            # Single delivery - add as a marker dot
            d = deliveries[0]
            marker_params.append(
                f"&markers=color:0x{hex_color}|size:mid|{d['lat']},{d['lng']}"
            )
        else:
            # Multiple deliveries - add path connecting them
            path_points = "|".join([f"{d['lat']},{d['lng']}" for d in deliveries])
            path_params.append(f"&path=color:0x{hex_color}FF|weight:5|{path_points}")

    all_paths = "".join(path_params)
    all_markers = "".join(marker_params)

    # Simplified styling
    style_params = (
        "&style=feature:poi|visibility:off&style=feature:transit|visibility:off"
    )

    # Create map URL
    map_url = (
        f"{API_BASE_URL}?size=2048x2048&scale=2&maptype=roadmap"
        f"{style_params}{all_markers}{all_paths}&key={api_key}"
    )

    print(f"URL length: {len(map_url)} characters")

    if len(map_url) > 8192:
        print(f"\nERROR: URL too long ({len(map_url)} chars, limit 8192)")
        print("Splitting into 3 separate maps...")

        # Split groups into 3 maps
        group_items = list(sorted(deliveries_by_group.items()))
        chunk_size = len(group_items) // 3 + 1

        for chunk_idx in range(3):
            start = chunk_idx * chunk_size
            end = min(start + chunk_size, len(group_items))
            if start >= len(group_items):
                break

            chunk_groups = dict(group_items[start:end])
            chunk_path = output_path.parent / f"delivery_routes_part{chunk_idx + 1}.png"

            print(f"\nCreating part {chunk_idx + 1}/3 (groups {start+1}-{end})...")
            create_single_map(chunk_groups, api_key, chunk_path, start)

        print(f"\n✨ Created 3 separate map files! ✨")
        return

    # Single map fits in URL
    print(f"Fetching map from Google Maps API...")
    response = requests.get(map_url, timeout=60)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content))
    img.save(output_path, dpi=(300, 300))

    print(f"Map saved to: {output_path}")
    print(f"Image size: {img.size[0]}x{img.size[1]} pixels")


def create_single_map(deliveries_by_group, api_key, output_path, color_offset=0):
    """Create a single map for a subset of groups"""
    path_params = []
    marker_params = []

    for group_idx, (group_id, deliveries) in enumerate(deliveries_by_group.items()):
        color = COLORS[(group_idx + color_offset) % len(COLORS)]
        hex_color = get_color_hex(color)

        if len(deliveries) == 1:
            # Single delivery - add as marker
            d = deliveries[0]
            marker_params.append(
                f"&markers=color:0x{hex_color}|size:mid|{d['lat']},{d['lng']}"
            )
        else:
            # Multiple deliveries - add path
            path_points = "|".join([f"{d['lat']},{d['lng']}" for d in deliveries])
            path_params.append(f"&path=color:0x{hex_color}FF|weight:5|{path_points}")

    all_paths = "".join(path_params)
    all_markers = "".join(marker_params)
    style_params = (
        "&style=feature:poi|visibility:off&style=feature:transit|visibility:off"
    )

    map_url = (
        f"{API_BASE_URL}?size=2048x2048&scale=2&maptype=roadmap"
        f"{style_params}{all_markers}{all_paths}&key={api_key}"
    )

    print(f"  URL length: {len(map_url)} characters")
    response = requests.get(map_url, timeout=60)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content))
    img.save(output_path, dpi=(300, 300))
    print(f"  Saved: {output_path} ({img.size[0]}x{img.size[1]} px)")


def main(args):
    """Main function"""
    print(f"Reading delivery groups from: {args.input}")

    # Read CSV and group by Group ID
    deliveries_by_group = {}

    with open(args.input, mode="r", encoding="utf-8") as f:
        csv_reader = csv.DictReader(f)

        for row in csv_reader:
            group_id = row.get("Group", "").strip()
            if not group_id:
                continue

            try:
                lat = float(row.get("Latitude", 0))
                lng = float(row.get("Longitude", 0))
            except (ValueError, TypeError):
                continue

            if group_id not in deliveries_by_group:
                deliveries_by_group[group_id] = []

            deliveries_by_group[group_id].append(
                {
                    "id": row.get("ID", "").strip(),
                    "name": row.get("Name", "").strip(),
                    "lat": lat,
                    "lng": lng,
                }
            )

    print(f"Found {len(deliveries_by_group)} delivery groups")
    total_deliveries = sum(len(d) for d in deliveries_by_group.values())
    print(f"Total deliveries: {total_deliveries}")

    # Create the map
    output_path = args.output / "delivery_routes_map.png"
    create_route_map(deliveries_by_group, args.api_token, output_path)

    print("\n✨ All done! ✨")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Draw delivery route map")
    parser.add_argument("api_token", type=str, help="Google Maps API key")
    parser.add_argument(
        "input", type=pathlib.Path, help="Input CSV file with delivery groups"
    )
    parser.add_argument(
        "--output",
        default=pathlib.Path.cwd(),
        type=pathlib.Path,
        help="Output directory for map. Default is current directory.",
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    if not args.output.exists():
        args.output.mkdir(parents=True)

    main(args)
