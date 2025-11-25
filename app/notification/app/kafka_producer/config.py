import asyncio
from aiokafka import AIOKafkaProducer
from app.notification.app.config import get_settings


def create_producer() -> AIOKafkaProducer:
    loop = asyncio.get_event_loop()
    kafka_instance = f"{get_settings().KAFKA_HOST}:{get_settings().KAFKA_PORT}"

    return AIOKafkaProducer(
        loop=loop,
        bootstrap_servers=kafka_instance,
    )


kafka_producer_config = create_producer()

