# agents/__init__.py

from .base_agent import BaseAgent
from .marketing_agents import (
    CampaignManagementAgent,
    LeadGenerationAgent
)

# Import new agents
from .content_agent import ContentCreationAgent
from .social_media_agent import SocialMediaAgent
from .analytics_agent import AnalyticsAgent
from .email_automation_agent import EmailAutomationAgent

__all__ = [
    'BaseAgent',
    'CampaignManagementAgent', 
    'LeadGenerationAgent',
    'ContentCreationAgent',
    'SocialMediaAgent',
    'AnalyticsAgent',
    'EmailAutomationAgent'
]

__version__ = '2.0.0'
