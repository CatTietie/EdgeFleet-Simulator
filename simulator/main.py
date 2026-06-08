import asyncio
import argparse
import logging
import signal
import sys

from .config import SimulatorConfig
from .device_factory import create_devices
from .mqtt_publisher import MqttPublisher


def parse_args():
    parser = argparse.ArgumentParser(description="EdgeFleet Device Simulator")
    parser.add_argument("--devices", type=int, default=100, help="Number of devices to simulate")
    parser.add_argument("--interval", type=float, default=5.0, help="Report interval in seconds")
    parser.add_argument("--org", type=str, default="org-demo", help="Organization ID")
    parser.add_argument("--group", type=str, default="default", help="Group ID")
    parser.add_argument("--anomaly-ratio", type=float, default=0.1, help="Fraction of anomaly-producing devices")
    parser.add_argument("--host", type=str, default=None, help="MQTT broker host")
    parser.add_argument("--port", type=int, default=None, help="MQTT broker port")
    return parser.parse_args()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("simulator")

    args = parse_args()
    config = SimulatorConfig()

    broker_host = args.host or config.mqtt_broker_host
    broker_port = args.port or config.mqtt_broker_port

    logger.info(f"Creating {args.devices} virtual devices for org={args.org}, group={args.group}")
    devices = create_devices(
        count=args.devices,
        org_id=args.org,
        group_id=args.group,
        anomaly_ratio=args.anomaly_ratio,
    )

    publisher = MqttPublisher(
        broker_host=broker_host,
        broker_port=broker_port,
        username=args.org,
        password="demo123",
        interval=args.interval,
    )

    loop = asyncio.get_event_loop()

    def shutdown():
        logger.info("Shutting down simulator...")
        publisher.stop()

    loop.add_signal_handler(signal.SIGINT, shutdown)
    loop.add_signal_handler(signal.SIGTERM, shutdown)

    try:
        await publisher.publish_loop(devices)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Simulator stopped")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
