"""
Seed script — populates the database with realistic sample data.
Run: python -m scripts.seed
"""
import sys
import os
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings, WEAK_SECRET_KEYS
from app.database import Base
from app.users.models import User, UserRole
from app.users.service import hash_password
from app.customers.models import Customer
from app.products.models import Product, ProductVariant, ProductCategory, ProductImage
from app.inventory.models import Material, Inventory
from app.orders.models import Order, OrderItem, OrderStatus, OrderPriority
from app.production.models import ProductionStage, StageName, StageStatus

# Default seed credentials — only used when seeding is explicitly enabled in
# production via ADMIN_INITIAL_PASSWORD. The default plaintext is rejected at
# every gate so it can never reach a production database.
DEFAULT_ADMIN_EMAIL = "admin@art-manufacturing.com"
DEFAULT_ADMIN_PASSWORD = "admin123456"
DEFAULT_USER_PASSWORD = "user123456"

# Passwords known to be public in this repo or commonly seen in seed scripts.
# Used as the production guard for ADMIN_INITIAL_PASSWORD.
WEAK_ADMIN_PASSWORDS = frozenset({
    "",
    "admin",
    "admin123",
    "admin123456",
    "password",
    "password123",
    "changeme",
    "change-me",
    "123456",
    "12345678",
})


def _should_run_seed() -> tuple[bool, str]:
    """Decide whether the seed script should run, and explain why.

    Production is opt-in: the script aborts unless ENABLE_SEED_DATA=true AND
    ADMIN_INITIAL_PASSWORD is set to a non-weak value. Local docker-compose
    and pytest (APP_ENV != production) keep the prior behaviour.
    """
    env = settings.app_env
    if env != "production":
        return True, f"non-production (APP_ENV={env}) — seeding allowed"

    enable_flag = os.environ.get("ENABLE_SEED_DATA", "").strip().lower()
    if enable_flag != "true":
        return False, "production with ENABLE_SEED_DATA != true — refusing to seed default credentials"

    admin_pw = os.environ.get("ADMIN_INITIAL_PASSWORD", "")
    if not admin_pw:
        return False, "production seed requested but ADMIN_INITIAL_PASSWORD is not set"
    if admin_pw.lower() in WEAK_ADMIN_PASSWORDS:
        return False, "production seed refused: ADMIN_INITIAL_PASSWORD is a known weak/default value"
    if len(admin_pw) < 12:
        return False, "production seed refused: ADMIN_INITIAL_PASSWORD must be at least 12 characters"

    return True, "production seed enabled with non-weak ADMIN_INITIAL_PASSWORD"


def _resolved_admin_password() -> str:
    """Return the password to seed the admin with. Production uses
    ADMIN_INITIAL_PASSWORD (already validated by _should_run_seed). Dev keeps
    the legacy default so docker-compose flows are unchanged."""
    if settings.app_env == "production":
        return os.environ["ADMIN_INITIAL_PASSWORD"]
    return os.environ.get("ADMIN_INITIAL_PASSWORD") or DEFAULT_ADMIN_PASSWORD


def seed():
    should_run, reason = _should_run_seed()
    if not should_run:
        print(f"[seed] skipped: {reason}")
        return

    print(f"[seed] running: {reason}")

    # Engine is created lazily so importing this module (e.g. from tests)
    # does not require a reachable database.
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Idempotency guard — if the admin user already exists, the DB has
        # already been seeded. Safe to call on every backend boot.
        existing_admin = db.query(User).filter(
            User.email == "admin@art-manufacturing.com"
        ).first()
        if existing_admin:
            print("Seed: admin user already exists, skipping.")
            return

        # ── Categories ──
        categories = [
            ProductCategory(name="Shirts", description="Formal and casual shirts"),
            ProductCategory(name="Trousers", description="Pants and trousers"),
            ProductCategory(name="Jackets", description="Outerwear and jackets"),
            ProductCategory(name="Dresses", description="Women's dresses"),
            ProductCategory(name="Uniforms", description="Corporate and work uniforms"),
        ]
        db.add_all(categories)
        db.flush()

        # ── Customers ──
        customers = [
            Customer(name="John Mitchell", company_name="Mitchell & Co Retail", email="john@mitchell-retail.com", phone="+1-555-0101", address="123 Commerce St, New York, NY 10001", notes="Preferred customer, monthly bulk orders"),
            Customer(name="Sarah Chen", company_name="Chen Fashion Group", email="sarah@chenfashion.com", phone="+1-555-0102", address="456 Fashion Ave, Los Angeles, CA 90015", notes="High-end fashion retailer"),
            Customer(name="David Okafor", company_name="Okafor Uniforms Ltd", email="david@okafor-uniforms.com", phone="+44-20-7946-0958", address="78 Industrial Way, London, UK", notes="Specializes in corporate uniforms"),
            Customer(name="Maria Garcia", company_name="Garcia Textiles", email="maria@garciatextiles.com", phone="+34-91-555-0103", address="Calle Moda 12, Madrid, Spain", notes="European distributor"),
            Customer(name="Alex Petrov", company_name="Petrov Import/Export", email="alex@petrov-ie.com", phone="+49-30-555-0104", address="Berliner Str. 45, Berlin, Germany"),
        ]
        db.add_all(customers)
        db.flush()

        # ── Users ──
        admin_password = _resolved_admin_password()
        admin = User(
            email=DEFAULT_ADMIN_EMAIL,
            hashed_password=hash_password(admin_password),
            role=UserRole.admin,
        )
        db.add(admin)

        user1 = User(
            email="john@mitchell-retail.com",
            hashed_password=hash_password("user123456"),
            role=UserRole.simple_user,
            customer_id=customers[0].id,
        )
        user2 = User(
            email="sarah@chenfashion.com",
            hashed_password=hash_password("user123456"),
            role=UserRole.simple_user,
            customer_id=customers[1].id,
        )
        db.add_all([user1, user2])
        db.flush()

        # ── Materials ──
        materials_data = [
            ("Cotton Fabric 200gsm", "MAT-COT-200", "meters", 50),
            ("Polyester Blend 150gsm", "MAT-POL-150", "meters", 30),
            ("Silk Fabric Premium", "MAT-SLK-001", "meters", 20),
            ("Denim 12oz", "MAT-DEN-012", "meters", 40),
            ("Wool Blend 300gsm", "MAT-WOL-300", "meters", 25),
            ("Buttons — Standard White", "MAT-BTN-WHT", "pieces", 500),
            ("Buttons — Metal Gold", "MAT-BTN-GLD", "pieces", 200),
            ("Zipper 20cm", "MAT-ZIP-020", "pieces", 300),
            ("Thread — White", "MAT-THR-WHT", "spools", 100),
            ("Thread — Black", "MAT-THR-BLK", "spools", 100),
            ("Labels — Brand Woven", "MAT-LBL-BRD", "pieces", 1000),
            ("Elastic Band 2cm", "MAT-ELS-002", "meters", 200),
        ]

        materials = []
        for name, sku, unit, threshold in materials_data:
            mat = Material(name=name, sku=sku, unit=unit, low_stock_threshold=Decimal(str(threshold)))
            db.add(mat)
            materials.append(mat)
        db.flush()

        # Create inventory records
        stock_levels = [150, 80, 15, 120, 60, 2000, 450, 800, 250, 300, 5000, 500]
        for mat, qty in zip(materials, stock_levels):
            inv = Inventory(material_id=mat.id, quantity_on_hand=Decimal(str(qty)))
            db.add(inv)
        db.flush()

        # ── Products ──
        products_data = [
            ("Classic Oxford Shirt", "PRD-OXF-001", categories[0].id, "Timeless oxford button-down shirt", "100% cotton, reinforced collar, french seams"),
            ("Slim Fit Chinos", "PRD-CHI-001", categories[1].id, "Modern slim fit chinos", "97% cotton, 3% elastane blend"),
            ("Wool Blend Blazer", "PRD-BLZ-001", categories[2].id, "Tailored wool blend blazer", "Italian wool blend, half canvas construction"),
            ("Summer Linen Dress", "PRD-DRS-001", categories[3].id, "Light summer linen dress", "100% linen, relaxed fit"),
            ("Corporate Polo Uniform", "PRD-UNI-001", categories[4].id, "Branded corporate polo", "Pique cotton, embroidery-ready"),
            ("Denim Work Jacket", "PRD-JKT-001", categories[2].id, "Heavy-duty denim work jacket", "12oz denim, reinforced elbows and shoulders"),
            ("Formal Dress Shirt", "PRD-FRM-001", categories[0].id, "Tailored formal dress shirt", "Egyptian cotton, french cuffs"),
            ("Cargo Trousers", "PRD-CRG-001", categories[1].id, "Multi-pocket cargo trousers", "Ripstop cotton, reinforced knees"),
        ]

        products = []
        for name, sku, cat_id, desc, tech_notes in products_data:
            p = Product(name=name, sku=sku, category_id=cat_id, description=desc, technical_notes=tech_notes)
            db.add(p)
            products.append(p)
        db.flush()

        # ── Variants ──
        sizes = ["S", "M", "L", "XL"]
        # Prices in AMD (Armenian dram). Demo values.
        colors_map = {
            0: [("White", 18000), ("Blue", 19000), ("Black", 18000)],
            1: [("Khaki", 22000), ("Navy", 22000), ("Olive", 21000)],
            2: [("Charcoal", 72000), ("Navy", 70000)],
            3: [("Ivory", 34000), ("Sage", 36000)],
            4: [("White", 11000), ("Navy", 11000), ("Black", 11000)],
            5: [("Indigo", 48000), ("Black", 50000)],
            6: [("White", 26000), ("Light Blue", 27000)],
            7: [("Khaki", 24000), ("Black", 25000)],
        }

        variants = []
        for pi, product in enumerate(products):
            for size in sizes:
                for color, base_price in colors_map[pi]:
                    v = ProductVariant(
                        product_id=product.id,
                        size=size,
                        color=color,
                        price=Decimal(str(base_price)),
                        stock_quantity=25,
                    )
                    db.add(v)
                    variants.append(v)
        db.flush()

        # ── Orders ──
        now = datetime.utcnow()
        # Seed only the 3 active statuses (draft / confirmed / completed). The
        # historical in_production / shipped / cancelled values still exist in
        # the enum so older DBs remain readable, but they're no longer used by
        # the application flow — see migration 011 + handoff/CURRENT_STATE.md.
        orders_data = [
            (customers[0].id, admin.id, OrderStatus.confirmed, OrderPriority.high, now + timedelta(days=14), "Bulk order — 500 oxford shirts"),
            (customers[1].id, admin.id, OrderStatus.confirmed, OrderPriority.normal, now + timedelta(days=21), "Spring collection chinos"),
            (customers[2].id, admin.id, OrderStatus.draft, OrderPriority.urgent, now + timedelta(days=7), "Corporate uniform rush order"),
            (customers[0].id, admin.id, OrderStatus.completed, OrderPriority.normal, now - timedelta(days=5), "Repeat order — blazers"),
            (customers[3].id, admin.id, OrderStatus.confirmed, OrderPriority.normal, now + timedelta(days=30), "European distribution batch"),
            (customers[4].id, admin.id, OrderStatus.confirmed, OrderPriority.low, now + timedelta(days=45), "Sample order for new client"),
        ]

        orders = []
        for cust_id, creator_id, status, priority, deadline, notes in orders_data:
            o = Order(customer_id=cust_id, created_by=creator_id, status=status, priority=priority, deadline=deadline, notes=notes)
            db.add(o)
            orders.append(o)
        db.flush()

        # Add items to orders
        for i, order in enumerate(orders):
            for j in range(2):
                vi = (i * 3 + j) % len(variants)
                item = OrderItem(
                    order_id=order.id,
                    product_variant_id=variants[vi].id,
                    quantity=50 + (i * 10),
                    unit_price=variants[vi].price,
                )
                db.add(item)
        db.flush()

        # ── Production Stages (five default stages per in-production order) ──
        for order in orders:
            if order.status in (OrderStatus.in_production, OrderStatus.completed):
                default_stages = [
                    StageName.cutting,
                    StageName.sewing,
                    StageName.quality_control,
                    StageName.packaging,
                    StageName.ready_for_shipment,
                ]
                for idx, stage_name in enumerate(default_stages):
                    if order.status == OrderStatus.completed:
                        status = StageStatus.completed
                        started = now - timedelta(days=3)
                        completed = now - timedelta(days=1)
                    elif idx == 0:
                        status = StageStatus.in_progress
                        started = now - timedelta(days=2)
                        completed = None
                    else:
                        status = StageStatus.pending
                        started = None
                        completed = None
                    stage = ProductionStage(
                        order_id=order.id,
                        stage_name=stage_name,
                        status=status,
                        assigned_to=admin.id,
                        started_at=started,
                        completed_at=completed,
                    )
                    db.add(stage)
        db.flush()

        db.commit()
        print("Seed data inserted successfully!")
        if settings.app_env == "production":
            print(f"  Admin login: {DEFAULT_ADMIN_EMAIL} / <ADMIN_INITIAL_PASSWORD>")
        else:
            print(f"  Admin login: {DEFAULT_ADMIN_EMAIL} / {admin_password}")
            print(f"  User login:  john@mitchell-retail.com / {DEFAULT_USER_PASSWORD}")
            print(f"  User login:  sarah@chenfashion.com / {DEFAULT_USER_PASSWORD}")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
