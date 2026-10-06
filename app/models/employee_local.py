from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func
from ..database import Base


class EmployeeLocal(Base):
    __tablename__ = "employees_local"

    id                = Column(Integer, primary_key=True, index=True)
    matricule         = Column(String(20),  unique=True, index=True, nullable=False)
    nom               = Column(String(100), nullable=False)
    prenom            = Column(String(200), nullable=True)
    email             = Column(String(200), nullable=True)
    fonction          = Column(String(250), nullable=True)
    service           = Column(String(150), nullable=True)
    type_contrat      = Column(String(50),  nullable=True)
    statut            = Column(String(50),  nullable=True)
    date_embauche     = Column(Date,        nullable=True)
    date_fin_cdd      = Column(Date,        nullable=True)
    fin_periode_essai = Column(Date,        nullable=True)
    genre             = Column(String(20),  nullable=True)
    telephone         = Column(String(100), nullable=True)
    manager_n1        = Column(String(200), nullable=True)
    manager_n2        = Column(String(200), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())
