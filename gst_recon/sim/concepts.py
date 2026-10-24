"""Concept catalog: what is bought, its HSN/SAC, date-effective rates and surface forms.

A concept is a kind of inward supply ("small petrol car", "gym membership").
Its ITC treatment depends on the concept's s.17(5) category AND on the buyer's
business and the stated purpose (see rules.line_block_reason), never on the
wording. Each concept carries >= 8 hand-written core phrases (brands,
abbreviations, Hinglish, vendor jargon, misspellings); `splits.surface_forms`
expands each core into variants. No phrase states the use.

Post-cutover rate refs (RULES.md "Rate regimes"): N9 = 9/2025-CT(R) schedule and
S.No.; N10 = 10/2025-CT(R) exemption S.No.; N15 = 15/2025-CT(R) (services, "n/a" =
entry not amended); CC = 1/2017-Compensation Cess (Rate) S.No. as amended by
2/2025-CC(R). Pre-cutover rates are from domain knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass

from gst_recon.schema import ItcCategory as C

NOT_VERIFIED = None


@dataclass(frozen=True)
class Concept:
    id: str
    family: str
    hsn: str
    rate: float  # pre-cutover GST rate, percent
    post_rate: float | None  # from 22 Sep 2025; None = not verified, never generated after the cutover
    unit: str
    price_range: tuple[float, float]
    qty_range: tuple[int, int]
    forms: tuple[str, ...]  # core phrases
    source: str = ""  # citation for post_rate
    category: C = C.NORMAL
    cess_rate: float = 0.0
    post_cess_rate: float = 0.0
    reverse_charge: bool = False

    @property
    def is_service(self) -> bool:
        return self.hsn.startswith("99")


def _c(cid, family, hsn, pre, post, unit, price, qty, src, forms, **kw) -> Concept:
    return Concept(cid, family, hsn, pre, post, unit, price, qty, tuple(forms), src, **kw)


MV, FB, CLUB, WC = C.MOTOR_VEHICLE, C.FOOD_BEVERAGE, C.CLUB_MEMBERSHIP, C.WORKS_CONTRACT

CONCEPTS: tuple[Concept, ...] = (
    # ---------------------------------------------------------------- industrial inputs
    _c("hr_steel_coil", "industrial", "7208", 18, 18, "MT", (52000, 61000), (1, 12), "N9 II-267", [
        "HR Steel Coil 2.5mm IS 2062", "Hot rolled coil E250", "HRC 3mm x 1250", "MS sheet coil (hot rolled)",
        "H.R. coil - JSW", "Tata Steel HR plate 6mm", "SAIL HR coil 2.0 mm", "garam rolled coil (HRC)"]),
    _c("fasteners", "industrial", "7318", 18, 18, "Kg", (140, 320), (20, 400), "N9 II-296", [
        "Hex bolts M12 x 50 HT", "SS fasteners assorted", "Nut bolt washer set", "Allen cap screw M8",
        "Unbrako socket head screws", "GI J-bolts with nuts", "spring washers M10", "nut-bolt (8.8 grade)"]),
    _c("bearings", "industrial", "8482", 18, 18, "Nos", (180, 4500), (4, 120), "N9 II-467", [
        "SKF 6205 ZZ ball bearing", "Deep groove ball brg 6308", "Taper roller bearing 32210",
        "NBC bearing 6204-2RS", "FAG spherical roller bearing", "Roller brg. 22216", "bearing set for conveyor",
        "Timken taper roller brg"]),
    _c("valves", "industrial", "8481", 18, 18, "Nos", (900, 2600), (5, 80), "N9 II-466", [
        "Ball Valve 2 inch SS", "Gate valve 4in CI flanged", "L&T butterfly valve DN100", "NRV 1.5 inch brass",
        "Solenoid valve 24V", "Pressure relief valve", "SS 316 needle valve", "Zoloto gate valve 50mm"]),
    _c("cables", "industrial", "8544", 18, 18, "Roll", (3800, 6200), (2, 40), "N9 II-516", [
        "Copper Cable 4 sq mm 90m", "Polycab FR wire 2.5 sqmm", "Havells 3 core armoured cable",
        "XLPE Al cable 3.5C x 95", "Finolex PVC insulated wire", "control cable 12 core 1.5sqmm",
        "multistrand Cu wire 6mm", "LAN cable Cat6 305m"]),
    _c("plastic_pipes", "industrial", "3917", 18, 18, "Nos", (120, 2400), (10, 200), "N9 II-118", [
        "UPVC pipe 4 inch SWR", "Supreme CPVC pipe 1in", "HDPE pipe 63mm PN6", "PVC hose braided 1/2in",
        "Astral pipe fittings elbow tee", "PPR pipe 25mm", "flexible PVC suction hose", "Finolex column pipe 32mm"]),
    _c("plastic_packing", "industrial", "3923", 18, 18, "Nos", (6, 450), (100, 3000), "N9 II-124", [
        "HDPE jerry cans 20L", "PET jars 500ml", "plastic crates (returnable)", "PP woven bags 25kg",
        "HDPE drums 200L", "bottle caps 28mm", "plastic pallets 1200x1000", "LDPE poly bags 12x18"]),
    _c("cartons", "industrial", "4819", 18, 5, "Nos", (18, 95), (200, 5000), "N9 I-322", [
        "Corrugated boxes 5 ply", "3 ply carton 12x10x8", "Shipping cartons printed", "CFB boxes 7 ply export",
        "gatte ke dabbe (5 ply)", "Master carton brown kraft", "RSC corrugated box", "duplex mono carton"]),
    _c("paint", "industrial", "3208", 18, 18, "Ltr", (210, 380), (20, 200), "N9 II-50", [
        "Enamel Paint 20L", "Asian Paints Apcolite enamel", "Epoxy floor coating", "PU top coat 4L",
        "Berger synthetic enamel", "red oxide primer (synthetic)", "industrial paint - RAL 7035", "Nerolac PU enamel"]),
    _c("lubricants", "industrial", "2710", 18, 18, "Ltr", (220, 340), (20, 400), "N9 II-29", [
        "Lubricating Oil SAE 20W-40", "Servo hydraulic oil 68", "Castrol gear oil EP 90", "Mobil DTE 25",
        "engine oil 15W40 (bulk)", "Shell Tellus S2 M 46", "compressor oil ISO 100", "Gulf turbine oil 32"]),
    _c("detergent", "industrial", "3402", 18, 18, "Bag", (400, 2300), (2, 30), "N9 II-67", [
        "Industrial detergent powder 25 kg", "Liquid detergent drum 50 L", "Surf Excel Easy Wash 5kg",
        "Tide detergent bulk pack", "degreaser surfactant cleaner", "dishwash liquid 5L (Vim)",
        "Henko laundry powder", "Ariel matic 4kg"]),
    _c("electric_motors", "industrial", "8501", 18, 18, "Nos", (4500, 85000), (1, 10), "N9 II-474", [
        "Crompton 5 HP induction motor", "ABB 3-phase motor 7.5kW", "Siemens IE3 motor 11 kW", "BLDC motor 250W",
        "geared motor 1HP", "Kirloskar electric motor 3hp", "servo motor 750W", "Havells foot-mounted motor"]),
    _c("switchgear", "industrial", "8536", 18, 18, "Nos", (90, 8000), (5, 200), "N9 II-508", [
        "Schneider MCB 32A DP", "L&T contactor MNX 25", "Legrand modular switches", "relay 24VDC 8 pin",
        "Havells RCCB 63A 4P", "terminal blocks 6 sq mm", "industrial plug & socket 32A", "isolator switch 63A"]),
    _c("ups_transformers", "industrial", "8504", 18, 18, "Nos", (6500, 240000), (1, 4), "N9 II-477", [
        "Online UPS 10 kVA", "APC UPS 3kVA", "servo stabiliser 15 kVA", "control transformer 500VA",
        "dry type transformer 100 kVA", "SMPS 24V 10A", "Luminous inverter 1100VA", "isolation transformer 5 kVA"]),
    _c("compressors_fans", "industrial", "8414", 18, 18, "Nos", (2200, 380000), (1, 10), "N9 II-401", [
        "Elgi screw compressor 15 HP", "Atlas Copco air compressor", "exhaust fan 18 inch",
        "Crompton industrial wall fan", "Orient ceiling fans 1200mm", "blower 2HP centrifugal",
        "Usha pedestal fan", "Ingersoll Rand reciprocating compressor"]),
    _c("truck_tyres", "industrial", "4011", 28, 18, "Nos", (15500, 21000), (2, 12), "N9 II-137", [
        "Pneumatic Tyre 10.00-20 Truck", "MRF Steel Muscle 295/80R22.5", "Apollo EnduRace RD tyre",
        "JK Jetway truck tyre", "CEAT Mile XL 10.00R20", "Bridgestone M840 11R22.5", "nylon truck tyres 9.00-20",
        "radial truck tyre 12R20"]),
    # ------------------------------------------------- goods vehicles (not s.17(5)(a): carry goods)
    _c("goods_vehicle", "goods_vehicle", "8704", 28, 18, "Nos", (650000, 3500000), (1, 2), "N9 II-540", [
        "Tata Ace Gold mini truck", "Mahindra Bolero Pik-Up", "Ashok Leyland Dost+", "Eicher Pro 2049 goods carrier",
        "Tata 1512 LPT truck chassis", "Maruti Super Carry", "BharatBenz 1617R truck", "refrigerated reefer truck 14ft"]),
    # ------------------------------------------------------------ construction materials
    _c("cement", "construction", "2523", 28, 18, "Bag", (340, 420), (50, 600), "N9 II-9", [
        "Portland Cement OPC 53 Grade 50kg", "UltraTech PPC cement", "ACC Gold water shield", "Ambuja cement bags",
        "OPC 43 grade", "PSC slag cement", "Birla A1 cement", "siment OPC53 (50 kg)"]),
    _c("tmt_bars", "construction", "7214", 18, 18, "MT", (54000, 68000), (1, 20), "N9 II-268", [
        "TMT bars Fe 500D 12mm", "JSW Neosteel 16mm", "Tata Tiscon 500SD", "saria 10 mm (TMT)", "Kamdhenu TMT 8mm",
        "SAIL TMT Fe550", "rebar 25mm Fe500", "TMT sariya 20mm"]),
    _c("tiles", "construction", "6907", 18, 18, "Box", (380, 1900), (20, 400), "N9 II-238", [
        "Kajaria vitrified tiles 600x600", "Somany floor tiles", "ceramic wall tiles 300x450",
        "glazed vitrified tiles GVT", "anti-skid parking tiles", "Johnson bathroom tiles",
        "double charge vitrified 800x800", "porcelain tiles matt finish"]),
    _c("sanitaryware", "construction", "6910", 18, 18, "Nos", (1800, 32000), (2, 40), "N9 II-240", [
        "Hindware wash basin", "Cera EWC western commode", "Jaquar wall-hung WC", "ceramic urinal",
        "Parryware counter top basin", "ceramic kitchen sink", "Kohler one-piece toilet", "pedestal wash basin white"]),
    _c("putty_sealants", "construction", "3214", 18, 18, "Bag", (650, 1200), (10, 200), "N9 II-56", [
        "Birla White wall care putty", "JK wall putty 40kg", "acrylic putty", "silicone sealant cartridge",
        "Asian Paints TruCare putty", "caulking compound", "waterproof wall putty", "mastic sealant 280ml"]),
    _c("aluminium_structures", "construction", "7610", 18, 18, "Sqft", (450, 1400), (50, 1500), "N9 II-339", [
        "Aluminium section window frames", "aluminium partition system", "Jindal aluminium door frames",
        "Al curtain wall structure", "alu. glazing frames", "aluminium railing system",
        "aluminium scaffolding tower", "Al sliding window frame"]),
    # ----------------------------------------------------------------------- office
    _c("laptop", "office", "8471", 18, 18, "Nos", (42000, 78000), (1, 6), "N9 II-456", [
        "Dell Latitude 5440 i5", "HP ProBook 440 G10", "Lenovo ThinkPad E14 Gen 5", "Laptop Core i5 16GB RAM",
        "Notebook computer 14in", "Apple MacBook Air M2", "Asus ExpertBook B1", "Acer TravelMate P2 laptop"]),
    _c("computer_parts", "office", "8473", 18, 18, "Nos", (1800, 42000), (1, 10), "N9 II-458", [
        "DDR5 RAM 16GB module", "Motherboard B760", "Graphics card RTX 4060", "laptop battery replacement",
        "server RAM 32GB ECC", "replacement laptop keyboard", "CPU cabinet with fans", "laptop display panel 14in"]),
    _c("printer", "office", "8443", 18, 18, "Nos", (9000, 24000), (1, 3), "N9 II-430", [
        "Laser Printer A4 Mono", "HP LaserJet Pro M126nw", "Canon imageRUNNER 2206N copier", "Epson EcoTank L3250",
        "Brother multifunction printer", "Kyocera ECOSYS MFP", "label printer TSC TE244", "Zebra barcode printer"]),
    _c("office_furniture", "office", "9403", 18, 18, "Nos", (6500, 18000), (2, 20), "N9 II-612", [
        "Office Workstation Table", "Godrej Interio steel almirah", "modular workstation 4 seater",
        "conference table 10 pax", "filing cabinet 4 drawer", "reception desk", "compactor storage system",
        "Featherlite office desk"]),
    _c("phones_network", "office", "8517", 18, 18, "Nos", (2500, 82000), (1, 8), "N9 II-490", [
        "Apple iPhone 15 128GB", "Samsung Galaxy S24", "OnePlus 12R mobile", "Cisco IP phone 7821",
        "TP-Link router Archer", "Poly conference phone", "mobile handset Redmi Note 13", "D-Link 24 port switch"]),
    _c("air_conditioner", "office", "8415", 28, 18, "Nos", (32000, 46000), (1, 4), "N9 II-404", [
        "Split Air Conditioner 1.5T", "Daikin 1.5 ton inverter split AC", "Voltas cassette AC 2 TR",
        "Blue Star window AC", "LG dual inverter AC 1 ton", "tower AC 3 ton", "ductable AC unit 8.5 TR",
        "Hitachi split ac 2 ton 5 star"]),
    _c("pens_markers", "office", "9608", 18, 18, "Box", (60, 900), (5, 60), "N9 II-626", [
        "Reynolds ball pens box", "Cello gel pens", "whiteboard markers (Camlin)", "Parker Vector pens",
        "highlighter set", "Pilot V7 pens", "permanent marker black", "Linc pentonic ball pen 10 pk"]),
    _c("tissue_paper", "office", "4818", 18, 18, "Pack", (45, 900), (10, 200), "N9 II-184", [
        "Toilet paper rolls 2 ply", "facial tissue box", "paper napkins 30x30", "kitchen towel rolls",
        "Origami tissue pack", "hand towel C-fold", "jumbo toilet roll", "Selpak napkins"]),
    # ------------------------------------------------------------------- household
    _c("led_tv", "household", "8528", 28, 18, "Nos", (38000, 90000), (1, 4), "N9 II-500", [
        "LED Television 55in", "Sony Bravia 55X80L", "Samsung Crystal 4K 43in", "LG OLED 65 inch",
        "Mi smart TV 43", "TCL QLED 55", "Panasonic 50in 4K TV", "OnePlus Y1S TV 50in"]),
    _c("refrigerator", "household", "8418", 18, 18, "Nos", (14000, 95000), (1, 3), "N9 II-407", [
        "Samsung double door fridge 345L", "LG 260L frost free refrigerator", "Godrej single door fridge",
        "visi cooler 300L", "deep freezer 400L", "Whirlpool 3 door fridge", "Haier side-by-side refrigerator",
        "mini bar fridge 40L"]),
    _c("washing_machine", "household", "8450", 18, 18, "Nos", (12000, 85000), (1, 3), "N9 II-437", [
        "IFB front load 8kg", "LG top load washing machine", "Samsung 7kg fully automatic",
        "Whirlpool semi-automatic 9kg", "Bosch washer", "commercial laundry machine 25kg",
        "Godrej washing machine 6.5kg", "washer dryer combo"]),
    _c("water_heater", "household", "8516", 18, 18, "Nos", (1200, 14000), (1, 6), "N9 II-489", [
        "Racold geyser 25L", "AO Smith water heater", "instant geyser 3L", "Bajaj storage water heater",
        "Havells Monza geyser", "electric kettle 1.5L", "oil filled room heater", "induction cooktop"]),
    _c("mixer_grinder", "household", "8509", 18, 18, "Nos", (1800, 9000), (1, 10), "N9 II-482", [
        "Philips mixer grinder 750W", "Preethi Zodiac mixer", "Bajaj juicer mixer grinder", "Sujata dynamix",
        "Prestige hand blender", "Inalsa food processor", "wet grinder 2L", "Butterfly mixie 3 jar"]),
    # -------------------------------------------------------------------- giftable
    _c("watches", "giftable", "9102", 18, 18, "Nos", (2500, 9000), (2, 60), "N9 II-584", [
        "Wrist Watches", "Titan Edge watch", "Fossil chronograph", "Fastrack analog watches", "Casio G-Shock",
        "Sonata watches box of 10", "Timex mens watch", "Titan Raga ladies watch"]),
    _c("jewellery", "giftable", "7113", 3, 3, "Nos", (6000, 95000), (1, 20), "N9 IV-10", [
        "Gold pendant 18K", "silver jewellery set", "Tanishq gold earrings", "diamond studded ring",
        "silver bracelet 925", "Kalyan gold chain 22K", "silver anklets payal", "platinum ring"]),
    _c("perfume", "giftable", "3303", 18, 18, "Nos", (450, 7500), (2, 100), "N9 II-60", [
        "Davidoff Cool Water EDT", "perfume combo pack (EDT)", "Titan Skinn EDP", "Bella Vita perfume combo",
        "Calvin Klein EDT 100ml", "Wild Stone EDP", "Hugo Boss perfume", "Park Avenue eau de parfum"]),
    _c("luggage", "giftable", "4202", 18, 18, "Nos", (1500, 18000), (2, 60), "N9 II-145", [
        "VIP strolley 65cm", "Samsonite trolley bag", "American Tourister cabin luggage", "leather briefcase",
        "laptop backpack Wildcraft", "Safari hard luggage set", "executive office bag", "trolley bag set of 3"]),
    # ------------------------------------------------------------------- toiletries
    _c("toilet_soap", "toiletries", "3401", 18, 5, "Nos", (12, 70), (50, 2000), "N9 I-251", [
        "Dove soap bar 100g", "Lux toilet soap carton", "hotel guest soaps 25g", "Pears soap", "Lifebuoy bar soap",
        "Dettol soap pack", "Medimix soap", "Santoor soap 4 in 1"]),
    _c("shampoo_hairoil", "toiletries", "3305", 18, 5, "Nos", (2, 480), (50, 2000), "N9 I-245", [
        "Clinic Plus shampoo sachets", "Head & Shoulders 340ml", "Dabur Amla hair oil", "guest shampoo bottles 30ml",
        "Dove shampoo 1L", "Sunsilk shampoo pouch", "Bajaj almond drops hair oil", "Pantene shampoo"]),
    _c("toothpaste", "toiletries", "3306", 18, 5, "Nos", (8, 160), (50, 1500), "N9 I-246", [
        "Colgate toothpaste 200g", "Pepsodent", "Close-Up toothpaste", "dental kit toothpaste 12g",
        "Sensodyne 75g", "Dabur Red paste", "Patanjali Dant Kanti", "Himalaya Complete Care toothpaste"]),
    # ------------------------------------------------------------------------- misc
    _c("medicaments", "misc", "3004", 12, 5, "Strip", (12, 120), (20, 500), "N9 I-234", [
        "Paracetamol 500mg", "Dolo 650 strips", "first aid medicines", "Crocin advance", "ORS sachets",
        "Betadine ointment", "Combiflam tablets", "Azithromycin 500 strip"]),
    _c("books", "misc", "4901", 0, 0, "Nos", (450, 2500), (1, 15), "N10-132", [
        "Technical Reference Book", "IS code books (BIS)", "accounting textbooks set", "Bare Act - CGST",
        "engineering handbooks", "Python programming book", "Taxmann GST manual", "reference books for library"]),
    _c("uniform_tshirts", "misc", "6109", 5, 5, "Nos", (180, 450), (20, 300), "N9 I-388", [
        "Cotton T-Shirt uniform", "polo t-shirts with logo", "round neck tees (printed)", "staff uniform T-shirts",
        "hosiery t shirt", "Jockey crew neck tee", "dri-fit t-shirts", "promotional t-shirts"]),
    # ------------------------------------------------- gym equipment (goods, not a membership)
    _c("gym_equipment", "gym_equipment", "9506", 18, 18, "Nos", (2500, 450000), (1, 10), "N9 II-619", [
        "Treadmill commercial", "Life Fitness elliptical", "dumbbell set 2.5-25kg", "Olympic barbell + plates",
        "multi-gym station", "spin bikes", "Cybex leg press", "power rack with pull-up bar"]),
    # -------------------------------------------------------------------- car parts
    _c("car_parts", "car_parts", "8708", 28, 18, "Nos", (450, 38000), (1, 40), "N9 II-544", [
        "Bosch brake pads", "clutch plate assembly", "MGP shock absorber", "front bumper Swift",
        "radiator assy Innova", "Valeo clutch kit", "disc brake rotor", "silencer assembly"]),
    # ----------------------------------------------------------------------- services
    _c("it_consulting", "services", "998313", 18, 18, "Hrs", (1500, 4500), (8, 120), "N15 n/a (S.No.21(ii))", [
        "IT Consulting Services", "software development charges - sprint 4", "SAP S/4 implementation support",
        "custom app dev (React)", "IT consultancy fees", "tech support retainer", "ERP customisation services",
        "managed IT services"]),
    _c("cloud_hosting", "services", "998315", 18, 18, "Month", (3000, 180000), (1, 3), "N15 n/a", [
        "AWS cloud hosting charges", "Azure subscription consumption", "web hosting annual", "VPS server rental",
        "data centre colocation", "cloud backup services", "DigitalOcean droplets", "dedicated server hosting"]),
    _c("software_licence", "services", "997331", 18, 18, "Nos", (900, 95000), (1, 50), "N15 n/a", [
        "Microsoft 365 Business licences", "Tally Prime Gold licence", "Adobe Creative Cloud", "AutoCAD subscription",
        "antivirus licences Quick Heal", "Zoho One subscription", "Windows 11 Pro licence", "SolidWorks annual licence"]),
    _c("advertising", "services", "998361", 18, 18, "Job", (15000, 450000), (1, 1), "N15 n/a", [
        "digital marketing - Google ads", "newspaper ad - Times of India", "hoarding display charges", "FM radio spots",
        "social media marketing retainer", "print ad design + placement", "outdoor branding (bus shelters)",
        "SEO & SEM services"]),
    _c("audit_accounting", "services", "998221", 18, 18, "Job", (8000, 250000), (1, 1), "N15 n/a", [
        "Statutory audit fees", "tax audit u/s 44AB", "GST return filing fees", "internal audit - Q2",
        "accounting & bookkeeping", "ROC compliance fees", "CA professional charges", "TDS return filing"]),
    _c("manpower_supply", "services", "998513", 18, 18, "Month", (18000, 450000), (1, 1), "N15 n/a", [
        "manpower supply - helpers", "contract labour charges", "temp staffing services",
        "data entry operators on contract", "outsourced staff - 5 pax", "labour supply (unskilled)",
        "payroll staffing services", "contract staff billing"]),
    _c("housekeeping", "services", "998533", 18, 18, "Month", (12000, 180000), (1, 1), "N15 n/a", [
        "housekeeping services", "office cleaning charges", "deep cleaning - factory", "pest control services",
        "facility management - soft services", "janitorial services", "sanitization charges",
        "safai karmachari services"]),
    _c("training", "services", "999293", 18, 18, "Job", (15000, 350000), (1, 1), "N15 n/a", [
        "corporate training - Excel", "soft skills workshop", "leadership training program",
        "safety training (NEBOSH)", "POSH awareness session", "technical training fees", "sales training - 2 days",
        "online course licences"]),
    _c("event_management", "services", "998596", 18, 18, "Job", (45000, 900000), (1, 1), "N15 n/a", [
        "event management charges", "dealer meet organisation", "conference setup & AV", "booth design services",
        "product launch event", "annual sales conference management", "event production services",
        "stage, sound & lights"]),
    _c("amc_repairs", "services", "998719", 18, 18, "Job", (12000, 90000), (1, 1), "N15 n/a", [
        "Annual Maintenance Contract - Machinery", "AMC for DG set", "CNC machine servicing", "lift AMC charges",
        "AC servicing contract", "breakdown repair - compressor", "preventive maintenance - quarterly", "UPS AMC"]),
    _c("office_rent", "services", "997212", 18, 18, "Month", (45000, 260000), (1, 1), "N15 n/a", [
        "Office Rent", "rent for warehouse premises", "lease rental - office", "godown rent",
        "commercial premises rent", "shop rent - monthly", "co-working seats rent", "factory shed rent"]),
    _c("telecom", "services", "998412", 18, 18, "Month", (2500, 18000), (1, 1), "N15 n/a", [
        "Telecommunication Services", "Airtel postpaid bill", "Jio Fiber broadband", "leased line charges ILL",
        "mobile bill - corporate plan", "Vi business postpaid", "MPLS link rental", "BSNL landline"]),
    _c("courier", "services", "996812", 18, 18, "Shipment", (90, 900), (5, 120), "N15 S.No.9(ii)", [
        "Courier Services", "Blue Dart shipments", "DTDC courier charges", "Delhivery B2B courier",
        "documents courier - monthly", "express parcel charges", "Professional Couriers", "air courier - docs"]),
    # ------------------------------------------------------------------------- travel
    _c("hotel_stay", "travel", "996311", 12, 5, "Night", (3500, 7000), (1, 8), "N15 S.No.7(i)", [
        "Hotel Accommodation", "room charges - 2 nights", "Lemon Tree room rent", "lodging charges",
        "hotel stay (business trip)", "Ginger hotel room tariff", "guest house accommodation", "OYO rooms booking"]),
    _c("air_travel", "travel", "996425", 5, 5, "Ticket", (4500, 14000), (1, 6), "N15 n/a", [
        "Air Travel Economy", "IndiGo air ticket", "economy airfare BOM-DEL", "Air India economy ticket",
        "flight booking - economy", "Akasa Air ticket", "air fare (economy class)", "SpiceJet economy fare"]),
    # ---------------------------------------------------------------- reverse charge
    _c("gta_freight", "rcm", "996791", 5, 5, "Trip", (6000, 45000), (1, 8), "N15 S.No.9(iii): RCM option unchanged", [
        "Goods Transport Agency freight", "freight charges - LR no.", "transport charges (GTA)",
        "lorry hire - consignment", "truck freight Pune-Chennai", "bhada (freight) - GTA", "carriage inward charges",
        "full truck load freight"], reverse_charge=True),
    _c("legal_fees", "rcm", "998211", 18, 18, "Job", (15000, 150000), (1, 1), "N15 n/a", [
        "Legal fees - advocate", "professional fees for legal opinion", "litigation fees (High Court)", "vakil fees",
        "legal retainership", "drafting of agreements - advocate", "appearance fees - tribunal", "counsel fees"],
       reverse_charge=True),
    _c("security_services", "rcm", "998525", 18, 18, "Month", (40000, 160000), (1, 1), "N15 n/a", [
        "Security Services", "security guards - 4 shifts", "chowkidar services", "watch & ward charges",
        "security manpower (non-corporate)", "night guard charges", "gate security services", "guarding services"],
       reverse_charge=True),
    # ------------------------------------------- s.17(5)(a)/(ab): passenger vehicles <= 13 seats
    _c("small_car", "motor_vehicle", "8703", 28, 18, "Nos", (450000, 900000), (1, 2), "N9 II-534; CC S.No.50 Nil", [
        "Maruti Suzuki Swift VXi", "Hyundai Grand i10 Nios", "Tata Tiago XZ", "Maruti WagonR LXi", "Renault Kwid RXT",
        "Maruti Alto K10", "Tata Punch petrol", "Maruti Dzire petrol"], category=MV, cess_rate=1),
    _c("suv", "motor_vehicle", "8703", 28, 40, "Nos", (1450000, 2400000), (1, 1), "N9 III-5; CC S.No.52B Nil", [
        "Motor Car SUV 7-seater", "Toyota Innova Crysta 2.4 VX", "Mahindra XUV700 AX7", "Toyota Fortuner 4x2 AT",
        "Mahindra Scorpio-N Z8", "Hyundai Tucson", "MG Hector Plus diesel", "Tata Safari XZ+"],
       category=MV, cess_rate=22),
    _c("car_servicing", "motor_vehicle", "998714", 18, 18, "Job", (6000, 45000), (1, 1), "N15 n/a", [
        "Car Servicing and Repair", "periodic maintenance service (car)", "wheel alignment & balancing",
        "car denting painting", "AC gas refill - car", "authorised service bill - 40k km", "vehicle repair labour",
        "gaadi service charges"], category=MV),
    # ----------------------------------------------------------- s.17(5)(b)(i): food & beverages
    _c("restaurant_meals", "food", "996331", 5, 5, "Plate", (450, 1500), (8, 150), "N15 n/a (S.No.7(ii))", [
        "Restaurant bill", "food & beverages - dinner", "lunch buffet charges", "Haldiram's restaurant bill",
        "catering - working lunch", "Barbeque Nation dinner", "khana - team lunch", "F&B bill"], category=FB),
    _c("tea", "food", "0902", 5, 5, "Kg", (280, 900), (2, 60), "N9 I-34", [
        "Tata Tea Gold 1kg", "Red Label tea", "chai patti 500g", "Wagh Bakri tea", "green tea bags Lipton",
        "Taj Mahal tea", "CTC tea loose", "Society tea"], category=FB),
    _c("coffee", "food", "0901", 5, 5, "Kg", (450, 1800), (1, 40), "N9 I-33", [
        "filter coffee powder 1kg", "roasted coffee beans (arabica)", "Coorg coffee powder", "Blue Tokai coffee beans",
        "Lavazza coffee beans", "espresso beans 1kg", "ground coffee for vending", "Malabar roasted coffee"],
       category=FB),
    _c("biscuits", "food", "1905", 18, 5, "Box", (40, 900), (10, 300), "N9 I-123", [
        "Parle-G biscuits carton", "Britannia Good Day", "cookies assorted", "Sunfeast Marie Light", "Oreo biscuits",
        "cream biscuits box", "McVitie's digestive", "Hide & Seek"], category=FB),
    _c("fruit_juice", "food", "2009", 12, 5, "Case", (300, 1500), (2, 80), "N9 I-133", [
        "Real fruit juice 1L", "Tropicana orange juice", "mixed fruit juice tetra pack", "B Natural guava",
        "apple juice 200ml (24 pc)", "Raw Pressery cold pressed juice", "Real Activ juice", "litchi juice 1L"],
       category=FB),
    _c("aerated_drinks", "food", "2202", 28, 40, "Case", (420, 700), (5, 40), "N9 III-1; CC S.No.2 Nil", [
        "Aerated Beverages", "Coca-Cola 300ml crate", "Pepsi 2.25L", "Thums Up cans", "Sprite 750ml",
        "soft drinks assorted", "Limca", "cold drinks (Mirinda) 24 pc"], category=FB, cess_rate=12),
    _c("packaged_rice", "food", "1006", 5, 5, "Bag", (450, 2600), (2, 60), "N9 I-48", [
        "India Gate basmati rice 5kg", "Daawat Rozana basmati", "sona masoori rice 25kg (branded)", "Kohinoor rice pack",
        "Fortune biryani rice", "branded rice 10 kg bag", "kolam rice (packed)", "Lal Qilla basmati"], category=FB),
    _c("edible_oil", "food", "1507", 5, 5, "Tin", (1700, 2300), (2, 20), "N9 I-84", [
        "Refined Soyabean Oil 15L", "Fortune soya oil", "soyabean oil tin 15 kg", "Dhara soya oil",
        "Nature Fresh soya", "refined oil (soya) 1L pouch", "Ruchi Gold soya", "Mahakosh soyabean oil"], category=FB),
    _c("sugar", "food", "1701", 5, 5, "Qtl", (3800, 4400), (1, 20), "N9 I-105", [
        "Sugar M-30", "cheeni 50kg bag", "Madhur sugar 5kg", "white crystal sugar S-30", "refined sugar sachets",
        "Uttam sugar", "sugar (M grade) quintal", "Dhampure sugar"], category=FB),
    _c("pulses_loose", "food", "0713", 0, 0, "Kg", (110, 160), (50, 500), "N10-39", [
        "Toor Dal unbranded loose", "chana dal loose", "moong dal (loose)", "masoor dal bulk", "arhar dal 50kg bag",
        "urad dal unbranded", "kabuli chana loose", "rajma loose"], category=FB),
    # --------------------------------------------------- s.17(5)(b)(ii): club / fitness membership
    _c("gym_membership", "club", "999723", 18, 5, "Year", (18000, 60000), (1, 10), "N15 S.No.35(i)", [
        "Gym and Fitness Centre Membership", "Cult.fit corporate pass", "annual gym subscr.", "fitness club fees - Q3",
        "health club membrshp", "Gold's Gym membership", "Anytime Fitness annual plan",
        "corporate wellness - fitness passes"], category=CLUB),
    _c("club_membership", "club", "999599", 18, 18, "Year", (25000, 400000), (1, 4), "N15 n/a", [
        "club membership fees", "Gymkhana annual subscription", "golf club corporate membership",
        "country club entrance fee", "recreation club charges - annual", "sports club membership (corporate)",
        "clubhouse membership dues", "city club life membership"], category=CLUB),
    # ------------------------------------- s.17(5)(c): works contract for immovable property
    _c("wc_building", "works_contract", "995414", 18, 18, "Job", (350000, 2500000), (1, 1), "N15 S.No.3(xii) n/a", [
        "Works Contract - building extension", "civil construction works (RA bill 3)", "RCC structure work contract",
        "turnkey construction - admin block", "building construction labour + material", "G+2 construction works",
        "factory shed construction (composite)", "constrn work - RA bill no. 5"], category=WC),
    _c("wc_interior", "works_contract", "995468", 18, 18, "Job", (150000, 1800000), (1, 1), "N15 S.No.3(xii) n/a", [
        "interior fit-out works", "false ceiling & partition work", "office interiors turnkey",
        "flooring & tiling works contract", "modular interior works (civil)", "carpentry & civil fit-out",
        "turnkey interior project - RA 2", "renovation works - office"], category=WC),
    _c("wc_electrical", "works_contract", "995461", 18, 18, "Job", (90000, 900000), (1, 1), "N15 S.No.3(xii) n/a", [
        "electrical wiring works contract", "internal electrification works", "building electrification - RA bill",
        "conduit wiring work", "lighting installation works", "earthing & wiring contract",
        "electrical works (supply + installation)", "bijli fitting kaam (building)"], category=WC),
)

BY_ID = {c.id: c for c in CONCEPTS}
FAMILIES = tuple(dict.fromkeys(c.family for c in CONCEPTS))
