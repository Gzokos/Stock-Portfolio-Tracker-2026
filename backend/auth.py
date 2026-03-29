

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
import jwt
import bcrypt
from sqlalchemy.orm import Session
import logging
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database_models import User

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key_change_this_in_production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 1440))  # 24 hours


class AuthService:
  

    def __init__(self, session: Session):
        ession = session

    @staticmethod
    def hash_password(password: str) -> str:
      
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
    
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def create_access_token(self, user_id: str, expires_delta: Optional[timedelta] = None) -> str:
     
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.utcnow()
        }

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[str]:
     
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            
            if user_id is None:
                return None
            
            return user_id
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def register(
        self,
        email: str,
        username: str,
        password: str,
        first_name: str = None,
        last_name: str = None
    ) -> Tuple[Optional[User], Optional[str]]:
      
        # Check if email already exists
        existing_email = self.session.query(User).filter(
            User.email == email
        ).first()
        
        if existing_email:
            return None, "Email already registered"

        # Check if username already exists
        existing_username = self.session.query(User).filter(
            User.username == username
        ).first()
        
        if existing_username:
            return None, "Username already taken"

        try:
            # Hash password
            password_hash = self.hash_password(password)

            # Create user
            user = User(
                email=email,
                username=username,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )

            self.session.add(user)
            self.session.commit()

            logger.info(f"User registered: {email}")
            return user, None

        except Exception as e:
            self.session.rollback()
            logger.error(f"Registration error: {e}")
            return None, str(e)

    def login(self, email: str, password: str) -> Tuple[Optional[str], Optional[str]]:
       
        # Find user
        user = self.session.query(User).filter(User.email == email).first()

        if not user:
            return None, "Invalid email or password"

        # Verify password
        if not self.verify_password(password, user.password_hash):
            return None, "Invalid email or password"

        if not user.is_active:
            return None, "Account is disabled"

        # Update last login
        user.last_login = datetime.utcnow()
        self.session.commit()

        # Create token
        token = self.create_access_token(user.id)

        logger.info(f"User logged in: {email}")
        return token, None

    def get_user(self, user_id: str) -> Optional[User]:
       
        return self.session.query(User).filter(User.id == user_id).first()

    def update_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, Optional[str]]:
       
        user = self.get_user(user_id)

        if not user:
            return False, "User not found"

        # Verify old password
        if not self.verify_password(old_password, user.password_hash):
            return False, "Incorrect password"

        # Set new password
        try:
            user.password_hash = self.hash_password(new_password)
            self.session.commit()
            logger.info(f"Password updated for user: {user.email}")
            return True, None
        except Exception as e:
            self.session.rollback()
            return False, str(e)

    def refresh_token(self, token: str) -> Tuple[Optional[str], Optional[str]]:
      
        user_id = self.verify_token(token)

        if not user_id:
            return None, "Invalid token"

        user = self.get_user(user_id)

        if not user or not user.is_active:
            return None, "User not found or inactive"

        # Create new token
        new_token = self.create_access_token(user.id)
        return new_token, None


# Dependency for FastAPI
async def get_current_user(token: str, session: Session) -> Optional[User]:
   
    if not token:
        return None

    auth_service = AuthService(session)
    user_id = auth_service.verify_token(token)

    if not user_id:
        return None

    return auth_service.get_user(user_id)
