import csv

menu_data = [
    {"category": "Shareables", "name": "Baked Jumbo Wings", "unit_price": 18.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Buffalo Cauliflower", "unit_price": 15.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Charcuterie Board", "unit_price": 25.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Crispy Burrata", "unit_price": 23.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Four Cheese Dip", "unit_price": 18.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Four Cheese Mac", "unit_price": 15.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Guac & Chips", "unit_price": 15.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Hummus and Pita", "unit_price": 22.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Rustic Bread", "unit_price": 19.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Short Rib Fries", "unit_price": 23.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Shareables", "name": "Waygu Meatballs", "unit_price": 20.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Branzino", "unit_price": 38.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Crusted Tuna", "unit_price": 25.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Duck Confit", "unit_price": 32.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Filet Steak Sliders", "unit_price": 27.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Korean Short Ribs", "unit_price": 29.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Lamb Shank", "unit_price": 56.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Rack of Lamb", "unit_price": 34.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Roasted Greek Chicken", "unit_price": 29.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Seabass Ratatouille", "unit_price": 36.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Seafood Pasta", "unit_price": 27.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Short Rib Pappardelle", "unit_price": 32.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Steak Au Poivre", "unit_price": 48.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Steak Frites", "unit_price": 48.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Entrées", "name": "Wagyu Burger", "unit_price": 26.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Sides", "name": "Crisps", "unit_price": 12.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Sides", "name": "French Fries", "unit_price": 12.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Sides", "name": "Greek Salad", "unit_price": 10.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Sides", "name": "Sweet Fries", "unit_price": 12.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Sides", "name": "Truffle Fries", "unit_price": 15.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Salads", "name": "Asian Chicken Salad", "unit_price": 20.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Salads", "name": "English Garden Salad", "unit_price": 18.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Salads", "name": "Goat Cheese Beets", "unit_price": 18.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Salads", "name": "Heirloom Salad", "unit_price": 15.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Desserts", "name": "Apple Streudel", "unit_price": 14.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Desserts", "name": "Brownie", "unit_price": 14.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Desserts", "name": "Burbon Bread Pudding", "unit_price": 14.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Desserts", "name": "Cheesecake", "unit_price": 14.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Desserts", "name": "Creme Brulee", "unit_price": 14.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20},
    {"category": "Desserts", "name": "Tiramisu", "unit_price": 14.00, "line_inv": 10, "walk_in_inv": 5, "freezer_inv": 5, "par_level": 20}
]

# We write this to "menu.csv"
with open("menu.csv", "w", newline="", encoding="utf-8") as file:
    # Notice we include 'category' because it's in your dict, 
    # but the Auditor script looks specifically for 'name', 'unit_price', etc.
    fieldnames = ["category", "name", "unit_price", "line_inv", "walk_in_inv", "freezer_inv", "par_level"]
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    
    writer.writeheader()
    writer.writerows(menu_data)

<<<<<<< HEAD
print("✅ menu.csv generated! The KeyError should now be resolved.")
=======
print("✅ menu.csv generated! The KeyError should now be resolved.")
>>>>>>> master
