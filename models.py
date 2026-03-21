#feat: initialize project structure and models file

class MenuItem:
    def __init__(self, category: str, name: str, price: float, line_inv: int, walk_in: int, freezer: int, par: int):
        self.category = category
        self.name = name
        self.price = float(price)
        # Inventory tracking
        self.line_inv = int(line_inv)
        self.walk_in_inv = int(walk_in)
        self.freezer_inv = int(freezer)
        self.par_level = int(par)

    @property
    def total_inventory(self) -> int:
        return self.line_inv + self.walk_in_inv + self.freezer_inv

    def __str__(self):
        stock_status = "INSTOCK" if self.total_inventory > 0 else "OUT OF STOCK"
        return f"[{self.category:10}] {self.name:25} ${self.price:>6.2f} | Stock: {self.total_inventory} ({stock_status})"

class Menu:
    def __init__(self):
        self.items = []

    def add_item(self, item: MenuItem):
        self.items.append(item)

    def find_item(self, name: str) -> MenuItem:
        """Search for an item by name (case-insensitive)."""
        for item in self.items:
            if item.name.lower() == name.lower():
                return item
        return None

class Cart:
    def __init__(self):
        self.items = []
        self.tax_rate = 0.08  # 8% Tax

    def add_to_cart(self, item: MenuItem):
        """
        Logic: 
        1. Check if total_inventory > 0.
        2. If yes, add to self.items and subtract 1 from item.line_inv.
        3. If no, print an 'Out of Stock' error.
        """
        if item.total_inventory > 0:
            self.items.append(item)
            item.line_inv -= 1 
            print(f"Added {item.name} to cart.")
        else:
            print(f"Error: {item.name} is out of stock!")

    @property
    def subtotal(self) -> float:
        return sum(item.price for item in self.items)

    @property
    def grand_total(self) -> float:
        return self.subtotal * (1 + self.tax_rate)
    