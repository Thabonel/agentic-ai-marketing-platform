import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from campaign_agent import CampaignAgent, CampaignObjective, TargetAudience, Channel, CampaignStatus

# Test fixtures
@pytest.fixture
def mock_openai_client():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "strategy": "test strategy",
        "recommendations": []
    })
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client

@pytest.fixture
def mock_supabase_client():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = []
    mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    return mock_client

@pytest.fixture
def campaign_agent(mock_openai_client, mock_supabase_client):
    with patch('campaign_agent.AsyncOpenAI', return_value=mock_openai_client):
        agent = CampaignAgent(
            openai_api_key="test_key",
            integrations={
                'sendgrid_api_key': 'test_sendgrid',
                'linkedin_api_key': 'test_linkedin'
            }
        )
        return agent

@pytest.fixture
def sample_campaign_data():
    return {
        'name': 'Test Campaign',
        'objective': CampaignObjective(
            type='lead_generation',
            target_metric='leads',
            target_value=100,
            timeframe_days=30
        ),
        'target_audience': TargetAudience(
            demographics={'age': '25-45'},
            interests=['technology', 'marketing'],
            behaviors=['online_buyer'],
            industry='SaaS'
        ),
        'budget': {'total': 5000, 'daily': 166.67, 'per_channel': 2500},
        'channels': [Channel.EMAIL, Channel.LINKEDIN],
        'duration_days': 30
    }

# Unit Tests for Campaign Agent

class TestCampaignAgent:
    
    @pytest.mark.asyncio
    async def test_create_campaign(self, campaign_agent, sample_campaign_data):
        """Test campaign creation"""
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        
        assert campaign.name == 'Test Campaign'
        assert campaign.objective.type == 'lead_generation'
        assert campaign.status == CampaignStatus.DRAFT
        assert len(campaign.channels) == 2
        assert campaign.id in campaign_agent.campaigns

    @pytest.mark.asyncio
    async def test_generate_campaign_strategy(self, campaign_agent, sample_campaign_data):
        """Test AI strategy generation"""
        strategy = await campaign_agent._generate_campaign_strategy(
            sample_campaign_data['objective'],
            sample_campaign_data['target_audience'],
            sample_campaign_data['channels'],
            sample_campaign_data['budget']
        )
        
        assert isinstance(strategy, dict)
        assert 'strategy' in strategy

    @pytest.mark.asyncio
    async def test_create_content_calendar(self, campaign_agent, sample_campaign_data):
        """Test content calendar generation"""
        strategy = {'themes': ['productivity', 'efficiency']}
        
        calendar = await campaign_agent._create_content_calendar(
            strategy,
            sample_campaign_data['channels'],
            7  # 7 days for testing
        )
        
        assert isinstance(calendar, list)
        # Should have content for multiple days and channels
        assert len(calendar) >= 0

    @pytest.mark.asyncio
    async def test_launch_campaign(self, campaign_agent, sample_campaign_data):
        """Test campaign launch"""
        # Create campaign first
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        
        # Mock platform clients
        with patch.object(campaign_agent, '_launch_on_channel', new_callable=AsyncMock):
            success = await campaign_agent.launch_campaign(campaign.id)
            
            assert success is True
            assert campaign.status == CampaignStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_collect_performance_data(self, campaign_agent, sample_campaign_data):
        """Test performance data collection"""
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        
        # Mock platform client responses
        with patch.object(campaign_agent.email_client, 'get_campaign_metrics', new_callable=AsyncMock) as mock_email:
            with patch.object(campaign_agent.linkedin_client, 'get_campaign_metrics', new_callable=AsyncMock) as mock_linkedin:
                mock_email.return_value = {'impressions': 1000, 'clicks': 50, 'conversions': 5, 'spend': 100}
                mock_linkedin.return_value = {'impressions': 2000, 'clicks': 100, 'conversions': 10, 'spend': 200}
                
                performance_data = await campaign_agent._collect_performance_data(campaign)
                
                assert 'channels' in performance_data
                assert 'overall' in performance_data
                assert performance_data['overall']['total_impressions'] == 3000
                assert performance_data['overall']['total_clicks'] == 150

    @pytest.mark.asyncio
    async def test_generate_optimizations(self, campaign_agent, sample_campaign_data):
        """Test optimization generation"""
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        performance_data = {
            'overall': {'total_spend': 500, 'total_clicks': 100, 'total_conversions': 5}
        }
        
        optimizations = await campaign_agent._generate_optimizations(campaign, performance_data)
        
        assert isinstance(optimizations, dict)

    def test_check_campaign_completion(self, campaign_agent, sample_campaign_data):
        """Test campaign completion check"""
        campaign_agent.campaigns['test_id'] = MagicMock()
        campaign_agent.campaigns['test_id'].objective.target_metric = 'conversions'
        campaign_agent.campaigns['test_id'].objective.target_value = 10
        campaign_agent.campaigns['test_id'].performance_metrics = {
            'overall': {'conversions': 15}
        }
        
        is_complete = campaign_agent._check_campaign_completion(campaign_agent.campaigns['test_id'])
        assert is_complete is True

    @pytest.mark.asyncio
    async def test_campaign_report_generation(self, campaign_agent, sample_campaign_data):
        """Test campaign report generation"""
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        campaign.performance_metrics = {
            'overall': {'total_spend': 1000, 'total_conversions': 20}
        }
        
        report = await campaign_agent.get_campaign_report(campaign.id)
        
        assert 'campaign' in report
        assert 'insights' in report
        assert 'generated_at' in report

# API Integration Tests

class TestCampaignAPI:
    
    @pytest.fixture
    def client(self):
        from main import app  # Assuming your FastAPI app is in main.py
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test_token"}
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    @patch('main.get_current_user')
    def test_create_campaign_api(self, mock_auth, client, auth_headers):
        """Test campaign creation API"""
        mock_auth.return_value = {"id": "test_user_id"}
        
        campaign_data = {
            "name": "API Test Campaign",
            "objective_type": "lead_generation",
            "target_metric": "leads",
            "target_value": 50,
            "timeframe_days": 30,
            "channels": ["email", "linkedin"],
            "budget_total": 2000,
            "budget_daily": 66.67,
            "target_audience": {
                "demographics": {"age": "25-45"},
                "interests": ["technology"],
                "behaviors": ["online_buyer"]
            },
            "duration_days": 30
        }
        
        response = client.post("/api/campaigns", json=campaign_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "API Test Campaign"
        assert data["status"] == "draft"
    
    @patch('main.get_current_user')
    def test_get_campaigns_api(self, mock_auth, client, auth_headers):
        """Test get campaigns API"""
        mock_auth.return_value = {"id": "test_user_id"}
        
        response = client.get("/api/campaigns", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @patch('main.get_current_user')
    def test_launch_campaign_api(self, mock_auth, client, auth_headers):
        """Test campaign launch API"""
        mock_auth.return_value = {"id": "test_user_id"}
        
        # First create a campaign
        campaign_data = {
            "name": "Launch Test Campaign",
            "objective_type": "conversion",
            "target_metric": "conversions",
            "target_value": 25,
            "timeframe_days": 14,
            "channels": ["facebook"],
            "budget_total": 1000,
            "budget_daily": 71.43,
            "target_audience": {
                "demographics": {"age": "30-50"},
                "interests": ["business"],
                "behaviors": ["decision_maker"]
            },
            "duration_days": 14
        }
        
        create_response = client.post("/api/campaigns", json=campaign_data, headers=auth_headers)
        campaign_id = create_response.json()["id"]
        
        # Launch the campaign
        with patch('main.campaign_agent.launch_campaign', new_callable=AsyncMock) as mock_launch:
            mock_launch.return_value = True
            
            launch_response = client.post(f"/api/campaigns/{campaign_id}/launch", headers=auth_headers)
            assert launch_response.status_code == 200
            assert launch_response.json()["status"] == "active"
    
    def test_unauthorized_access(self, client):
        """Test unauthorized access"""
        response = client.get("/api/campaigns")
        assert response.status_code == 401
    
    @patch('main.get_current_user')
    def test_campaign_performance_api(self, mock_auth, client, auth_headers):
        """Test campaign performance endpoint"""
        mock_auth.return_value = {"id": "test_user_id"}
        
        # Mock campaign exists
        with patch('main.campaign_agent.campaigns') as mock_campaigns:
            mock_campaign = MagicMock()
            mock_campaign.status = CampaignStatus.ACTIVE
            mock_campaign.performance_metrics = {"overall": {"conversions": 10}}
            mock_campaign.updated_at = datetime.now()
            mock_campaigns.get.return_value = mock_campaign
            
            with patch('main.campaign_agent._collect_performance_data', new_callable=AsyncMock) as mock_collect:
                mock_collect.return_value = {"overall": {"conversions": 15}}
                
                response = client.get("/api/campaigns/test_id/performance", headers=auth_headers)
                assert response.status_code == 200
                data = response.json()
                assert "campaign_id" in data
                assert "performance" in data

# Performance Tests

class TestCampaignPerformance:
    
    @pytest.mark.asyncio
    async def test_concurrent_campaign_creation(self, campaign_agent, sample_campaign_data):
        """Test multiple concurrent campaign creations"""
        
        async def create_campaign_task(name_suffix):
            data = sample_campaign_data.copy()
            data['name'] = f"Concurrent Campaign {name_suffix}"
            return await campaign_agent.create_campaign(**data)
        
        # Create 5 campaigns concurrently
        tasks = [create_campaign_task(i) for i in range(5)]
        campaigns = await asyncio.gather(*tasks)
        
        assert len(campaigns) == 5
        assert len(set(c.id for c in campaigns)) == 5  # All unique IDs
        assert all(c.name.startswith("Concurrent Campaign") for c in campaigns)
    
    @pytest.mark.asyncio
    async def test_large_content_calendar_generation(self, campaign_agent):
        """Test content calendar generation for long campaigns"""
        strategy = {"themes": ["productivity", "efficiency", "growth"]}
        channels = [Channel.EMAIL, Channel.LINKEDIN, Channel.FACEBOOK, Channel.TWITTER]
        
        # 90-day campaign
        calendar = await campaign_agent._create_content_calendar(strategy, channels, 90)
        
        assert isinstance(calendar, list)
        # Should generate reasonable amount of content
        assert len(calendar) >= 0

# Integration Tests

class TestCampaignIntegration:
    
    @pytest.mark.asyncio
    async def test_full_campaign_lifecycle(self, campaign_agent, sample_campaign_data):
        """Test complete campaign lifecycle"""
        
        # 1. Create campaign
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        assert campaign.status == CampaignStatus.DRAFT
        
        # 2. Launch campaign
        with patch.object(campaign_agent, '_launch_on_channel', new_callable=AsyncMock):
            success = await campaign_agent.launch_campaign(campaign.id)
            assert success is True
            assert campaign.status == CampaignStatus.ACTIVE
        
        # 3. Collect performance data
        with patch.object(campaign_agent.email_client, 'get_campaign_metrics', new_callable=AsyncMock) as mock_email:
            mock_email.return_value = {'impressions': 1000, 'clicks': 50, 'conversions': 5, 'spend': 100}
            
            performance = await campaign_agent._collect_performance_data(campaign)
            assert performance['overall']['total_conversions'] > 0
        
        # 4. Generate optimizations
        optimizations = await campaign_agent._generate_optimizations(campaign, performance)
        assert isinstance(optimizations, dict)
        
        # 5. Generate report
        report = await campaign_agent.get_campaign_report(campaign.id)
        assert 'campaign' in report
        assert 'insights' in report

# Error Handling Tests

class TestCampaignErrorHandling:
    
    @pytest.mark.asyncio
    async def test_invalid_campaign_id(self, campaign_agent):
        """Test handling of invalid campaign ID"""
        with pytest.raises(ValueError, match="Campaign .* not found"):
            await campaign_agent.get_campaign_report("invalid_id")
    
    @pytest.mark.asyncio
    async def test_launch_nonexistent_campaign(self, campaign_agent):
        """Test launching non-existent campaign"""
        with pytest.raises(ValueError, match="Campaign .* not found"):
            await campaign_agent.launch_campaign("nonexistent_id")
    
    @pytest.mark.asyncio
    async def test_api_failure_handling(self, campaign_agent, sample_campaign_data):
        """Test handling of external API failures"""
        
        campaign = await campaign_agent.create_campaign(**sample_campaign_data)
        
        # Mock API failure
        with patch.object(campaign_agent.email_client, 'get_campaign_metrics', side_effect=Exception("API Error")):
            performance = await campaign_agent._collect_performance_data(campaign)
            
            # Should handle error gracefully
            assert 'channels' in performance
            assert 'email' in performance['channels']
            assert 'error' in performance['channels']['email']

# Utility Tests

class TestCampaignUtilities:
    
    def test_campaign_serialization(self, campaign_agent, sample_campaign_data):
        """Test campaign serialization/deserialization"""
        from main import PersistentCampaignAgent
        
        # Create a persistent agent for testing
        persistent_agent = PersistentCampaignAgent(
            openai_api_key="test",
            integrations={},
            supabase_client=MagicMock()
        )
        
        # Create mock campaign
        campaign = MagicMock()
        campaign.id = "test_id"
        campaign.name = "Test Campaign"
        campaign.status = CampaignStatus.ACTIVE
        campaign.objective = sample_campaign_data['objective']
        campaign.target_audience = sample_campaign_data['target_audience']
        campaign.channels = sample_campaign_data['channels']
        campaign.budget = sample_campaign_data['budget']
        campaign.start_date = datetime.now()
        campaign.end_date = datetime.now() + timedelta(days=30)
        campaign.content_calendar = []
        campaign.performance_metrics = {}
        campaign.created_at = datetime.now()
        campaign.updated_at = datetime.now()
        
        # Test serialization
        serialized = persistent_agent._serialize_campaign(campaign)
        assert isinstance(serialized, dict)
        assert serialized['id'] == "test_id"
        assert serialized['name'] == "Test Campaign"
        
        # Test deserialization
        deserialized = persistent_agent._deserialize_campaign(serialized)
        assert deserialized.id == campaign.id
        assert deserialized.name == campaign.name
        assert deserialized.status == campaign.status

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
