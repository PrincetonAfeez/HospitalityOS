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
    