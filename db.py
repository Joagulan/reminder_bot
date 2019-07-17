from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date, Time
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session


engine = create_engine('postgresql://postgres:12345@localhost/reminder',
                       isolation_level="READ COMMITTED")
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)

    reminders = relationship("Reminder", back_populates="user")
    notes = relationship("Note", back_populates="user")
    categories = relationship("Category", back_populates="user")

    def __repr__(self):
        return f"telegram_id={self.id}"


class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)
    text = Column(String)
    notification = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="reminders")

    def __repr__(self):
        return f"date = {self.date}, time = {self.time}, text = {self.text}"


class Note(Base):
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True)
    text = Column(String)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="notes")

    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship('Category', back_populates="notes")

    def __repr__(self):
        return f"note: {self.text}"


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name_of_category = Column(String)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="categories")

    notes = relationship("Note", back_populates="category")

    def __repr__(self):
        return f"category: {self.name_of_category}"


Base.metadata.create_all(bind=engine)

session_factory = sessionmaker(bind=engine)

Session = scoped_session(session_factory)
session = Session()



