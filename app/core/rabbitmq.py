"""
RabbitMQ connection and message queue utilities
"""
import pika
import json
import logging
from typing import Dict, Any, Optional
from app.core.config import config

logger = logging.getLogger(__name__)

class RabbitMQConnection:
    _connection: Optional[pika.BlockingConnection] = None
    _channel: Optional[pika.channel.Channel] = None

    @classmethod
    def get_connection(cls) -> pika.BlockingConnection:
        """Get or create RabbitMQ connection"""
        if cls._connection is None or cls._connection.is_closed:
            try:
                # Get RabbitMQ URL from config or use defaults
                rabbitmq_host = config.get("rabbitmq_host", "localhost")
                rabbitmq_port = int(config.get("rabbitmq_port", "5672"))
                rabbitmq_user = config.get("rabbitmq_user", "guest")
                rabbitmq_password = config.get("rabbitmq_password", "guest")
                rabbitmq_vhost = config.get("rabbitmq_vhost", "/")

                credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
                parameters = pika.ConnectionParameters(
                    host=rabbitmq_host,
                    port=rabbitmq_port,
                    virtual_host=rabbitmq_vhost,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                cls._connection = pika.BlockingConnection(parameters)
                logger.info("RabbitMQ connection established")
            except Exception as e:
                logger.error("Failed to connect to RabbitMQ: %s", e)
                raise
        return cls._connection

    @classmethod
    def get_channel(cls) -> pika.channel.Channel:
        """Get or create RabbitMQ channel"""
        if cls._channel is None or cls._channel.is_closed:
            connection = cls.get_connection()
            cls._channel = connection.channel()
            # Declare exchanges and queues
            cls._setup_queues()
        return cls._channel

    @classmethod
    def _setup_queues(cls):
        """Setup RabbitMQ queues and exchanges"""
        channel = cls._channel
        if channel is None:
            return

        # Declare exchange for notifications
        channel.exchange_declare(
            exchange='notifications',
            exchange_type='direct',
            durable=True
        )

        # Declare queues
        queues = [
            'notifications.request',
            'notifications.milestone',
            'notifications.general'
        ]

        for queue_name in queues:
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(
                exchange='notifications',
                queue=queue_name,
                routing_key=queue_name.split('.')[-1]  # 'request', 'milestone', 'general'
            )

        logger.info("RabbitMQ queues and exchanges setup complete")

    @classmethod
    def publish_message(
        cls,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any],
        persistent: bool = True
    ):
        """Publish a message to RabbitMQ"""
        try:
            channel = cls.get_channel()
            properties = pika.BasicProperties(
                delivery_mode=2 if persistent else 1,  # 2 = persistent
                content_type='application/json'
            )
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=properties
            )
            logger.debug("Message published: exchange=%s routing_key=%s", exchange, routing_key)
        except Exception as e:
            logger.error("Failed to publish message to RabbitMQ: %s", e)
            raise

    @classmethod
    def close(cls):
        """Close RabbitMQ connection"""
        try:
            if cls._channel and not cls._channel.is_closed:
                cls._channel.close()
            if cls._connection and not cls._connection.is_closed:
                cls._connection.close()
            logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error("Error closing RabbitMQ connection: %s", e)

