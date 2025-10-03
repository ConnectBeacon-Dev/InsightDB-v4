#!/usr/bin/env python3
"""
Classification helpers for Products, Facilities, Certifications, and other entities
Provides standardized categorization across all data entities
"""

from industry_reference_data import get_industry_from_hsn

# Product Category Classification based on keywords
PRODUCT_CATEGORIES = {
    'Electrical Components': [
        'transformer', 'motor', 'generator', 'alternator', 'relay', 'contactor',
        'switch', 'circuit breaker', 'fuse', 'panel', 'busbar', 'conductor',
        'cable', 'wire', 'capacitor', 'resistor', 'inductor', 'coil',
    ],
    'Power Systems': [
        'substation', 'switchgear', 'power distribution', 'control panel',
        'transformer station', 'grid', 'transmission', 'UPS', 'inverter',
        'battery', 'energy storage', 'solar panel', 'wind turbine',
    ],
    'Electronic Devices': [
        'semiconductor', 'diode', 'transistor', 'IC', 'PCB', 'LED',
        'sensor', 'actuator', 'microcontroller', 'processor', 'chip',
    ],
    'Lighting Products': [
        'lamp', 'light', 'lighting', 'fixture', 'bulb', 'LED light',
        'street light', 'flood light', 'emergency light',
    ],
    'Pharmaceutical Products': [
        'tablet', 'capsule', 'injection', 'syrup', 'ointment', 'cream',
        'vaccine', 'antibiotic', 'medicine', 'drug', 'formulation',
    ],
    'Automotive Parts': [
        'brake', 'clutch', 'gear', 'axle', 'suspension', 'steering',
        'engine part', 'transmission', 'wheel', 'tyre', 'battery',
    ],
    'Metal Products': [
        'steel', 'iron', 'aluminum', 'copper', 'brass', 'alloy',
        'rod', 'bar', 'sheet', 'plate', 'coil', 'wire rope', 'casting',
    ],
    'Chemical Products': [
        'acid', 'alkali', 'solvent', 'resin', 'polymer', 'coating',
        'paint', 'adhesive', 'fertilizer', 'pesticide',
    ],
    'Textile Products': [
        'fabric', 'yarn', 'thread', 'cloth', 'garment', 'apparel',
        'cotton', 'polyester', 'silk', 'wool',
    ],
    'Machinery & Equipment': [
        'pump', 'compressor', 'valve', 'bearing', 'conveyor', 'crane',
        'lathe', 'machine tool', 'hydraulic', 'pneumatic',
    ],
    'Test & Measurement': [
        'meter', 'gauge', 'instrument', 'tester', 'analyzer', 'sensor',
        'oscilloscope', 'multimeter', 'calibration equipment',
    ],
}

# Facility Type Classification
FACILITY_TYPES = {
    'R&D Facilities': {
        'keywords': ['research', 'development', 'innovation', 'prototyping', 'pilot plant'],
        'capabilities': ['design', 'testing', 'validation', 'simulation', 'modeling'],
    },
    'Testing & Quality': {
        'keywords': ['testing', 'quality', 'inspection', 'laboratory', 'QC', 'QA'],
        'capabilities': ['destructive testing', 'non-destructive testing', 'calibration',
                        'material testing', 'performance testing', 'reliability testing'],
        'equipment': ['universal testing machine', 'hardness tester', 'microscope',
                     'spectrometer', 'chromatograph', 'tensile tester'],
    },
    'Manufacturing': {
        'keywords': ['manufacturing', 'production', 'assembly', 'fabrication', 'machining'],
        'capabilities': ['CNC machining', 'welding', 'casting', 'forging', 'molding',
                        'heat treatment', 'surface treatment', 'painting'],
        'equipment': ['CNC machine', 'lathe', 'milling machine', 'press', 'furnace',
                     'assembly line', 'welding machine'],
    },
    'Calibration': {
        'keywords': ['calibration', 'metrology', 'standards', 'precision'],
        'capabilities': ['dimensional calibration', 'electrical calibration', 
                        'pressure calibration', 'temperature calibration'],
    },
    'Environmental Testing': {
        'keywords': ['environmental', 'climate', 'EMC', 'EMI', 'vibration', 'shock'],
        'capabilities': ['temperature cycling', 'humidity testing', 'salt spray',
                        'vibration testing', 'shock testing', 'EMC testing'],
        'equipment': ['climate chamber', 'vibration table', 'shaker', 'EMC chamber'],
    },
}

# Certification Type Classification
CERTIFICATION_TYPES = {
    'Quality Management': [
        'ISO 9001', 'ISO 9000', 'TS 16949', 'IATF 16949', 'AS9100',
    ],
    'Environmental': [
        'ISO 14001', 'ISO 14000', 'OHSAS 18001', 'ISO 45001',
    ],
    'Product Safety': [
        'CE', 'UL', 'CSA', 'BIS', 'ISI', 'FCC', 'RoHS', 'REACH',
    ],
    'Industry Specific': [
        'ISO 13485',  # Medical devices
        'ISO/TS 22163',  # Railway
        'ISO 17025',  # Testing labs
        'NABL',  # Lab accreditation
        'FSSAI',  # Food safety
        'WHO GMP',  # Pharma
        'USFDA',  # Pharma/Medical
    ],
    'Information Security': [
        'ISO 27001', 'ISO 20000', 'CMMI', 'SOC 2',
    ],
    'Defence & Aerospace': [
        'AS9100', 'NADCAP', 'Defence approval',
    ],
}

# Accreditation Bodies
ACCREDITATION_BODIES = {
    'NABL': 'National Accreditation Board for Testing and Calibration Laboratories',
    'BIS': 'Bureau of Indian Standards',
    'CERT-IN': 'Indian Computer Emergency Response Team',
    'DGQA': 'Directorate General of Quality Assurance (Defence)',
    'DRDO': 'Defence Research and Development Organisation',
    'AERB': 'Atomic Energy Regulatory Board',
    'FSSAI': 'Food Safety and Standards Authority of India',
    'CDSCO': 'Central Drugs Standard Control Organization',
    'PESO': 'Petroleum and Explosives Safety Organisation',
}


def classify_product(product_name, product_desc='', hsn_code=None):
    """
    Classify a product into categories
    Returns: {
        'category': str,
        'industry': str,
        'hsn_category': str
    }
    """
    result = {
        'category': 'Other',
        'industry': None,
        'hsn_category': None
    }
    
    # HSN-based classification (most accurate)
    if hsn_code:
        result['industry'] = get_industry_from_hsn(hsn_code)
    
    # Keyword-based category
    text = f"{product_name} {product_desc}".lower()
    for category, keywords in PRODUCT_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in text:
                result['category'] = category
                break
        if result['category'] != 'Other':
            break
    
    return result


def classify_facility(facility_name='', facility_desc='', facility_type='', equipment=''):
    """
    Classify a facility/capability
    Returns: {
        'primary_type': str,
        'capabilities': list,
        'accreditation_suggested': str
    }
    """
    result = {
        'primary_type': facility_type or 'Other',
        'capabilities': [],
        'accreditation_suggested': None
    }
    
    text = f"{facility_name} {facility_desc} {facility_type} {equipment}".lower()
    
    # Check each facility type
    scores = {}
    for fac_type, details in FACILITY_TYPES.items():
        score = 0
        # Check keywords
        if 'keywords' in details:
            for keyword in details['keywords']:
                if keyword.lower() in text:
                    score += 2
        # Check capabilities
        if 'capabilities' in details:
            for cap in details['capabilities']:
                if cap.lower() in text:
                    score += 1
                    if cap not in result['capabilities']:
                        result['capabilities'].append(cap)
        # Check equipment
        if 'equipment' in details:
            for eq in details['equipment']:
                if eq.lower() in text:
                    score += 1.5
        
        if score > 0:
            scores[fac_type] = score
    
    # Pick facility type with highest score
    if scores:
        result['primary_type'] = max(scores.items(), key=lambda x: x[1])[0]
    
    # Suggest accreditation
    if 'Testing' in result['primary_type'] or 'Quality' in result['primary_type']:
        result['accreditation_suggested'] = 'NABL (ISO 17025)'
    elif 'Manufacturing' in result['primary_type']:
        result['accreditation_suggested'] = 'ISO 9001'
    
    return result


def classify_certification(cert_name='', cert_number='', issuer=''):
    """
    Classify a certification
    Returns: {
        'type': str,
        'category': str,
        'issuing_body': str,
        'scope': str
    }
    """
    result = {
        'type': 'Other',
        'category': 'General',
        'issuing_body': issuer or 'Unknown',
        'scope': None
    }
    
    text = f"{cert_name} {cert_number} {issuer}".upper()
    
    # Check certification types
    for category, certs in CERTIFICATION_TYPES.items():
        for cert in certs:
            if cert.upper() in text:
                result['category'] = category
                result['type'] = cert
                break
        if result['type'] != 'Other':
            break
    
    # Identify issuing body
    for body, full_name in ACCREDITATION_BODIES.items():
        if body.upper() in text:
            result['issuing_body'] = f"{body} ({full_name})"
            break
    
    # Infer scope
    if 'ISO 9001' in result['type']:
        result['scope'] = 'Quality Management System'
    elif 'ISO 14001' in result['type']:
        result['scope'] = 'Environmental Management'
    elif 'ISO 27001' in result['type']:
        result['scope'] = 'Information Security'
    elif 'NABL' in text or 'ISO 17025' in result['type']:
        result['scope'] = 'Testing and Calibration Laboratory'
    elif 'BIS' in text or 'ISI' in text:
        result['scope'] = 'Product Standards and Certification'
    
    return result


def get_capability_keywords():
    """
    Return all capability keywords for search/matching
    """
    capabilities = set()
    for details in FACILITY_TYPES.values():
        if 'capabilities' in details:
            capabilities.update(details['capabilities'])
    return list(capabilities)


def get_equipment_keywords():
    """
    Return all equipment keywords for search/matching
    """
    equipment = set()
    for details in FACILITY_TYPES.values():
        if 'equipment' in details:
            equipment.update(details['equipment'])
    return list(equipment)
