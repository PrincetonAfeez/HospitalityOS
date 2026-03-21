import csv
from models import MenuItem, Menu

def load_menu_from_csv(file_path: str) -> Menu:
    restaurant_menu = Menu()
    
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Mapping your specific CSV columns to the MenuItem class
                item = MenuItem(
                    category=row['category'],
                    name=row['name'],
                    price=row['unit_price'],       # Matches your CSV header
                    line_inv=row['line_inv'],
                    walk_in=row['walk_in_inv'],    # Matches your CSV header
                    freezer=row['freezer_inv'],    # Matches your CSV header
                    par=row['par_level']           # Matches your CSV header
                )
                restaurant_menu.add_item(item)
        print(f"✅ Successfully loaded {len(restaurant_menu.items)} items into Hospitality OS.")
    except FileNotFoundError:
        print(f"❌ Error: The file '{file_path}' was not found.")
    except KeyError as e:
        print(f"❌ Error: Missing column in CSV: {e}")
        
    return restaurant_menu