from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulatorConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIM_")

    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str = "org-demo"
    mqtt_password: str = "demo123"
    org_id: str = "org-demo"
    group_id: str = "default"
    report_interval: float = 5.0
    device_count: int = 100
