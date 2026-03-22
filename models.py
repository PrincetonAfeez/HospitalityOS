from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
# Import your new settings
from settings.restaurant_defaults import TAX_RATE

class MenuItem:
    def __init__(self, category, name, price, line_inv, walk_in, freezer, par):
        self.category = category
        self.name = name
        self.price = Decimal(str(price)) # Use Decimal for money
        self.line_inv = int(line_inv)
        self.walk_in_inv = int(walk_in)
        self.freezer_inv = int(freezer)
        self.par_level = int(par)
    
    def to_dict(self):
        """Converts MenuItem to a dictionary for JSON storage."""
        return {
            "category": self.category,
            "name": self.name,
            "price": str(self.price),  # JSON doesn't support Decimal, convert to string
            "line_inv": self.line_inv,
            "walk_in_inv": self.walk_in_inv,
            "freezer_inv": self.freezer_inv,
            "par_level": self.par_level,
            "total_inventory": self.total_inventory
        }
    @property
    def total_inventory(self):
        return self.line_inv + self.walk_in_inv + self.freezer_inv

    def __str__(self):
        return f"[{self.category:10}] {self.name:25} ${self.price:>6.2f}"

class Menu:
    def __init__(self):
        self.items = []

    def add_item(self, item: MenuItem):
        self.items.append(item)

    def find_item(self, name: str) -> MenuItem:
        for item in self.items:
            if item.name.lower() == name.lower():
                return item
        return None
    
class Cart:
    def __init__(self):
        self.items = []
        # Task 4: Link to settings.py
        self.tax_rate = Decimal(str(TAX_RATE))

    def add_to_cart(self, item: MenuItem):
        if item.line_inv > 0:
            self.items.append(item)
            item.line_inv -= 1
            print(f"✅ Added {item.name}. Subtotal: ${self.subtotal:.2f}")
        else:
            print(f"⚠️  CANNOT ADD: {item.name} is 86'd (Out of stock on line)!")
    
    def remove_from_cart(self, item_name: str):
        for i, item in enumerate(self.items):
            if item.name.lower() == item_name.lower():
                item.line_inv += 1
                self.items.pop(i)
                print(f"🗑️ Removed {item.name}. (Inventory Restored)")
                return True
        print(f"❌ '{item_name}' not found in cart.")
        return False

    @property
    def subtotal(self) -> Decimal:
        return sum((item.price for item in self.items), Decimal("0.00"))

    @property
    def sales_tax(self) -> Decimal:
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def grand_total(self) -> Decimal:
        return self.subtotal + self.sales_tax
    
# --- Transaction is now its own class (NOT indented) ---
class Transaction:
    def __init__(self, cart: Cart, table_num: int):
        self.cart = cart
        self.table_num = table_num
        self.tip = Decimal("0.00")
        self.split_count = 1

    def apply_tip(self, amount: str):
        try:
            if "%" in amount:
                percent = Decimal(amount.replace("%", "")) / 100
                self.tip = (self.cart.subtotal * percent).quantize(Decimal("0.01"), ROUND_HALF_UP)
            else:
                self.tip = Decimal(amount.replace("$", "")).quantize(Decimal("0.01"), ROUND_HALF_UP)
            return True
        except:
            print("Invalid tip format.")
            return False

    def to_dict(self):
        """Converts the full Transaction and its Cart to a dictionary with a timestamp."""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "table_num": self.table_num,
            "items": [item.to_dict() for item in self.cart.items],
            "financials": {
                "subtotal": str(self.cart.subtotal),
                "tax": str(self.cart.sales_tax),
                "tip": str(self.tip),
                "grand_total": str(self.final_total)
            },
            "split_count": self.split_count
        }
    
    @property
    def final_total(self) -> Decimal:
        return self.cart.grand_total + self.tip

    @property
    def per_person(self) -> Decimal:
        return (self.final_total / Decimal(str(self.split_count))).quantize(Decimal("0.01"), ROUND_HALF_UP)

    def generate_receipt(self):
        print("\n" + "="*35)
        print(f"{'HOSPITALITY OS RECEIPT':^35}")
        print(f"{'Table: ' + str(self.table_num):^35}")
        print("="*35)
        
        from collections import Counter
        item_counts = Counter(item.name for item in self.cart.items)
        
        for name, count in item_counts.items():
            price = next(item.price for item in self.cart.items if item.name == name)
            print(f"{count}x {name:<20} ${price * count:>8.2f}")

        print("-" * 35)
        print(f"Subtotal:            ${self.cart.subtotal:>8.2f}")
        print(f"Tax (8%):            ${self.cart.sales_tax:>8.2f}")
        print(f"Tip:                 ${self.tip:>8.2f}")
        print("-" * 35)
        print(f"TOTAL:               ${self.final_total:>8.2f}")
        if self.split_count > 1:
            print(f"Each ({self.split_count} ways):      ${self.per_person:>8.2f}")
        print("="*35 + "\n")