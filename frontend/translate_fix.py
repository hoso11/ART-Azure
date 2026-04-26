#!/usr/bin/env python3
"""Fix remaining untranslated English strings in ART Manufacturing admin panel."""

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
    any_changed = False
    for old, new in reps:
        if old not in c:
            print(f'  WARN not found in {p}: {repr(old[:80])}')
        else:
            c = c.replace(old, new)
            any_changed = True
    if any_changed:
        wf(p, c)
        changed_files.append(p)
        print(f'  OK: {p}')
    else:
        print(f'  SKIP (no changes): {p}')

def build_extras(T):
    """Build Armenian translations using chr() codes."""
    # Logout = chr(0x0535) + chr(0x056c) + chr(0x0584)
    LOGOUT = chr(0x0535) + chr(0x056c) + chr(0x0584)

    # Sign In = chr(0x0544) + chr(0x057f) + chr(0x0576) + chr(0x0565) + chr(0x056c)
    SIGN_IN = chr(0x0544) + chr(0x057f) + chr(0x0576) + chr(0x0565) + chr(0x056c)

    # Contact Sales = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x057e) + chr(0x0565) + chr(0x0584)
    #   + " " + chr(0x057e) + chr(0x0561) + chr(0x057c) + chr(0x0584) + chr(0x056b)
    #   + " " + chr(0x0562) + chr(0x0561) + chr(0x056a) + chr(0x0576) + chr(0x056b) + chr(0x0576)
    CONTACT_SALES = chr(0x053f) + chr(0x0561) + chr(0x057a) + chr(0x057e) + chr(0x0565) + chr(0x0584) + " " + chr(0x057e) + chr(0x0561) + chr(0x057c) + chr(0x0584) + chr(0x056b) + " " + chr(0x0562) + chr(0x0561) + chr(0x056a) + chr(0x0576) + chr(0x056b) + chr(0x0576)

    # New Order = chr(0x0546) + chr(0x0578) + chr(0x0580) + " " + chr(0x057a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x0565) + chr(0x0580)
    NEW_ORDER = T.get("New Order", chr(0x0546) + chr(0x0578) + chr(0x0580) + " " + chr(0x057a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x0565) + chr(0x0580))

    # No orders found
    NOT_FOUND = chr(0x0579) + chr(0x0565) + chr(0x0576) + " " + chr(0x0563) + chr(0x057f) + chr(0x0576) + chr(0x057e) + chr(0x0565) + chr(0x056c)
    NO_ORDERS = T.get("Orders", chr(0x054a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x0565) + chr(0x0580) + chr(0x0576) + chr(0x0565) + chr(0x0580)) + " " + NOT_FOUND

    # View = chr(0x0534) + chr(0x056b) + chr(0x057f) + chr(0x0565) + chr(0x056c)
    VIEW = chr(0x0534) + chr(0x056b) + chr(0x057f) + chr(0x0565) + chr(0x056c)

    # Previous = chr(0x0546) + chr(0x0561) + chr(0x056d) + chr(0x0578) + chr(0x0580) + chr(0x0564)
    PREVIOUS = chr(0x0546) + chr(0x0561) + chr(0x056d) + chr(0x0578) + chr(0x0580) + chr(0x0564)

    # Next = chr(0x0540) + chr(0x0561) + chr(0x057b) + chr(0x0578) + chr(0x0580) + chr(0x0564)
    NEXT = chr(0x0540) + chr(0x0561) + chr(0x057b) + chr(0x0578) + chr(0x0580) + chr(0x0564)

    # Back to orders = chr(0x054e) + chr(0x0565) + chr(0x0580) + chr(0x0561) + chr(0x0564) + chr(0x0561) + chr(0x057c) + chr(0x0576) + chr(0x0561) + chr(0x056c)
    #   + " " + orders (lowercase)
    BACK = T.get("Back", chr(0x054e) + chr(0x0565) + chr(0x0580) + chr(0x0561) + chr(0x0564) + chr(0x0561) + chr(0x057c) + chr(0x0576) + chr(0x0561) + chr(0x056c))
    ORDERS_LC = T.get("Orders", chr(0x054a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x0565) + chr(0x0580) + chr(0x0576) + chr(0x0565) + chr(0x0580))
    ORDERS_LC_FMT = ORDERS_LC[0].lower() + ORDERS_LC[1:] if ORDERS_LC else ORDERS_LC
    BACK_TO_ORDERS = BACK + " " + ORDERS_LC_FMT

    # Add Item
    ADD = T.get("Add", chr(0x0531) + chr(0x057e) + chr(0x0565) + chr(0x056c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c))
    ITEMS = T.get("Items", chr(0x0531) + chr(0x057a) + chr(0x0580) + chr(0x0561) + chr(0x0576) + chr(0x0584) + chr(0x0576) + chr(0x0565) + chr(0x0580))
    ITEMS_LC = ITEMS[0].lower() + ITEMS[1:] if ITEMS else ITEMS
    ADD_ITEM = ADD + " " + ITEMS_LC

    # Remove = chr(0x0540) + chr(0x0565) + chr(0x057c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c)
    REMOVE = chr(0x0540) + chr(0x0565) + chr(0x057c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c)

    # Confirm = chr(0x0540) + chr(0x0561) + chr(0x057d) + chr(0x057f) + chr(0x0561) + chr(0x057f) + chr(0x0565) + chr(0x056c)
    CONFIRM = chr(0x0540) + chr(0x0561) + chr(0x057d) + chr(0x057f) + chr(0x0561) + chr(0x057f) + chr(0x0565) + chr(0x056c)

    # Cancel = chr(0x0549) + chr(0x0565) + chr(0x0572) + chr(0x0561) + chr(0x0580) + chr(0x056f) + chr(0x0565) + chr(0x056c)
    CANCEL = chr(0x0549) + chr(0x0565) + chr(0x0572) + chr(0x0561) + chr(0x0580) + chr(0x056f) + chr(0x0565) + chr(0x056c)

    # Delete = chr(0x054b) + chr(0x0576) + chr(0x057b) + chr(0x0565) + chr(0x056c)
    DELETE = T.get("Delete", chr(0x054b) + chr(0x0576) + chr(0x057b) + chr(0x0565) + chr(0x056c))

    # Primary = chr(0x0540) + chr(0x056b) + chr(0x0574) + chr(0x0576) + chr(0x0561) + chr(0x056f) + chr(0x0561) + chr(0x0576)
    PRIMARY = chr(0x0540) + chr(0x056b) + chr(0x0574) + chr(0x0576) + chr(0x0561) + chr(0x056f) + chr(0x0561) + chr(0x0576)

    # + Add Variant
    ADD_VARIANT = T.get("Add Variant", chr(0x0531) + chr(0x057e) + chr(0x0565) + chr(0x056c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + chr(0x057f) + chr(0x0561) + chr(0x0580) + chr(0x0562) + chr(0x0565) + chr(0x0580) + chr(0x0561) + chr(0x056f))
    PLUS_ADD_VARIANT = "+ " + ADD_VARIANT

    # + Add Movement
    ADD_STOCK_MOVEMENT = T.get("Add Stock Movement", chr(0x0531) + chr(0x057e) + chr(0x0565) + chr(0x056c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + chr(0x0577) + chr(0x0561) + chr(0x0580) + chr(0x056a))
    PLUS_ADD_MOVEMENT = "+ " + ADD_STOCK_MOVEMENT

    # Edit = chr(0x053d) + chr(0x0574) + chr(0x0562) + chr(0x0561) + chr(0x0563) + chr(0x0580) + chr(0x0565) + chr(0x056c)
    EDIT = T.get("Edit", chr(0x053d) + chr(0x0574) + chr(0x0562) + chr(0x0561) + chr(0x0563) + chr(0x0580) + chr(0x0565) + chr(0x056c))

    # Create Product = same as Add Product
    ADD_PRODUCT = T.get("Add Product", chr(0x0531) + chr(0x057e) + chr(0x0565) + chr(0x056c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + chr(0x0561) + chr(0x057a) + chr(0x0580) + chr(0x0561) + chr(0x0576) + chr(0x0584))
    CREATE_PRODUCT = ADD_PRODUCT

    # Create Customer = same as Add Customer
    ADD_CUSTOMER = T.get("Add Customer", chr(0x0531) + chr(0x057e) + chr(0x0565) + chr(0x056c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + chr(0x0570) + chr(0x0561) + chr(0x0573) + chr(0x0561) + chr(0x056d) + chr(0x0578) + chr(0x0580) + chr(0x0564))
    CREATE_CUSTOMER = ADD_CUSTOMER

    # Create User = same as Add User
    ADD_USER = T.get("Add User", chr(0x0531) + chr(0x057e) + chr(0x0565) + chr(0x056c) + chr(0x0561) + chr(0x0581) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + chr(0x0585) + chr(0x0563) + chr(0x057f) + chr(0x0561) + chr(0x057f) + chr(0x0565) + chr(0x0580))
    CREATE_USER = ADD_USER

    # Delete Product
    EDIT_PRODUCT = T.get("Edit Product", EDIT + " " + chr(0x0561) + chr(0x057a) + chr(0x0580) + chr(0x0561) + chr(0x0576) + chr(0x0584) + chr(0x0568))
    DELETE_PRODUCT = DELETE + " " + EDIT_PRODUCT.split()[-1] if EDIT_PRODUCT else DELETE

    # Delete Customer
    EDIT_CUSTOMER = T.get("Edit Customer", EDIT + " " + chr(0x0570) + chr(0x0561) + chr(0x0573) + chr(0x0561) + chr(0x056d) + chr(0x0578) + chr(0x0580) + chr(0x0564) + chr(0x0568))
    DELETE_CUSTOMER = DELETE + " " + EDIT_CUSTOMER.split()[-1] if EDIT_CUSTOMER else DELETE

    # Edit Product button label
    EDIT_PRODUCT_BTN = EDIT_PRODUCT

    # Edit Customer button label
    EDIT_CUSTOMER_BTN = EDIT_CUSTOMER

    # Edit User
    EDIT_USER = T.get("Edit User", EDIT + " " + chr(0x0585) + chr(0x0563) + chr(0x057f) + chr(0x0561) + chr(0x057f) + chr(0x056b) + chr(0x0580) + chr(0x0578) + chr(0x057b) + chr(0x0568))

    # Save Changes = Save
    SAVE = T.get("Save", chr(0x054a) + chr(0x0561) + chr(0x0570) + chr(0x057a) + chr(0x0561) + chr(0x0576) + chr(0x0565) + chr(0x056c))
    SAVE_CHANGES = SAVE

    # Export Orders CSV
    EXPORT_ORDERS = chr(0x0531) + chr(0x0580) + chr(0x057f) + chr(0x0561) + chr(0x0570) + chr(0x0561) + chr(0x0576) + chr(0x0565) + chr(0x056c) + " " + T.get("Orders", chr(0x054a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x0565) + chr(0x0580) + chr(0x0576) + chr(0x0565) + chr(0x0580)) + " CSV"

    # No products available
    CHKAN = chr(0x0579) + chr(0x056f) + chr(0x0561) + chr(0x0576)
    PRODUCTS = T.get("Products", chr(0x0531) + chr(0x057a) + chr(0x0580) + chr(0x0561) + chr(0x0576) + chr(0x0584) + chr(0x0576) + chr(0x0565) + chr(0x0580))
    NO_PRODUCTS_AVAILABLE = PRODUCTS + " " + CHKAN

    # Place Order
    PLACE_ORDER = chr(0x054a) + chr(0x0561) + chr(0x057f) + chr(0x057e) + chr(0x056b) + chr(0x0580) + chr(0x0565) + chr(0x056c)

    # Browse Files
    BROWSE_FILES = chr(0x0538) + chr(0x0576) + chr(0x057f) + chr(0x0580) + chr(0x0565) + chr(0x0584) + " " + chr(0x0586) + chr(0x0561) + chr(0x0575) + chr(0x056c)

    # Delete Image
    DELETE_IMAGE = DELETE + " " + chr(0x0576) + chr(0x056f) + chr(0x0561) + chr(0x0580) + chr(0x0568)

    return {
        'LOGOUT': LOGOUT,
        'SIGN_IN': SIGN_IN,
        'CONTACT_SALES': CONTACT_SALES,
        'NEW_ORDER': NEW_ORDER,
        'NO_ORDERS': NO_ORDERS,
        'VIEW': VIEW,
        'PREVIOUS': PREVIOUS,
        'NEXT': NEXT,
        'BACK_TO_ORDERS': BACK_TO_ORDERS,
        'ADD_ITEM': ADD_ITEM,
        'REMOVE': REMOVE,
        'CONFIRM': CONFIRM,
        'CANCEL': CANCEL,
        'DELETE': DELETE,
        'PRIMARY': PRIMARY,
        'PLUS_ADD_VARIANT': PLUS_ADD_VARIANT,
        'PLUS_ADD_MOVEMENT': PLUS_ADD_MOVEMENT,
        'EDIT': EDIT,
        'CREATE_PRODUCT': CREATE_PRODUCT,
        'CREATE_CUSTOMER': CREATE_CUSTOMER,
        'CREATE_USER': CREATE_USER,
        'DELETE_PRODUCT': DELETE_PRODUCT,
        'DELETE_CUSTOMER': DELETE_CUSTOMER,
        'EDIT_PRODUCT_BTN': EDIT_PRODUCT_BTN,
        'EDIT_CUSTOMER_BTN': EDIT_CUSTOMER_BTN,
        'EDIT_USER': EDIT_USER,
        'SAVE_CHANGES': SAVE_CHANGES,
        'EXPORT_ORDERS': EXPORT_ORDERS,
        'NO_PRODUCTS_AVAILABLE': NO_PRODUCTS_AVAILABLE,
        'PLACE_ORDER': PLACE_ORDER,
        'BROWSE_FILES': BROWSE_FILES,
        'DELETE_IMAGE': DELETE_IMAGE,
    }


def fix_all(A):
    """Fix all remaining untranslated English strings."""

    # 1. TopHeader.tsx - "Logout" is standalone text (line 34)
    rep('components/layout/TopHeader.tsx', [
        ('          Logout\n', '          ' + A['LOGOUT'] + '\n'),
    ])

    # 2. Login page - "Sign In" and "Contact Sales" are standalone text
    rep('app/login/page.tsx', [
        ('              Sign In\n', '              ' + A['SIGN_IN'] + '\n'),
        ('            Contact Sales\n', '            ' + A['CONTACT_SALES'] + '\n'),
    ])

    # 3. Orders page - "New Order", "No orders found", "View", "Previous", "Next"
    rep('app/dashboard/orders/page.tsx', [
        ('          New Order\n', '          ' + A['NEW_ORDER'] + '\n'),
        ('                      No orders found\n', '                      ' + A['NO_ORDERS'] + '\n'),
        ('                          View\n', '                          ' + A['VIEW'] + '\n'),
        ('              Previous\n', '              ' + A['PREVIOUS'] + '\n'),
        ('              Next\n', '              ' + A['NEXT'] + '\n'),
    ])

    # 4. Order detail - "&larr; Back to orders" (standalone text on line 45)
    rep('app/dashboard/orders/[id]/page.tsx', [
        ('            &larr; Back to orders\n', '            &larr; ' + A['BACK_TO_ORDERS'] + '\n'),
    ])

    # 5. New order page - "Add Item", "Remove"
    rep('app/dashboard/orders/new/page.tsx', [
        ('                Add Item\n', '                ' + A['ADD_ITEM'] + '\n'),
        ('                    Remove\n', '                    ' + A['REMOVE'] + '\n'),
    ])

    # 6. OrderStatusChange - "Confirm" and "Cancel" standalone
    rep('app/dashboard/orders/OrderStatusChange.tsx', [
        ('{loading ? "\u0539\u0561\u0580\u0574\u0561\u0581\u0576\u0578\u0582\u0574..." : "Confirm"}', '{loading ? "\u0539\u0561\u0580\u0574\u0561\u0581\u0576\u0578\u0582\u0574..." : "' + A['CONFIRM'] + '"}'),
        ('              Cancel\n', '              ' + A['CANCEL'] + '\n'),
    ])

    # 7. Products page - "View" standalone
    rep('app/dashboard/products/page.tsx', [
        ('                        View\n', '                        ' + A['VIEW'] + '\n'),
    ])

    # 8. Product detail - "Primary" standalone
    rep('app/dashboard/products/[id]/page.tsx', [
        ('                          Primary\n', '                          ' + A['PRIMARY'] + '\n'),
    ])

    # 9. ProductActions - "Delete" (button), "Cancel" (button), "Delete Product", "Create Product"
    rep('app/dashboard/products/ProductActions.tsx', [
        ('        Delete\n      </Button>\n\n      <Modal open={confirmOpen}', '        ' + A['DELETE'] + '\n      </Button>\n\n      <Modal open={confirmOpen}'),
        ('            Cancel\n          </Button>\n          <Button variant="danger" onClick={handleDelete}', '            ' + A['CANCEL'] + '\n          </Button>\n          <Button variant="danger" onClick={handleDelete}'),
        ('            Delete Product\n', '            ' + A['DELETE_PRODUCT'] + '\n'),
        ('            Cancel\n          </Button>\n            <Button type="submit"', '            ' + A['CANCEL'] + '\n          </Button>\n            <Button type="submit"'),
        ('              Create Product\n', '              ' + A['CREATE_PRODUCT'] + '\n'),
    ])

    # 10. EditProductForm - "Edit Product" (button text), "Cancel", "Save Changes"
    rep('app/dashboard/products/EditProductForm.tsx', [
        ('        Edit Product\n', '        ' + A['EDIT_PRODUCT_BTN'] + '\n'),
        ('              Cancel\n', '              ' + A['CANCEL'] + '\n'),
        ('              Save Changes\n', '              ' + A['SAVE_CHANGES'] + '\n'),
    ])

    # 11. ProductImageUpload - "Primary" (badge), "Cancel", "Delete Image"
    rep('app/dashboard/products/ProductImageUpload.tsx', [
        ('                  Primary\n', '                  ' + A['PRIMARY'] + '\n'),
        ('            Cancel\n', '            ' + A['CANCEL'] + '\n'),
        ('            Delete Image\n', '            ' + A['DELETE_IMAGE'] + '\n'),
    ])

    # 12. VariantActions - "+ Add Variant", "Confirm", "Cancel"
    rep('app/dashboard/products/VariantActions.tsx', [
        ('          + Add Variant\n', '          ' + A['PLUS_ADD_VARIANT'] + '\n'),
        ('{deleting ? "..." : "Confirm"}', '{deleting ? "..." : "' + A['CONFIRM'] + '"}'),
        ('                            Cancel\n', '                            ' + A['CANCEL'] + '\n'),
    ])

    # 13. Inventory page - "View"
    rep('app/dashboard/inventory/page.tsx', [
        ('                        View\n', '                        ' + A['VIEW'] + '\n'),
    ])

    # 14. InventoryActions - "Edit" (button), "Delete" (button), "+ Add Movement"
    rep('app/dashboard/inventory/InventoryActions.tsx', [
        ('        Edit\n      </Button>', '        ' + A['EDIT'] + '\n      </Button>'),
        ('        Delete\n      </Button>', '        ' + A['DELETE'] + '\n      </Button>'),
        ('            Delete\n          </Button>', '            ' + A['DELETE'] + '\n          </Button>'),
        ('        + Add Movement\n', '        ' + A['PLUS_ADD_MOVEMENT'] + '\n'),
    ])

    # 15. Customers page - "View"
    rep('app/dashboard/customers/page.tsx', [
        ('                      View\n', '                      ' + A['VIEW'] + '\n'),
    ])

    # 16. CustomerActions - "Cancel" (two occurrences), "Create Customer", "Delete" (button), "Delete Customer"
    rep('app/dashboard/customers/CustomerActions.tsx', [
        ('              Cancel\n            </Button>\n            <Button type="submit" loading={loading}>\n              Create Customer',
         '              ' + A['CANCEL'] + '\n            </Button>\n            <Button type="submit" loading={loading}>\n              ' + A['CREATE_CUSTOMER']),
        ('        Delete\n      </Button>\n\n      <Modal open={confirmOpen}',
         '        ' + A['DELETE'] + '\n      </Button>\n\n      <Modal open={confirmOpen}'),
        ('            Cancel\n          </Button>\n          <Button variant="danger" onClick={handleDelete} loading={loading}>\n            Delete Customer',
         '            ' + A['CANCEL'] + '\n          </Button>\n          <Button variant="danger" onClick={handleDelete} loading={loading}>\n            ' + A['DELETE_CUSTOMER']),
    ])

    # 17. EditCustomerForm - "Edit Customer" (button), "Cancel", "Save Changes"
    rep('app/dashboard/customers/EditCustomerForm.tsx', [
        ('        Edit Customer\n', '        ' + A['EDIT_CUSTOMER_BTN'] + '\n'),
        ('              Cancel\n', '              ' + A['CANCEL'] + '\n'),
        ('              Save Changes\n', '              ' + A['SAVE_CHANGES'] + '\n'),
    ])

    # 18. Users page - "View"
    rep('app/dashboard/users/page.tsx', [
        ('                      View\n', '                      ' + A['VIEW'] + '\n'),
    ])

    # 19. UserActions - "Cancel" (two occurrences), "Create User"
    rep('app/dashboard/users/UserActions.tsx', [
        ('              Cancel\n            </Button>\n            <Button type="submit" loading={loading}>\n              Create User',
         '              ' + A['CANCEL'] + '\n            </Button>\n            <Button type="submit" loading={loading}>\n              ' + A['CREATE_USER']),
        ('            Cancel\n          </Button>\n          <Button',
         '            ' + A['CANCEL'] + '\n          </Button>\n          <Button'),
    ])

    # 20. EditUserForm - "Edit User" (button), "Cancel", "Save Changes"
    rep('app/dashboard/users/EditUserForm.tsx', [
        ('        Edit User\n', '        ' + A['EDIT_USER'] + '\n'),
        ('              Cancel\n', '              ' + A['CANCEL'] + '\n'),
        ('              Save Changes\n', '              ' + A['SAVE_CHANGES'] + '\n'),
    ])

    # 21. Reports page - "Export Orders CSV"
    rep('app/dashboard/reports/page.tsx', [
        ('          Export Orders CSV\n', '          ' + A['EXPORT_ORDERS'] + '\n'),
    ])

    # 22. Catalog page - "No products available"
    rep('app/catalog/page.tsx', [
        ('            No products available\n', '            ' + A['NO_PRODUCTS_AVAILABLE'] + '\n'),
    ])

    # 23. Catalog detail - "Place Order"
    rep('app/catalog/[id]/page.tsx', [
        ('              Place Order\n', '              ' + A['PLACE_ORDER'] + '\n'),
    ])

    # 24. ImageUpload - "Browse Files"
    rep('components/ui/ImageUpload.tsx', [
        ('        Browse Files\n', '        ' + A['BROWSE_FILES'] + '\n'),
    ])

    # 25. Production page - "View"
    rep('app/dashboard/production/page.tsx', [
        ('                      View\n', '                      ' + A['VIEW'] + '\n'),
    ])


def main():
    T = load_translations()
    print(f'Loaded {len(T)} base translations')

    A = build_extras(T)
    print(f'Built {len(A)} fix translations')

    fix_all(A)

    print(f'\n=== Files fixed ({len(changed_files)}) ===')
    for f in changed_files:
        print(f'  {f}')


if __name__ == '__main__':
    main()
