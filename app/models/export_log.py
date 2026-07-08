from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class ExportLog(Base):
    __tablename__ = "export_logs"

    id         = Column(Integer, primary_key=True, index=True)
    user_name  = Column(String(100), nullable=False)
    filename   = Column(String(200), nullable=False)
    filters    = Column(Text, nullable=True)   # JSON string des filtres actifs
    nb_rows    = Column(Text, nullable=True)   # JSON string {sheet: count}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
