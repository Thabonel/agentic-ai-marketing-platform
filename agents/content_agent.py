import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
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
    content: Dict[str, Any]  # Contains title, body, meta, etc.
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
        """Generate content using OpenAI based on content type"""
        
        # Base prompt setup
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
        
        # Content type specific prompts
        prompts = {
            ContentType.BLOG_POST: f"""
            {base_context}
            
            Create a comprehensive blog post with:
            1. Engaging headline
            2. Meta description (150-160 chars)
            3. Introduction paragraph
            4. Main content with subheadings
            5. Conclusion with CTA
            6. Suggested tags
            
            Format as JSON with keys: title, meta_description, introduction, sections, conclusion, tags
            """,
            
            ContentType.EMAIL: f"""
            {base_context}
            
            Create an email campaign with:
            1. Subject line (compelling, under 50 chars)
            2. Preview text
            3. Email body (HTML-friendly)
            4. Call-to-action button text
            
            Format as JSON with keys: subject, preview, body, cta_button
            """,
            
            ContentType.SOCIAL_POST: f"""
            {base_context}
            
            Create social media post optimized for {brief.platform.value}:
            1. Main post text (platform-appropriate length)
            2. Hashtags (relevant and trending)
            3. Image suggestion/description
            4. Best posting time recommendation
            
            Format as JSON with keys: text, hashtags, image_suggestion, best_time
            """,
            
            ContentType.AD_COPY: f"""
            {base_context}
            
            Create advertising copy with:
            1. Headline (attention-grabbing)
            2. Description (persuasive)
            3. Call-to-action
            4. Multiple variations (A/B testing)
            
            Format as JSON with keys: headline, description, cta, variations
            """,
            
            ContentType.VIDEO_SCRIPT: f"""
            {base_context}
            
            Create video script with:
            1. Hook (first 5 seconds)
            2. Main content structure
            3. Visual cues and transitions
            4. Call-to-action ending
            5. Estimated duration
            
            Format as JSON with keys: hook, script_sections, visual_cues, cta, duration
            """,
            
            ContentType.LANDING_PAGE: f"""
            {base_context}
            
            Create landing page content with:
            1. Compelling headline
            2. Subheadline
            3. Value propositions (3-5 key points)
            4. Social proof section
            5. CTA sections
            6. FAQ content
            
            Format as JSON with keys: headline, subheadline, value_props, social_proof, cta_sections, faq
            """
        }
        
        prompt = prompts.get(brief.content_type, prompts[ContentType.BLOG_POST])
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert content creator and copywriter. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content_json = response.choices[0].message.content
            return json.loads(content_json)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            # Fallback: return structured content
            return {
                "title": brief.title,
                "content": response.choices[0].message.content,
                "generated_at": datetime.now().isoformat()
            }

    async def _analyze_content_quality(self, content: GeneratedContent):
        """Analyze content for SEO, readability, and engagement prediction"""
        
        # SEO Analysis
        seo_prompt = f"""
        Analyze this content for SEO quality (score 0-100):
        Title: {content.content.get('title', '')}
        Content: {str(content.content)}
        Target Keywords: {content.brief.keywords or []}
        
        Consider: keyword usage, title optimization, meta descriptions, content length, structure.
        Respond with just a number 0-100.
        """
        
        # Readability Analysis
        readability_prompt = f"""
        Analyze this content for readability (score 0-100):
        Content: {str(content.content)}
        Target Audience: {content.brief.target_audience}
        
        Consider: sentence length, vocabulary complexity, structure, clarity.
        Respond with just a number 0-100.
        """
        
        # Engagement Prediction
        engagement_prompt = f"""
        Predict engagement potential for this content (score 0.0-1.0):
        Content Type: {content.brief.content_type.value}
        Platform: {content.brief.platform.value}
        Content: {str(content.content)}
        
        Consider: platform fit, audience appeal, trending topics, emotional impact.
        Respond with just a decimal number 0.0-1.0.
        """
        
        try:
            # Run analyses concurrently
            seo_task = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": seo_prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            readability_task = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": readability_prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            engagement_task = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": engagement_prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            # Wait for all analyses
            seo_response, readability_response, engagement_response = await asyncio.gather(
                seo_task, readability_task, engagement_task
            )
            
            # Extract scores
            content.seo_score = int(seo_response.choices[0].message.content.strip())
            content.readability_score = int(readability_response.choices[0].message.content.strip())
            content.engagement_prediction = float(engagement_response.choices[0].message.content.strip())
            
        except Exception as e:
            logger.error(f"Error analyzing content quality: {str(e)}")
            # Set default scores
            content.seo_score = 70
            content.readability_score = 75
            content.engagement_prediction = 0.6

    async def optimize_content(self, content_id: str, optimization_goals: List[str]) -> GeneratedContent:
        """Optimize existing content based on goals"""
        if content_id not in self.content_store:
            raise ValueError(f"Content {content_id} not found")
        
        content = self.content_store[content_id]
        
        optimization_prompt = f"""
        Optimize this content based on these goals: {', '.join(optimization_goals)}
        
        Current Content: {json.dumps(content.content, indent=2)}
        Current SEO Score: {content.seo_score}
        Current Readability Score: {content.readability_score}
        Current Engagement Prediction: {content.engagement_prediction}
        
        Provide optimized version with improvements. Format as JSON matching the original structure.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a content optimization expert. Always respond with valid JSON."},
                    {"role": "user", "content": optimization_prompt}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            
            optimized_content = json.loads(response.choices[0].message.content)
            
            # Update content
            content.content = optimized_content
            content.updated_at = datetime.now()
            
            # Re-analyze quality
            await self._analyze_content_quality(content)
            
            # Save updates
            if self.supabase:
                await self._save_content_to_db(content)
            
            logger.info(f"Optimized content: {content_id}")
            return content
            
        except Exception as e:
            logger.error(f"Error optimizing content: {str(e)}")
            raise

    async def generate_content_calendar(self, 
                                      days: int = 30, 
                                      content_types: List[ContentType] = None,
                                      platforms: List[Platform] = None) -> Dict[str, List[ContentBrief]]:
        """Generate content calendar for specified period"""
        
        if not content_types:
            content_types = [ContentType.SOCIAL_POST, ContentType.BLOG_POST, ContentType.EMAIL]
        
        if not platforms:
            platforms = [Platform.LINKEDIN, Platform.TWITTER, Platform.BLOG]
        
        calendar_prompt = f"""
        Create a {days}-day content calendar with:
        - Content Types: {[ct.value for ct in content_types]}
        - Platforms: {[p.value for p in platforms]}
        - Mix of educational, promotional, and engaging content
        - Strategic posting frequency
        - Trending topics and seasonal relevance
        
        Format as JSON with date keys (YYYY-MM-DD) and content brief arrays.
        Each brief should have: title, content_type, platform, target_audience, key_messages, tone
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a content strategy expert. Create comprehensive content calendars."},
                    {"role": "user", "content": calendar_prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            calendar_data = json.loads(response.choices[0].message.content)
            
            # Convert to ContentBrief objects
            calendar = {}
            for date_str, briefs in calendar_data.items():
                calendar[date_str] = []
                for brief_data in briefs:
                    brief = ContentBrief(
                        title=brief_data.get('title', ''),
                        content_type=ContentType(brief_data.get('content_type', 'blog_post')),
                        target_audience=brief_data.get('target_audience', ''),
                        key_messages=brief_data.get('key_messages', []),
                        platform=Platform(brief_data.get('platform', 'blog')),
                        tone=brief_data.get('tone', 'professional')
                    )
                    calendar[date_str].append(brief)
            
            logger.info(f"Generated {days}-day content calendar")
            return calendar
            
        except Exception as e:
            logger.error(f"Error generating content calendar: {str(e)}")
            raise

    async def get_content_analytics(self) -> Dict[str, Any]:
        """Get analytics for all generated content"""
        total_content = len(self.content_store)
        
        if total_content == 0:
            return {"message": "No content generated yet"}
        
        # Calculate averages
        avg_seo = sum(c.seo_score for c in self.content_store.values()) / total_content
        avg_readability = sum(c.readability_score for c in self.content_store.values()) / total_content
        avg_engagement = sum(c.engagement_prediction for c in self.content_store.values()) / total_content
        
        # Content type breakdown
        type_breakdown = {}
        platform_breakdown = {}
        status_breakdown = {}
        
        for content in self.content_store.values():
            # Type breakdown
            content_type = content.brief.content_type.value
            type_breakdown[content_type] = type_breakdown.get(content_type, 0) + 1
            
            # Platform breakdown
            platform = content.brief.platform.value
            platform_breakdown[platform] = platform_breakdown.get(platform, 0) + 1
            
            # Status breakdown
            status = content.status.value
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        return {
            "total_content": total_content,
            "average_scores": {
                "seo": round(avg_seo, 1),
                "readability": round(avg_readability, 1),
                "engagement_prediction": round(avg_engagement, 2)
            },
            "content_type_breakdown": type_breakdown,
            "platform_breakdown": platform_breakdown,
            "status_breakdown": status_breakdown,
            "top_performing_content": await self._get_top_performing_content()
        }

    async def _get_top_performing_content(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing content based on composite score"""
        if not self.content_store:
            return []
        
        # Calculate composite scores
        scored_content = []
        for content in self.content_store.values():
            composite_score = (
                content.seo_score * 0.3 + 
                content.readability_score * 0.3 + 
                content.engagement_prediction * 100 * 0.4
            )
            
            scored_content.append({
                "id": content.id,
                "title": content.content.get('title', content.brief.title),
                "type": content.brief.content_type.value,
                "platform": content.brief.platform.value,
                "composite_score": round(composite_score, 1),
                "seo_score": content.seo_score,
                "readability_score": content.readability_score,
                "engagement_prediction": content.engagement_prediction
            })
        
        # Sort by composite score and return top performers
        scored_content.sort(key=lambda x: x['composite_score'], reverse=True)
        return scored_content[:limit]

    async def _save_content_to_db(self, content: GeneratedContent):
        """Save content to Supabase database"""
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
            
            # Convert datetime objects in brief
            if content_data["brief"]["deadline"]:
                content_data["brief"]["deadline"] = content.brief.deadline.isoformat()
            
            # Convert enums to strings
            content_data["brief"]["content_type"] = content.brief.content_type.value
            content_data["brief"]["platform"] = content.brief.platform.value
            
            self.supabase.table('generated_content').upsert(content_data).execute()
            
        except Exception as e:
            logger.error(f"Error saving content to database: {str(e)}")

    def get_content(self, content_id: str) -> Optional[GeneratedContent]:
        """Get specific content by ID"""
        return self.content_store.get(content_id)

    def list_content(self, 
                    status: ContentStatus = None,
                    content_type: ContentType = None,
                    platform: Platform = None) -> List[GeneratedContent]:
        """List content with optional filtering"""
        content_list = list(self.content_store.values())
        
        if status:
            content_list = [c for c in content_list if c.status == status]
        
        if content_type:
            content_list = [c for c in content_list if c.brief.content_type == content_type]
        
        if platform:
            content_list = [c for c in content_list if c.brief.platform == platform]
        
        # Sort by creation date, newest first
        content_list.sort(key=lambda x: x.created_at, reverse=True)
        return content_list

    async def update_content_status(self, content_id: str, new_status: ContentStatus) -> GeneratedContent:
        """Update content status"""
        if content_id not in self.content_store:
            raise ValueError(f"Content {content_id} not found")
        
        content = self.content_store[content_id]
        content.status = new_status
        content.updated_at = datetime.now()
        
        # Save to database
        if self.supabase:
            await self._save_content_to_db(content)
        
        logger.info(f"Updated content {content_id} status to {new_status.value}")
        return content
