from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.schemas.auth import UserCreate
from app.utils.security import get_password_hash, verify_password

class AuthService:
    @staticmethod
    async def create_user(db: AsyncSession, user: UserCreate) -> User:
        hashed_password = get_password_hash(user.password)
        db_user = User(email=user.email, password_hash=hashed_password)
        db.add(db_user)
        try:
            await db.commit()
            await db.refresh(db_user)
            return db_user
        except IntegrityError:
            await db.rollback()
            raise ValueError("Email already registered")

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user