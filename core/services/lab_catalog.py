"""Standard lab test catalog with Nepal OPD reference pricing (NPR)."""

from decimal import Decimal

from core.constants import DEFAULT_LAB_FEE

# Reference rates aligned with typical Nepal private OPD / diagnostic lab tariffs.
LAB_TEST_CATALOG = [
    {
        'code': 'cbc',
        'name': 'Complete Blood Count (CBC)',
        'category': 'Hematology',
        'fee': Decimal('450'),
    },
    {
        'code': 'lipid_profile',
        'name': 'Lipid Profile',
        'category': 'Biochemistry',
        'fee': Decimal('1350'),
    },
    {
        'code': 'fbs',
        'name': 'Blood Glucose (Fasting)',
        'category': 'Biochemistry',
        'fee': Decimal('200'),
    },
    {
        'code': 'lft',
        'name': 'Liver Function Test (LFT)',
        'category': 'Biochemistry',
        'fee': Decimal('950'),
    },
    {
        'code': 'kft',
        'name': 'Kidney Function Test (KFT)',
        'category': 'Biochemistry',
        'fee': Decimal('950'),
    },
    {
        'code': 'ecg',
        'name': 'ECG (12-lead)',
        'category': 'Cardiology',
        'fee': Decimal('650'),
    },
    {
        'code': 'troponin_i',
        'name': 'Troponin I',
        'category': 'Cardiology',
        'fee': Decimal('3200'),
    },
    {
        'code': 'tsh',
        'name': 'Thyroid Profile (TSH)',
        'category': 'Endocrinology',
        'fee': Decimal('750'),
    },
    {
        'code': 'vitamin_d3',
        'name': 'Vitamin D3',
        'category': 'Biochemistry',
        'fee': Decimal('2800'),
    },
    {
        'code': 'hba1c',
        'name': 'HbA1c',
        'category': 'Biochemistry',
        'fee': Decimal('950'),
    },
]

_BY_NAME = {item['name'].casefold(): item for item in LAB_TEST_CATALOG}
_BY_CODE = {item['code'].casefold(): item for item in LAB_TEST_CATALOG}


def serialize_lab_catalog():
    return [
        {
            'code': item['code'],
            'name': item['name'],
            'category': item['category'],
            'fee': float(item['fee']),
        }
        for item in LAB_TEST_CATALOG
    ]


def resolve_lab_test(test_name_or_code):
    """Match a doctor-selected test to catalog entry; unknown names use default fee."""
    key = (test_name_or_code or '').strip()
    if not key:
        raise ValueError('Lab test name is required')

    match = _BY_NAME.get(key.casefold()) or _BY_CODE.get(key.casefold())
    if match:
        return {
            'code': match['code'],
            'name': match['name'],
            'category': match['category'],
            'fee': match['fee'],
        }

    return {
        'code': None,
        'name': key,
        'category': 'Other',
        'fee': Decimal(str(DEFAULT_LAB_FEE)),
    }


def get_lab_fee(test_name_or_code):
    return resolve_lab_test(test_name_or_code)['fee']
