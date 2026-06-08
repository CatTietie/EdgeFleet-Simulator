from dataclasses import dataclass, field
from .sensor_models import SensorModel, AnomalySensorModel


@dataclass
class VirtualDevice:
    device_id: str
    org_id: str
    group_id: str
    sensor: SensorModel = field(default_factory=SensorModel)
    seq: int = 0

    def read(self) -> dict:
        self.seq += 1
        metrics = self.sensor.tick()
        return {
            "device_id": self.device_id,
            "timestamp": None,  # filled at publish time
            "metrics": metrics,
            "seq": self.seq,
        }


def create_devices(
    count: int,
    org_id: str,
    group_id: str,
    anomaly_ratio: float = 0.1,
) -> list[VirtualDevice]:
    """Create a fleet of virtual devices. A fraction will produce anomalies."""
    devices = []
    anomaly_count = int(count * anomaly_ratio)

    for i in range(count):
        device_id = f"sensor-{i:05d}"
        if i < anomaly_count:
            sensor = AnomalySensorModel()
        else:
            sensor = SensorModel()
        devices.append(VirtualDevice(
            device_id=device_id,
            org_id=org_id,
            group_id=group_id,
            sensor=sensor,
        ))

    return devices
