#!/usr/bin/env python3
"""
Multi-Channel Notifier

Sends notifications to stakeholders via Slack, email, PagerDuty, etc.

Key Features:
- Multi-channel support
- Severity-based routing
- Template-based messages
- Delivery tracking
"""

from typing import List, Optional, Dict
from enum import Enum
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"


class NotificationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Notifier:
    """Sends notifications to multiple channels"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.enabled_channels = config.get('enabled_channels', [])
    
    def send(
        self,
        title: str,
        message: str,
        severity: NotificationSeverity,
        channels: Optional[List[NotificationChannel]] = None,
        metadata: Optional[Dict] = None
    ):
        """Send notification to specified channels"""
        target_channels = channels or self._get_default_channels(severity)
        
        for channel in target_channels:
            if channel.value in self.enabled_channels:
                self._send_to_channel(channel, title, message, severity, metadata)
    
    def _get_default_channels(self, severity: NotificationSeverity) -> List[NotificationChannel]:
        """Get default channels based on severity"""
        if severity == NotificationSeverity.CRITICAL:
            return [NotificationChannel.SLACK, NotificationChannel.PAGERDUTY]
        elif severity == NotificationSeverity.ERROR:
            return [NotificationChannel.SLACK, NotificationChannel.EMAIL]
        else:
            return [NotificationChannel.SLACK]
    
    def _send_to_channel(
        self,
        channel: NotificationChannel,
        title: str,
        message: str,
        severity: NotificationSeverity,
        metadata: Optional[Dict]
    ):
        """Send to specific channel"""
        logger.info(f"[{channel.value}] {severity.value.upper()}: {title}")
        logger.info(f"  Message: {message}")
        # In production: Call actual Slack/Email/PagerDuty APIs


if __name__ == '__main__':
    notifier = Notifier({'enabled_channels': ['slack', 'email']})
    notifier.send(
        title='Lock Acquired',
        message='Lock acquired for payment-service by orchestrator-1',
        severity=NotificationSeverity.INFO
    )
