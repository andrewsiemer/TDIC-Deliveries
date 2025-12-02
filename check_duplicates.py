#!/usr/bin/env python3
"""
Script to check for duplicate names and/or locations in a CSV file.
"""

import csv
import sys
from collections import defaultdict
from typing import Dict, List, Tuple


def check_duplicates(csv_file: str) -> None:
    """
    Check for duplicate names and addresses in the CSV file.
    
    Args:
        csv_file: Path to the CSV file to check
    """
    # Dictionaries to track duplicates
    # Key: (last_name, first_name), Value: list of row data
    names: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    
    # Key: (address, apartment, city, zip), Value: list of row data
    addresses: Dict[Tuple[str, str, str, str], List[Dict]] = defaultdict(list)
    
    # Read the CSV file
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Skip empty rows
                if not row.get('ID'):
                    continue
                
                # Track by name (Last name, First name)
                last_name = row.get('Last name', '').strip()
                first_name = row.get('First name', '').strip()
                
                if last_name and first_name:
                    name_key = (last_name, first_name)
                    names[name_key].append(row)
                
                # Track by address (Address, Apartment, City, Zip)
                address = row.get('Address', '').strip()
                apartment = row.get('Apartment', '').strip()
                city = row.get('City', '').strip()
                zip_code = row.get('Zip', '').strip()
                
                if address:  # At least need an address
                    address_key = (address, apartment, city, zip_code)
                    addresses[address_key].append(row)
    
    except FileNotFoundError:
        print(f"Error: File '{csv_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    # Report duplicate names
    print("=" * 80)
    print("DUPLICATE NAMES CHECK")
    print("=" * 80)
    
    duplicate_names = {k: v for k, v in names.items() if len(v) > 1}
    
    if duplicate_names:
        print(f"\nFound {len(duplicate_names)} duplicate name(s):\n")
        
        for (last_name, first_name), entries in sorted(duplicate_names.items()):
            print(f"\n{last_name}, {first_name} ({len(entries)} occurrences):")
            for entry in entries:
                id_num = entry.get('ID', 'N/A')
                phone = entry.get('Phone', 'N/A')
                address = entry.get('Address', 'N/A')
                apartment = entry.get('Apartment', '')
                city = entry.get('City', 'N/A')
                
                full_address = f"{address}"
                if apartment:
                    full_address += f", {apartment}"
                full_address += f", {city}"
                
                print(f"  - ID {id_num}: {phone} | {full_address}")
    else:
        print("\n✓ No duplicate names found.")
    
    # Report duplicate addresses
    print("\n" + "=" * 80)
    print("DUPLICATE ADDRESSES CHECK")
    print("=" * 80)
    
    duplicate_addresses = {k: v for k, v in addresses.items() if len(v) > 1}
    
    if duplicate_addresses:
        print(f"\nFound {len(duplicate_addresses)} duplicate address(es):\n")
        
        for (address, apartment, city, zip_code), entries in sorted(duplicate_addresses.items()):
            full_addr = f"{address}"
            if apartment:
                full_addr += f", {apartment}"
            full_addr += f", {city}, {zip_code}"
            
            print(f"\n{full_addr} ({len(entries)} occurrences):")
            for entry in entries:
                id_num = entry.get('ID', 'N/A')
                last_name = entry.get('Last name', 'N/A')
                first_name = entry.get('First name', 'N/A')
                phone = entry.get('Phone', 'N/A')
                
                print(f"  - ID {id_num}: {last_name}, {first_name} | {phone}")
    else:
        print("\n✓ No duplicate addresses found.")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total unique names: {len(names)}")
    print(f"Duplicate names: {len(duplicate_names)}")
    print(f"Total unique addresses: {len(addresses)}")
    print(f"Duplicate addresses: {len(duplicate_addresses)}")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        # Default to draft.csv in the same directory as the script
        csv_file = "draft.csv"
    
    print(f"Checking duplicates in: {csv_file}\n")
    check_duplicates(csv_file)

