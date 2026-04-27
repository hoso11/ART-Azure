import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.users.models import User, UserRole
from app.users.service import hash_password
from app.auth.service import create_access_token
from app.customers.models import Customer

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def admin_user(db_session: AsyncSession):
    user = User(
        email="admin@test.com",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def customer(db_session: AsyncSession):
    c = Customer(name="Test Customer", company_name="Test Co", email="customer@test.com")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest.fixture
async def simple_user(db_session: AsyncSession, customer: Customer):
    user = User(
        email="user@test.com",
        hashed_password=hash_password("userpass123"),
        role=UserRole.simple_user,
        customer_id=customer.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_cookies(admin_user: User):
    token = create_access_token(admin_user.id, admin_user.role.value)
    return {"access_token": token}


@pytest.fixture
async def user_cookies(simple_user: User):
    token = create_access_token(simple_user.id, simple_user.role.value)
    return {"access_token": token}
