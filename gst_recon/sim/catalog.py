"""Static reference data: states, HSN/SAC catalog with date-effective GST rates.

Each product carries its rate before and after the 22 Sep 2025 GST 2.0
cutover; `rate_on` picks the one in force on the supply date (RULES.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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


# GST 2.0 rate rationalisation: notifications dated 17 Sep 2025, in force from
# 22 Sep 2025 (see RULES.md "Rate regimes" for the citations).
RATE_CUTOVER = date(2025, 9, 22)


@dataclass(frozen=True)
class Product:
    description: str
    hsn: str
    rate: float  # pre-cutover total GST rate, percent
    unit: str
    price_range: tuple[float, float]  # unit price in INR
    qty_range: tuple[int, int]
    category: C = C.NORMAL
    cess_rate: float = 0.0  # pre-cutover ad valorem compensation cess, percent
    reverse_charge: bool = False
    post_rate: float | None = None  # from RATE_CUTOVER; None = not verified, excluded after cutover
    post_cess_rate: float = 0.0


def rate_on(p: Product, d: date) -> tuple[float, float] | None:
    """(GST rate, cess rate) applicable to a supply on date d, or None if the
    product is not offered on that date (post-cutover rate unverified).
    s.14 CGST Act: with supply and invoice on the same date and payment later,
    the rate in force on the invoice date applies."""
    if d < RATE_CUTOVER:
        return p.rate, p.cess_rate
    return None if p.post_rate is None else (p.post_rate, p.post_cess_rate)


# Post-cutover refs: N9 = 9/2025-CT(R) schedule (I 5%, II 18%, III 40%) and S.No.;
# N10 = 10/2025-CT(R) exemption S.No.; N15 = 15/2025-CT(R) amending 11/2017-CT(R)
# (services; "n/a" = entry not amended); CC2 = 2/2025-Compensation Cess (Rate).
# Normal business inputs (ITC eligible when s.16(2) conditions are met).
GOODS = (
    Product("Laptop Core i5 16GB RAM", "8471", 18, "Nos", (42000, 78000), (1, 6), post_rate=18),  # N9 II-456
    Product("Laser Printer A4 Mono", "8443", 18, "Nos", (9000, 24000), (1, 3), post_rate=18),  # N9 II-430
    Product("Office Workstation Table", "9403", 18, "Nos", (6500, 18000), (2, 20), post_rate=18),  # N9 II-612
    Product("HR Steel Coil 2.5mm", "7208", 18, "MT", (52000, 61000), (1, 12), post_rate=18),  # N9 II-267
    Product("Portland Cement OPC 53 Grade 50kg", "2523", 28, "Bag", (340, 420), (50, 600), post_rate=18),  # N9 II-9
    Product("Split Air Conditioner 1.5T (factory)", "8415", 28, "Nos", (32000, 46000), (1, 4), post_rate=18),  # N9 II-404
    Product("Pneumatic Tyre 10.00-20 Truck", "4011", 28, "Nos", (15500, 21000), (2, 12), post_rate=18),  # N9 II-137
    Product("Enamel Paint 20L", "3208", 18, "Ltr", (210, 380), (20, 200), post_rate=18),  # N9 II-50
    Product("Ball Valve 2 inch SS", "8481", 18, "Nos", (900, 2600), (5, 80), post_rate=18),  # N9 II-466
    Product("Copper Cable 4 sq mm 90m", "8544", 18, "Roll", (3800, 6200), (2, 40), post_rate=18),  # N9 II-516
    Product("Industrial Detergent 25kg", "3402", 18, "Bag", (1400, 2300), (2, 30), post_rate=18),  # N9 II-67
    Product("Lubricating Oil SAE 20W-40", "2710", 18, "Ltr", (220, 340), (20, 400), post_rate=18),  # N9 II-29
    Product("Refined Soyabean Oil 15L (canteen stock)", "1507", 5, "Tin", (1700, 2300), (2, 20), post_rate=5),  # N9 I-84
    Product("Sugar M-30", "1701", 5, "Qtl", (3800, 4400), (1, 20), post_rate=5),  # N9 I-105
    Product("Cotton T-Shirt (uniform)", "6109", 5, "Nos", (180, 450), (20, 300), post_rate=5),  # N9 I-388 (<= Rs 2500/pc)
    Product("Paracetamol 500mg (first aid)", "3004", 12, "Strip", (12, 30), (50, 500), post_rate=5),  # N9 I-234
    Product("Technical Reference Book", "4901", 0, "Nos", (450, 2500), (1, 15), post_rate=0),  # N10-132
    Product("Toor Dal unbranded loose", "0713", 0, "Kg", (110, 160), (50, 500), post_rate=0),  # N10-39
)

SERVICES = (
    Product("IT Consulting Services", "998313", 18, "Hrs", (1500, 4500), (8, 120), post_rate=18),  # N15 n/a (S.No.21(ii))
    Product("Office Rent (commercial premises)", "997212", 18, "Month", (45000, 260000), (1, 1), post_rate=18),  # N15 n/a
    Product("Courier Services", "996812", 18, "Shipment", (90, 900), (5, 120), post_rate=18),  # N15 S.No.9 (ii) 9%
    Product("Telecommunication Services", "998412", 18, "Month", (2500, 18000), (1, 1), post_rate=18),  # N15 n/a
    # N15 S.No.7(i): hotel accommodation <= Rs 7500/day to 5% (supplier forgoes ITC; recipient credit unaffected)
    Product("Hotel Accommodation (business travel)", "996311", 12, "Night", (3500, 7000), (1, 8), post_rate=5),
    Product("Air Travel Economy (business travel)", "996425", 5, "Ticket", (4500, 14000), (1, 6), post_rate=5),  # N15 n/a
    Product("Annual Maintenance Contract - Machinery", "998719", 18, "Job", (12000, 90000), (1, 1), post_rate=18),  # N15 n/a
)

# Reverse charge supplies from registered suppliers (s.9(3), notification 13/2017-CT(R)).
RCM = (
    # N15 S.No.9(iii): only the forward-charge GTA option (b) moved 12% -> 18%; RCM option stays 5%
    Product("Goods Transport Agency freight", "996791", 5, "Trip", (6000, 45000), (1, 8), reverse_charge=True,
            post_rate=5),
    Product("Legal Services by Advocate firm", "998211", 18, "Job", (15000, 150000), (1, 1), reverse_charge=True,
            post_rate=18),  # N15 n/a
    Product("Security Services (non body corporate)", "998525", 18, "Month", (40000, 160000), (1, 1),
            reverse_charge=True, post_rate=18),  # N15 n/a
)

# s.17(5) blocked credits.
BLOCKED = (
    # SUV > 4000 mm, > 1500 cc: N9 III-5 (40%); cess Nil from CC2 (S.No.52-52B)
    Product("Motor Car SUV 7-seater (staff use)", "8703", 28, "Nos", (1450000, 2400000), (1, 1),
            C.MOTOR_VEHICLE, cess_rate=22, post_rate=40),
    Product("Car Servicing and Repair (company car)", "998714", 18, "Job", (6000, 45000), (1, 1), C.MOTOR_VEHICLE,
            post_rate=18),  # N15 n/a
    Product("Restaurant Catering - staff party", "996331", 5, "Plate", (450, 1500), (20, 150), C.FOOD_BEVERAGE,
            post_rate=5),  # N15 n/a (S.No.7(ii))
    # Aerated waters with added sugar: N9 III-1 (40%); cess Nil from CC2 (S.No.2)
    Product("Aerated Beverages (office pantry)", "2202", 28, "Case", (420, 700), (5, 40),
            C.FOOD_BEVERAGE, cess_rate=12, post_rate=40),
    # Group 99972 beauty and physical well-being: N15 S.No.35(i) 5%
    Product("Gym and Fitness Centre Membership", "999723", 18, "Year", (18000, 60000), (1, 10), C.CLUB_MEMBERSHIP,
            post_rate=5),
    Product("Works Contract - office building extension", "995414", 18, "Job", (350000, 2500000), (1, 1),
            C.WORKS_CONTRACT, post_rate=18),  # N15 S.No.3: only items (vii), (viii), (x) amended
    Product("LED Television 55in (director residence)", "8528", 28, "Nos", (48000, 90000), (1, 2), C.PERSONAL_USE,
            post_rate=18),  # N9 II-500
    Product("Wrist Watches (Diwali gifts to dealers)", "9102", 18, "Nos", (2500, 9000), (10, 60), C.GIFT,
            post_rate=18),  # N9 II-584
)

NAME_PREFIX = ("Shree", "Sai", "Om", "Vardhman", "Navkar", "Balaji", "Kaveri", "Sahyadri", "Ganga",
               "Annapurna", "Bharat", "Pragati", "Sunrise", "Patel", "Sharma", "Iyer", "Reddy", "Mehta")
NAME_CORE = ("Steel", "Polymers", "Traders", "Enterprises", "Logistics", "Infotech", "Industries",
             "Agencies", "Hospitality", "Motors", "Electricals", "Chemicals", "Services", "Builders")
NAME_SUFFIX = ("Pvt Ltd", "LLP", "& Co", "Private Limited", "", "Associates")
STREETS = ("MIDC Industrial Area", "Ring Road", "Station Road", "GIDC Estate", "Sector 18",
           "Phase II Industrial Area", "MG Road", "Old Market Yard")
