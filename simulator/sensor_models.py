import random
import math
from dataclasses import dataclass, field


@dataclass
class SensorModel:
    """Simulates a sensor with random walk behavior within realistic bounds."""
    temperature: float = field(default_factory=lambda: random.uniform(20.0, 30.0))
    humidity: float = field(default_factory=lambda: random.uniform(40.0, 60.0))
    _temp_drift: float = field(default=0.0, init=False)
    _hum_drift: float = field(default=0.0, init=False)

    TEMP_MIN: float = -10.0
    TEMP_MAX: float = 100.0
    HUM_MIN: float = 5.0
    HUM_MAX: float = 95.0

    def tick(self) -> dict[str, float]:
        """Advance one time step and return current metrics."""
        self._temp_drift += random.gauss(0, 0.3)
        self._temp_drift = max(-2.0, min(2.0, self._temp_drift))
        self.temperature += self._temp_drift + random.gauss(0, 0.5)
        self.temperature = max(self.TEMP_MIN, min(self.TEMP_MAX, self.temperature))

        self._hum_drift += random.gauss(0, 0.2)
        self._hum_drift = max(-1.5, min(1.5, self._hum_drift))
        self.humidity += self._hum_drift + random.gauss(0, 0.3)
        self.humidity = max(self.HUM_MIN, min(self.HUM_MAX, self.humidity))

        return {
            "temperature": round(self.temperature, 2),
            "humidity": round(self.humidity, 2),
        }


@dataclass
class AnomalySensorModel(SensorModel):
    """Sensor that periodically generates anomalous readings (for testing alarms)."""
    anomaly_probability: float = 0.05
    anomaly_temp_range: tuple = (82.0, 95.0)
    anomaly_hum_range: tuple = (8.0, 18.0)

    def tick(self) -> dict[str, float]:
        if random.random() < self.anomaly_probability:
            return {
                "temperature": round(random.uniform(*self.anomaly_temp_range), 2),
                "humidity": round(random.uniform(*self.anomaly_hum_range), 2),
            }
        return super().tick()
