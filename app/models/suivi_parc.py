from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func
from ..database import Base


class SuiviParcItem(Base):
    __tablename__ = "suivi_parc"

    id                     = Column(Integer,      primary_key=True, index=True)
    code_ref               = Column(String(50),   unique=True, index=True, nullable=False)
    nom                    = Column(String(100),  nullable=True)
    prenom                 = Column(String(200),  nullable=True)
    projet                 = Column(String(100),  nullable=True)
    lieu                   = Column(String(50),   nullable=True)
    nature                 = Column(String(50),   nullable=True)
    designation_equipement = Column(String(250),  nullable=True)
    ref_carte_reseau       = Column(String(100),  nullable=True)
    numero_serie           = Column(String(100),  nullable=True)
    po                     = Column(String(50),   nullable=True)
    date_attribution       = Column(Date,         nullable=True)
    statut                 = Column(String(50),   nullable=True)
    source_onglet          = Column(String(50),   nullable=True)
    created_at             = Column(DateTime(timezone=True), server_default=func.now())
    updated_at             = Column(DateTime(timezone=True), onupdate=func.now())
