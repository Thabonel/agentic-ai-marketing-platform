from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from campaign_agent import CampaignAgent, CampaignObjective, TargetAudience, Channel, CampaignStatus, Campaign
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
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

# Pydantic Models
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

# Campaign Endpoints

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

# Dashboard Analytics Endpoints

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

# Legacy Agent Endpoints (keep your existing ones)

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
