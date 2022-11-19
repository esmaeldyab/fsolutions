{
    'name': 'Payment Voucher',
    'description': 'Payment Voucher for multi lines',
    'version': '15.0.1',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'author': 'Mohamed Saber',
    'website': '',
    'depends': ['account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_voucher_view.xml',
    ],
    'application': True,
    'installable': True,
}
