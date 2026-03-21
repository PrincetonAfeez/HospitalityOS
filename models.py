from decimal import Decimal, ROUND_HALF_UP

class MenuItem:
    def __init__(self, category, name, price, line_inv, walk_in, freezer, par):
        self.category = category
        self.name = name
        self.price = Decimal(str(price)) # Use Decimal for money
        self.line_inv = int(line_inv)
        self.walk_in_inv = int(walk_in)
        self.freezer_inv = int(freezer)
        self.par_level = int(par)

    @property
    def total_inventory(self):
        return self.line_inv + self.walk_in_inv + self.freezer_inv

    def __str__(self):
        return f"[{self.category:10}] {self.name:25} ${self.price:>6.2f}"

class Cart:
    def __init__(self):
        self.items = []
        self.tax_rate = Decimal("0.08") # 8% Tax

    def add_to_cart(self, item: MenuItem):
        # FEATURE: Inventory Guardrail (from original script)
        if item.line_inv > 0:
            self.items.append(item)
            item.line_inv -= 1 # Deduct from 'Line' first
            print(f"✅ Added {item.name}. (Line Stock: {item.line_inv})")
        elif item.total_inventory > 0:
            print(f"⚠️ {item.name} empty on line! Restock from Walk-in.")
        else:
            print(f"❌ CANNOT ADD: {item.name} is 86'd!")

    @property
    def subtotal(self) -> Decimal:
        return sum((item.price for item in self.items), Decimal("0.00"))

    @property
    def sales_tax(self) -> Decimal:
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def grand_total(self) -> Decimal:
        return self.subtotal + self.sales_tax