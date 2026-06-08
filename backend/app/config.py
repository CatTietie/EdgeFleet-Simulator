from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    # MQTT
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str = "platform-service"
    mqtt_password: str = "platform123"

    # InfluxDB
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "edgefleet-dev-token"
    influxdb_org: str = "edgefleet"
    influxdb_bucket: str = "telemetry"
    influx_batch_size: int = 500
    influx_flush_interval_ms: int = 1000

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://edgefleet:edgefleet123@localhost:5432/edgefleet"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # JWT
    jwt_secret: str = "dev-secret-change-in-production!!"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
