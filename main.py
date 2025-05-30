from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from campaign_agent import CampaignAgent, CampaignObjective, TargetAudience, Channel, CampaignStatus, Campaign
from lead_generation_agent import (
    LeadGenerationAgent, LeadCriteria, DataSource, LeadStatus, LeadQuality, Lead, SearchTask
)
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import io
from datetime import datetime
from supabase import create_client, Client
import asyncio

app = FastAPI(title="AI Marketing Campaign Manager", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

# Persistent Campaign Agent with Supabase integration
class PersistentCampaignAgent(CampaignAgent):
    def __init__(self, openai_api_key: str, integrations: Dict[str, str], supabase_client: Client):
        super().__init__(openai_api_key, integrations)
        self.supabase = supabase_client
        asyncio.create_task(self.load_campaigns())
    
    async def load_campaigns(self):
        """Load campaigns from Supabase on startup"""
        try:
            response = self.supabase.table('campaigns').select('*').execute()
            for row in response.data:
                campaign_data = json.loads(row['campaign_data'])
                # Reconstruct campaign object
                campaign = self._deserialize_campaign(campaign_data)
                self.campaigns[campaign.id] = campaign
            self.logger.info(f"Loaded {len(self.campaigns)} campaigns from database")
        except Exception as e:
            self.logger.error(f"Error loading campaigns: {str(e)}")
    
    async def save_campaign(self, campaign):
        """Save campaign to Supabase"""
        try:
            campaign_data = {
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status.value,
                'created_at': campaign.created_at.isoformat(),
                'updated_at': campaign.updated_at.isoformat(),
                'campaign_data': json.dumps(self._serialize_campaign(campaign), default=str)
            }
            
            # Upsert campaign
            self.supabase.table('campaigns').upsert(campaign_data).execute()
            self.logger.info(f"Saved campaign {campaign.id} to database")
            
        except Exception as e:
            self.logger.error(f"Error saving campaign: {str(e)}")
    
    def _serialize_campaign(self, campaign):
        """Convert campaign to serializable dict"""
        return {
            'id': campaign.id,
            'name': campaign.name,
            'objective': {
                'type': campaign.objective.type,
                'target_metric': campaign.objective.target_metric,
                'target_value': campaign.objective.target_value,
                'timeframe_days': campaign.objective.timeframe_days
            },
            'target_audience': {
                'demographics': campaign.target_audience.demographics,
                'interests': campaign.target_audience.interests,
                'behaviors': campaign.target_audience.behaviors,
                'company_size': campaign.target_audience.company_size,
                'industry': campaign.target_audience.industry,
                'job_titles': campaign.target_audience.job_titles
            },
            'channels': [c.value for c in campaign.channels],
            'budget': campaign.budget,
            'status': campaign.status.value,
            'start_date': campaign.start_date.isoformat(),
            'end_date': campaign.end_date.isoformat(),
            'content_calendar': campaign.content_calendar,
            'performance_metrics': campaign.performance_metrics,
            'created_at': campaign.created_at.isoformat(),
            'updated_at': campaign.updated_at.isoformat()
        }
    
    def _deserialize_campaign(self, data):
        """Convert dict back to campaign object"""
        
        objective = CampaignObjective(
            type=data['objective']['type'],
            target_metric=data['objective']['target_metric'],
            target_value=data['objective']['target_value'],
            timeframe_days=data['objective']['timeframe_days']
        )
        
        target_audience = TargetAudience(
            demographics=data['target_audience']['demographics'],
            interests=data['target_audience']['interests'],
            behaviors=data['target_audience']['behaviors'],
            company_size=data['target_audience'].get('company_size'),
            industry=data['target_audience'].get('industry'),
            job_titles=data['target_audience'].get('job_titles', [])
        )
        
        channels = [Channel(c) for c in data['channels']]
        
        return Campaign(
            id=data['id'],
            name=data['name'],
            objective=objective,
            target_audience=target_audience,
            channels=channels,
            budget=data['budget'],
            status=CampaignStatus(data['status']),
            start_date=datetime.fromisoformat(data['start_date']),
            end_date=datetime.fromisoformat(data['end_date']),
            content_calendar=data['content_calendar'],
            performance_metrics=data['performance_metrics'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )
    
    async def create_campaign(self, *args, **kwargs):
        """Override to add persistence"""
        campaign = await super().create_campaign(*args, **kwargs)
        await self.save_campaign(campaign)
        return campaign

# Initialize persistent campaign agent
campaign_agent = PersistentCampaignAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    integrations={
        'sendgrid_api_key': os.getenv("SENDGRID_API_KEY"),
        'linkedin_api_key': os.getenv("LINKEDIN_API_KEY"),
        'facebook_api_key': os.getenv("FACEBOOK_API_KEY"),
        'google_ads_api_key': os.getenv("GOOGLE_ADS_API_KEY"),
        'twitter_api_key': os.getenv("TWITTER_API_KEY"),
    },
    supabase_client=supabase
)

# Initialize Lead Generation Agent
lead_agent = LeadGenerationAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    integrations={
        'linkedin_api_key': os.getenv("LINKEDIN_API_KEY"),
        'google_search_api_key': os.getenv("GOOGLE_SEARCH_API_KEY"),
        'apollo_api_key': os.getenv("APOLLO_API_KEY"),
        'zoominfo_api_key': os.getenv("ZOOMINFO_API_KEY"),
    }
)

# Authentication dependency
async def get_current_user(authorization: str = Header(None)):
    """Validate user token from Supabase"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        # Extract token from "Bearer <token>"
        token = authorization.split(" ")[1] if authorization.startswith("Bearer ") else authorization
        
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return user.user
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# Campaign Pydantic Models
class CreateCampaignRequest(BaseModel):
    name: str
    objective_type: str  # lead_generation, brand_awareness, conversion, retention
    target_metric: str  # leads, impressions, clicks, revenue
    target_value: float
    timeframe_days: int
    channels: List[str]  # email, linkedin, facebook, google_ads, twitter
    budget_total: float
    budget_daily: float
    target_audience: Dict[str, Any]
    duration_days: int

class CampaignResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    start_date: str
    end_date: str
    budget: Dict[str, float]
    channels: List[str]
    performance_metrics: Dict[str, Any]

# Lead Generation Pydantic Models
class CreateSearchTaskRequest(BaseModel):
    name: str
    criteria: Dict[str, Any]
    sources: List[str]  # "website_scraping", "linkedin", "google_search", "database"
    max_leads: int = 100

class UpdateLeadStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class ExportLeadsRequest(BaseModel):
    format: str = "csv"  # "csv" or "json"
    quality_filter: Optional[str] = None
    status_filter: Optional[str] = None
    source_filter: Optional[str] = None
    include_fields: Optional[List[str]] = None
    limit: int = 1000

class LeadResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    job_title: Optional[str]
    company: str
    company_website: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    quality_score: float
    quality_level: str
    status: str
    source: str
    created_at: str
    last_contacted: Optional[str]
    contact_attempts: int

class SearchTaskResponse(BaseModel):
    id: str
    name: str
    status: str
    progress: float
    leads_found: int
    created_at: str
    completed_at: Optional[str]
    results_summary: Dict[str, Any]

# CAMPAIGN ENDPOINTS

@app.post("/api/campaigns", response_model=CampaignResponse)
async def create_campaign(request: CreateCampaignRequest, user=Depends(get_current_user)):
    """Create a new marketing campaign"""
    
    try:
        # Create objective
        objective = CampaignObjective(
            type=request.objective_type,
            target_metric=request.target_metric,
            target_value=request.target_value,
            timeframe_days=request.timeframe_days
        )
        
        # Create target audience
        target_audience = TargetAudience(
            demographics=request.target_audience.get('demographics', {}),
            interests=request.target_audience.get('interests', []),
            behaviors=request.target_audience.get('behaviors', []),
            company_size=request.target_audience.get('company_size'),
            industry=request.target_audience.get('industry'),
            job_titles=request.target_audience.get('job_titles', [])
        )
        
        # Convert channel strings to enums
        channels = [Channel(channel) for channel in request.channels]
        
        # Create budget dict
        budget = {
            'total': request.budget_total,
            'daily': request.budget_daily,
            'per_channel': request.budget_total / len(channels)
        }
        
        # Create campaign
        campaign = await campaign_agent.create_campaign(
            name=request.name,
            objective=objective,
            target_audience=target_audience,
            budget=budget,
            channels=channels,
            duration_days=request.duration_days
        )
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status.value,
            created_at=campaign.created_at.isoformat(),
            start_date=campaign.start_date.isoformat(),
            end_date=campaign.end_date.isoformat(),
            budget=campaign.budget,
            channels=[c.value for c in campaign.channels],
            performance_metrics=campaign.performance_metrics
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create campaign: {str(e)}")

@app.get("/api/campaigns", response_model=List[CampaignResponse])
async def get_campaigns(user=Depends(get_current_user)):
    """Get all campaigns"""
    
    campaigns = []
    for campaign in campaign_agent.campaigns.values():
        campaigns.append(CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status.value,
            created_at=campaign.created_at.isoformat(),
            start_date=campaign.start_date.isoformat(),
            end_date=campaign.end_date.isoformat(),
            budget=campaign.budget,
            channels=[c.value for c in campaign.channels],
            performance_metrics=campaign.performance_metrics
        ))
    
    return campaigns

@app.get("/api/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str, user=Depends(get_current_user)):
    """Get specific campaign details"""
    
    campaign = campaign_agent.campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status.value,
        created_at=campaign.created_at.isoformat(),
        start_date=campaign.start_date.isoformat(),
        end_date=campaign.end_date.isoformat(),
        budget=campaign.budget,
        channels=[c.value for c in campaign.channels],
        performance_metrics=campaign.performance_metrics
    )

@app.post("/api/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: str, user=Depends(get_current_user)):
    """Launch a campaign"""
    
    try:
        success = await campaign_agent.launch_campaign(campaign_id)
        if success:
            # Save updated campaign status
            campaign = campaign_agent.campaigns[campaign_id]
            await campaign_agent.save_campaign(campaign)
            
            return {"message": f"Campaign {campaign_id} launched successfully", "status": "active"}
        else:
            raise HTTPException(status_code=400, detail="Failed to launch campaign")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error launching campaign: {str(e)}")

@app.post("/api/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, user=Depends(get_current_user)):
    """Pause a campaign"""
    
    campaign = campaign_agent.campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = CampaignStatus.PAUSED
    campaign.updated_at = datetime.now()
    
    # Save to database
    await campaign_agent.save_campaign(campaign)
    
    return {"message": f"Campaign {campaign_id} paused", "status": "paused"}

@app.get("/api/campaigns/{campaign_id}/performance")
async def get_campaign_performance(campaign_id: str, user=Depends(get_current_user)):
    """Get real-time campaign performance data"""
    
    campaign = campaign_agent.campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get fresh performance data
    if campaign.status == CampaignStatus.ACTIVE:
        performance_data = await campaign_agent._collect_performance_data(campaign)
        campaign.performance_metrics = performance_data
        await campaign_agent.save_campaign(campaign)
    
    return {
        "campaign_id": campaign_id,
        "performance": campaign.performance_metrics,
        "last_updated": campaign.updated_at.isoformat()
    }

@app.get("/api/campaigns/{campaign_id}/content-calendar")
async def get_content_calendar(campaign_id: str, user=Depends(get_current_user)):
    """Get campaign content calendar"""
    
    campaign = campaign_agent.campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "campaign_id": campaign_id,
        "content_calendar": campaign.content_calendar
    }

@app.get("/api/campaigns/{campaign_id}/report")
async def get_campaign_report(campaign_id: str, user=Depends(get_current_user)):
    """Generate comprehensive campaign report with AI insights"""
    
    try:
        report = await campaign_agent.get_campaign_report(campaign_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@app.post("/api/campaigns/{campaign_id}/optimize")
async def optimize_campaign(campaign_id: str, user=Depends(get_current_user)):
    """Get AI optimization recommendations for campaign"""
    
    campaign = campaign_agent.campaigns.get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    try:
        # Get current performance data
        performance_data = await campaign_agent._collect_performance_data(campaign)
        
        # Generate optimizations
        optimizations = await campaign_agent._generate_optimizations(campaign, performance_data)
        
        return {
            "campaign_id": campaign_id,
            "current_performance": performance_data,
            "optimizations": optimizations,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating optimizations: {str(e)}")

@app.get("/api/dashboard/campaign-overview")
async def get_campaign_overview(user=Depends(get_current_user)):
    """Get high-level campaign overview for dashboard"""
    
    total_campaigns = len(campaign_agent.campaigns)
    active_campaigns = len([c for c in campaign_agent.campaigns.values() if c.status == CampaignStatus.ACTIVE])
    total_spend = sum([c.performance_metrics.get('overall', {}).get('total_spend', 0) for c in campaign_agent.campaigns.values()])
    total_conversions = sum([c.performance_metrics.get('overall', {}).get('total_conversions', 0) for c in campaign_agent.campaigns.values()])
    
    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_spend": total_spend,
        "total_conversions": total_conversions,
        "avg_conversion_rate": (total_conversions / max(total_spend, 1)) * 100 if total_spend > 0 else 0,
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status.value,
                "performance": c.performance_metrics.get('overall', {})
            }
            for c in campaign_agent.campaigns.values()
        ]
    }

# LEAD GENERATION ENDPOINTS

@app.post("/api/leads/search", response_model=SearchTaskResponse)
async def create_lead_search_task(request: CreateSearchTaskRequest, user=Depends(get_current_user)):
    """Create a new lead generation search task"""
    
    try:
        # Convert request to LeadCriteria
        criteria = LeadCriteria(
            industry=request.criteria.get('industry'),
            company_size=request.criteria.get('company_size'),
            location=request.criteria.get('location'),
            job_titles=request.criteria.get('job_titles', []),
            keywords=request.criteria.get('keywords', []),
            technologies=request.criteria.get('technologies', []),
            revenue_range=request.criteria.get('revenue_range'),
            exclude_competitors=request.criteria.get('exclude_competitors', True)
        )
        
        # Convert source strings to enums
        sources = [DataSource(source) for source in request.sources]
        
        # Create search task
        task = await lead_agent.create_search_task(
            name=request.name,
            criteria=criteria,
            sources=sources,
            max_leads=request.max_leads
        )
        
        return SearchTaskResponse(
            id=task.id,
            name=task.name,
            status=task.status,
            progress=task.progress,
            leads_found=task.leads_found,
            created_at=task.created_at.isoformat(),
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            results_summary=task.results_summary
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create search task: {str(e)}")

@app.get("/api/leads/search/{task_id}", response_model=SearchTaskResponse)
async def get_search_task(task_id: str, user=Depends(get_current_user)):
    """Get search task status and results"""
    
    task = lead_agent.search_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Search task not found")
    
    return SearchTaskResponse(
        id=task.id,
        name=task.name,
        status=task.status,
        progress=task.progress,
        leads_found=task.leads_found,
        created_at=task.created_at.isoformat(),
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        results_summary=task.results_summary
    )

@app.get("/api/leads/search", response_model=List[SearchTaskResponse])
async def get_search_tasks(user=Depends(get_current_user)):
    """Get all search tasks"""
    
    tasks = []
    for task in lead_agent.search_tasks.values():
        tasks.append(SearchTaskResponse(
            id=task.id,
            name=task.name,
            status=task.status,
            progress=task.progress,
            leads_found=task.leads_found,
            created_at=task.created_at.isoformat(),
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            results_summary=task.results_summary
        ))
    
    # Sort by creation date (newest first)
    tasks.sort(key=lambda x: x.created_at, reverse=True)
    return tasks

@app.get("/api/leads", response_model=List[LeadResponse])
async def get_leads(
    quality: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100,
    user=Depends(get_current_user)
):
    """Get leads with optional filtering"""
    
    try:
        # Convert string filters to enums
        quality_filter = LeadQuality(quality) if quality else None
        status_filter = LeadStatus(status) if status else None
        source_filter = DataSource(source) if source else None
        
        leads = await lead_agent.get_leads(
            quality_filter=quality_filter,
            status_filter=status_filter,
            source_filter=source_filter,
            limit=limit
        )
        
        return [
            LeadResponse(
                id=lead.id,
                first_name=lead.first_name,
                last_name=lead.last_name,
                email=lead.email,
                phone=lead.phone,
                job_title=lead.job_title,
                company=lead.company,
                company_website=lead.company_website,
                industry=lead.industry,
                location=lead.location,
                quality_score=lead.quality_score,
                quality_level=lead.quality_level.value,
                status=lead.status.value,
                source=lead.source.value,
                created_at=lead.created_at.isoformat(),
                last_contacted=lead.last_contacted.isoformat() if lead.last_contacted else None,
                contact_attempts=lead.contact_attempts
            )
            for lead in leads
        ]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving leads: {str(e)}")

@app.get("/api/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: str, user=Depends(get_current_user)):
    """Get specific lead details"""
    
    lead = lead_agent.leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return LeadResponse(
        id=lead.id,
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=lead.email,
        phone=lead.phone,
        job_title=lead.job_title,
        company=lead.company,
        company_website=lead.company_website,
        industry=lead.industry,
        location=lead.location,
        quality_score=lead.quality_score,
        quality_level=lead.quality_level.value,
        status=lead.status.value,
        source=lead.source.value,
        created_at=lead.created_at.isoformat(),
        last_contacted=lead.last_contacted.isoformat() if lead.last_contacted else None,
        contact_attempts=lead.contact_attempts
    )

@app.put("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: str, request: UpdateLeadStatusRequest, user=Depends(get_current_user)):
    """Update lead status"""
    
    try:
        status = LeadStatus(request.status)
        await lead_agent.update_lead_status(lead_id, status, request.notes)
        
        return {"message": f"Lead {lead_id} status updated to {request.status}"}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating lead status: {str(e)}")

@app.post("/api/leads/export")
async def export_leads(request: ExportLeadsRequest, user=Depends(get_current_user)):
    """Export leads to CSV or JSON"""
    
    try:
        # Convert string filters to enums
        quality_filter = LeadQuality(request.quality_filter) if request.quality_filter else None
        status_filter = LeadStatus(request.status_filter) if request.status_filter else None
        source_filter = DataSource(request.source_filter) if request.source_filter else None
        
        # Get filtered leads
        leads = await lead_agent.get_leads(
            quality_filter=quality_filter,
            status_filter=status_filter,
            source_filter=source_filter,
            limit=request.limit
        )
        
        if not leads:
            raise HTTPException(status_code=404, detail="No leads found matching criteria")
        
        # Export leads
        exported_data = await lead_agent.export_leads(
            leads=leads,
            format=request.format,
            include_fields=request.include_fields
        )
        
        # Return as downloadable file
        if request.format.lower() == "csv":
            media_type = "text/csv"
            filename = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            media_type = "application/json"
            filename = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        return StreamingResponse(
            io.StringIO(exported_data),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export failed: {str(e)}")

@app.get("/api/leads/analytics/overview")
async def get_leads_analytics(user=Depends(get_current_user)):
    """Get lead generation analytics overview"""
    
    all_leads = list(lead_agent.leads.values())
    
    if not all_leads:
        return {
            "total_leads": 0,
            "quality_distribution": {},
            "status_distribution": {},
            "source_distribution": {},
            "average_score": 0,
            "recent_activity": []
        }
    
    # Calculate analytics
    total_leads = len(all_leads)
    
    quality_distribution = {}
    for quality in LeadQuality:
        count = len([l for l in all_leads if l.quality_level == quality])
        quality_distribution[quality.value] = count
    
    status_distribution = {}
    for status in LeadStatus:
        count = len([l for l in all_leads if l.status == status])
        status_distribution[status.value] = count
    
    source_distribution = {}
    for source in DataSource:
        count = len([l for l in all_leads if l.source == source])
        source_distribution[source.value] = count
    
    average_score = sum(l.quality_score for l in all_leads) / total_leads
    
    # Recent activity (last 10 leads)
    recent_leads = sorted(all_leads, key=lambda x: x.created_at, reverse=True)[:10]
    recent_activity = [
        {
            "lead_id": l.id,
            "name": f"{l.first_name} {l.last_name}",
            "company": l.company,
            "quality_score": l.quality_score,
            "created_at": l.created_at.isoformat()
        }
        for l in recent_leads
    ]
    
    return {
        "total_leads": total_leads,
        "quality_distribution": quality_distribution,
        "status_distribution": status_distribution,
        "source_distribution": source_distribution,
        "average_score": round(average_score, 2),
        "recent_activity": recent_activity
    }

@app.post("/api/leads/{lead_id}/mark-qualified")
async def mark_lead_qualified(lead_id: str, user=Depends(get_current_user)):
    """Quick action: Mark lead as qualified"""
    
    try:
        await lead_agent.update_lead_status(lead_id, LeadStatus.QUALIFIED, "Marked as qualified")
        return {"message": f"Lead {lead_id} marked as qualified"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/leads/{lead_id}/mark-contacted")
async def mark_lead_contacted(lead_id: str, user=Depends(get_current_user)):
    """Quick action: Mark lead as contacted"""
    
    try:
        await lead_agent.update_lead_status(lead_id, LeadStatus.CONTACTED, "Outreach initiated")
        return {"message": f"Lead {lead_id} marked as contacted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/leads/bulk-update")
async def bulk_update_leads(
    lead_ids: List[str],
    status: str,
    notes: Optional[str] = None,
    user=Depends(get_current_user)
):
    """Bulk update multiple leads"""
    
    try:
        status_enum = LeadStatus(status)
        
        updated_count = 0
        for lead_id in lead_ids:
            try:
                await lead_agent.update_lead_status(lead_id, status_enum, notes)
                updated_count += 1
            except ValueError:
                continue  # Skip invalid lead IDs
        
        return {
            "message": f"Updated {updated_count} out of {len(lead_ids)} leads",
            "updated_count": updated_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bulk update failed: {str(e)}")

@app.post("/api/leads/{lead_id}/enrich")
async def enrich_lead(lead_id: str, user=Depends(get_current_user)):
    """Enrich lead data with additional information"""
    
    lead = lead_agent.leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    try:
        # This would integrate with data enrichment services
        # For now, return mock enriched data
        
        enriched_data = {
            "social_profiles": {
                "linkedin": f"https://linkedin.com/in/{lead.first_name.lower()}-{lead.last_name.lower()}",
                "twitter": f"@{lead.first_name.lower()}{lead.last_name.lower()}"
            },
            "company_info": {
                "employee_count": "51-200",
                "annual_revenue": "$10M-$50M",
                "technologies": ["Salesforce", "HubSpot", "Slack"]
            },
            "contact_info": {
                "direct_phone": "+1-555-0123",
                "mobile_phone": "+1-555-0124"
            },
            "enrichment_score": 85
        }
        
        # Update lead with enriched data
        lead.custom_fields.update(enriched_data)
        lead.updated_at = datetime.now()
        
        return {
            "message": f"Lead {lead_id} enriched successfully",
            "enriched_data": enriched_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")

# LEGACY AGENT ENDPOINTS (keep your existing ones)

class Agent(BaseModel):
    id: str
    name: str
    description: str
    status: str

@app.get("/api/agents")
async def get_agents():
    """Get all agents"""
    return [
        Agent(id="1", name="Lead Generator", description="Finds potential customers", status="active"),
        Agent(id="2", name="Content Creator", description="Creates marketing content", status="active"),
        Agent(id="3", name="Social Media Manager", description="Manages social media posts", status="inactive")
    ]

@app.post("/api/agents")
async def create_agent(agent: Agent):
    """Create a new agent"""
    return {"message": "Agent created successfully", "agent": agent}

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent"""
    return Agent(id=agent_id, name="Sample Agent", description="Sample description", status="active")

@app.post("/api/agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, message: dict):
    """Chat with an agent"""
    return {
        "response": f"Agent {agent_id} received: {message.get('message', '')}",
        "timestamp": datetime.now().isoformat()
    }

# Health check endpoint (no auth required)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
