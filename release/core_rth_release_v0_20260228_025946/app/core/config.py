#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

RTH SYNAPSEâ„¢ v4.0.1 - Configuration

Configurazione centralizzata con supporto per file .env

"""



import logging.handlers

from pydantic_settings import BaseSettings

from pydantic import validator

from typing import Optional, List

import logging

from pathlib import Path

import os



# Carica le variabili d'ambiente dai file .env

try:

    from dotenv import load_dotenv

    

    # Carica i file .env in ordine di prioritÃ 

    env_files = [
        ".env",
        ".env.rth.quickstart.local",
        "API_RTH_Gateway.env", 
        "KEY_API.env.py"
    ]
    

    for env_file in env_files:

        if os.path.exists(env_file):

            load_dotenv(env_file, override=False)

            print(f"Loaded config file: {env_file}")

            

except ImportError:

    print("WARNING: python-dotenv not installed; using system environment variables only")



diskless_env = os.getenv("RTH_DISKLESS", "false").lower() in ("1", "true", "yes")



# Configurazione logging

log_dir = Path("logs")

handlers = [logging.StreamHandler()]

if not diskless_env:

    try:

        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "core.log"

        handlers = [

            logging.handlers.RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5),

            logging.StreamHandler()

        ]

    except Exception:

        # Fallback: solo console se il filesystem ? read-only

        handlers = [logging.StreamHandler()]



logging.basicConfig(

    level=logging.INFO,

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',

    handlers=handlers

)



logger = logging.getLogger(__name__)

class Settings(BaseSettings):

    # App

    PROJECT_NAME: str = "RTH SYNAPSEâ„¢ v4.0.1"

    DEBUG: bool = True

    API_V1_STR: str = "/api/v1"

    API_TITLE: str = "RTH SYNAPSEâ„¢ API"

    API_DESCRIPTION: str = "Sistema di Valutazione Psicometrica Multi-Dimensionale"

    API_VERSION: str = "4.0.1"

    

    # Database

    DATABASE_URL: str = "sqlite:///./rth_auth.db"

    DATABASE_POOL_SIZE: int = 5

    DATABASE_MAX_OVERFLOW: int = 10

    DATABASE_ECHO: bool = False

    

    # Security

    SECRET_KEY: str = "your-secret-key-change-me"

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 11520  # 8 giorni in minuti

    PASSWORD_MIN_LENGTH: int = 8

    PASSWORD_MAX_LENGTH: int = 100

    

    # AI Services - Legge dalle variabili d'ambiente

    GOOGLE_AI_API_KEY: Optional[str] = None

    GEMINI_API_KEY: Optional[str] = None

    OPENAI_API_KEY: Optional[str] = None

    

    # Frontend

    FRONTEND_URL: str = "http://localhost:3006"

    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3006", "http://localhost:8000", "http://localhost:3000"]

    FRONTEND_API_KEY: str = "core_rth_ui_dev"

    

    # Email

    SMTP_TLS: bool = True

    SMTP_PORT: int = 587

    SMTP_HOST: Optional[str] = None

    SMTP_USER: Optional[str] = None

    SMTP_PASSWORD: Optional[str] = None

    EMAILS_FROM_EMAIL: str = "noreply@example.com"

    EMAILS_FROM_NAME: str = "RTH SYNAPSEâ„¢"

    

    # Logging

    LOG_LEVEL: str = "INFO"

    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    LOG_FILE: str = "logs/core.log"

    

    # Cache

    REDIS_URL: Optional[str] = None

    CACHE_TTL: int = 3600  # 1 ora

    

    # Rate Limiting

    RATE_LIMIT_PER_MINUTE: int = 60

    

    # Runtime
    RTH_DISKLESS: bool = False
    FEEDBACK_ANALYSIS_INTERVAL_SECONDS: int = 300
    RTH_PROPOSAL_TTL_HOURS: int = 24
    RTH_REQUIRE_OWNER_APPROVAL: bool = True
    RTH_PROCESS_EXEC_ALLOWED_ACTIONS: List[str] = [
        "app_launch",
        "workspace_command",
        "rth_lm_action",
        "shadow_ccs_action",
    ]
    RTH_SHADOW_ROOT: Optional[str] = None

    # RTH Specific
    RTH_VERSION: str = "4.0.1"
    RTH_ENVIRONMENT: str = "development"
    RTH_AI_ENABLED: bool = True
    RTH_PDF_ENABLED: bool = True

    RTH_NARRATIVE_AI_ENABLED: bool = True



    @validator('GEMINI_API_KEY', pre=True, always=True)

    def set_gemini_api_key(cls, v, values):

        """Usa GOOGLE_AI_API_KEY se GEMINI_API_KEY non Ã¨ impostata"""

        if not v and values.get('GOOGLE_AI_API_KEY'):

            return values['GOOGLE_AI_API_KEY']

        return v



    

    @validator('DEBUG', pre=True)
    def parse_debug_bool(cls, v):
        if isinstance(v, bool) or v is None:
            return v
        s = str(v).strip().lower()
        if s in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if s in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return True

    @validator('BACKEND_CORS_ORIGINS', pre=True)

    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @validator('RTH_PROCESS_EXEC_ALLOWED_ACTIONS', pre=True)
    def assemble_process_exec_allowed_actions(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


    def validate_settings(self):

        """Valida le impostazioni critiche"""

        if not self.SECRET_KEY or self.SECRET_KEY == "your-secret-key-change-me":

            print("WARNING: SECRET_KEY not configured correctly")

        

        if not self.GOOGLE_AI_API_KEY and not self.GEMINI_API_KEY:

            print("WARNING: No AI API key configured")

        else:

            print("AI API key configured")

        

        return True



    class Config:

        case_sensitive = True

        extra = "ignore"

        # Specifica i file .env da caricare

        env_file = [".env", ".env.rth.quickstart.local", "API_RTH_Gateway.env", "KEY_API.env.py"]
        env_file_encoding = 'utf-8'



# Istanza globale delle impostazioni

settings = Settings()



# Valida le impostazioni all'avvio

settings.validate_settings()



# Debug info

if settings.DEBUG:

    print(f"RTH SYNAPSE v{settings.RTH_VERSION} - Config loaded")

    print(f"API URL: {settings.API_V1_STR}")

    print(f"Frontend URL: {settings.FRONTEND_URL}")

    print(f"AI Enabled: {settings.RTH_AI_ENABLED}")

    if settings.GOOGLE_AI_API_KEY:

        print(f"Google AI API Key: {'*' * 20}{settings.GOOGLE_AI_API_KEY[-10:]}")






