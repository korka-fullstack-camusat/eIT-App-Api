from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class LicenceKaspersky(Base):
    __tablename__ = "licences_kaspersky"

    id              = Column(Integer, primary_key=True, index=True)
    numero          = Column(Integer,      nullable=True)
    produit         = Column(String(100),  nullable=False)
    code_activation = Column(String(100),  unique=True, index=True, nullable=False)
    nb_machines     = Column(Integer,      nullable=True)
    date_debut      = Column(Date,         nullable=True)
    date_expiration = Column(Date,         nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    machines = relationship(
        "KasperskyMachine",
        back_populates="licence",
        cascade="all, delete-orphan",
        foreign_keys="KasperskyMachine.code_activation",
    )


class KasperskyMachine(Base):
    __tablename__ = "kaspersky_machines"

    id              = Column(Integer,      primary_key=True, index=True)
    numero          = Column(Integer,      nullable=True)
    machine         = Column(String(250),  nullable=False)
    code_activation = Column(
        String(100),
        ForeignKey("licences_kaspersky.code_activation", ondelete="CASCADE"),
        nullable=False,
    )
    date_expiration = Column(Date,        nullable=True)
    statut          = Column(String(50),  nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    licence = relationship(
        "LicenceKaspersky",
        back_populates="machines",
        foreign_keys=[code_activation],
    )


class LicenceM365Compte(Base):
    __tablename__ = "licences_m365_comptes"

    id                     = Column(Integer,      primary_key=True, index=True)
    numero                 = Column(Integer,      nullable=True)
    produit                = Column(String(100),  nullable=False)
    compte_organisateur    = Column(String(100),  unique=True, index=True, nullable=False)
    email_organisateur     = Column(String(200),  nullable=True)
    nb_utilisateurs        = Column(Integer,      nullable=True)
    places_libres          = Column(Integer,      nullable=True)
    date_debut             = Column(Date,         nullable=True)
    dernier_renouvellement = Column(Date,         nullable=True)
    date_expiration        = Column(Date,         nullable=True)
    created_at             = Column(DateTime(timezone=True), server_default=func.now())

    membres = relationship(
        "LicenceM365Membre",
        back_populates="compte",
        cascade="all, delete-orphan",
        foreign_keys="LicenceM365Membre.compte_organisateur",
    )


class LicenceM365Membre(Base):
    __tablename__ = "licences_m365_membres"

    id                  = Column(Integer,     primary_key=True, index=True)
    numero              = Column(Integer,     nullable=True)
    nom                 = Column(String(200), nullable=False)
    email               = Column(String(200), nullable=True)
    role                = Column(String(50),  nullable=True)
    compte_organisateur = Column(
        String(100),
        ForeignKey("licences_m365_comptes.compte_organisateur", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    compte = relationship(
        "LicenceM365Compte",
        back_populates="membres",
        foreign_keys=[compte_organisateur],
    )


class LicenceAdobe(Base):
    __tablename__ = "licences_adobe"

    id                     = Column(Integer,      primary_key=True, index=True)
    numero                 = Column(Integer,      nullable=True)
    produit                = Column(String(100),  nullable=False)
    utilisateur            = Column(String(200),  nullable=True)
    email_compte           = Column(String(200),  nullable=True)
    fournisseur            = Column(String(100),  nullable=True)
    date_activation        = Column(Date,         nullable=True)
    dernier_renouvellement = Column(Date,         nullable=True)
    date_expiration        = Column(Date,         nullable=True)
    created_at             = Column(DateTime(timezone=True), server_default=func.now())


class LicencePowerBI(Base):
    __tablename__ = "licences_powerbi"

    id                     = Column(Integer,      primary_key=True, index=True)
    numero                 = Column(Integer,      nullable=True)
    produit                = Column(String(100),  nullable=False)
    utilisateur            = Column(String(200),  nullable=True)
    compte_powerbi         = Column(String(250),  nullable=True)
    fournisseur            = Column(String(100),  nullable=True)
    date_activation        = Column(Date,         nullable=True)
    dernier_renouvellement = Column(Date,         nullable=True)
    date_expiration        = Column(Date,         nullable=True)
    created_at             = Column(DateTime(timezone=True), server_default=func.now())
