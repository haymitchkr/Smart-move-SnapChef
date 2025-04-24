from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    recipes = relationship('RecipeHistory', back_populates='user')
    preferences = relationship('UserPreferences', uselist=False, back_populates='user')

class RecipeHistory(Base):
    __tablename__ = 'recipe_history'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    ingredients = Column(Text, nullable=False)
    recipe = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    user = relationship('User', back_populates='recipes')

class UserPreferences(Base):
    __tablename__ = 'user_preferences'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    healthy_profile = Column(Boolean, default=False)
    preferred_cuisine = Column(String, default='Любая')
    user = relationship('User', back_populates='preferences') 