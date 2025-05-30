# agents/content_agent.py

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class ContentType(Enum):
    BLOG_POST = "blog_post"
    EMAIL = "email"
    SOCIAL_POST = "social_post"
    AD_COPY = "ad_copy"
    VIDEO_SCRIPT = "video_script"
    LANDING_PAGE = "landing_page"
    NEWSLETTER = "newsletter"
    PRODUCT_DESCRIPTION = "product_description"

class ContentStatus(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Platform(Enum):
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    BLOG = "blog"
    EMAIL = "email"

@dataclass
class ContentBrief:
    title: str
    content_type: ContentType
    target_audience: str
    key_messages: List[str]
    platform: Platform
    tone: str = "professional"
    length: str = "medium"
    keywords: List[str] = None
    cta: str = None
    deadline: Optional[datetime] = None

@dataclass
class GeneratedContent:
    id: str
    brief: ContentBrief
    content: Dict[str, Any]
    status: ContentStatus
    created_at: datetime
    updated_at: datetime
    performance_metrics: Dict[str, float] = None
    seo_score: int = 0
    readability_score: int = 0
    engagement_prediction: float = 0.0

class ContentCreationAgent:
    def __init__(self, openai_api_key: str, supabase_client=None):
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.supabase = supabase_client
        self.content_store: Dict[str, GeneratedContent] = {}
        
    async def create_content(self, brief: ContentBrief) -> GeneratedContent:
        """Generate content based on brief using AI"""
        try:
            # Generate unique content ID
            content_id = f"content_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{brief.content_type.value}"
            
            # Generate content using AI
            content_data = await self._generate_content_with_ai(brief)
            
            # Create content object
            content = GeneratedContent(
                id=content_id,
                brief=brief,
                content=content_data,
                status=ContentStatus.DRAFT,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Analyze content quality
            await self._analyze_content_quality(content)
            
            # Store content
            self.content_store[content_id] = content
            
            # Save to database if available
            if self.supabase:
                await self._save_content_to_db(content)
            
            logger.info(f"Created content: {content_id}")
            return content
            
        except Exception as e:
            logger.error(f"Error creating content: {str(e)}")
            raise

    async def _generate_content_with_ai(self, brief: ContentBrief) -> Dict[str, Any]:
        """Generate content using OpenAI"""
        
        base_context = f"""
        Create {brief.content_type.value} content for {brief.platform.value} platform.
        Target Audience: {brief.target_audience}
        Tone: {brief.tone}
        Length: {brief.length}
        Key Messages: {', '.join(brief.key_messages)}
        """
        
        if brief.keywords:
            base_context += f"\nKeywords to include: {', '.join(brief.keywords)}"
        
        if brief.cta:
            base_context += f"\nCall to Action: {brief.cta}"
        
        prompt = f"""
        {base_context}
        
        Create engaging content with:
        1. Compelling headline/title
        2. Main content body
        3. Call-to-action
        4. Relevant hashtags or tags
        
        Format as JSON with keys: title, content, cta, tags
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert content creator. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content_json = response.choices[0].message.content
            return json.loads(content_json)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return {
                "title": brief.title,
                "content": "Content generation failed, please try again.",
                "cta": brief.cta or "Learn more",
                "tags": brief.keywords or []
            }

    async def _analyze_content_quality(self, content: GeneratedContent):
        """Analyze content quality"""
        try:
            content_text = str(content.content)
            keywords = content.brief.keywords or []
            
            # Simple quality scoring
            keyword_mentions = sum(content_text.lower().count(kw.lower()) for kw in keywords)
            content.seo_score = min(100, max(50, 70 + keyword_mentions * 5))
            
            word_count = len(content_text.split())
            if 300 <= word_count <= 800:
                content.readability_score = 85
            else:
                content.readability_score = 70
            
            content.engagement_prediction = 0.7  # Default prediction
            
        except Exception as e:
            logger.error(f"Error analyzing content quality: {str(e)}")
            content.seo_score = 70
            content.readability_score = 75
            content.engagement_prediction = 0.6

    async def _save_content_to_db(self, content: GeneratedContent):
        """Save content to database"""
        if not self.supabase:
            return
        
        try:
            content_data = {
                "id": content.id,
                "brief": asdict(content.brief),
                "content": content.content,
                "status": content.status.value,
                "seo_score": content.seo_score,
                "readability_score": content.readability_score,
                "engagement_prediction": content.engagement_prediction,
                "created_at": content.created_at.isoformat(),
                "updated_at": content.updated_at.isoformat()
            }
            
            # Convert enums to strings
            content_data["brief"]["content_type"] = content.brief.content_type.value
            content_data["brief"]["platform"] = content.brief.platform.value
            
            self.supabase.table('generated_content').upsert(content_data).execute()
            
        except Exception as e:
            logger.error(f"Error saving content to database: {str(e)}")

    def get_content(self, content_id: str) -> Optional[GeneratedContent]:
        """Get specific content by ID"""
        return self.content_store.get(content_id)

    def list_content(self, content_type: ContentType = None, platform: Platform = None) -> List[GeneratedContent]:
        """List content with optional filtering"""
        content_list = list(self.content_store.values())
        
        if content_type:
            content_list = [c for c in content_list if c.brief.content_type == content_type]
        
        if platform:
            content_list = [c for c in content_list if c.brief.platform == platform]
        
        content_list.sort(key=lambda x: x.created_at, reverse=True)
        return content_list

    async def get_content_analytics(self) -> Dict[str, Any]:
        """Get analytics for all generated content"""
        total_content = len(self.content_store)
        
        if total_content == 0:
            return {"message": "No content generated yet"}
        
        avg_seo = sum(c.seo_score for c in self.content_store.values()) / total_content
        avg_readability = sum(c.readability_score for c in self.content_store.values()) / total_content
        avg_engagement = sum(c.engagement_prediction for c in self.content_store.values()) / total_content
        
        return {
            "total_content": total_content,
            "average_scores": {
                "seo": round(avg_seo, 1),
                "readability": round(avg_readability, 1),
                "engagement_prediction": round(avg_engagement, 2)
            }
        }
