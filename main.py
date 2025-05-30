# main.py - Complete AI Marketing Automation System with 6 Agents

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
from dotenv import load_dotenv

# Import all agents
from agents import (
    CampaignManagementAgent,
    LeadGenerationAgent,
    ContentCreationAgent,
    SocialMediaAgent,
    AnalyticsAgent,
    EmailAutomationAgent
)

# Import enums for the new agents
from agents.content_agent import ContentType, Platform, ContentBrief
from agents.social_media_agent import SocialPlatform
from agents.email_automation_agent import EmailType, TriggerType

from supabase import create_client, Client

load_dotenv()

app = FastAPI(title="AI Marketing Automation Suite", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

# Initialize all agents
campaign_agent = CampaignManagementAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    supabase_client=supabase
)

lead_agent = LeadGenerationAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    supabase_client=supabase
)

content_agent = ContentCreationAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    supabase_client=supabase
)

social_agent = SocialMediaAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    platform_credentials={
        "linkedin_token": os.getenv("LINKEDIN_ACCESS_TOKEN"),
        "linkedin_person_id": os.getenv("LINKEDIN_PERSON_ID"),
        "twitter_bearer_token": os.getenv("TWITTER_BEARER_TOKEN"),
        "facebook_access_token": os.getenv("FACEBOOK_ACCESS_TOKEN"),
        "facebook_page_id": os.getenv("FACEBOOK_PAGE_ID"),
        "instagram_access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN"),
        "instagram_user_id": os.getenv("INSTAGRAM_USER_ID")
    },
    supabase_client=supabase
)

analytics_agent = AnalyticsAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    supabase_client=supabase
)

email_agent = EmailAutomationAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    email_service_credentials={
        "email_service": os.getenv("EMAIL_SERVICE", "sendgrid"),
        "sendgrid_api_key": os.getenv("SENDGRID_API_KEY"),
        "from_email": os.getenv("FROM_EMAIL"),
        "from_name": os.getenv("FROM_NAME")
    },
    supabase_client=supabase
)

# Pydantic models
class ContentCreationRequest(BaseModel):
    title: str
    content_type: str
    target_audience: str
    key_messages: List[str]
    platform: str
    tone: str = "professional"
    length: str = "medium"
    keywords: Optional[List[str]] = None
    cta: Optional[str] = None

class SocialPostRequest(BaseModel):
    platform: str
    content: str
    scheduled_time: datetime
    media_urls: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None

class EmailTemplateRequest(BaseModel):
    name: str
    email_type: str
    content_brief: str
    target_audience: str = "general"

# =============================================================================
# EXISTING ENDPOINTS (keep your current campaign and lead endpoints)
# =============================================================================

@app.get("/")
async def read_root():
    return {"message": "AI Marketing Automation Suite", "version": "2.0.0", "agents": 6}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "agents": {
            "campaign_agent": "active",
            "lead_agent": "active", 
            "content_agent": "active",
            "social_agent": "active",
            "analytics_agent": "active",
            "email_agent": "active"
        },
        "timestamp": datetime.now().isoformat()
    }

# =============================================================================
# NEW CONTENT CREATION AGENT ENDPOINTS
# =============================================================================

@app.post("/api/content/create")
async def create_content(request: ContentCreationRequest):
    """Create AI-generated content"""
    try:
        brief = ContentBrief(
            title=request.title,
            content_type=ContentType(request.content_type),
            target_audience=request.target_audience,
            key_messages=request.key_messages,
            platform=Platform(request.platform),
            tone=request.tone,
            length=request.length,
            keywords=request.keywords,
            cta=request.cta
        )
        
        content = await content_agent.create_content(brief)
        
        return {
            "content_id": content.id,
            "content": content.content,
            "seo_score": content.seo_score,
            "readability_score": content.readability_score,
            "engagement_prediction": content.engagement_prediction,
            "status": content.status.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/content")
async def list_content():
    """List generated content"""
    try:
        content_list = content_agent.list_content()
        
        return [
            {
                "id": content.id,
                "title": content.content.get("title", content.brief.title),
                "type": content.brief.content_type.value,
                "platform": content.brief.platform.value,
                "status": content.status.value,
                "seo_score": content.seo_score,
                "created_at": content.created_at.isoformat()
            }
            for content in content_list
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/content/analytics")
async def get_content_analytics():
    """Get content analytics"""
    try:
        analytics = await content_agent.get_content_analytics()
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# NEW SOCIAL MEDIA AGENT ENDPOINTS
# =============================================================================

@app.post("/api/social/schedule")
async def schedule_social_post(request: SocialPostRequest):
    """Schedule a social media post"""
    try:
        post = await social_agent.schedule_post(
            platform=SocialPlatform(request.platform),
            content=request.content,
            scheduled_time=request.scheduled_time,
            media_urls=request.media_urls,
            hashtags=request.hashtags
        )
        
        return {
            "post_id": post.id,
            "platform": post.platform.value,
            "content": post.content,
            "scheduled_time": post.scheduled_time.isoformat(),
            "status": post.status.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/social/posts")
async def list_social_posts():
    """List social media posts"""
    try:
        posts = social_agent.list_posts()
        
        return [
            {
                "id": post.id,
                "platform": post.platform.value,
                "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                "scheduled_time": post.scheduled_time.isoformat(),
                "status": post.status.value,
                "engagement_metrics": post.engagement_metrics or {}
            }
            for post in posts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# NEW EMAIL AUTOMATION AGENT ENDPOINTS
# =============================================================================

@app.post("/api/email/templates")
async def create_email_template(request: EmailTemplateRequest):
    """Create AI-generated email template"""
    try:
        template = await email_agent.create_email_template(
            name=request.name,
            email_type=EmailType(request.email_type),
            content_brief=request.content_brief,
            target_audience=request.target_audience
        )
        
        return {
            "template_id": template.id,
            "name": template.name,
            "email_type": template.email_type.value,
            "subject_line": template.subject_line,
            "created_at": template.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/email/contacts")
async def add_email_contact(
    email: str,
    first_name: str = "",
    last_name: str = "",
    company: str = ""
):
    """Add new email contact"""
    try:
        contact = await email_agent.add_contact(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company
        )
        
        return {
            "contact_id": contact.id,
            "email": contact.email,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "created_at": contact.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# NEW ANALYTICS AGENT ENDPOINTS
# =============================================================================

@app.get("/api/analytics/dashboard")
async def get_analytics_dashboard():
    """Get comprehensive dashboard data"""
    try:
        # Collect metrics from all agents
        metrics = await analytics_agent.collect_all_metrics(
            campaign_agent=campaign_agent,
            lead_agent=lead_agent,
            content_agent=content_agent,
            social_agent=social_agent
        )
        
        dashboard_data = await analytics_agent.create_dashboard_data()
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/stats")
async def get_system_stats():
    """Get system-wide statistics"""
    try:
        stats = {
            "campaigns": {
                "total": len(campaign_agent.campaigns_store),
                "active": len([c for c in campaign_agent.campaigns_store.values() if c.status.value == "active"])
            },
            "leads": {
                "total": len(lead_agent.leads_store),
                "qualified": len([l for l in lead_agent.leads_store.values() if l.status.value == "qualified"])
            },
            "content": {
                "total": len(content_agent.content_store)
            },
            "social_posts": {
                "total": len(social_agent.posts_store)
            },
            "email_contacts": {
                "total": len(email_agent.contacts_store)
            }
        }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
