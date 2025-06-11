# main.py - Complete AI Marketing Automation System with ALL APIs

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
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
from agents.content_agent import ContentType, Platform, ContentBrief, ContentStatus
from agents.social_media_agent import SocialPlatform, PostStatus
from agents.email_automation_agent import EmailType, TriggerType, CampaignStatus
from agents.analytics_agent import ReportType

from supabase import create_client, Client

load_dotenv()

app = FastAPI(title="AI Marketing Automation Suite", version="2.0.0")

# Configure CORS with specific origins
origins = [
    "https://aiboostcampaign.com",
    "https://www.aiboostcampaign.com",  # Include www version
    "https://main--agentic-ai-marketing.netlify.app",  # Add frontend URL
    "http://localhost:3000",            # For local React development
    "http://localhost:5173",            # For Vite development
    "http://localhost:5174",            # Alternative Vite port
]

# Add additional origins from environment variable if needed
additional_origins = os.getenv("CORS_ORIGINS", "")
if additional_origins:
    origins.extend([origin.strip() for origin in additional_origins.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

# Optional: Add logging middleware to debug CORS issues
@app.middleware("http")
async def log_requests(request, call_next):
    # Log requests in development mode
    if os.getenv("ENVIRONMENT") != "production":
        origin = request.headers.get("origin", "No origin")
        print(f"{request.method} {request.url.path} - Origin: {origin}")
    
    response = await call_next(request)
    return response

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

# =============================================================================
# PYDANTIC MODELS FOR ALL ENDPOINTS
# =============================================================================

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

class EmailCampaignRequest(BaseModel):
    campaign_name: str
    template_id: str
    audience_filter: Dict[str, Any]
    send_time: Optional[datetime] = None

class AutomationSequenceRequest(BaseModel):
    name: str
    trigger_type: str
    trigger_conditions: Dict[str, Any]
    sequence_brief: str

class ReportRequest(BaseModel):
    report_type: str
    period_start: datetime
    period_end: datetime

class CampaignRequest(BaseModel):
    name: str
    objective: str
    target_audience: Dict[str, Any]
    budget: float
    channels: List[str]

class LeadSearchRequest(BaseModel):
    criteria: Dict[str, Any]
    max_results: int = 100

# =============================================================================
# SYSTEM ENDPOINTS
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
        "cors_origins": origins,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.now().isoformat()
    }

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
                "total": len(content_agent.content_store),
                "published": len([c for c in content_agent.content_store.values() if c.status == ContentStatus.PUBLISHED])
            },
            "social_posts": {
                "total": len(social_agent.posts_store),
                "published": len([p for p in social_agent.posts_store.values() if p.status == PostStatus.PUBLISHED])
            },
            "email_contacts": {
                "total": len(email_agent.contacts_store),
                "subscribed": len([c for c in email_agent.contacts_store.values() if c.subscribed])
            },
            "reports": {
                "total": len(analytics_agent.reports_store)
            }
        }
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# CAMPAIGN MANAGEMENT AGENT ENDPOINTS
# =============================================================================

@app.post("/api/campaigns")
async def create_campaign(request: CampaignRequest):
    """Create new campaign"""
    try:
        campaign = await campaign_agent.create_campaign(
            name=request.name,
            objective=request.objective,
            target_audience=request.target_audience,
            budget=request.budget,
            channels=request.channels
        )
        
        return {
            "campaign_id": campaign.id,
            "name": campaign.name,
            "status": campaign.status.value,
            "budget": campaign.budget,
            "created_at": campaign.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns")
async def list_campaigns():
    """List all campaigns"""
    try:
        campaigns = list(campaign_agent.campaigns_store.values())
        
        return [
            {
                "id": campaign.id,
                "name": campaign.name,
                "objective": campaign.objective,
                "status": campaign.status.value,
                "budget": campaign.budget,
                "budget_used": campaign.budget_used,
                "created_at": campaign.created_at.isoformat()
            }
            for campaign in campaigns
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get specific campaign"""
    campaign = campaign_agent.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "objective": campaign.objective,
        "target_audience": campaign.target_audience,
        "budget": campaign.budget,
        "budget_used": campaign.budget_used,
        "status": campaign.status.value,
        "channels": campaign.channels,
        "metrics": campaign.metrics or {},
        "created_at": campaign.created_at.isoformat()
    }

@app.post("/api/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: str):
    """Launch campaign"""
    try:
        success = await campaign_agent.launch_campaign(campaign_id)
        return {"success": success, "campaign_id": campaign_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause campaign"""
    try:
        success = await campaign_agent.pause_campaign(campaign_id)
        return {"success": success, "campaign_id": campaign_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns/{campaign_id}/performance")
async def get_campaign_performance(campaign_id: str):
    """Get campaign performance metrics"""
    try:
        performance = await campaign_agent.get_campaign_performance(campaign_id)
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# LEAD GENERATION AGENT ENDPOINTS
# =============================================================================

@app.post("/api/leads/search")
async def create_lead_search(request: LeadSearchRequest):
    """Create lead search task"""
    try:
        task = await lead_agent.create_search_task(request.criteria, request.max_results)
        
        return {
            "task_id": task.id,
            "criteria": task.criteria,
            "status": task.status.value,
            "created_at": task.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/search")
async def list_search_tasks():
    """List search tasks"""
    try:
        tasks = list(lead_agent.search_tasks_store.values())
        
        return [
            {
                "id": task.id,
                "criteria": task.criteria,
                "status": task.status.value,
                "progress": task.progress,
                "results_count": task.results_count,
                "created_at": task.created_at.isoformat()
            }
            for task in tasks
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/search/{task_id}")
async def get_search_task(task_id: str):
    """Get search task status"""
    task = lead_agent.get_search_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Search task not found")
    
    return {
        "id": task.id,
        "criteria": task.criteria,
        "status": task.status.value,
        "progress": task.progress,
        "results_count": task.results_count,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }

@app.get("/api/leads")
async def list_leads():
    """List leads"""
    try:
        leads = list(lead_agent.leads_store.values())
        
        return [
            {
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "title": lead.title,
                "source": lead.source,
                "score": lead.score,
                "status": lead.status.value,
                "created_at": lead.created_at.isoformat()
            }
            for lead in leads
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: str):
    """Get specific lead"""
    lead = lead_agent.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "title": lead.title,
        "linkedin_url": lead.linkedin_url,
        "source": lead.source,
        "score": lead.score,
        "status": lead.status.value,
        "contact_info": lead.contact_info or {},
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat()
    }

@app.put("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, status: str):
    """Update lead status"""
    try:
        success = await lead_agent.update_lead_status(lead_id, status)
        return {"success": success, "lead_id": lead_id, "new_status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads/analytics/overview")
async def get_leads_analytics():
    """Get lead analytics overview"""
    try:
        analytics = await lead_agent.get_analytics_overview()
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# CONTENT CREATION AGENT ENDPOINTS
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
async def list_content(content_type: Optional[str] = None, platform: Optional[str] = None):
    """List generated content"""
    try:
        content_type_enum = ContentType(content_type) if content_type else None
        platform_enum = Platform(platform) if platform else None
        
        content_list = content_agent.list_content(
            content_type=content_type_enum,
            platform=platform_enum
        )
        
        return [
            {
                "id": content.id,
                "title": content.content.get("title", content.brief.title),
                "type": content.brief.content_type.value,
                "platform": content.brief.platform.value,
                "status": content.status.value,
                "seo_score": content.seo_score,
                "readability_score": content.readability_score,
                "engagement_prediction": content.engagement_prediction,
                "created_at": content.created_at.isoformat()
            }
            for content in content_list
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/content/{content_id}")
async def get_content(content_id: str):
    """Get specific content"""
    content = content_agent.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return {
        "id": content.id,
        "brief": {
            "title": content.brief.title,
            "content_type": content.brief.content_type.value,
            "target_audience": content.brief.target_audience,
            "platform": content.brief.platform.value,
            "tone": content.brief.tone
        },
        "content": content.content,
        "status": content.status.value,
        "seo_score": content.seo_score,
        "readability_score": content.readability_score,
        "engagement_prediction": content.engagement_prediction,
        "created_at": content.created_at.isoformat()
    }

@app.get("/api/content/analytics")
async def get_content_analytics():
    """Get content performance analytics"""
    try:
        analytics = await content_agent.get_content_analytics()
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# SOCIAL MEDIA AGENT ENDPOINTS
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
async def list_social_posts(platform: Optional[str] = None, status: Optional[str] = None):
    """List social media posts"""
    try:
        platform_enum = SocialPlatform(platform) if platform else None
        status_enum = PostStatus(status) if status else None
        
        posts = social_agent.list_posts(platform=platform_enum, status=status_enum)
        
        return [
            {
                "id": post.id,
                "platform": post.platform.value,
                "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                "scheduled_time": post.scheduled_time.isoformat(),
                "status": post.status.value,
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "engagement_metrics": post.engagement_metrics or {}
            }
            for post in posts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/social/posts/{post_id}/publish")
async def publish_social_post(post_id: str):
    """Manually publish a scheduled post"""
    try:
        success = await social_agent.publish_post(post_id)
        return {"success": success, "post_id": post_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/social/engagement")
async def get_social_engagement():
    """Monitor social media engagement"""
    try:
        engagement = await social_agent.monitor_engagement()
        
        return [
            {
                "id": item.id,
                "platform": item.platform.value,
                "type": item.type.value,
                "author": item.author,
                "content": item.content[:100] + "..." if len(item.content) > 100 else item.content,
                "sentiment": item.sentiment,
                "requires_response": item.requires_response,
                "responded": item.responded,
                "timestamp": item.timestamp.isoformat()
            }
            for item in engagement
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/social/analytics")
async def get_social_analytics(platform: Optional[str] = None, days: int = 30):
    """Get social media analytics"""
    try:
        platform_enum = SocialPlatform(platform) if platform else None
        analytics = await social_agent.get_social_analytics(platform=platform_enum, days=days)
        
        # Convert to serializable format
        analytics_dict = {}
        for platform_name, analytics_obj in analytics.items():
            analytics_dict[platform_name] = {
                "platform": analytics_obj.platform.value,
                "period": analytics_obj.period,
                "metrics": analytics_obj.metrics,
                "top_posts": analytics_obj.top_posts,
                "engagement_rate": analytics_obj.engagement_rate,
                "follower_growth": analytics_obj.follower_growth,
                "best_posting_times": analytics_obj.best_posting_times
            }
        
        return analytics_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# EMAIL AUTOMATION AGENT ENDPOINTS
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
            "variables": template.variables,
            "created_at": template.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/templates")
async def list_email_templates(email_type: Optional[str] = None):
    """List email templates"""
    try:
        email_type_enum = EmailType(email_type) if email_type else None
        templates = email_agent.list_templates(email_type=email_type_enum)
        
        return [
            {
                "id": template.id,
                "name": template.name,
                "email_type": template.email_type.value,
                "subject_line": template.subject_line,
                "variables": template.variables,
                "created_at": template.created_at.isoformat()
            }
            for template in templates
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/email/contacts")
async def add_email_contact(
    email: str,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
    tags: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None
):
    """Add new email contact"""
    try:
        contact = await email_agent.add_contact(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            tags=tags or [],
            custom_fields=custom_fields or {}
        )
        
        return {
            "contact_id": contact.id,
            "email": contact.email,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "company": contact.company,
            "tags": contact.tags,
            "subscribed": contact.subscribed,
            "created_at": contact.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/contacts")
async def list_email_contacts(subscribed_only: bool = True, limit: int = 100):
    """List email contacts"""
    try:
        contacts = email_agent.list_contacts(subscribed_only=subscribed_only, limit=limit)
        
        return [
            {
                "id": contact.id,
                "email": contact.email,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "company": contact.company,
                "tags": contact.tags,
                "subscribed": contact.subscribed,
                "created_at": contact.created_at.isoformat() if contact.created_at else None
            }
            for contact in contacts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/email/campaigns")
async def send_email_campaign(request: EmailCampaignRequest):
    """Send email campaign"""
    try:
        campaign = await email_agent.send_campaign(
            campaign_name=request.campaign_name,
            template_id=request.template_id,
            audience_filter=request.audience_filter,
            send_time=request.send_time
        )
        
        return {
            "campaign_id": campaign.id,
            "name": campaign.name,
            "email_type": campaign.email_type.value,
            "status": campaign.status.value,
            "metrics": campaign.metrics,
            "created_at": campaign.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/analytics")
async def get_email_analytics(campaign_id: Optional[str] = None):
    """Get email campaign analytics"""
    try:
        analytics = await email_agent.get_campaign_analytics(campaign_id=campaign_id)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# ANALYTICS AGENT ENDPOINTS
# =============================================================================

@app.post("/api/analytics/collect")
async def collect_all_metrics():
    """Collect metrics from all agents"""
    try:
        metrics = await analytics_agent.collect_all_metrics(
            campaign_agent=campaign_agent,
            lead_agent=lead_agent,
            content_agent=content_agent,
            social_agent=social_agent
        )
        
        # Convert MetricData objects to dict
        metrics_dict = {}
        for metric_name, metric_data in metrics.items():
            metrics_dict[metric_name] = {
                "metric_name": metric_data.metric_name,
                "value": metric_data.value,
                "previous_value": metric_data.previous_value,
                "change_percent": metric_data.change_percent,
                "timestamp": metric_data.timestamp.isoformat()
            }
        
        return metrics_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analytics/insights")
async def generate_insights():
    """Generate AI-powered insights"""
    try:
        # First collect current metrics
        metrics = await analytics_agent.collect_all_metrics(
            campaign_agent=campaign_agent,
            lead_agent=lead_agent,
            content_agent=content_agent,
            social_agent=social_agent
        )
        
        # Generate insights
        insights = await analytics_agent.generate_insights(metrics)
        
        return [
            {
                "id": insight.id,
                "level": insight.level.value,
                "title": insight.title,
                "description": insight.description,
                "metric_type": insight.metric_type.value,
                "impact_score": insight.impact_score,
                "recommendations": insight.recommendations,
                "timestamp": insight.timestamp.isoformat()
            }
            for insight in insights
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analytics/reports")
async def create_analytics_report(request: ReportRequest):
    """Create comprehensive analytics report"""
    try:
        # Collect metrics for the period
        metrics = await analytics_agent.collect_all_metrics(
            campaign_agent=campaign_agent,
            lead_agent=lead_agent,
            content_agent=content_agent,
            social_agent=social_agent
        )
        
        # Create report
        report = await analytics_agent.create_report(
            report_type=ReportType(request.report_type),
            period_start=request.period_start,
            period_end=request.period_end,
            metrics=metrics
        )
        
        return {
            "report_id": report.id,
            "title": report.title,
            "report_type": report.report_type.value,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "executive_summary": report.executive_summary,
            "insights": [
                {
                    "title": insight.title,
                    "level": insight.level.value,
                    "impact_score": insight.impact_score,
                    "recommendations": insight.recommendations
                }
                for insight in report.insights
            ],
            "recommendations": report.recommendations,
            "created_at": report.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/dashboard")
async def get_analytics_dashboard():
    """Get comprehensive dashboard data"""
    try:
        dashboard_data = await analytics_agent.create_dashboard_data()
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# INTEGRATED WORKFLOWS
# =============================================================================

@app.post("/api/workflows/content-to-social")
async def content_to_social_workflow(content_id: str, platforms: List[str], schedule_times: List[datetime]):
    """Workflow: Convert content to social posts"""
    try:
        content = content_agent.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        results = []
        for i, (platform, schedule_time) in enumerate(zip(platforms, schedule_times)):
            # Extract main text for social post
            social_content = str(content.content)[:280]
            
            # Schedule social post
            post = await social_agent.schedule_post(
                platform=SocialPlatform(platform),
                content=social_content,
                scheduled_time=schedule_time,
                hashtags=content.brief.keywords
            )
            
            results.append({
                "platform": platform,
                "post_id": post.id,
                "scheduled_time": schedule_time.isoformat()
            })
        
        return {"workflow": "content_to_social", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/workflows/lead-to-email")
async def lead_to_email_workflow(lead_id: str):
    """Workflow: Add qualified lead to email automation"""
    try:
        lead = lead_agent.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Add lead as email contact
        contact = await email_agent.add_contact(
            email=lead.email,
            first_name=lead.name.split()[0] if lead.name else "",
            last_name=" ".join(lead.name.split()[1:]) if len(lead.name.split()) > 1 else "",
            company=lead.company,
            tags=["lead", f"score_{int(lead.score)}"],
            custom_fields={"lead_source": lead.source, "lead_score": lead.score}
        )
        
        return {
            "workflow": "lead_to_email",
            "contact_id": contact.id,
            "lead_score": lead.score,
            "email": contact.email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/workflows/full-campaign")
async def full_campaign_workflow(
    campaign_name: str,
    target_audience: str,
    content_topics: List[str],
    platforms: List[str],
    email_sequence: bool = True
):
    """Workflow: Create full integrated marketing campaign"""
    try:
        results = {}
        
        # 1. Create content pieces
        content_pieces = []
        for topic in content_topics:
            for platform in platforms:
                brief = ContentBrief(
                    title=f"{topic} - {platform.title()} Content",
                    content_type=ContentType.SOCIAL_POST if platform in ["linkedin", "twitter", "facebook"] else ContentType.BLOG_POST,
                    target_audience=target_audience,
                    key_messages=[topic],
                    platform=Platform(platform),
                    tone="professional",
                    length="medium"
                )
                
                content = await content_agent.create_content(brief)
                content_pieces.append(content)
        
        results["content_created"] = len(content_pieces)
        
        # 2. Schedule social posts
        social_posts = []
        base_time = datetime.now() + timedelta(hours=1)
        
        for i, content in enumerate(content_pieces):
            if content.brief.platform.value in platforms:
                schedule_time = base_time + timedelta(days=i, hours=i*2)
                
                social_content = str(content.content)[:280]
                post = await social_agent.schedule_post(
                    platform=SocialPlatform(content.brief.platform.value),
                    content=social_content,
                    scheduled_time=schedule_time
                )
                social_posts.append(post)
        
        results["social_posts_scheduled"] = len(social_posts)
        
        # 3. Create email sequence if requested
        if email_sequence:
            sequence = await email_agent.create_automation_sequence(
                name=f"{campaign_name} Email Sequence",
                trigger_type=TriggerType.EVENT_BASED,
                trigger_conditions={"event": "campaign_signup"},
                sequence_brief=f"Email nurture sequence for {campaign_name} targeting {target_audience}"
            )
            results["email_sequence_id"] = sequence.id
        
        results["campaign_name"] = campaign_name
        results["workflow"] = "full_campaign"
        results["status"] = "completed"
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# BULK OPERATIONS
# =============================================================================

@app.post("/api/bulk/content/create")
async def bulk_create_content(content_requests: List[ContentCreationRequest]):
    """Bulk create multiple content pieces"""
    try:
        results = []
        for request in content_requests:
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
            results.append({
                "content_id": content.id,
                "title": content.content.get("title", content.brief.title),
                "status": content.status.value
            })
        
        return {"created": len(results), "content_pieces": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bulk/social/schedule")
async def bulk_schedule_social_posts(social_requests: List[SocialPostRequest]):
    """Bulk schedule multiple social posts"""
    try:
        results = []
        for request in social_requests:
            post = await social_agent.schedule_post(
                platform=SocialPlatform(request.platform),
                content=request.content,
                scheduled_time=request.scheduled_time,
                media_urls=request.media_urls,
                hashtags=request.hashtags
            )
            
            results.append({
                "post_id": post.id,
                "platform": post.platform.value,
                "scheduled_time": post.scheduled_time.isoformat()
            })
        
        return {"scheduled": len(results), "posts": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bulk/email/contacts")
async def bulk_add_email_contacts(contacts: List[Dict[str, Any]]):
    """Bulk add email contacts"""
    try:
        results = []
        for contact_data in contacts:
            contact = await email_agent.add_contact(
                email=contact_data["email"],
                first_name=contact_data.get("first_name", ""),
                last_name=contact_data.get("last_name", ""),
                company=contact_data.get("company", ""),
                tags=contact_data.get("tags", []),
                custom_fields=contact_data.get("custom_fields", {})
            )
            
            results.append({
                "contact_id": contact.id,
                "email": contact.email
            })
        
        return {"added": len(results), "contacts": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# EXPORT ENDPOINTS
# =============================================================================

@app.get("/api/export/campaigns")
async def export_campaigns():
    """Export all campaigns data"""
    try:
        campaigns = list(campaign_agent.campaigns_store.values())
        
        export_data = [
            {
                "id": campaign.id,
                "name": campaign.name,
                "objective": campaign.objective,
                "status": campaign.status.value,
                "budget": campaign.budget,
                "budget_used": campaign.budget_used,
                "channels": campaign.channels,
                "metrics": campaign.metrics or {},
                "created_at": campaign.created_at.isoformat()
            }
            for campaign in campaigns
        ]
        
        return {"campaigns": export_data, "exported_at": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/leads")
async def export_leads():
    """Export all leads data"""
    try:
        leads = list(lead_agent.leads_store.values())
        
        export_data = [
            {
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "title": lead.title,
                "source": lead.source,
                "score": lead.score,
                "status": lead.status.value,
                "contact_info": lead.contact_info or {},
                "created_at": lead.created_at.isoformat()
            }
            for lead in leads
        ]
        
        return {"leads": export_data, "exported_at": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/content")
async def export_content():
    """Export all content data"""
    try:
        content_list = list(content_agent.content_store.values())
        
        export_data = [
            {
                "id": content.id,
                "brief": {
                    "title": content.brief.title,
                    "content_type": content.brief.content_type.value,
                    "target_audience": content.brief.target_audience,
                    "platform": content.brief.platform.value
                },
                "content": content.content,
                "status": content.status.value,
                "seo_score": content.seo_score,
                "readability_score": content.readability_score,
                "engagement_prediction": content.engagement_prediction,
                "created_at": content.created_at.isoformat()
            }
            for content in content_list
        ]
        
        return {"content": export_data, "exported_at": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.post("/api/admin/reset/{agent_name}")
async def reset_agent_data(agent_name: str):
    """Reset specific agent data (admin only)"""
    try:
        if agent_name == "campaign":
            campaign_agent.campaigns_store.clear()
        elif agent_name == "lead":
            lead_agent.leads_store.clear()
            lead_agent.search_tasks_store.clear()
        elif agent_name == "content":
            content_agent.content_store.clear()
        elif agent_name == "social":
            social_agent.posts_store.clear()
            social_agent.engagement_store.clear()
        elif agent_name == "email":
            email_agent.contacts_store.clear()
            email_agent.templates_store.clear()
            email_agent.campaigns_store.clear()
        elif agent_name == "analytics":
            analytics_agent.reports_store.clear()
            analytics_agent.insights_store.clear()
        else:
            raise HTTPException(status_code=400, detail="Invalid agent name")
        
        return {"message": f"{agent_name} agent data reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/system/info")
async def get_system_info():
    """Get detailed system information"""
    try:
        return {
            "version": "2.0.0",
            "agents": {
                "campaign_agent": {
                    "campaigns": len(campaign_agent.campaigns_store),
                    "status": "active"
                },
                "lead_agent": {
                    "leads": len(lead_agent.leads_store),
                    "search_tasks": len(lead_agent.search_tasks_store),
                    "status": "active"
                },
                "content_agent": {
                    "content_pieces": len(content_agent.content_store),
                    "status": "active"
                },
                "social_agent": {
                    "posts": len(social_agent.posts_store),
                    "engagement_items": len(social_agent.engagement_store),
                    "status": "active"
                },
                "email_agent": {
                    "contacts": len(email_agent.contacts_store),
                    "templates": len(email_agent.templates_store),
                    "campaigns": len(email_agent.campaigns_store),
                    "status": "active"
                },
                "analytics_agent": {
                    "reports": len(analytics_agent.reports_store),
                    "insights": len(analytics_agent.insights_store),
                    "status": "active"
                }
            },
            "environment": os.getenv("ENVIRONMENT", "development"),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# STARTUP EVENT
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("🚀 AI Marketing Automation Suite v2.0.0 starting up...")
    print("✅ Campaign Management Agent initialized")
    print("✅ Lead Generation Agent initialized")
    print("✅ Content Creation Agent initialized")
    print("✅ Social Media Agent initialized")
    print("✅ Analytics Agent initialized")
    print("✅ Email Automation Agent initialized")
    print("🎯 All 6 agents are ready!")
    print(f"📌 CORS enabled for: {', '.join(origins)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
