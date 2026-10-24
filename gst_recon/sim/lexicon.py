"""Text pools for buyer profile headers and invoice remarks, plus what each profile buys.

Every pool is split deterministically (splits.py) so test phrasing never
appears in training cases.
"""

from __future__ import annotations

from gst_recon.schema import BusinessProfile as P
from gst_recon.schema import LinePurpose as U

# Header phrases per profile; "{x}" is filled from PROFILE_SLOTS.
PROFILE_HEADERS: dict[P, tuple[str, ...]] = {
    P.MANUFACTURER: ("Manufacturer of {x}", "{x} manufacturing unit", "Mfg. of {x} (own factory)",
                     "Industrial manufacturer - {x}", "Factory: production of {x}", "OEM supplier, makes {x}",
                     "{x} - manufacturing & assembly", "Producer of {x}"),
    P.IT_SERVICES: ("Software development & IT consulting", "IT services company (SaaS products)",
                    "Software exporter & IT-enabled services", "Custom software & cloud consulting firm",
                    "IT/ITES company", "Digital transformation consultancy", "B2B software product company",
                    "Managed IT services provider"),
    P.CAR_DEALER: ("Authorised {x} car dealer", "Car dealership (new & pre-owned)", "Multi-brand used car dealer",
                   "Automobile showroom - cars and SUVs", "Passenger car dealer ({x})",
                   "Pre-owned car trading company", "{x} sales outlet (cars)", "Dealer in new passenger vehicles"),
    P.PASSENGER_TRANSPORT: ("Cab and taxi fleet operator", "Tours & travels - car rentals with driver",
                            "Employee transportation services (cabs)", "Outstation taxi operator",
                            "Airport cab service provider", "Chauffeur-driven car rental company",
                            "Passenger transport operator (cabs, MUVs)", "Taxi aggregator fleet partner"),
    P.DRIVING_SCHOOL: ("Motor driving training school", "Driving school (RTO approved)",
                       "Car driving classes & training institute", "Learner driving academy",
                       "Driving training centre with dual-control cars", "Motor training school"),
    P.HOTEL: ("Business hotel with restaurant and banquets", "Resort & convention centre",
              "4-star hotel (rooms, F&B, banquets)", "Boutique hotel with in-house restaurant",
              "Hotel & banquet hall operator", "Hospitality - hotel with multi-cuisine restaurant",
              "Heritage hotel with restaurant", "City hotel and conference venue"),
    P.CATERER: ("Wedding & event caterers", "Industrial canteen contractor", "Outdoor catering services",
                "Corporate catering company", "Banquet catering & food services",
                "Institutional catering (food supply)"),
    P.GYM_OPERATOR: ("Chain of fitness centres", "Gym & fitness studio operator", "Fitness club (gym, yoga, CrossFit)",
                     "Health & fitness centre", "Fitness studio franchisee", "Gym operator - 3 branches",
                     "Boutique fitness and strength studio", "24x7 gym chain"),
    P.CONSTRUCTION_CONTRACTOR: ("Civil & interiors contractor (EPC)", "Building construction contractor",
                                "Works contractor - civil, electrical, interiors", "Turnkey construction company",
                                "Infrastructure & building contractor", "Interior fit-out contractor",
                                "Commercial building contractor", "Design & build contractor"),
    P.AUTO_WORKSHOP: ("Multi-brand car service centre", "Authorised car service workshop", "Auto repair garage (cars)",
                      "Car service & spare parts workshop", "Vehicle maintenance workshop",
                      "Body shop & mechanical repair centre"),
}

# Trading companies: the trade line decides what they buy for resale.
TRADE_LINES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "fmcg": (("food",), ("Wholesale distributor of FMCG & groceries", "Grocery & provisions wholesaler",
                         "FMCG super stockist", "Kirana wholesale trader (food & beverages)",
                         "Distributor - packaged foods and beverages", "Trader of food products and beverages")),
    "electronics": (("household", "office"), (
        "Dealer in consumer electronics & appliances", "Electronics & home appliance distributor",
        "Distributor of IT hardware and mobiles", "Trader - TVs, ACs, fridges, laptops",
        "Electronics wholesale (computers & appliances)", "Authorised distributor of home appliances")),
    "gifts": (("giftable",), ("Trader of watches, perfumes & gift articles", "Corporate gifting & lifestyle products dealer",
                              "Lifestyle accessories wholesaler (watches, bags, jewellery)",
                              "Gift articles & luggage distributor", "Jewellery and watch retailer",
                              "Retailer of lifestyle goods")),
    "building": (("construction",), ("Building materials trader (cement, tiles, sanitaryware)",
                                     "Hardware & building material supplier", "Cement & steel stockist",
                                     "Tiles and sanitaryware showroom", "Construction material wholesaler",
                                     "Dealer in cement, TMT & tiles")),
}

PROFILE_SLOTS: dict[P, tuple[str, ...]] = {
    P.MANUFACTURER: ("precision engineering components", "industrial valves", "auto components", "PVC pipes",
                     "packaged spices", "pharmaceutical formulations", "textile yarn", "electrical switchgear",
                     "corrugated packaging", "steel fabrication items"),
    P.CAR_DEALER: ("Maruti Suzuki", "Hyundai", "Tata Motors", "Mahindra", "Toyota", "Kia"),
}

# Remarks that reveal the purpose. Required whenever the purpose is not implied by the profile.
REMARKS: dict[U, tuple[str, ...]] = {
    U.FACTORY_CANTEEN: ("Supply to factory canteen", "canteen provisions - plant", "for workers' canteen",
                        "factory canteen consumption", "canteen stores (shop floor)", "kantin ke liye - factory",
                        "for in-house canteen at works", "canteen material - production unit"),
    U.STAFF_WELFARE: ("Annual day celebration", "team outing lunch", "staff Diwali party", "townhall get-together",
                      "employee birthday celebrations", "office party", "staff welfare - festival",
                      "team dinner - project closure"),
    U.OWN_CONSTRUCTION: ("Construction of new admin block", "for our new warehouse building",
                         "office building extension (capitalised)", "material for own factory shed construction",
                         "new godown construction at site", "capex - building construction",
                         "own premises - first floor addition", "naya office building - construction"),
    U.PERSONAL: ("Deliver to residence of Director", "for MD's personal use", "Ship to: residence (Director)",
                 "Personal - Director", "ghar ke liye - MD sir", "for partner's residence",
                 "personal use of proprietor", "residence of CEO - not for office"),
    U.GIFT: ("Diwali gifts for channel partners", "corporate gifting - dealers meet", "customer gifts (festival)",
             "gifts for employees - long service awards", "New Year gifts to clients", "dealer incentive gifts",
             "gift distribution - festive season", "tohfe - dealers ke liye"),
    # optional: purposes already implied by the profile
    U.FURTHER_SUPPLY: ("for resale", "stock for sale", "against customer order", "for onward supply",
                       "trading stock", "for client order no. 18", "inventory replenishment", "for sale to customers"),
    U.PASSENGER_TRANSPORT: ("fleet vehicle", "for cab fleet", "taxi permit vehicle", "commercial fleet addition",
                            "for operation as cab", "T-permit vehicle", "fleet no. 12", "yellow-board taxi"),
    U.DRIVING_TRAINING: ("dual control training car", "for driving school fleet", "learner training vehicle",
                         "training car with dual brakes", "for driving classes", "trainer vehicle",
                         "instruction vehicle", "LMV training car"),
}
NEUTRAL_REMARKS = ("As per PO 4500231", "against PO", "Ref: quotation dt. 12th", "delivery challan attached",
                   "payment within 30 days", "E&OE", "goods once sold will not be taken back",
                   "subject to local jurisdiction", "order ref: email", "dispatched via road")
REMARK_REQUIRED = {U.FACTORY_CANTEEN, U.STAFF_WELFARE, U.OWN_CONSTRUCTION, U.PERSONAL, U.GIFT}

# Relative weight of each concept family in a buyer's purchases.
COMMON = {"office": 8, "services": 10, "travel": 4, "rcm": 5, "misc": 2, "toiletries": 2, "household": 3,
          "giftable": 2, "food": 5, "club": 2, "works_contract": 2, "construction": 1.5, "motor_vehicle": 2,
          "goods_vehicle": 1}
PROFILE_FAMILIES: dict[P, dict[str, float]] = {
    P.MANUFACTURER: COMMON | {"industrial": 20, "goods_vehicle": 2},
    P.IT_SERVICES: COMMON | {"goods_vehicle": 0},
    P.TRADING_COMPANY: COMMON,  # + trade line boost
    P.CAR_DEALER: COMMON | {"motor_vehicle": 15, "car_parts": 8},
    P.PASSENGER_TRANSPORT: COMMON | {"motor_vehicle": 15, "car_parts": 6},
    P.DRIVING_SCHOOL: COMMON | {"motor_vehicle": 12, "car_parts": 4},
    P.HOTEL: COMMON | {"food": 15, "household": 8, "toiletries": 6, "motor_vehicle": 0},
    P.CATERER: COMMON | {"food": 20, "goods_vehicle": 2},
    P.GYM_OPERATOR: COMMON | {"gym_equipment": 12},
    P.CONSTRUCTION_CONTRACTOR: COMMON | {"works_contract": 12, "construction": 15, "industrial": 5},
    P.AUTO_WORKSHOP: COMMON | {"car_parts": 20, "industrial": 4, "motor_vehicle": 0},
}
TRADE_LINE_BOOST = 20.0
