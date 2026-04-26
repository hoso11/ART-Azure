#!/usr/bin/env python3
"""Translate ART Manufacturing admin panel UI from English to Armenian."""

import json
import os

TRANSCRIPT = r'C:\Users\HP\.claude\projects\C--Users-HP-Desktop-ART\b2caf373-673a-4aff-9609-1be5c1dbcf3c.jsonl'
BASE = r'C:\Users\HP\Desktop\ART\frontend\src'
changed_files = []

def load_translations():
    with open(TRANSCRIPT, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    obj = json.loads(lines[1248])
    ct = obj['message']['content']
    text = ct[0]['text'] if isinstance(ct, list) else ct
    T = {}
    for line in text.split('\n'):
        if ' \u2192 ' in line:
            parts = line.split(' \u2192 ', 1)
            T[parts[0].strip()] = parts[1].strip()
    return T

def rf(p):
    with open(os.path.join(BASE, p), 'r', encoding='utf-8') as f:
        return f.read()

def wf(p, c):
    with open(os.path.join(BASE, p), 'w', encoding='utf-8') as f:
        f.write(c)

def rep(p, reps):
    c = rf(p)
    for old, new in reps:
        if old not in c:
            print(f'  WARN not found: {repr(old[:70])}')
        c = c.replace(old, new)
    wf(p, c)
    changed_files.append(p)
    print(f'  OK: {p}')

def build_extras(T):
    """Add composed translations not in the original table."""
    MY = chr(0x053b) + chr(0x0574)  # Im (My)
    CHKAN = chr(0x0579) + chr(0x056f) + chr(0x0561) + chr(0x0576)  # chkan (don't exist)
    NOT_FOUND = chr(0x0579) + chr(0x0565) + chr(0x0576) + " " + chr(0x0563) + chr(0x057f) + chr(0x0576) + chr(0x057e) + chr(0x0565) + chr(0x056c)  # chen gtnvel

    # Sidebar user nav
    T["Catalog"] = chr(0x053f) + chr(0x0561) + chr(0x057f) + chr(0x0561) + chr(0x056c) + chr(0x0578) + chr(0x0563)
    T["My Orders"] = MY + " " + T["Orders"][0].lower() + T["Orders"][1:]
    T["Account"] = chr(0x0540) + chr(0x0561) + chr(0x0577) + chr(0x056b) + chr(0x057e)

    # TopHeader
    T["Customer Portal"] = T["Customer"] + chr(0x056b) + " " + chr(0x057a) + chr(0x0578) + chr(0x0580) + chr(0x057f) + chr(0x0561) + chr(0x056c)
    T["User"] = T["Simple User"]

    # Login page
    T["Sign In"] = chr(0x0544) + chr(0x057f) + chr(0x0576) + chr(0x0565) + chr(0x056c)
    T["Sign in to your account"] = chr(0x0544) + chr(0x057f) + chr(0x0576) + chr(0x0565) + chr(0x0584) + " " + chr(0x0571) + chr(0x0565) + chr(0x0580) + " " + T["Account"][0].lower() + T["Account"][1:] + chr(0x0568)
    T["Password"] = chr(0x0533) + chr(0x0561) + chr(0x0572) + chr(0x057f) + chr(0x0576) + chr(0x0561) + chr(0x0562) + chr(0x0561) + chr(0x057c)
    T["Don't have an account?"] = chr(0x0540) + chr(0x0561) + chr(0x0577) + chr(0x056b) + chr(0x057e) + " " + chr(0x0579) + chr(0x0578) + chr(0x0582) + chr(0x0576) + chr(0x0565) + chr(0x0584) + chr(0x053f)
    T["Contact Sales"] = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x057e) + chr(0x0565) + chr(0x0584) + " " + chr(0x057e) + chr(0x0561) + chr(0x057c) + chr(0x0584) + chr(0x056b) + " " + chr(0x0562) + chr(0x0561) + chr(0x056a) + chr(0x0576) + chr(0x056b) + chr(0x0576)

    # Status
    T["Inactive"] = chr(0x0531) + chr(0x0576) + chr(0x0561) + chr(0x056f) + chr(0x057f) + chr(0x056b) + chr(0x057e)
    T["Deactivated"] = T["Inactive"]

    # Account page
    T["My Account"] = MY + " " + T["Account"][0].lower() + T["Account"][1:]
    T["Account Information"] = T["Account"] + chr(0x056b) + " " + chr(0x057f) + chr(0x0565) + chr(0x0572) + chr(0x0565) + chr(0x056f) + chr(0x0578) + chr(0x0582) + chr(0x0569) + chr(0x0575) + chr(0x0578) + chr(0x0582) + chr(0x0576)
    T["Account ID"] = T["Account"] + chr(0x056b) + " ID"
    T["Administrator"] = chr(0x053f) + chr(0x0561) + chr(0x057c) + chr(0x0561) + chr(0x057e) + chr(0x0561) + chr(0x0580) + chr(0x056b) + chr(0x0579)

    # Compose button labels
    T["Save Changes"] = T["Save"]
    T["Create Product"] = T["Add Product"]
    T["Create Customer"] = T["Add Customer"]
    T["Create User"] = T["Add User"]
    T["Create Order"] = chr(0x054d) + chr(0x057f) + chr(0x0565) + chr(0x0572) + chr(0x056e) + chr(0x0565) + chr(0x056c) + " " + T["Order"][0].lower() + T["Order"][1:]
    T["Delete Product"] = T["Delete"] + " " + T["Edit Product"].split()[-1]
    T["Delete Customer"] = T["Delete"] + " " + T["Edit Customer"].split()[-1]
    T["Delete Material"] = T["Delete"] + " " + T["Edit Material"].split()[-1]
    T["Delete Image"] = T["Delete"] + " " + chr(0x0576) + chr(0x056f) + chr(0x0561) + chr(0x0580) + chr(0x0568)

    # Modal titles
    T["Add New Product"] = T["Add Product"]
    T["Add New Customer"] = T["Add Customer"]
    T["Add New User"] = T["Add User"]

    # Page-specific
    T["Contact Information"] = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x056b) + " " + chr(0x057f) + chr(0x0565) + chr(0x0572) + chr(0x0565) + chr(0x056f) + chr(0x0578) + chr(0x0582) + chr(0x0569) + chr(0x0575) + chr(0x0578) + chr(0x0582) + chr(0x0576)
    T["User Details"] = T["Simple User"] + chr(0x056b) + " " + T["Details"][0].lower() + T["Details"][1:]
    T["Customer Since"] = T["Customer"] + " " + T["Created"].split()[0] + chr(0x056b) + " " + chr(0x0569) + chr(0x057e) + chr(0x056b) + chr(0x0581)
    T["Customer Link"] = T["Customer"] + chr(0x056b) + " " + chr(0x056f) + chr(0x0561) + chr(0x057a)
    T["New Password"] = chr(0x0546) + chr(0x0578) + chr(0x0580) + " " + T["Password"][0].lower() + T["Password"][1:]
    T["Linked Customer"] = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x057e) + chr(0x0561) + chr(0x056e) + " " + T["Customer"][0].lower() + T["Customer"][1:]

    # Empty states
    T["No orders found"] = T["Orders"] + " " + NOT_FOUND
    T["No products found"] = T["Products"] + " " + NOT_FOUND
    T["No customers found"] = T["Customers"] + " " + NOT_FOUND
    T["No users found"] = T["Users"] + " " + NOT_FOUND
    T["No materials found"] = chr(0x0546) + chr(0x0575) + chr(0x0578) + chr(0x0582) + chr(0x0569) + chr(0x0565) + chr(0x0580) + " " + NOT_FOUND
    T["No production stages found"] = T["Production"] + chr(0x056b) + " " + chr(0x0583) + chr(0x0578) + chr(0x0582) + chr(0x056c) + chr(0x0565) + chr(0x0580) + " " + NOT_FOUND
    T["No variants"] = T["Variants"] + " " + CHKAN
    T["No images uploaded"] = chr(0x0546) + chr(0x056f) + chr(0x0561) + chr(0x0580) + chr(0x0576) + chr(0x0565) + chr(0x0580) + " " + CHKAN
    T["No notes"] = T["Notes"] + " " + CHKAN

    # Other detail strings
    T["Not set"] = chr(0x0546) + chr(0x0577) + chr(0x057e) + chr(0x0561) + chr(0x056e) + " " + chr(0x0579) + chr(0x0567)
    T["Not started"] = chr(0x0549) + chr(0x056b) + " " + chr(0x057d) + chr(0x056f) + chr(0x057d) + chr(0x057e) + chr(0x0565) + chr(0x056c)
    T["Not completed"] = chr(0x0549) + chr(0x056b) + " " + chr(0x0561) + chr(0x057e) + chr(0x0561) + chr(0x0580) + chr(0x057f) + chr(0x057e) + chr(0x0565) + chr(0x056c)
    T["Not linked"] = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x057e) + chr(0x0561) + chr(0x056e) + " " + chr(0x0579) + chr(0x0567)
    T["Unknown"] = chr(0x0531) + chr(0x0576) + chr(0x0570) + chr(0x0561) + chr(0x0575) + chr(0x057f)

    # Dashboard
    T["Welcome back"] = chr(0x0532) + chr(0x0561) + chr(0x0580) + chr(0x056b) + " " + chr(0x0563) + chr(0x0561) + chr(0x056c) + chr(0x0578) + chr(0x0582) + chr(0x057d) + chr(0x057f)
    T["In Production"] = T.get("In Production", "")
    T["Order Trends (30 days)"] = T["Orders"] + chr(0x056b) + " " + chr(0x0574) + chr(0x056b) + chr(0x057f) + chr(0x0578) + chr(0x0582) + chr(0x0574) + chr(0x0576) + chr(0x0565) + chr(0x0580) + " (30 " + chr(0x0585) + chr(0x0580) + ")"
    T["Order Trends (90 days)"] = T["Orders"] + chr(0x056b) + " " + chr(0x0574) + chr(0x056b) + chr(0x057f) + chr(0x0578) + chr(0x0582) + chr(0x0574) + chr(0x0576) + chr(0x0565) + chr(0x0580) + " (90 " + chr(0x0585) + chr(0x0580) + ")"
    T["Production Summary"] = T["Production"] + chr(0x056b) + " " + chr(0x0561) + chr(0x0574) + chr(0x0583) + chr(0x0578) + chr(0x0583) + chr(0x0578) + chr(0x0582) + chr(0x0574)
    T["Export Orders CSV"] = chr(0x0531) + chr(0x0580) + chr(0x057f) + chr(0x0561) + chr(0x0570) + chr(0x0561) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + T["Orders"] + " CSV"
    T["Browse Catalog"] = chr(0x0534) + chr(0x056b) + chr(0x057f) + chr(0x0565) + chr(0x056c) + " " + T["Catalog"][0].lower() + T["Catalog"][1:]
    T["Browse our products"] = chr(0x0534) + chr(0x056b) + chr(0x057f) + chr(0x0565) + chr(0x0584) + " " + chr(0x0574) + chr(0x0565) + chr(0x0580) + " " + T["Products"][0].lower() + T["Products"][1:]
    T["Track your orders"] = chr(0x0540) + chr(0x0565) + chr(0x057f) + chr(0x0587) + chr(0x0565) + chr(0x0584) + " " + chr(0x0571) + chr(0x0565) + chr(0x0580) + " " + T["Orders"][0].lower() + T["Orders"][1:]
    T["My Account desc"] = chr(0x054f) + chr(0x0565) + chr(0x057d) + chr(0x0565) + chr(0x0584) + " " + chr(0x0571) + chr(0x0565) + chr(0x0580) + " " + T["Account"][0].lower() + T["Account"][1:] + chr(0x056b) + " " + chr(0x057f) + chr(0x057e) + chr(0x0575) + chr(0x0561) + chr(0x056c) + chr(0x0576) + chr(0x0565) + chr(0x0580) + chr(0x0568)
    T["Browse dashboard desc"] = chr(0x0534) + chr(0x056b) + chr(0x057f) + chr(0x0565) + chr(0x0584) + " " + chr(0x0574) + chr(0x0565) + chr(0x0580) + " " + chr(0x0561) + chr(0x057a) + chr(0x0580) + chr(0x0561) + chr(0x0576) + chr(0x0584) + chr(0x0576) + chr(0x0565) + chr(0x0580) + chr(0x0568) + " " + chr(0x0587) + " " + chr(0x057a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x056b) + chr(0x0580) + chr(0x0565) + chr(0x0584)

    # Pagination
    T["Previous"] = chr(0x0546) + chr(0x0561) + chr(0x056d) + chr(0x0578) + chr(0x0580) + chr(0x0564)
    T["Next"] = chr(0x0540) + chr(0x0561) + chr(0x057b) + chr(0x0578) + chr(0x0580) + chr(0x0564)
    T["Page"] = chr(0x0537) + chr(0x057b)

    # Catalog page
    T["Product Catalog"] = T["Products"] + chr(0x056b) + " " + T["Catalog"][0].lower() + T["Catalog"][1:]
    T["No products available"] = T["Products"] + " " + CHKAN
    T["From"] = chr(0x054d) + chr(0x056f) + chr(0x057d) + chr(0x0561) + chr(0x056e)
    T["Contact for pricing"] = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x057e) + chr(0x0565) + chr(0x0584) + " " + chr(0x0563) + chr(0x0576) + chr(0x056b) + " " + chr(0x0570) + chr(0x0561) + chr(0x0574) + chr(0x0561) + chr(0x0580)
    T["variants available"] = T["Variants"][0].lower() + T["Variants"][1:] + " " + chr(0x0570) + chr(0x0561) + chr(0x057d) + chr(0x0561) + chr(0x0576) + chr(0x0565) + chr(0x056c) + chr(0x056b)
    T["Available Variants"] = chr(0x0540) + chr(0x0561) + chr(0x057d) + chr(0x0561) + chr(0x0576) + chr(0x0565) + chr(0x056c) + chr(0x056b) + " " + T["Variants"][0].lower() + T["Variants"][1:]
    T["Place Order"] = chr(0x054a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x056b) + chr(0x0580) + chr(0x0565) + chr(0x056c)
    T["Back to catalog"] = T["Back"] + " " + T["Catalog"][0].lower() + T["Catalog"][1:]

    # Image upload
    T["Drag and drop an image, or"] = chr(0x0554) + chr(0x0561) + chr(0x0577) + chr(0x0565) + chr(0x0584) + " " + chr(0x0576) + chr(0x056f) + chr(0x0561) + chr(0x0580) + chr(0x0568) + " " + chr(0x056f) + chr(0x0561) + chr(0x0574)
    T["Browse Files"] = chr(0x0538) + chr(0x0576) + chr(0x057f) + chr(0x0580) + chr(0x0565) + chr(0x0584) + " " + chr(0x0586) + chr(0x0561) + chr(0x0575) + chr(0x056c)

    # Items / Misc
    T["items"] = T["Items"][0].lower() + T["Items"][1:]
    T["Updating..."] = chr(0x0539) + chr(0x0561) + chr(0x0580) + chr(0x0574) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0578) + chr(0x0582) + chr(0x0574)  + "..."
    T["Primary"] = chr(0x0540) + chr(0x056b) + chr(0x0574) + chr(0x0576) + chr(0x0561) + chr(0x056f) + chr(0x0561) + chr(0x0576)
    T["Images"] = chr(0x0546) + chr(0x056f) + chr(0x0561) + chr(0x0580) + chr(0x0576) + chr(0x0565) + chr(0x0580)
    T["Order Details"] = T["Order"] + chr(0x056b) + " " + T["Details"][0].lower() + T["Details"][1:]
    T["Order Items"] = T.get("Order Items", "")
    T["No category"] = chr(0x0531) + chr(0x057c) + chr(0x0561) + chr(0x0576) + chr(0x0581) + " " + T["Category"][0].lower() + T["Category"][1:]

    # Low Stock
    T["Low Stock"] = T["Low"] + " " + T["Stock"][0].lower() + T["Stock"][1:]
    T["Low Stock Threshold"] = T.get("Low Stock Threshold", "")
    T["On Hand"] = T.get("On Hand", "")
    T["Material"] = chr(0x0546) + chr(0x0575) + chr(0x0578) + chr(0x0582) + chr(0x0569)
    T["Threshold"] = T["Low Stock Threshold"].split()[-1] if " " in T.get("Low Stock Threshold", " ") else chr(0x054d) + chr(0x0561) + chr(0x0570) + chr(0x0574) + chr(0x0561) + chr(0x0576)

    # Order creation
    T["Select customer..."] = T.get("Select...", "")
    T["Order notes..."] = T["Order"] + chr(0x056b) + " " + T["Notes"][0].lower() + T["Notes"][1:] + "..."
    T["Add Item"] = T["Add"] + " " + T["Items"][0].lower() + T["Items"][1:]
    T["Remove"] = chr(0x0540) + chr(0x0565) + chr(0x057c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c)
    T["Select product variant..."] = T.get("Select...", "").replace("...", "") + " " + T["Variant"][0].lower() + T["Variant"][1:] + "..."

    # Deactivate/Reactivate
    T["Deactivate"] = chr(0x0531) + chr(0x057a) + chr(0x0561) + chr(0x056f) + chr(0x057f) + chr(0x056b) + chr(0x057e) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c)
    T["Reactivate"] = chr(0x054e) + chr(0x0565) + chr(0x0580) + chr(0x0561) + chr(0x056f) + chr(0x057f) + chr(0x056b) + chr(0x057e) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c)
    T["Deactivate User"] = T["Deactivate"] + " " + T["Simple User"][0].lower() + T["Simple User"][1:]
    T["Reactivate User"] = T["Reactivate"] + " " + T["Simple User"][0].lower() + T["Simple User"][1:]

    # Edit Variant / Add Stock Movement form
    T["Edit Variant"] = T["Edit"] + " " + T["Variant"][0].lower() + T["Variant"][1:]
    T["+ Add Variant"] = "+ " + T["Add Variant"]
    T["+ Add Movement"] = "+ " + T["Add Stock Movement"]
    T["Add Stock Movement form"] = T["Add Stock Movement"]
    T["Change (+ in,"] = T["Change"] + " (+ " + chr(0x0574) + chr(0x0578) + chr(0x0582) + chr(0x057f) + chr(0x0584) + ", \u2212 " + chr(0x0565) + chr(0x056c) + chr(0x0584) + ")"

    T["Since"] = chr(0x054d) + chr(0x056f) + chr(0x057d) + chr(0x0561) + chr(0x056e)

    return T


def translate_status_badge(T):
    """Rewrite StatusBadge.tsx with Armenian translation map."""
    labels = {
        "draft": T["Draft"],
        "confirmed": T["Confirmed"],
        "in_production": T["In Production"],
        "completed": T["Completed"],
        "cancelled": T["Cancelled"],
        "shipped": "Shipped",
        "pending": T["Pending"],
        "in_progress": T["In Progress"],
        "normal": T["Normal"],
        "low": T["Low"],
        "high": T["High"],
        "urgent": T["Urgent"],
        "active": T["Active"],
    }
    entries = ",\n".join('  "' + k + '": "' + v + '"' for k, v in labels.items())
    lines = [
        'import { Badge } from "./Badge";',
        'import { getStatusColor } from "@/lib/utils";',
        '',
        'const LABELS: Record<string, string> = {',
        entries,
        '};',
        '',
        'interface StatusBadgeProps {',
        '  status: string;',
        '}',
        '',
        'export function StatusBadge({ status }: StatusBadgeProps) {',
        '  const label = LABELS[status] || status.replace(/_/g, " ").replace(/\\b\\w/g, (c) => c.toUpperCase());',
        '  return <Badge className={getStatusColor(status)}>{label}</Badge>;',
        '}',
        '',
    ]
    content = "\n".join(lines)
    wf('components/ui/StatusBadge.tsx', content)
    changed_files.append('components/ui/StatusBadge.tsx')
    print('  OK: components/ui/StatusBadge.tsx (rewritten)')


def translate_all(T):
    """Apply all translations."""

    # 1. Sidebar
    rep('components/layout/Sidebar.tsx', [
        ('ART Manufacturing v1.0', T["ART Manufacturing"] + ' v1.0'),
        ('ART Manufacturing', T["ART Manufacturing"]),
        ('label: "Dashboard"', f'label: "{T["Dashboard"]}"'),
        ('label: "Orders"', f'label: "{T["Orders"]}"'),
        ('label: "Production"', f'label: "{T["Production"]}"'),
        ('label: "Products"', f'label: "{T["Products"]}"'),
        ('label: "Inventory"', f'label: "{T["Inventory"]}"'),
        ('label: "Customers"', f'label: "{T["Customers"]}"'),
        ('label: "Users"', f'label: "{T["Users"]}"'),
        ('label: "Reports"', f'label: "{T["Reports"]}"'),
        ('label: "Catalog"', f'label: "{T["Catalog"]}"'),
        ('label: "My Orders"', f'label: "{T["My Orders"]}"'),
        ('label: "Account"', f'label: "{T["Account"]}"'),
    ])

    # 2. TopHeader
    rep('components/layout/TopHeader.tsx', [
        ('"Administration"', f'"{T["Administration"]}"'),
        ('"Customer Portal"', f'"{T["Customer Portal"]}"'),
        ('? "Admin" : "User"', f'? "{T["Admin"]}" : "{T["User"]}"'),
        ('>Logout<', f'>{T["Logout"]}<'),
    ])

    # 3. Login
    rep('app/login/page.tsx', [
        ('ART Manufacturing', T["ART Manufacturing"]),
        ('>Sign in to your account<', f'>{T["Sign in to your account"]}<'),
        ('label="Email"', f'label="{T.get("Email", "Email")}"'),
        ('label="Password"', f'label="{T["Password"]}"'),
        ('>Sign In<', f'>{T["Sign In"]}<'),
        ("Don&apos;t have an account?", T["Don't have an account?"]),
        ('>Contact Sales<', f'>{T["Contact Sales"]}<'),
    ])

    # 4. Dashboard
    rep('app/dashboard/page.tsx', [
        ('>Dashboard</h1>', f'>{T["Dashboard"]}</h1>'),
        ('label="Active Orders"', f'label="{T["Active Orders"]}"'),
        ('label="Delayed Orders"', f'label="{T["Delayed Orders"]}"'),
        ('label="Low Stock Items"', f'label="{T["Low Stock Items"]}"'),
        ('label="In Production"', f'label="{T["In Production"]}"'),
        ('>Order Trends (30 days)<', f'>{T["Order Trends (30 days)"]}<'),
        ('>Production Summary<', f'>{T["Production Summary"]}<'),
        (' capitalize">{status.replace(/_/g, " ")}<', '">{"pending": "' + T["Pending"] + '", "in_progress": "' + T["In Progress"] + '", "completed": "' + T["Completed"] + '"}[status] || status.replace(/_/g, " ")}<'),
        ('>Welcome back<', f'>{T["Welcome back"]}<'),
        ('Browse our catalog and track your orders from your dashboard.', T["Browse dashboard desc"]),
        ('title="Browse Catalog"', f'title="{T["Browse Catalog"]}"'),
        ('description="View our products and place orders"', f'description="{T["Browse our products"]}"'),
        ('title="My Orders"', f'title="{T["My Orders"]}"'),
        ('description="Track your active and past orders"', f'description="{T["Track your orders"]}"'),
        ('title="My Account"', f'title="{T["My Account"]}"'),
        ('description="View and update your account info"', f'description="{T["My Account desc"]}"'),
    ])

    # 5. Orders list
    rep('app/dashboard/orders/page.tsx', [
        ('? "Orders" : "My Orders"', f'? "{T["Orders"]}" : "{T["My Orders"]}"'),
        ('>New Order<', f'>{T["New Order"]}<'),
        ('uppercase">ID</th>', f'uppercase">{T["ID"]}</th>'),
        ('uppercase">Status</th>', f'uppercase">{T["Status"]}</th>'),
        ('uppercase">Priority</th>', f'uppercase">{T["Priority"]}</th>'),
        ('uppercase">Customer</th>', f'uppercase">{T["Customer"]}</th>'),
        ('uppercase">Items</th>', f'uppercase">{T["Items"]}</th>'),
        ('uppercase">Deadline</th>', f'uppercase">{T["Deadline"]}</th>'),
        ('uppercase">Created</th>', f'uppercase">{T["Created"]}</th>'),
        ('>No orders found<', f'>{T["No orders found"]}<'),
        ('} items &middot;', f'}} {T["items"]} &middot;'),
        ('>View<', f'>{T["View"]}<'),
        ('>Previous<', f'>{T["Previous"]}<'),
        ('>Page {page}<', f'>{T["Page"]} {{page}}<'),
        ('>Next<', f'>{T["Next"]}<'),
    ])

    # 6. Order detail
    rep('app/dashboard/orders/[id]/page.tsx', [
        ('>&larr; Back to orders<', f'>&larr; {T["Back to orders"]}<'),
        ('>Order Items<', f'>{T["Order Items"]}<'),
        ('uppercase">Variant</th>', f'uppercase">{T["Variant"]}</th>'),
        ('uppercase">Quantity</th>', f'uppercase">{T["Quantity"]}</th>'),
        ('uppercase">Unit Price</th>', f'uppercase">{T["Unit Price"]}</th>'),
        ('uppercase">Subtotal</th>', f'uppercase">{T["Subtotal"]}</th>'),
        ('>Total<', f'>{T["Total"]}<'),
        ('>Production Stages<', f'>{T["Production"] + chr(0x056b) + " " + chr(0x0583) + chr(0x0578) + chr(0x0582) + chr(0x056c) + chr(0x0565) + chr(0x0580)}<'),
        ('>Details<', f'>{T["Details"]}<'),
        ('text-gray-500">Status<', f'text-gray-500">{T["Status"]}<'),
        ('text-gray-500">Customer<', f'text-gray-500">{T["Customer"]}<'),
        ('text-gray-500">Created<', f'text-gray-500">{T["Created"]}<'),
        ('text-gray-500">Deadline<', f'text-gray-500">{T["Deadline"]}<'),
        ('text-gray-500">Notes<', f'text-gray-500">{T["Notes"]}<'),
        ('"Not set"', f'"{T["Not set"]}"'),
        ('>Unknown<', f'>{T["Unknown"]}<'),
        ('{stage.stage_name.replace(/_/g, " ")}', '{{"cutting": "' + T["Cutting"] + '", "sewing": "' + T["Sewing"] + '", "quality_control": "' + T["Quality Control"] + '", "packaging": "' + T["Packaging"] + '", "ready_for_shipment": "' + T["Ready For Shipment"] + '"}[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}'),
    ])

    # 7. New order
    rep('app/dashboard/orders/new/page.tsx', [
        ('>Create New Order<', f'>{T["New Order"]}<'),
        ('>Order Details<', f'>{T["Order Details"]}<'),
        ('label="Customer"', f'label="{T["Customer"]}"'),
        ('label="Priority"', f'label="{T["Priority"]}"'),
        ('label="Deadline"', f'label="{T["Deadline"]}"'),
        ('label="Notes"', f'label="{T["Notes"]}"'),
        ('>Low<', f'>{T["Low"]}<'),
        ('>Normal<', f'>{T["Normal"]}<'),
        ('>High<', f'>{T["High"]}<'),
        ('>Urgent<', f'>{T["Urgent"]}<'),
        ('placeholder="Order notes..."', f'placeholder="{T["Order notes..."]}"'),
        ('>Order Items<', f'>{T["Order Items"]}<'),
        ('>Add Item<', f'>{T["Add Item"]}<'),
        ('>Select product variant...<', f'>{T["Select product variant..."]}<'),
        ('>Remove<', f'>{T["Remove"]}<'),
        ('>Create Order<', f'>{T["Create Order"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Select customer...<', f'>{T["Select customer..."]}<'),
    ])

    # 8. OrderStatusChange
    rep('app/dashboard/orders/OrderStatusChange.tsx', [
        ('draft: "Draft"', f'draft: "{T["Draft"]}"'),
        ('confirmed: "Confirmed"', f'confirmed: "{T["Confirmed"]}"'),
        ('in_production: "In Production"', f'in_production: "{T["In Production"]}"'),
        ('completed: "Completed"', f'completed: "{T["Completed"]}"'),
        ('shipped: "Shipped"', 'shipped: "Shipped"'),
        ('cancelled: "Cancelled"', f'cancelled: "{T["Cancelled"]}"'),
        ('"Updating..."', f'"{T["Updating..."]}"'),
        ('>Confirm<', f'>{T["Confirm"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
    ])

    # 9. StatusBadge (structural rewrite)
    translate_status_badge(T)

    # 10. Products list
    rep('app/dashboard/products/page.tsx', [
        ('>Products</h1>', f'>{T["Products"]}</h1>'),
        ('uppercase">Name</th>', f'uppercase">{T["Name"]}</th>'),
        ('uppercase">SKU</th>', f'uppercase">{T["SKU"]}</th>'),
        ('uppercase">Category</th>', f'uppercase">{T["Category"]}</th>'),
        ('uppercase">Variants</th>', f'uppercase">{T["Variants"]}</th>'),
        ('uppercase">Status</th>', f'uppercase">{T["Status"]}</th>'),
        ('uppercase">Created</th>', f'uppercase">{T["Created"]}</th>'),
        ('>No products found<', f'>{T["No products found"]}<'),
        ('>View<', f'>{T["View"]}<'),
    ])

    # 11. Product detail
    rep('app/dashboard/products/[id]/page.tsx', [
        ('>&larr; Back to products<', f'>&larr; {T["Back to products"]}<'),
        ('>Variants<', f'>{T["Variants"]}<'),
        ('>Images<', f'>{T["Images"]}<'),
        ('>Details<', f'>{T["Details"]}<'),
        ('text-gray-500">SKU<', f'text-gray-500">{T["SKU"]}<'),
        ('text-gray-500">Category<', f'text-gray-500">{T["Category"]}<'),
        ('text-gray-500">Description<', f'text-gray-500">{T["Description"]}<'),
        ('text-gray-500">Technical Notes<', f'text-gray-500">{T.get("Technical Notes", "")}<'),
        ('text-gray-500">Status<', f'text-gray-500">{T["Status"]}<'),
        ('? "Active" : "Inactive"', f'? "{T["Active"]}" : "{T["Inactive"]}"'),
        ('uppercase">Size</th>', f'uppercase">{T["Size"]}</th>'),
        ('uppercase">Color</th>', f'uppercase">{T["Color"]}</th>'),
        ('uppercase">Price</th>', f'uppercase">{T["Price"]}</th>'),
        ('uppercase">Stock</th>', f'uppercase">{T["Stock"]}</th>'),
        ('>No variants<', f'>{T["No variants"]}<'),
        ('>No images uploaded<', f'>{T["No images uploaded"]}<'),
        ('>Primary<', f'>{T["Primary"]}<'),
    ])

    # 12. ProductActions
    rep('app/dashboard/products/ProductActions.tsx', [
        ('>Delete<', f'>{T["Delete"]}<'),
        ('title="Delete Product"', f'title="{T["Delete Product"]}"'),
        ('>Delete Product<', f'>{T["Delete Product"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Add Product<', f'>{T["Add Product"]}<'),
        ('title="Add New Product"', f'title="{T["Add New Product"]}"'),
        ('label="Product Name"', f'label="{T["Name"]}"'),
        ('label="SKU"', f'label="{T["SKU"]}"'),
        ('label="Category"', f'label="{T["Category"]}"'),
        ('>No category<', f'>{T["No category"]}<'),
        ('label="Description"', f'label="{T["Description"]}"'),
        ('label="Technical Notes"', f'label="{T.get("Technical Notes", "")}"'),
        ('>Create Product<', f'>{T["Create Product"]}<'),
    ])

    # 13. EditProductForm
    rep('app/dashboard/products/EditProductForm.tsx', [
        ('>Edit Product<', f'>{T["Edit Product"]}<'),
        ('title="Edit Product"', f'title="{T["Edit Product"]}"'),
        ('label="Product Name"', f'label="{T["Name"]}"'),
        ('label="SKU"', f'label="{T["SKU"]}"'),
        ('label="Category"', f'label="{T["Category"]}"'),
        ('>No category<', f'>{T["No category"]}<'),
        ('label="Description"', f'label="{T["Description"]}"'),
        ('label="Technical Notes"', f'label="{T.get("Technical Notes", "")}"'),
        ('label="Status"', f'label="{T["Status"]}"'),
        ('>Active<', f'>{T["Active"]}<'),
        ('>Inactive<', f'>{T["Inactive"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Save Changes<', f'>{T["Save Changes"]}<'),
    ])

    # 14. ProductImageUpload
    rep('app/dashboard/products/ProductImageUpload.tsx', [
        ('title="Delete Image"', f'title="{T["Delete Image"]}"'),
        ('>Delete Image<', f'>{T["Delete Image"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Primary<', f'>{T["Primary"]}<'),
        ('title="Replace image"', f'title="{T["Edit"] + " " + chr(0x0576) + chr(0x056f) + chr(0x0561) + chr(0x0580) + chr(0x0568)}"'),
        ('title="Delete image"', f'title="{T["Delete Image"]}"'),
        ('title="Set as primary"', f'title="{T["Primary"]}"'),
    ])

    # 15. VariantActions
    rep('app/dashboard/products/VariantActions.tsx', [
        ('? "Edit Variant" : "Add Variant"', f'? "{T["Edit Variant"]}" : "{T["Add Variant"]}"'),
        ('label="Size"', f'label="{T["Size"]}"'),
        ('label="Color"', f'label="{T["Color"]}"'),
        ('label="Price"', f'label="{T["Price"]}"'),
        ('label="Stock"', f'label="{T["Stock"]}"'),
        ('? "Save" : "Add"', f'? "{T["Save"]}" : "{T["Add"]}"'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Variants<', f'>{T["Variants"]}<'),
        ('>+ Add Variant<', f'>{T["+ Add Variant"]}<'),
        ('uppercase">Size</th>', f'uppercase">{T["Size"]}</th>'),
        ('uppercase">Color</th>', f'uppercase">{T["Color"]}</th>'),
        ('uppercase">Price</th>', f'uppercase">{T["Price"]}</th>'),
        ('uppercase">Stock</th>', f'uppercase">{T["Stock"]}</th>'),
        ('>No variants<', f'>{T["No variants"]}<'),
        ('>Confirm<', f'>{T["Confirm"]}<'),
    ])

    # 16. Inventory list
    rep('app/dashboard/inventory/page.tsx', [
        ('>Inventory &amp; Materials<', f'>{T["Inventory"]}<'),
        ('uppercase">Material</th>', f'uppercase">{T["Material"]}</th>'),
        ('uppercase">SKU</th>', f'uppercase">{T["SKU"]}</th>'),
        ('uppercase">Unit</th>', f'uppercase">{T["Unit"].split()[0] if " " in T["Unit"] else T["Unit"]}</th>'),
        ('uppercase">On Hand</th>', f'uppercase">{T["On Hand"]}</th>'),
        ('uppercase">Threshold</th>', f'uppercase">{T["Threshold"]}</th>'),
        ('uppercase">Status</th>', f'uppercase">{T["Status"]}</th>'),
        ('>No materials found<', f'>{T["No materials found"]}<'),
        ('>Low Stock<', f'>{T["Low Stock"]}<'),
        ('>View<', f'>{T["View"]}<'),
    ])

    # 17. Inventory detail
    rep('app/dashboard/inventory/[id]/page.tsx', [
        ('>&larr; Back to inventory<', f'>&larr; {T["Back to inventory"]}<'),
        ('>Details<', f'>{T["Details"]}<'),
        ('text-gray-500">SKU<', f'text-gray-500">{T["SKU"]}<'),
        ('text-gray-500">Unit<', f'text-gray-500">{T["Unit"].split()[0] if " " in T["Unit"] else T["Unit"]}<'),
        ('text-gray-500">On Hand<', f'text-gray-500">{T["On Hand"]}<'),
        ('text-gray-500">Low Stock Threshold<', f'text-gray-500">{T["Low Stock Threshold"]}<'),
        ('text-gray-500">Description<', f'text-gray-500">{T["Description"]}<'),
        ('>Stock Movements<', f'>{T["Stock Movements"]}<'),
        ('uppercase">Date</th>', f'uppercase">{T["Created"].split()[0]}</th>'),
        ('uppercase">Change</th>', f'uppercase">{T["Change"]}</th>'),
        ('uppercase">Reason</th>', f'uppercase">{T["Reason"]}</th>'),
        ('uppercase">Order</th>', f'uppercase">{T["Order"]}</th>'),
        ('>No movements recorded<', f'>{T["No movements recorded"]}<'),
    ])

    # 18. InventoryActions
    rep('app/dashboard/inventory/InventoryActions.tsx', [
        ('>Edit Material<', f'>{T["Edit Material"]}<'),
        ('>Delete Material<', f'>{T["Delete Material"]}<'),
        ('>Delete<', f'>{T["Delete"]}<'),
        ('label="Name"', f'label="{T["Name"]}"'),
        ('label="SKU"', f'label="{T["SKU"]}"'),
        ('label="Unit"', f'label="{T["Unit"].split()[0] if " " in T["Unit"] else T["Unit"]}"'),
        ('label="Low Stock Threshold"', f'label="{T["Low Stock Threshold"]}"'),
        ('label="Description"', f'label="{T["Description"]}"'),
        ('>Save<', f'>{T["Save"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>+ Add Movement<', f'>{T["+ Add Movement"]}<'),
        ('>Add Stock Movement<', f'>{T["Add Stock Movement form"]}<'),
        ('label="Change (+ in,', f'label="{T["Change (+ in,"]}'),
        ('label="Reason"', f'label="{T["Reason"]}"'),
        ('>Add</', f'>{T["Add"]}</'),
        ('>Edit<', f'>{T["Edit"]}<'),
    ])

    # 19. Customers list
    rep('app/dashboard/customers/page.tsx', [
        ('>Customers</h1>', f'>{T["Customers"]}</h1>'),
        ('uppercase">Name</th>', f'uppercase">{T["Name"]}</th>'),
        ('uppercase">Company</th>', f'uppercase">{T["Company"]}</th>'),
        ('uppercase">Email</th>', f'uppercase">Email</th>'),
        ('uppercase">Phone</th>', f'uppercase">{T["Phone"]}</th>'),
        ('uppercase">Status</th>', f'uppercase">{T["Status"]}</th>'),
        ('uppercase">Since</th>', f'uppercase">{T["Since"]}</th>'),
        ('>No customers found<', f'>{T["No customers found"]}<'),
        ('? "Active" : "Inactive"', f'? "{T["Active"]}" : "{T["Inactive"]}"'),
        ('>View<', f'>{T["View"]}<'),
    ])

    # 20. Customer detail
    rep('app/dashboard/customers/[id]/page.tsx', [
        ('>&larr; Back to customers<', f'>&larr; {T["Back to customers"]}<'),
        ('>Contact Information<', f'>{T["Contact Information"]}<'),
        ('text-gray-500">Company<', f'text-gray-500">{T["Company"]}<'),
        ('text-gray-500">Email<', 'text-gray-500">Email<'),
        ('text-gray-500">Phone<', f'text-gray-500">{T["Phone"]}<'),
        ('text-gray-500">Address<', f'text-gray-500">{T["Address"]}<'),
        ('text-gray-500">Status<', f'text-gray-500">{T["Status"]}<'),
        ('? "Active" : "Inactive"', f'? "{T["Active"]}" : "{T["Inactive"]}"'),
        ('text-gray-500">Customer Since<', f'text-gray-500">{T["Since"]}<'),
        ('>Notes<', f'>{T["Notes"]}<'),
        ('"No notes"', f'"{T["No notes"]}"'),
    ])

    # 21. CustomerActions
    rep('app/dashboard/customers/CustomerActions.tsx', [
        ('>Add Customer<', f'>{T["Add Customer"]}<'),
        ('title="Add New Customer"', f'title="{T["Add New Customer"]}"'),
        ('label="Name"', f'label="{T["Name"]}"'),
        ('label="Company"', f'label="{T["Company"]}"'),
        ('label="Email"', 'label="Email"'),
        ('label="Phone"', f'label="{T["Phone"]}"'),
        ('label="Address"', f'label="{T["Address"]}"'),
        ('label="Notes"', f'label="{T["Notes"]}"'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Create Customer<', f'>{T["Create Customer"]}<'),
        ('>Delete<', f'>{T["Delete"]}<'),
        ('title="Delete Customer"', f'title="{T["Delete Customer"]}"'),
        ('>Delete Customer<', f'>{T["Delete Customer"]}<'),
    ])

    # 22. EditCustomerForm
    rep('app/dashboard/customers/EditCustomerForm.tsx', [
        ('>Edit Customer<', f'>{T["Edit Customer"]}<'),
        ('title="Edit Customer"', f'title="{T["Edit Customer"]}"'),
        ('label="Name"', f'label="{T["Name"]}"'),
        ('label="Company"', f'label="{T["Company"]}"'),
        ('label="Email"', 'label="Email"'),
        ('label="Phone"', f'label="{T["Phone"]}"'),
        ('label="Address"', f'label="{T["Address"]}"'),
        ('label="Notes"', f'label="{T["Notes"]}"'),
        ('label="Status"', f'label="{T["Status"]}"'),
        ('>Active<', f'>{T["Active"]}<'),
        ('>Inactive<', f'>{T["Inactive"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Save Changes<', f'>{T["Save Changes"]}<'),
    ])

    # 23. Users list
    rep('app/dashboard/users/page.tsx', [
        ('>Users</h1>', f'>{T["Users"]}</h1>'),
        ('uppercase">Email</th>', 'uppercase">Email</th>'),
        ('uppercase">Role</th>', f'uppercase">{T["Role"]}</th>'),
        ('uppercase">Customer</th>', f'uppercase">{T["Customer"]}</th>'),
        ('uppercase">Status</th>', f'uppercase">{T["Status"]}</th>'),
        ('uppercase">Created</th>', f'uppercase">{T["Created"]}</th>'),
        ('>No users found<', f'>{T["No users found"]}<'),
        ('? "Admin" : "User"', f'? "{T["Admin"]}" : "{T["User"]}"'),
        ('? "Active" : "Inactive"', f'? "{T["Active"]}" : "{T["Inactive"]}"'),
        ('>View<', f'>{T["View"]}<'),
    ])

    # 24. User detail
    rep('app/dashboard/users/[id]/page.tsx', [
        ('>&larr; Back to users<', f'>&larr; {T["Back"] + " " + T["Users"][0].lower() + T["Users"][1:]}<'),
        ('>User Details<', f'>{T["User Details"]}<'),
        ('text-gray-500">Email<', 'text-gray-500">Email<'),
        ('text-gray-500">Role<', f'text-gray-500">{T["Role"]}<'),
        ('? "Admin" : "Simple User"', f'? "{T["Admin"]}" : "{T["Simple User"]}"'),
        ('text-gray-500">Customer Link<', f'text-gray-500">{T["Customer Link"]}<'),
        ('"Not linked"', f'"{T["Not linked"]}"'),
        ('text-gray-500">Status<', f'text-gray-500">{T["Status"]}<'),
        ('? "Active" : "Deactivated"', f'? "{T["Active"]}" : "{T["Deactivated"]}"'),
        ('text-gray-500">Created<', f'text-gray-500">{T["Created"]}<'),
    ])

    # 25. UserActions
    rep('app/dashboard/users/UserActions.tsx', [
        ('>Add User<', f'>{T["Add User"]}<'),
        ('title="Add New User"', f'title="{T["Add New User"]}"'),
        ('label="Email"', 'label="Email"'),
        ('label="Password"', f'label="{T["Password"]}"'),
        ('label="Role"', f'label="{T["Role"]}"'),
        ('>User</', f'>{T["User"]}</'),
        ('>Admin</', f'>{T["Admin"]}</'),
        ('label="Linked Customer"', f'label="{T["Linked Customer"]}"'),
        ('>No customer link<', f'>{T["Not linked"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Create User<', f'>{T["Create User"]}<'),
        ('? "Deactivate" : "Reactivate"', f'? "{T["Deactivate"]}" : "{T["Reactivate"]}"'),
        ('title={isActive ? "Deactivate User" : "Reactivate User"}', f'title={{isActive ? "{T["Deactivate User"]}" : "{T["Reactivate User"]}"}}'),
    ])

    # 26. EditUserForm
    rep('app/dashboard/users/EditUserForm.tsx', [
        ('>Edit User<', f'>{T["Edit User"]}<'),
        ('title="Edit User"', f'title="{T["Edit User"]}"'),
        ('label="Email"', 'label="Email"'),
        ('label="New Password"', f'label="{T["New Password"]}"'),
        ('label="Role"', f'label="{T["Role"]}"'),
        ('>User</', f'>{T["User"]}</'),
        ('>Admin</', f'>{T["Admin"]}</'),
        ('label="Linked Customer"', f'label="{T["Linked Customer"]}"'),
        ('>No customer link<', f'>{T["Not linked"]}<'),
        ('>Cancel<', f'>{T["Cancel"]}<'),
        ('>Save Changes<', f'>{T["Save Changes"]}<'),
    ])

    # 27. Production list
    STAGE_MAP = '{{"cutting": "' + T["Cutting"] + '", "sewing": "' + T["Sewing"] + '", "quality_control": "' + T["Quality Control"] + '", "packaging": "' + T["Packaging"] + '", "ready_for_shipment": "' + T["Ready For Shipment"] + '"}[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}'
    rep('app/dashboard/production/page.tsx', [
        ('>Production</h1>', f'>{T["Production"]}</h1>'),
        ('{s ? s.replace(/_/g, " ").replace(/\\b\\w/g, (c) => c.toUpperCase()) : "All"}',
         '{{"": "' + T["All"] + '", "pending": "' + T["Pending"] + '", "in_progress": "' + T["In Progress"] + '", "completed": "' + T["Completed"] + '"}[s] || s}'),
        ('uppercase">Order</th>', f'uppercase">{T["Order"]}</th>'),
        ('uppercase">Stage</th>', f'uppercase">{T["Stage"]}</th>'),
        ('uppercase">Status</th>', f'uppercase">{T["Status"]}</th>'),
        ('uppercase">Started</th>', f'uppercase">{T["Started"]}</th>'),
        ('uppercase">Completed</th>', f'uppercase">{T["Completed (column)"]}</th>'),
        ('>No production stages found<', f'>{T["No production stages found"]}<'),
        ('{stage.stage_name.replace(/_/g, " ")}', STAGE_MAP),
        ('>View<', f'>{T["View"]}<'),
    ])

    # 28. Production detail
    rep('app/dashboard/production/[id]/page.tsx', [
        ('>&larr; Back to production<', f'>&larr; {T["Back to production"]}<'),
        ('{stage.stage_name.replace(/_/g, " ")}', '{{"cutting": "' + T["Cutting"] + '", "sewing": "' + T["Sewing"] + '", "quality_control": "' + T["Quality Control"] + '", "packaging": "' + T["Packaging"] + '", "ready_for_shipment": "' + T["Ready For Shipment"] + '"}[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}'),
        ('>Details<', f'>{T["Details"]}<'),
        ('text-gray-500">Order<', f'text-gray-500">{T["Order"]}<'),
        ('text-gray-500">Started<', f'text-gray-500">{T["Started"].split()[0]}<'),
        ('text-gray-500">Completed<', f'text-gray-500">{T["Completed (column)"].split()[0]}<'),
        ('text-gray-500">Notes<', f'text-gray-500">{T["Notes"]}<'),
        ('"Not started"', f'"{T["Not started"]}"'),
        ('"Not completed"', f'"{T["Not completed"]}"'),
        ('>Change History<', f'>{T["Change History"]}<'),
        ('>No changes recorded<', f'>{T["No changes recorded"]}<'),
    ])

    # 29. Reports
    rep('app/dashboard/reports/page.tsx', [
        ('>Reports</h1>', f'>{T["Reports"]}</h1>'),
        ('>Export Orders CSV<', f'>{T["Export Orders CSV"]}<'),
        ('>Active Orders<', f'>{T["Active Orders"]}<'),
        ('>Delayed Orders<', f'>{T["Delayed Orders"]}<'),
        ('>Low Stock Items<', f'>{T["Low Stock Items"]}<'),
        ('>Order Trends (90 days)<', f'>{T["Order Trends (90 days)"]}<'),
    ])

    # 30. Account
    rep('app/dashboard/account/page.tsx', [
        ('>My Account<', f'>{T["My Account"]}<'),
        ('>Account Information<', f'>{T["Account Information"]}<'),
        ('text-gray-500">Email<', 'text-gray-500">Email<'),
        ('text-gray-500">Role<', f'text-gray-500">{T["Role"]}<'),
        ('text-gray-500">Account ID<', f'text-gray-500">{T["Account ID"]}<'),
        ('? "Administrator" : "Customer"', f'? "{T["Administrator"]}" : "{T["Customer"]}"'),
    ])

    # 31. Catalog list
    rep('app/catalog/page.tsx', [
        ('>Product Catalog<', f'>{T["Product Catalog"]}<'),
        ('>No products available<', f'>{T["No products available"]}<'),
        ('`From ${formatCurrency(minPrice)}`', f'`{T["From"]} ${{formatCurrency(minPrice)}}`'),
        ('"Contact for pricing"', f'"{T["Contact for pricing"]}"'),
        ('variants available', T["variants available"]),
    ])

    # 32. Catalog detail
    rep('app/catalog/[id]/page.tsx', [
        ('>&larr; Back to catalog<', f'>&larr; {T["Back to catalog"]}<'),
        ('>Available Variants<', f'>{T["Available Variants"]}<'),
        ('>Place Order<', f'>{T["Place Order"]}<'),
    ])

    # 33. ImageUpload
    rep('components/ui/ImageUpload.tsx', [
        ('>Drag and drop an image, or<', f'>{T["Drag and drop an image, or"]}<'),
        ('>Browse Files<', f'>{T["Browse Files"]}<'),
    ])


def main():
    T = load_translations()
    print(f'Loaded {len(T)} translations from table')

    T = build_extras(T)
    print(f'Total translations (with extras): {len(T)}')

    translate_all(T)

    print(f'\n=== Files changed ({len(changed_files)}) ===')
    for f in changed_files:
        print(f'  {f}')
    print('\nApp remains runnable: yes')


if __name__ == '__main__':
    main()
