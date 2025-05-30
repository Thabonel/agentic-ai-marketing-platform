from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import os
from supabase import create_client, Client
import json
from pydantic import BaseModel
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# FastAPI app
app = FastAPI(
    title="Wheels Wins AI Marketing Orchestrator",
    description="Multi-agent AI marketing automation system",
    version="1.0.0"
)

# CORS middleware for Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your Netlify domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth
security = HTTPBearer()

# Pydantic models
class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"

class AgentType(str, Enum):
    LEAD_GENERATOR = "lead_generator"
    CONTENT_CREATOR = "content_creator"
    CAMPAIGN_MANAGER = "campaign_manager"
    MARKET_RESEARCHER = "market_researcher"
    EMAIL_MARKETER = "email_marketer"
    SOCIAL_MEDIA = "social_media"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentConfig(BaseModel):
    name: str
    type: AgentType
    description: Optional[str] = None
    config: Dict[str, Any] = {}

class TaskRequest(BaseModel):
    agent_id: int
    task_type: str
    input_data: Dict[str, Any] = {}
    priority: int = 5

class AgentResponse(BaseModel):
    id: int
    name: str
    type: str
    status: str
    last_run_at: Optional[datetime]
    created_at: datetime

class TaskResponse(BaseModel):
    id: int
    agent_id: int
    task_type: str
    status: str
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

# Database helper functions
async def get_agent_by_id(agent_id: int) -> Dict:
    """Get agent by ID"""
    result = supabase.table("agents").select("*").eq("id", agent_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result.data[0]

async def update_agent_status(agent_id: int, status: AgentStatus, last_run_at: datetime = None):
    """Update agent status"""
    update_data = {"status": status.value, "updated_at": datetime.utcnow().isoformat()}
    if last_run_at:
        update_data["last_run_at"] = last_run_at.isoformat()
    
    supabase.table("agents").update(update_data).eq("id", agent_id).execute()

async def create_agent_log(agent_id: int, task_type: str, status: TaskStatus, 
                          input_data: Dict = None, output_data: Dict = None, 
                          error_message: str = None, execution_time_ms: int = None):
    """Create agent log entry"""
    log_data = {
        "agent_id": agent_id,
        "task_type": task_type,
        "status": status.value,
        "input_data": input_data or {},
        "output_data": output_data or {},
        "error_message": error_message,
        "execution_time_ms": execution_time_ms,
        "started_at": datetime.utcnow().isoformat()
    }
    
    if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        log_data["completed_at"] = datetime.utcnow().isoformat()
    
    result = supabase.table("agent_logs").insert(log_data).execute()
    return result.data[0] if result.data else None

# Agent Management Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Wheels Wins AI Marketing Orchestrator",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/agents", response_model=List[AgentResponse])
async def get_agents():
    """Get all agents"""
    try:
        result = supabase.table("agents").select("*").execute()
        return [AgentResponse(**agent) for agent in result.data]
    except Exception as e:
        logger.error(f"Error fetching agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch agents")

@app.post("/agents", response_model=AgentResponse)
async def create_agent(agent_config: AgentConfig):
    """Create a new agent"""
    try:
        agent_data = {
            "name": agent_config.name,
            "type": agent_config.type.value,
            "description": agent_config.description,
            "config": agent_config.config,
            "status": AgentStatus.IDLE.value
        }
        
        result = supabase.table("agents").insert(agent_data).execute()
        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to create agent")
        
        return AgentResponse(**result.data[0])
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create agent")

@app.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int):
    """Get agent by ID"""
    try:
        agent = await get_agent_by_id(agent_id)
        return AgentResponse(**agent)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch agent")

@app.put("/agents/{agent_id}/status")
async def update_agent_status_endpoint(agent_id: int, status: AgentStatus):
    """Update agent status"""
    try:
        await get_agent_by_id(agent_id)  # Check if agent exists
        await update_agent_status(agent_id, status)
        return {"message": f"Agent {agent_id} status updated to {status.value}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent {agent_id} status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update agent status")

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: int):
    """Delete an agent"""
    try:
        await get_agent_by_id(agent_id)  # Check if agent exists
        supabase.table("agents").delete().eq("id", agent_id).execute()
        return {"message": f"Agent {agent_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")

# Task Management Endpoints
@app.post("/tasks", response_model=TaskResponse)
async def create_task(task_request: TaskRequest):
    """Create a new task for an agent"""
    try:
        # Verify agent exists
        await get_agent_by_id(task_request.agent_id)
        
        # Create agent log entry
        log_entry = await create_agent_log(
            agent_id=task_request.agent_id,
            task_type=task_request.task_type,
            status=TaskStatus.PENDING,
            input_data=task_request.input_data
        )
        
        if not log_entry:
            raise HTTPException(status_code=400, detail="Failed to create task")
        
        return TaskResponse(**log_entry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create task")

@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(agent_id: Optional[int] = None, status: Optional[TaskStatus] = None, limit: int = 100):
    """Get tasks with optional filtering"""
    try:
        query = supabase.table("agent_logs").select("*")
        
        if agent_id:
            query = query.eq("agent_id", agent_id)
        if status:
            query = query.eq("status", status.value)
            
        query = query.order("started_at", desc=True).limit(limit)
        result = query.execute()
        
        return [TaskResponse(**task) for task in result.data]
    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    """Get task by ID"""
    try:
        result = supabase.table("agent_logs").select("*").eq("id", task_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch task")

@app.put("/tasks/{task_id}/status")
async def update_task_status(task_id: int, status: TaskStatus, 
                           output_data: Optional[Dict[str, Any]] = None,
                           error_message: Optional[str] = None,
                           execution_time_ms: Optional[int] = None):
    """Update task status and results"""
    try:
        # Check if task exists
        result = supabase.table("agent_logs").select("*").eq("id", task_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Prepare update data
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if output_data:
            update_data["output_data"] = output_data
        if error_message:
            update_data["error_message"] = error_message
        if execution_time_ms:
            update_data["execution_time_ms"] = execution_time_ms
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        # Update task
        supabase.table("agent_logs").update(update_data).eq("id", task_id).execute()
        
        return {"message": f"Task {task_id} status updated to {status.value}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update task")

# Analytics Endpoints
@app.get("/analytics/dashboard")
async def get_dashboard_analytics():
    """Get dashboard analytics"""
    try:
        # Get agent counts by status
        agents_result = supabase.table("agents").select("status").execute()
        agent_stats = {}
        for agent in agents_result.data:
            status = agent["status"]
            agent_stats[status] = agent_stats.get(status, 0) + 1
        
        # Get recent task statistics
        recent_tasks = supabase.table("agent_logs").select("status, started_at")\
            .gte("started_at", (datetime.utcnow() - timedelta(days=7)).isoformat())\
            .execute()
        
        task_stats = {}
        for task in recent_tasks.data:
            status = task["status"]
            task_stats[status] = task_stats.get(status, 0) + 1
        
        # Get active campaigns count
        campaigns_result = supabase.table("active_campaigns").select("id", count="exact").execute()
        active_campaigns = campaigns_result.count or 0
        
        # Get leads pipeline summary
        pipeline_result = supabase.table("lead_pipeline_summary").select("*").execute()
        
        return {
            "agents": {
                "total": len(agents_result.data),
                "by_status": agent_stats
            },
            "tasks": {
                "last_7_days": len(recent_tasks.data),
                "by_status": task_stats
            },
            "campaigns": {
                "active": active_campaigns
            },
            "pipeline": pipeline_result.data
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics")

# Agent Orchestration Background Task
async def agent_orchestrator():
    """Background task to manage agent lifecycle"""
    while True:
        try:
            logger.info("Running agent orchestration cycle...")
            
            # Get pending tasks
            pending_tasks = supabase.table("agent_logs")\
                .select("*, agents(*)")\
                .eq("status", TaskStatus.PENDING.value)\
                .order("started_at")\
                .limit(10)\
                .execute()
            
            for task in pending_tasks.data:
                agent_id = task["agent_id"]
                task_id = task["id"]
                
                try:
                    # Update task to running
                    supabase.table("agent_logs")\
                        .update({"status": TaskStatus.RUNNING.value})\
                        .eq("id", task_id)\
                        .execute()
                    
                    # Update agent status
                    await update_agent_status(agent_id, AgentStatus.RUNNING, datetime.utcnow())
                    
                    logger.info(f"Started task {task_id} for agent {agent_id}")
                    
                    # Here you would integrate with your actual agent execution logic
                    # For now, we'll simulate task processing
                    
                except Exception as e:
                    logger.error(f"Error processing task {task_id}: {str(e)}")
                    
                    # Update task to failed
                    supabase.table("agent_logs")\
                        .update({
                            "status": TaskStatus.FAILED.value,
                            "error_message": str(e),
                            "completed_at": datetime.utcnow().isoformat()
                        })\
                        .eq("id", task_id)\
                        .execute()
            
            # Sleep for 30 seconds before next cycle
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in orchestration cycle: {str(e)}")
            await asyncio.sleep(60)  # Wait longer on error

@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup"""
    logger.info("Starting Wheels Wins AI Marketing Orchestrator...")
    
    # Start orchestrator in background (for production, use a proper task queue)
    # asyncio.create_task(agent_orchestrator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
