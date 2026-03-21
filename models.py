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
    
    class Transaction:
    def __init__(self, cart: Cart, table_num: int):
        self.cart = cart
        self.table_num = table_num
        self.tip = Decimal("0.00")
        self.split_count = 1

    def apply_tip(self, amount: str):
        """Processes tip as a percentage (e.g., '20%') or a flat rate (e.g., '10')."""
        try:
            if "%" in amount:
                percent = Decimal(amount.replace("%", "")) / 100
                self.tip = (self.cart.subtotal * percent).quantize(Decimal("0.01"), ROUND_HALF_UP)
            else:
                self.tip = Decimal(amount).quantize(Decimal("0.01"), ROUND_HALF_UP)
            return True
        except:
            print("Invalid tip format.")
            return False

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
        
        # Count identical items for receipt display
        from collections import Counter
        item_counts = Counter(item.name for item in self.cart.items)
        
        for name, count in item_counts.items():
            # Find the first instance to get the price
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