"""Canonical Dramatiq broker for every TiBan background actor."""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.core.config import REDIS_URL


broker = RedisBroker(url=REDIS_URL)
dramatiq.set_broker(broker)
