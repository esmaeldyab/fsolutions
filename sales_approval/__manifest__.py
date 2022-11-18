# -*- coding: utf-8 -*-
###################################################################################
#
#    Authors: Mohamed Saber,mohamedabosaber94@gmail.com,+201153909418
###################################################################################
{
    'name': "Sales Approval",

    'summary': """
        Applied approval in Sales and CRM""",

    'description': """
        Applied approval in Sales and CRM
    """,

    'author': 'Mohamed Saber',
    'category': 'Sales',
    'version': '15.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'crm', 'sale_management', 'hr_approval_structure'],

    # always loaded
    'data': [
        'views/sale_order.xml',
        'views/crm_lead.xml',
    ],
}
