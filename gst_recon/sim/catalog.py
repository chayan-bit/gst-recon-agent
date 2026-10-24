"""Static reference data: states, HSN/SAC catalog with FY 2024-25 GST rates.

Rates are the pre-22-Sep-2025 schedule (0/5/12/18/28 + compensation cess),
which is why simulated periods are pinned to FY 2024-25 (see RULES.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from gst_recon.schema import ItcCategory as C

# GST state code -> (state, a few cities)
STATES: dict[str, tuple[str, tuple[str, ...]]] = {
    "07": ("Delhi", ("New Delhi", "Okhla", "Naraina")),
    "06": ("Haryana", ("Gurugram", "Faridabad", "Manesar")),
    "08": ("Rajasthan", ("Jaipur", "Jodhpur", "Bhiwadi")),
    "09": ("Uttar Pradesh", ("Noida", "Lucknow", "Kanpur")),
    "19": ("West Bengal", ("Kolkata", "Howrah", "Durgapur")),
    "24": ("Gujarat", ("Ahmedabad", "Surat", "Vadodara")),
    "27": ("Maharashtra", ("Mumbai", "Pune", "Nashik")),
    "29": ("Karnataka", ("Bengaluru", "Mysuru", "Hubballi")),
    "32": ("Kerala", ("Kochi", "Thiruvananthapuram", "Kozhikode")),
    "33": ("Tamil Nadu", ("Chennai", "Coimbatore", "Hosur")),
    "36": ("Telangana", ("Hyderabad", "Secunderabad", "Warangal")),
}


@dataclass(frozen=True)
class Product:
    description: str
    hsn: str
    rate: float
    unit: str
    price_range: tuple[float, float]  # unit price in INR
    qty_range: tuple[int, int]
    category: C = C.NORMAL
    cess_rate: float = 0.0  # ad valorem compensation cess, percent
    reverse_charge: bool = False


# Normal business inputs (ITC eligible when s.16(2) conditions are met).
GOODS = (
    Product("Laptop Core i5 16GB RAM", "8471", 18, "Nos", (42000, 78000), (1, 6)),
    Product("Laser Printer A4 Mono", "8443", 18, "Nos", (9000, 24000), (1, 3)),
    Product("Office Chair Ergonomic", "9403", 18, "Nos", (4500, 12000), (2, 20)),
    Product("HR Steel Coil 2.5mm", "7208", 18, "MT", (52000, 61000), (1, 12)),
    Product("Portland Cement OPC 53 Grade 50kg", "2523", 28, "Bag", (340, 420), (50, 600)),
    Product("Split Air Conditioner 1.5T (factory)", "8415", 28, "Nos", (32000, 46000), (1, 4)),
    Product("Pneumatic Tyre 10.00-20 Truck", "4011", 28, "Nos", (15500, 21000), (2, 12)),
    Product("Enamel Paint 20L", "3208", 18, "Ltr", (210, 380), (20, 200)),
    Product("Ball Valve 2 inch SS", "8481", 18, "Nos", (900, 2600), (5, 80)),
    Product("Copper Cable 4 sq mm 90m", "8544", 18, "Roll", (3800, 6200), (2, 40)),
    Product("Industrial Detergent 25kg", "3402", 18, "Bag", (1400, 2300), (2, 30)),
    Product("Lubricating Oil SAE 20W-40", "2710", 18, "Ltr", (220, 340), (20, 400)),
    Product("Refined Soyabean Oil 15L (canteen stock)", "1507", 5, "Tin", (1700, 2300), (2, 20)),
    Product("Sugar M-30", "1701", 5, "Qtl", (3800, 4400), (1, 20)),
    Product("Cotton T-Shirt (uniform)", "6109", 5, "Nos", (180, 450), (20, 300)),
    Product("Paracetamol 500mg (first aid)", "3004", 12, "Strip", (12, 30), (50, 500)),
    Product("Technical Reference Book", "4901", 0, "Nos", (450, 2500), (1, 15)),
    Product("Toor Dal unbranded loose", "0713", 0, "Kg", (110, 160), (50, 500)),
)

SERVICES = (
    Product("IT Consulting Services", "998313", 18, "Hrs", (1500, 4500), (8, 120)),
    Product("Office Rent (commercial premises)", "997212", 18, "Month", (45000, 260000), (1, 1)),
    Product("Courier Services", "996812", 18, "Shipment", (90, 900), (5, 120)),
    Product("Telecommunication Services", "998412", 18, "Month", (2500, 18000), (1, 1)),
    Product("Hotel Accommodation (business travel)", "996311", 12, "Night", (3500, 7000), (1, 8)),
    Product("Air Travel Economy (business travel)", "996425", 5, "Ticket", (4500, 14000), (1, 6)),
    Product("Annual Maintenance Contract - Machinery", "998719", 18, "Job", (12000, 90000), (1, 1)),
)

# Reverse charge supplies from registered suppliers (s.9(3), notification 13/2017-CT(R)).
RCM = (
    Product("Goods Transport Agency freight", "996791", 5, "Trip", (6000, 45000), (1, 8), reverse_charge=True),
    Product("Legal Services by Advocate firm", "998211", 18, "Job", (15000, 150000), (1, 1), reverse_charge=True),
    Product("Security Services (non body corporate)", "998525", 18, "Month", (40000, 160000), (1, 1), reverse_charge=True),
)

# s.17(5) blocked credits.
BLOCKED = (
    Product("Motor Car SUV 7-seater (staff use)", "8703", 28, "Nos", (1450000, 2400000), (1, 1),
            C.MOTOR_VEHICLE, cess_rate=22),
    Product("Car Servicing and Repair (company car)", "998714", 18, "Job", (6000, 45000), (1, 1), C.MOTOR_VEHICLE),
    Product("Restaurant Catering - staff party", "996331", 5, "Plate", (450, 1500), (20, 150), C.FOOD_BEVERAGE),
    Product("Aerated Beverages (office pantry)", "2202", 28, "Case", (420, 700), (5, 40),
            C.FOOD_BEVERAGE, cess_rate=12),
    Product("Gym and Fitness Centre Membership", "999723", 18, "Year", (18000, 60000), (1, 10), C.CLUB_MEMBERSHIP),
    Product("Works Contract - office building extension", "995414", 18, "Job", (350000, 2500000), (1, 1),
            C.WORKS_CONTRACT),
    Product("LED Television 55in (director residence)", "8528", 28, "Nos", (48000, 90000), (1, 2), C.PERSONAL_USE),
    Product("Wrist Watches (Diwali gifts to dealers)", "9102", 18, "Nos", (2500, 9000), (10, 60), C.GIFT),
)

NAME_PREFIX = ("Shree", "Sai", "Om", "Vardhman", "Navkar", "Balaji", "Kaveri", "Sahyadri", "Ganga",
               "Annapurna", "Bharat", "Pragati", "Sunrise", "Patel", "Sharma", "Iyer", "Reddy", "Mehta")
NAME_CORE = ("Steel", "Polymers", "Traders", "Enterprises", "Logistics", "Infotech", "Industries",
             "Agencies", "Hospitality", "Motors", "Electricals", "Chemicals", "Services", "Builders")
NAME_SUFFIX = ("Pvt Ltd", "LLP", "& Co", "Private Limited", "", "Associates")
STREETS = ("MIDC Industrial Area", "Ring Road", "Station Road", "GIDC Estate", "Sector 18",
           "Phase II Industrial Area", "MG Road", "Old Market Yard")
