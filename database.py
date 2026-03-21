import csv
import json
import os
from decimal import Decimal
from models import MenuItem, Menu

def load_menu_from_csv(file_path: str) -> Menu:
    restaurant_menu = Menu()
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                item = MenuItem(
                    category=row['category'],
                    name=row['name'],
                    price=row['unit_price'],
                    line_inv=row['line_inv'],
                    walk_in=row['walk_in_inv'],
                    freezer=row['freezer_inv'],
                    par=row['par_level']
                )
                restaurant_menu.add_item(item)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
    return restaurant_menu

def save_system_state(menu, net_sales, filename="restaurant_state.json"):
    state = {
        "net_sales": float(net_sales),
        "inventory": {item.name: {
            "line": item.line_inv,
            "walk_in": item.walk_in_inv,
            "freezer": item.freezer_inv
        } for item in menu.items}
    }
    with open(filename, "w") as f:
        json.dump(state, f, indent=4)

def load_system_state(menu, filename="restaurant_state.json"):
    try:
        with open(filename, "r") as f:
            state = json.load(f)
            for item in menu.items:
                if item.name in state["inventory"]:
                    inv = state["inventory"][item.name]
                    item.line_inv = inv["line"]
                    item.walk_in_inv = inv["walk_in"]
                    item.freezer_inv = inv["freezer"]
            return Decimal(str(state.get("net_sales", "0.00")))
    except (FileNotFoundError, json.JSONDecodeError):
        return Decimal("0.00")

def initialize_system_state(menu):
    """Restore your original 'New Service Day' logic"""
    filename = "restaurant_state.json"
    print("\n" + "="*35)
    print(f"{'SYSTEM INITIALIZATION':^35}")
    print("="*35)
    
    choice = input("Is this a NEW service day? (yes/no): ").strip().lower()

    if choice == "yes":
        print("☀️  Starting New Service Day. Resetting inventory...")
        # Create fresh state based on menu objects
        save_system_state(menu, Decimal("0.00"))
        return Decimal("0.00")
    else:
        print("🌙 Continuing Current Shift...")
        return load_system_state(menu)