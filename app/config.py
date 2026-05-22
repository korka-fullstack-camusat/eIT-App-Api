from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://parc_user:parc_pass@localhost:5434/parc_it"
    erh_api_url: str = "http://localhost:8030"
    erh_api_token: str = ""
    secret_key: str = "changeme-secret-key-parc-it"

    # API Employés externe (apierh.camusatsn.com)
    erh_external_api_url: str = "https://apierh.camusatsn.com/api/employees/external/internes/"
    erh_api_key:          str = ""

    # SMTP
    smtp_host:     str = "smtp.gmail.com"
    smtp_port:     int = 587
    smtp_user:     str = ""
    smtp_password: str = ""
    smtp_from:     str = "noreply@camusat.sn"

    class Config:
        env_file = ".env"


settings = Settings()
