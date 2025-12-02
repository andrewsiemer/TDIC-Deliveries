#!/usr/bin/env python
"""Distribute deliveries geographically among deliverers"""
import argparse
import csv
import json
import pathlib
import re
import time
from io import BytesIO

import numpy as np
import requests
from PIL import Image
from sklearn.cluster import KMeans

# Google Maps API parameters
API_BASE_URL = "https://maps.googleapis.com/maps/api/staticmap"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Colors for different delivery groups (up to 20 groups)
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

# Cache file for geocoded addresses
GEOCODE_CACHE_FILE = "geocode_cache.json"


def load_geocode_cache(cache_file):
    """Load geocode cache from JSON file."""
    if pathlib.Path(cache_file).exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cache file: {e}")
            return {}
    return {}


def save_geocode_cache(cache, cache_file):
    """Save geocode cache to JSON file."""
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save cache file: {e}")


def clean_address(address):
    """
    Clean and normalize address for better geocoding.
    """
    # Remove multiple spaces first
    address = " ".join(address.split())

    # Expand OKC to Oklahoma City (handle various formats)
    address = address.replace(", OKC,", ", Oklahoma City,")
    address = address.replace(",OKC,", ", Oklahoma City,")
    address = address.replace(" OKC,", " Oklahoma City,")
    address = address.replace(" OKC ", " Oklahoma City ")

    # Fix common spacing issues around commas
    address = address.replace(" ,", ",")

    # Fix ordinal numbers with spaces (12 th -> 12th, 1st -> 1st, etc)
    address = re.sub(r"(\d+)\s+(st|nd|rd|th)\b", r"\1\2", address, flags=re.IGNORECASE)

    return address


def geocode_address(address, api_key, cache=None, max_retries=3):
    """
    Geocode an address to get latitude and longitude.
    Retries with exponential backoff on REQUEST_DENIED errors.
    Uses cache to avoid redundant API calls.
    """
    # Clean the address first
    cleaned_address = clean_address(address)

    # Check cache first
    if cache is not None and cleaned_address in cache:
        cached = cache[cleaned_address]
        return cached["lat"], cached["lng"]

    for attempt in range(max_retries):
        response = requests.get(
            GEOCODE_URL, params={"address": cleaned_address, "key": api_key}, timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data["status"] == "OK" and data["results"]:
            location = data["results"][0]["geometry"]["location"]
            lat, lng = location["lat"], location["lng"]

            # Cache the result
            if cache is not None:
                cache[cleaned_address] = {"lat": lat, "lng": lng}

            return lat, lng

        status = data.get("status", "UNKNOWN")

        # Retry on REQUEST_DENIED with exponential backoff
        if status == "REQUEST_DENIED" and attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
            time.sleep(wait_time)
            continue

        # On final attempt or non-retryable error, raise exception
        error_msg = data.get("error_message", "")
        raise ValueError(
            f"Could not geocode address: {address} (cleaned: {cleaned_address}) "
            f"[API Status: {status}]{f' - {error_msg}' if error_msg else ''}"
        )


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    Returns distance in miles.
    """
    from math import asin, cos, radians, sin, sqrt

    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Radius of earth in miles
    r = 3956
    return c * r


def cluster_deliveries_with_max_size(locations, max_size=2, max_distance_miles=5):
    """
    Cluster delivery locations ensuring no cluster exceeds max_size.
    Uses a greedy nearest-neighbor approach with proper distance calculation.
    No two deliveries in a group can be more than max_distance_miles apart.
    """
    if len(locations) == 0:
        return np.array([]), None

    if len(locations) == 1:
        return np.array([0]), None

    coords = [(lat, lng) for lat, lng in locations]
    n = len(coords)

    # Calculate all pairwise distances in miles using haversine
    distances = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                distances[i][j] = haversine_distance(
                    coords[i][0], coords[i][1], coords[j][0], coords[j][1]
                )

    # Identify outliers - deliveries with no neighbors within threshold
    is_outlier = []
    for i in range(n):
        has_close_neighbor = any(
            distances[i][j] <= max_distance_miles for j in range(n) if i != j
        )
        is_outlier.append(not has_close_neighbor)

    # Track which points are assigned
    assigned = [False] * n
    cluster_assignments = [-1] * n
    current_cluster = 0

    # First, assign outliers to their own clusters
    for i in range(n):
        if is_outlier[i]:
            cluster_assignments[i] = current_cluster
            assigned[i] = True
            current_cluster += 1

    # Then cluster non-outliers with max_size and distance constraints
    while not all(assigned):
        # Find first unassigned point
        start_idx = next(i for i in range(n) if not assigned[i])

        # Start new cluster
        cluster_members = [start_idx]
        cluster_assignments[start_idx] = current_cluster
        assigned[start_idx] = True

        # Try to add more deliveries up to max_size
        while len(cluster_members) < max_size:
            # Find nearest unassigned neighbor that satisfies distance constraint
            min_dist = float("inf")
            nearest_idx = None

            for i in range(n):
                if assigned[i]:
                    continue

                # Check distance to ALL current cluster members
                # Ensure new member is within max_distance_miles of all existing members
                valid = True
                max_dist_to_cluster = 0

                for member_idx in cluster_members:
                    member_dist = distances[member_idx][i]
                    if member_dist > max_distance_miles:
                        valid = False
                        break
                    max_dist_to_cluster = max(max_dist_to_cluster, member_dist)

                # Only consider if within threshold of all members
                if valid and max_dist_to_cluster < min_dist:
                    min_dist = max_dist_to_cluster
                    nearest_idx = i

            # Assign nearest valid neighbor to same cluster if found
            if nearest_idx is not None:
                cluster_assignments[nearest_idx] = current_cluster
                assigned[nearest_idx] = True
                cluster_members.append(nearest_idx)
            else:
                break  # No more valid unassigned deliveries

        current_cluster += 1

    return np.array(cluster_assignments), None


def cluster_deliveries(locations, num_deliverers):
    """
    Cluster delivery locations into groups using K-means clustering.
    Returns cluster assignments for each location.
    """
    # Convert to numpy array
    coords = np.array([(lat, lng) for lat, lng in locations])

    # Use K-means clustering
    kmeans = KMeans(n_clusters=num_deliverers, random_state=42, n_init=10)
    cluster_assignments = kmeans.fit_predict(coords)

    return cluster_assignments, kmeans.cluster_centers_


def generate_group_id(cluster_num):
    """
    Generate a unique two-letter group ID from a cluster number.
    Uses base-26 encoding: 0=AA, 1=AB, 2=AC, ..., 25=AZ, 26=BA, etc.
    """
    first_letter = chr(65 + (cluster_num // 26))
    second_letter = chr(65 + (cluster_num % 26))
    return f"{first_letter}{second_letter}"


def create_map_with_markers(deliveries, cluster_assignments, api_key, output_path):
    """
    Create a map with all delivery locations marked by cluster.
    Each marker shows the delivery ID from the CSV.
    """
    # Build markers string for Google Maps Static API
    # Group by cluster but use individual delivery IDs as labels
    markers_by_cluster = {}

    for i, delivery in enumerate(deliveries):
        cluster = cluster_assignments[i]
        lat, lng = delivery["lat"], delivery["lng"]
        delivery_id = delivery["id"]

        if cluster not in markers_by_cluster:
            markers_by_cluster[cluster] = []

        # Store location with its delivery ID
        markers_by_cluster[cluster].append((lat, lng, delivery_id))

    # Build URL with markers grouped by color, labeled with delivery IDs
    markers_param = ""
    for cluster, locations in markers_by_cluster.items():
        color = COLORS[cluster % len(COLORS)]

        # Add each marker individually with its delivery ID as the label
        for lat, lng, delivery_id in locations:
            # Use delivery ID as label (Google Maps limits label to single character for default markers)
            # For full ID visibility, we'll use custom markers or just use color grouping
            markers_param += f"&markers=color:{color}|size:small|{lat},{lng}"

    # Style to hide landmarks, labels, and text
    style_params = (
        "&style=feature:poi|visibility:off"  # Hide points of interest
        "&style=feature:transit|visibility:off"  # Hide transit stations
        "&style=feature:administrative|element:labels|visibility:off"  # Hide admin labels
        "&style=feature:road|element:labels|visibility:off"  # Hide road labels
    )

    # Create map URL - fetch max size from API (2048x2048)
    # We'll request landscape proportions close to letter size ratio (11:8.5 = 1.294:1)
    map_url = (
        f"{API_BASE_URL}?size=500x386&maptype=roadmap"
        f"{style_params}{markers_param}&key={api_key}"
    )

    print(f"Fetching map from Google Maps API...")
    response = requests.get(map_url, timeout=30)
    response.raise_for_status()

    # Load image and resize to letter size landscape at 300 DPI
    # Letter landscape: 11" x 8.5" at 300 DPI = 3300 x 2550 pixels
    img = Image.open(BytesIO(response.content))
    letter_size = (3300, 2550)
    img_resized = img.resize(letter_size, Image.Resampling.LANCZOS)
    img_resized.save(output_path, dpi=(300, 300))
    print(
        f"Map saved to: {output_path} (Letter size landscape: 11x8.5 inches at 300 DPI)"
    )


def main(args):
    """
    Main function to distribute deliveries.
    """
    print(f"Reading deliveries from: {args.input}")

    # Read input CSV
    deliveries = []
    with open(args.input, mode="r", encoding="latin-1") as f:
        csv_reader = csv.reader(f)

        for row in csv_reader:
            # Skip if not enough columns or ID is not numeric
            if len(row) < 13 or not row[0].strip().isnumeric():
                continue

            # Build full address string
            # Columns: 0=ID, 1=Confirmation, 2=Last name, 3=First name, 4=Phone,
            # 5=Address, 6=Apartment, 7=City, 8=State, 9=Zip, 10=Meals, 11=Boxes, 12=Language
            address_parts = [
                row[5].strip(),  # Address
                row[7].strip(),  # City
                row[8].strip(),  # State
                row[9].strip(),  # Zip
            ]
            full_address = ", ".join([part for part in address_parts if part])

            if not full_address.strip():
                continue

            delivery_id = row[0].strip()
            if not delivery_id:
                continue

            deliveries.append(
                {
                    "id": delivery_id,
                    "name": f"{row[3].strip()} {row[2].strip()}".strip(),  # First Last
                    "address": full_address,
                    "phone": row[4].strip(),
                    "meals": row[10].strip(),
                    "language": (
                        row[12].strip().upper()
                        if len(row) > 12 and row[12].strip()
                        else "ENGLISH"
                    ),
                }
            )

    print(f"Found {len(deliveries)} deliveries")

    if len(deliveries) == 0:
        print("No deliveries found in CSV")
        return

    # Load geocode cache
    cache_file = args.output / GEOCODE_CACHE_FILE
    geocode_cache = load_geocode_cache(cache_file)
    print(f"Loaded {len(geocode_cache)} cached addresses")

    # Geocode all addresses
    print("Geocoding addresses...")
    locations = []
    valid_deliveries = []
    cache_hits = 0
    api_calls = 0

    for i, delivery in enumerate(deliveries):
        try:
            # Check if address is in cache before calling
            cleaned_address = clean_address(delivery["address"])
            was_cached = cleaned_address in geocode_cache

            lat, lng = geocode_address(
                delivery["address"], args.api_token, geocode_cache
            )
            delivery["lat"] = lat
            delivery["lng"] = lng
            locations.append((lat, lng))
            valid_deliveries.append(delivery)

            if was_cached:
                cache_hits += 1
                print(
                    f"  [{i+1}/{len(deliveries)}] Geocoded (cached): {delivery['id']}"
                )
            else:
                api_calls += 1
                print(f"  [{i+1}/{len(deliveries)}] Geocoded (API): {delivery['id']}")

            # Small delay only for API calls, not cached results
            if not was_cached:
                time.sleep(0.1)
        except Exception as e:
            print(
                f"  [{i+1}/{len(deliveries)}] Failed to geocode {delivery['id']}: {e}"
            )

    # Save updated cache
    save_geocode_cache(geocode_cache, cache_file)
    print(f"\nSuccessfully geocoded {len(valid_deliveries)} addresses")
    print(f"  - Cache hits: {cache_hits}")
    print(f"  - API calls: {api_calls}")
    print(f"  - Total cached addresses: {len(geocode_cache)}")

    if len(valid_deliveries) == 0:
        print("No valid addresses to cluster")
        return

    # Group deliveries by language first
    deliveries_by_language = {}
    for delivery in valid_deliveries:
        lang = delivery["language"]
        if lang not in deliveries_by_language:
            deliveries_by_language[lang] = []
        deliveries_by_language[lang].append(delivery)

    print(f"\nFound {len(deliveries_by_language)} language groups:")
    for lang, delivs in deliveries_by_language.items():
        print(f"  {lang}: {len(delivs)} deliveries")

    # Cluster deliveries within each language group
    # Calculate minimum groups needed to keep max 2 deliveries per group
    max_group_size = 3
    min_groups_needed = sum(
        (len(delivs) + max_group_size - 1) // max_group_size
        for delivs in deliveries_by_language.values()
    )

    num_deliverers = max(args.deliverers, min_groups_needed)
    print(
        f"\nClustering into {num_deliverers} total groups (max {max_group_size} per group, preserving language grouping)..."
    )
    print(f"Note: Outliers (>5 miles from any delivery) will be single deliveries\n")

    all_cluster_assignments = []
    all_deliveries_ordered = []
    cluster_offset = 0

    # Process each language group
    for lang in sorted(deliveries_by_language.keys()):
        lang_deliveries = deliveries_by_language[lang]
        lang_locations = [(d["lat"], d["lng"]) for d in lang_deliveries]

        # Calculate clusters needed to keep max 2 deliveries per group
        num_lang_clusters = (
            len(lang_deliveries) + max_group_size - 1
        ) // max_group_size

        print(
            f"  Language {lang}: {len(lang_deliveries)} deliveries → {num_lang_clusters} groups"
        )

        if len(lang_deliveries) == 1:
            # Single delivery, assign to one cluster
            lang_cluster_assignments = [0]
        else:
            # Cluster this language group geographically with max size constraint
            lang_cluster_assignments, _ = cluster_deliveries_with_max_size(
                lang_locations, max_size=max_group_size
            )

        # Offset cluster numbers to make them globally unique
        for delivery, cluster in zip(lang_deliveries, lang_cluster_assignments):
            all_deliveries_ordered.append(delivery)
            all_cluster_assignments.append(cluster + cluster_offset)

        cluster_offset += num_lang_clusters

    # Update to use the language-aware clustering results
    valid_deliveries = all_deliveries_ordered
    cluster_assignments = np.array(all_cluster_assignments)

    # Count deliveries per cluster
    cluster_counts = {}
    for cluster in cluster_assignments:
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

    print("\nDeliveries per group:")
    for cluster in sorted(cluster_counts.keys()):
        count = cluster_counts[cluster]
        group_id = generate_group_id(cluster)
        print(f"  Group {group_id}: {count} deliveries")

    # Write output CSV
    output_csv = args.output / "delivery_groups.csv"
    print(f"\nWriting delivery groups to: {output_csv}")

    with open(output_csv, mode="w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "Group",
            "ID",
            "Name",
            "Address",
            "Phone",
            "Language",
            "Meals",
            "Latitude",
            "Longitude",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, delivery in enumerate(valid_deliveries):
            cluster = cluster_assignments[i]
            group_id = generate_group_id(cluster)

            writer.writerow(
                {
                    "Group": group_id,
                    "ID": delivery["id"],
                    "Name": delivery["name"],
                    "Address": delivery["address"],
                    "Phone": delivery["phone"],
                    "Language": delivery["language"],
                    "Meals": delivery["meals"],
                    "Latitude": delivery["lat"],
                    "Longitude": delivery["lng"],
                }
            )

    # Create map
    output_map = args.output / "delivery_map.png"
    print(f"\nCreating map...")
    create_map_with_markers(
        valid_deliveries, cluster_assignments, args.api_token, output_map
    )

    print("\n✨ All done! ✨")
    print(f"  - Map: {output_map}")
    print(f"  - CSV: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distribute deliveries geographically")
    parser.add_argument("api_token", type=str, help="Google Maps API key")
    parser.add_argument(
        "input", type=pathlib.Path, help="Input CSV file with delivery addresses"
    )
    parser.add_argument(
        "deliverers", type=int, help="Number of deliverers/groups to create"
    )
    parser.add_argument(
        "--output",
        default=pathlib.Path.cwd(),
        type=pathlib.Path,
        help="Output directory for map and CSV. Default is current directory.",
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    if not args.output.exists():
        args.output.mkdir(parents=True)

    if args.deliverers < 1:
        raise ValueError("Number of deliverers must be at least 1")

    main(args)
