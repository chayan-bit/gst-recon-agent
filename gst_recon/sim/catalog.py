"""Static reference data: states, rate cutover, supplier-name vocabulary, number formats.

What is bought (HSN/SAC, rates, surface forms) lives in `concepts.py`.
"""

from __future__ import annotations

from datetime import date

from gst_recon.sim.concepts import Concept

# GST state code -> (state, a few cities)
STATES: dict[str, tuple[str, tuple[str, ...]]] = {
    "02": ("Himachal Pradesh", ("Shimla", "Baddi", "Solan")),
    "03": ("Punjab", ("Ludhiana", "Mohali", "Jalandhar")),
    "05": ("Uttarakhand", ("Dehradun", "Haridwar", "Rudrapur")),
    "06": ("Haryana", ("Gurugram", "Faridabad", "Manesar")),
    "07": ("Delhi", ("New Delhi", "Okhla", "Naraina")),
    "08": ("Rajasthan", ("Jaipur", "Jodhpur", "Bhiwadi")),
    "09": ("Uttar Pradesh", ("Noida", "Lucknow", "Kanpur")),
    "10": ("Bihar", ("Patna", "Muzaffarpur", "Gaya")),
    "18": ("Assam", ("Guwahati", "Dibrugarh", "Silchar")),
    "19": ("West Bengal", ("Kolkata", "Howrah", "Durgapur")),
    "20": ("Jharkhand", ("Ranchi", "Jamshedpur", "Dhanbad")),
    "21": ("Odisha", ("Bhubaneswar", "Cuttack", "Rourkela")),
    "22": ("Chhattisgarh", ("Raipur", "Bhilai", "Bilaspur")),
    "23": ("Madhya Pradesh", ("Indore", "Bhopal", "Pithampur")),
    "24": ("Gujarat", ("Ahmedabad", "Surat", "Vadodara")),
    "27": ("Maharashtra", ("Mumbai", "Pune", "Nashik")),
    "29": ("Karnataka", ("Bengaluru", "Mysuru", "Hubballi")),
    "30": ("Goa", ("Panaji", "Margao", "Vasco da Gama")),
    "32": ("Kerala", ("Kochi", "Thiruvananthapuram", "Kozhikode")),
    "33": ("Tamil Nadu", ("Chennai", "Coimbatore", "Hosur")),
    "36": ("Telangana", ("Hyderabad", "Secunderabad", "Warangal")),
    "37": ("Andhra Pradesh", ("Visakhapatnam", "Vijayawada", "Tirupati")),
}

# GST 2.0 rate rationalisation: notifications dated 17 Sep 2025, in force from
# 22 Sep 2025 (see RULES.md "Rate regimes" for the citations).
RATE_CUTOVER = date(2025, 9, 22)


def rate_on(c: Concept, d: date) -> tuple[float, float] | None:
    """(GST rate, cess rate) for a supply on date d, or None if the concept is
    not offered then (post-cutover rate unverified).
    s.14 CGST Act: with supply and invoice on the same date and payment later,
    the rate in force on the invoice date applies."""
    if d < RATE_CUTOVER:
        return c.rate, c.cess_rate
    return None if c.post_rate is None else (c.post_rate, c.post_cess_rate)


# Supplier-name vocabulary. Deliberately neutral: a name token never hints at
# what the supplier sells (that would be a shortcut to the ITC decision).
NAME_PREFIX = ("Shree", "Sai", "Om", "Vardhman", "Navkar", "Balaji", "Kaveri", "Sahyadri", "Ganga",
               "Annapurna", "Bharat", "Pragati", "Sunrise", "Patel", "Sharma", "Iyer", "Reddy", "Mehta",
               "Agarwal", "Kapoor", "Nair", "Menon", "Joshi", "Desai", "Bansal", "Chawla", "Gill", "Bose",
               "Das", "Pillai", "Rathore", "Saxena", "Trivedi", "Kulkarni", "Hegde", "Arora")
NAME_CORE = ("Traders", "Enterprises", "Industries", "Agencies", "Services", "Associates", "Corporation",
             "Ventures", "Solutions", "Sales", "Distributors", "Suppliers", "Group", "Brothers", "Overseas",
             "International", "Udyog", "Vyapar", "Commercial", "Impex", "Trading Co", "Marketing", "Global",
             "Networks")
NAME_SUFFIX = ("Pvt Ltd", "LLP", "& Co", "Private Limited", "", "")
STREETS = ("MIDC Industrial Area", "Ring Road", "Station Road", "GIDC Estate", "Sector 18",
           "Phase II Industrial Area", "MG Road", "Old Market Yard", "Transport Nagar", "Civil Lines",
           "Link Road", "Industrial Estate")

# Supplier invoice-number formats ({fy} = financial year label like 25-26).
NUMBER_FORMATS = ("INV/{fy}/{:04d}", "{:05d}", "GST-{:04d}", "SI{:06d}", "{fy}/{:d}", "TI/{:03d}",
                  "B-{:04d}", "{fy}-INV-{:05d}", "TAX/{:04d}/{fy}", "S/{:d}", "No.{:04d}", "BILL{:05d}")
