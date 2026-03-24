"""Write roster rows to data/staff.csv (PathManager). Run: python staff.py"""

import csv

from utils import PathManager

staff = [
    {"staff_id": "EMP-01", "name": "Flores, Ever", "dept": "BOH", "hourly_rate": 22.00},
    {"staff_id": "EMP-02", "name": "Ramirez, Edward", "dept": "BOH", "hourly_rate": 22.00},
    {"staff_id": "EMP-03", "name": "Gong, Bai", "dept": "BOH", "hourly_rate": 21.00},
    {"staff_id": "EMP-04", "name": "Espinosa, Jose", "dept": "BOH", "hourly_rate": 23.00},
    {"staff_id": "EMP-05", "name": "Verrera, Jorge", "dept": "BOH", "hourly_rate": 25.00},
    {"staff_id": "EMP-06", "name": "Manilla, Maureen", "dept": "FOH", "hourly_rate": 18.00},
    {"staff_id": "EMP-07", "name": "Quintilla, Cindy", "dept": "FOH", "hourly_rate": 18.00},
    {"staff_id": "EMP-08", "name": "Adler, Samantha", "dept": "FOH", "hourly_rate": 18.00},
    {"staff_id": "EMP-09", "name": "Manni, Malina", "dept": "FOH", "hourly_rate": 18.00},
    {"staff_id": "EMP-10", "name": "Crawford, Nichole", "dept": "FOH", "hourly_rate": 18.00},
]

if __name__ == "__main__":
    out_path = PathManager.get_path("staff.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as file:
        fieldnames = ["staff_id", "name", "dept", "hourly_rate"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(staff)
    print(f"Wrote {out_path}")
