#!/usr/bin/env python3
"""
Reference data for industry classification using HSN codes and known company patterns
HSN (Harmonized System of Nomenclature) - International product classification standard
"""

# HSN Code ranges mapped to industries
# Format: (start_code, end_code) tuples
HSN_INDUSTRY_MAP = {
    'Electrical & Electronics': [
        (8501, 8548),  # Electric motors, generators, transformers, batteries, cables, etc.
        (8504, 8505),  # Transformers, inductors
        (8536, 8548),  # Electrical switches, relays, cables, panels
        (9032, 9033),  # Automatic regulating instruments
        (8541, 8542),  # Semiconductors, transistors
        (9405, 9405),  # Lamps and lighting fittings
    ],
    'Pharmaceuticals': [
        (2936, 3006),  # All pharmaceutical products
        (3001, 3006),  # Medical preparations, vaccines
        (3822, 3822),  # Diagnostic reagents
    ],
    'Automotive': [
        (8701, 8716),  # Vehicles, tractors, parts
        (8407, 8409),  # Engines
        (8708, 8708),  # Vehicle parts
        (4011, 4013),  # Rubber tyres
    ],
    'Steel & Metals': [
        (7201, 7229),  # Iron and steel
        (7301, 7326),  # Articles of iron/steel
        (7401, 7419),  # Copper
        (7601, 7616),  # Aluminium
    ],
    'Chemicals': [
        (2801, 2853),  # Inorganic chemicals
        (2901, 2942),  # Organic chemicals
        (3201, 3215),  # Paints, dyes
        (3801, 3826),  # Chemical products
    ],
    'Textiles': [
        (5001, 5212),  # Silk, wool, cotton
        (5401, 5516),  # Man-made fibers
        (6001, 6117),  # Knitted fabrics, clothing
        (6201, 6217),  # Clothing
    ],
    'Plastics': [
        (3901, 3926),  # Plastics and articles
    ],
    'Food & Beverages': [
        (1, 2499),     # Agricultural products
        (1501, 1522),  # Fats and oils
        (1601, 1704),  # Meat, sugar preparations
        (1801, 2106),  # Cocoa, cereals, edible preparations
        (2201, 2209),  # Beverages
    ],
    'Machinery & Equipment': [
        (8401, 8406),  # Reactors, boilers, turbines
        (8410, 8485),  # Pumps, engines, machinery
        (8486, 8487),  # Semiconductor manufacturing equipment
        (9024, 9031),  # Testing/measuring instruments
    ],
    'IT & Software': [
        (8471, 8473),  # Computing machines
        (8517, 8517),  # Communication equipment
        (8523, 8529),  # Recording media, monitors
    ],
    'Aerospace & Defence': [
        (8801, 8805),  # Aircraft, spacecraft
        (9301, 9307),  # Arms and ammunition
    ],
    'Construction & Engineering': [
        (6801, 6815),  # Stone, cement articles
        (6901, 6914),  # Ceramic products
        (2523, 2523),  # Portland cement
        (6807, 6810),  # Gypsum, cement articles
    ],
}

# Known major companies for exact matching
KNOWN_COMPANIES = {
    # Electrical & Electronics
    'TATA POWER': 'Electrical & Electronics',
    'BHEL': 'Electrical & Electronics',
    'BHARAT HEAVY ELECTRICALS': 'Electrical & Electronics',
    'SIEMENS': 'Electrical & Electronics',
    'ABB': 'Electrical & Electronics',
    'SCHNEIDER ELECTRIC': 'Electrical & Electronics',
    'CROMPTON GREAVES': 'Electrical & Electronics',
    'HAVELLS': 'Electrical & Electronics',
    'POLYCAB': 'Electrical & Electronics',
    'FINOLEX CABLES': 'Electrical & Electronics',
    'ELANTAS': 'Electrical & Electronics',
    'ELANTAS BECK': 'Electrical & Electronics',
    'KEI INDUSTRIES': 'Electrical & Electronics',
    'RR KABEL': 'Electrical & Electronics',
    'V-GUARD': 'Electrical & Electronics',
    'Orient ELECTRIC': 'Electrical & Electronics',
    'BAJAJ ELECTRICALS': 'Electrical & Electronics',
    'CROMPTON': 'Electrical & Electronics',
    
    # Pharmaceuticals
    'SUN PHARMA': 'Pharmaceuticals',
    'CIPLA': 'Pharmaceuticals',
    'DR REDDY': 'Pharmaceuticals',
    'LUPIN': 'Pharmaceuticals',
    'AUROBINDO': 'Pharmaceuticals',
    'EMCURE': 'Pharmaceuticals',
    'EMCURE PHARMACEUTICALS': 'Pharmaceuticals',
    'BIOCON': 'Pharmaceuticals',
    'CADILA': 'Pharmaceuticals',
    'ZYDUS': 'Pharmaceuticals',
    'ALKEM': 'Pharmaceuticals',
    'TORRENT PHARMA': 'Pharmaceuticals',
    'GLENMARK': 'Pharmaceuticals',
    'IPCA': 'Pharmaceuticals',
    'MANKIND PHARMA': 'Pharmaceuticals',
    'SUN PHARMACEUTICAL': 'Pharmaceuticals',
    
    # Automotive
    'TATA MOTORS': 'Automotive',
    'MAHINDRA': 'Automotive',
    'MARUTI': 'Automotive',
    'HERO MOTOCORP': 'Automotive',
    'BAJAJ AUTO': 'Automotive',
    'TVS MOTOR': 'Automotive',
    'ASHOK LEYLAND': 'Automotive',
    'EICHER MOTORS': 'Automotive',
    'FORCE MOTORS': 'Automotive',
    'BHARAT FORGE': 'Automotive',
    'MOTHERSON SUMI': 'Automotive',
    'BOSCH': 'Automotive',
    'MINDA': 'Automotive',
    
    # Steel & Metals
    'TATA STEEL': 'Steel & Metals',
    'JSW STEEL': 'Steel & Metals',
    'JINDAL STEEL': 'Steel & Metals',
    'SAIL': 'Steel & Metals',
    'HINDALCO': 'Steel & Metals',
    'NALCO': 'Steel & Metals',
    'VEDANTA': 'Steel & Metals',
    'JINDAL STAINLESS': 'Steel & Metals',
    'RATNAMANI': 'Steel & Metals',
    
    # IT & Software
    'TCS': 'IT & Software',
    'INFOSYS': 'IT & Software',
    'WIPRO': 'IT & Software',
    'HCL': 'IT & Software',
    'TECH MAHINDRA': 'IT & Software',
    'LTI': 'IT & Software',
    'MINDTREE': 'IT & Software',
    'MPHASIS': 'IT & Software',
    'PERSISTENT': 'IT & Software',
    'CYIENT': 'IT & Software',
    
    # Aerospace & Defence
    'HAL': 'Aerospace & Defence',
    'HINDUSTAN AERONAUTICS': 'Aerospace & Defence',
    'BEL': 'Aerospace & Defence',
    'BHARAT ELECTRONICS': 'Aerospace & Defence',
    'BDL': 'Aerospace & Defence',
    'BHARAT DYNAMICS': 'Aerospace & Defence',
    'GRSE': 'Aerospace & Defence',
    'GARDEN REACH': 'Aerospace & Defence',
    'MDL': 'Aerospace & Defence',
    'MAZAGON DOCK': 'Aerospace & Defence',
    
    # Textiles
    'WELSPUN': 'Textiles',
    'TRIDENT': 'Textiles',
    'VARDHMAN': 'Textiles',
    'ARVIND': 'Textiles',
    'RAYMOND': 'Textiles',
    'GARWARE': 'Textiles',
    'GARWARE TECHNICAL FIBRES': 'Textiles',
    
    # Chemicals
    'DEEPAK NITRITE': 'Chemicals',
    'AARTI INDUSTRIES': 'Chemicals',
    'SRF': 'Chemicals',
    'PI INDUSTRIES': 'Chemicals',
    'GUJARAT FLUOROCHEMICALS': 'Chemicals',
    'VINATI ORGANICS': 'Chemicals',
    'NAVIN FLUORINE': 'Chemicals',
    'ALKYL AMINES': 'Chemicals',
    
    # Others
    'SAHYADRI': 'Manufacturing',
    'SAHYADRI INDUSTRIES': 'Manufacturing',
}


def get_industry_from_hsn(hsn_code):
    """
    Map HSN code to industry. Returns industry name or None.
    HSN code can be string like '8504' or '850410' or int.
    """
    if not hsn_code or str(hsn_code).strip() == '':
        return None
    
    try:
        # Extract first 4 digits (chapter level)
        hsn_str = str(hsn_code).strip()
        # Remove any non-numeric characters
        hsn_digits = ''.join(c for c in hsn_str if c.isdigit())
        if len(hsn_digits) < 4:
            return None
        
        hsn_chapter = int(hsn_digits[:4])
        
        # Check which industry this HSN falls into
        for industry, ranges in HSN_INDUSTRY_MAP.items():
            for start, end in ranges:
                if start <= hsn_chapter <= end:
                    return industry
    except (ValueError, TypeError):
        pass
    
    return None


def check_known_company(company_name):
    """Check if company name matches known major companies"""
    if not company_name:
        return None
    
    name_upper = company_name.upper().strip()
    
    # Exact match
    if name_upper in KNOWN_COMPANIES:
        return KNOWN_COMPANIES[name_upper]
    
    # Partial match (if known company name is in the company name)
    for known, industry in KNOWN_COMPANIES.items():
        if known in name_upper:
            return industry
    
    return None
