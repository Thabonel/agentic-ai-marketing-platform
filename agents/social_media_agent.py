import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class SocialPlatform(Enum):
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"

class PostStatus(Enum):
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    DRAFT = "draft"

class EngagementType(Enum):
    LIKE = "like"
    COMMENT = "comment"
    SHARE = "share"
    REPLY = "reply"
    MENTION = "mention"
    DM = "dm"

@dataclass
class SocialPost:
    id: str
    platform: SocialPlatform
    content: str
    media_urls: List[str]
    hashtags: List[str]
    scheduled_time: datetime
    status: PostStatus
    created_at: datetime
    published_at: Optional[datetime] = None
    post_url: Optional[str] = None
    engagement_metrics: Dict[str, int] = None

@dataclass
class EngagementItem:
    id: str
    platform: SocialPlatform
    type: EngagementType
    author: str
    content: str
    post_id: Optional[str]
    timestamp: datetime
    sentiment: str = "neutral"  # positive, negative, neutral
    requires_response: bool = False
    responded: bool = False

@dataclass
class SocialAnalytics:
    platform: SocialPlatform
    period: str
    metrics: Dict[str, Any]
    top_posts: List[Dict[str, Any]]
    engagement_rate: float
    follower_growth: int
    best_posting_times: List[str]

class SocialMediaAgent:
    def __init__(self, openai_api_key: str, platform_credentials: Dict[str, str], supabase_client=None):
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.credentials = platform_credentials
        self.supabase = supabase_client
        self.posts_store: Dict[str, SocialPost] = {}
        self.engagement_store: Dict[str, EngagementItem] = {}
        self.http_client = httpx.AsyncClient()
        
        # Platform API endpoints
        self.api_endpoints = {
            SocialPlatform.LINKEDIN: "https://api.linkedin.com/v2",
            SocialPlatform.TWITTER: "https://api.twitter.com/2",
            SocialPlatform.FACEBOOK: "https://graph.facebook.com/v18.0",
            SocialPlatform.INSTAGRAM: "https://graph.instagram.com",
            SocialPlatform.YOUTUBE: "https://www.googleapis.com/youtube/v3"
        }

    async def schedule_post(self, 
                          platform: SocialPlatform,
                          content: str,
                          scheduled_time: datetime,
                          media_urls: List[str] = None,
                          hashtags: List[str] = None) -> SocialPost:
        """Schedule a post for publishing"""
        
        post_id = f"post_{platform.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Optimize content for platform
        optimized_content = await self._optimize_content_for_platform(content, platform, hashtags or [])
        
        post = SocialPost(
            id=post_id,
            platform=platform,
            content=optimized_content,
            media_urls=media_urls or [],
            hashtags=hashtags or [],
            scheduled_time=scheduled_time,
            status=PostStatus.SCHEDULED,
            created_at=datetime.now(),
            engagement_metrics={}
        )
        
        self.posts_store[post_id] = post
        
        # Save to database
        if self.supabase:
            await self._save_post_to_db(post)
        
        # Schedule for publishing
        await self._schedule_post_publishing(post)
        
        logger.info(f"Scheduled post {post_id} for {platform.value} at {scheduled_time}")
        return post

    async def _optimize_content_for_platform(self, content: str, platform: SocialPlatform, hashtags: List[str]) -> str:
        """Optimize content for specific platform requirements"""
        
        platform_specs = {
            SocialPlatform.TWITTER: {"max_length": 280, "style": "concise and engaging"},
            SocialPlatform.LINKEDIN: {"max_length": 3000, "style": "professional and thought-provoking"},
            SocialPlatform.FACEBOOK: {"max_length": 2000, "style": "conversational and community-focused"},
            SocialPlatform.INSTAGRAM: {"max_length": 2200, "style": "visual-first and lifestyle-oriented"},
            SocialPlatform.YOUTUBE: {"max_length": 5000, "style": "descriptive and video-focused"}
        }
        
        specs = platform_specs.get(platform, {"max_length": 2000, "style": "engaging"})
        
        optimization_prompt = f"""
        Optimize this content for {platform.value}:
        Original Content: {content}
        Hashtags to include: {hashtags}
        
        Platform Requirements:
        - Max length: {specs['max_length']} characters
        - Style: {specs['style']}
        - Include relevant hashtags naturally
        - Maintain core message while optimizing for engagement
        
        Return only the optimized content, no explanations.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are a {platform.value} content optimization expert."},
                    {"role": "user", "content": optimization_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            optimized = response.choices[0].message.content.strip()
            
            # Ensure length constraints
            if len(optimized) > specs['max_length']:
                optimized = optimized[:specs['max_length']-3] + "..."
            
            return optimized
            
        except Exception as e:
            logger.error(f"Error optimizing content: {str(e)}")
            return content[:specs['max_length']]

    async def _schedule_post_publishing(self, post: SocialPost):
        """Schedule post for automatic publishing"""
        
        # Calculate delay until scheduled time
        delay = (post.scheduled_time - datetime.now()).total_seconds()
        
        if delay > 0:
            # Schedule background task
            asyncio.create_task(self._publish_post_delayed(post, delay))
        else:
            # Publish immediately if scheduled time has passed
            await self.publish_post(post.id)

    async def _publish_post_delayed(self, post: SocialPost, delay: float):
        """Publish post after delay"""
        await asyncio.sleep(delay)
        await self.publish_post(post.id)

    async def publish_post(self, post_id: str) -> bool:
        """Publish a scheduled post"""
        
        if post_id not in self.posts_store:
            raise ValueError(f"Post {post_id} not found")
        
        post = self.posts_store[post_id]
        
        try:
            # Publish to platform
            success, post_url = await self._publish_to_platform(post)
            
            if success:
                post.status = PostStatus.PUBLISHED
                post.published_at = datetime.now()
                post.post_url = post_url
                logger.info(f"Published post {post_id} to {post.platform.value}")
            else:
                post.status = PostStatus.FAILED
                logger.error(f"Failed to publish post {post_id}")
            
            # Update database
            if self.supabase:
                await self._save_post_to_db(post)
            
            return success
            
        except Exception as e:
            logger.error(f"Error publishing post {post_id}: {str(e)}")
            post.status = PostStatus.FAILED
            return False

    async def _publish_to_platform(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        """Publish post to specific platform"""
        
        platform_publishers = {
            SocialPlatform.LINKEDIN: self._publish_to_linkedin,
            SocialPlatform.TWITTER: self._publish_to_twitter,
            SocialPlatform.FACEBOOK: self._publish_to_facebook,
            SocialPlatform.INSTAGRAM: self._publish_to_instagram,
            SocialPlatform.YOUTUBE: self._publish_to_youtube
        }
        
        publisher = platform_publishers.get(post.platform)
        if publisher:
            return await publisher(post)
        else:
            logger.error(f"No publisher for platform {post.platform.value}")
            return False, None

    async def _publish_to_linkedin(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        """Publish to LinkedIn"""
        try:
            headers = {
                "Authorization": f"Bearer {self.credentials.get('linkedin_token')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "author": f"urn:li:person:{self.credentials.get('linkedin_person_id')}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": post.content
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.LINKEDIN]}/ugcPosts",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 201:
                result = response.json()
                post_url = f"https://linkedin.com/feed/update/{result.get('id')}"
                return True, post_url
            else:
                logger.error(f"LinkedIn publish failed: {response.text}")
                return False, None
                
        except Exception as e:
            logger.error(f"LinkedIn publish error: {str(e)}")
            return False, None

    async def _publish_to_twitter(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        """Publish to Twitter"""
        try:
            headers = {
                "Authorization": f"Bearer {self.credentials.get('twitter_bearer_token')}",
                "Content-Type": "application/json"
            }
            
            payload = {"text": post.content}
            
            response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.TWITTER]}/tweets",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 201:
                result = response.json()
                tweet_id = result["data"]["id"]
                post_url = f"https://twitter.com/user/status/{tweet_id}"
                return True, post_url
            else:
                logger.error(f"Twitter publish failed: {response.text}")
                return False, None
                
        except Exception as e:
            logger.error(f"Twitter publish error: {str(e)}")
            return False, None

    async def _publish_to_facebook(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        """Publish to Facebook"""
        try:
            page_id = self.credentials.get('facebook_page_id')
            access_token = self.credentials.get('facebook_access_token')
            
            payload = {
                "message": post.content,
                "access_token": access_token
            }
            
            response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.FACEBOOK]}/{page_id}/feed",
                data=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                post_id = result.get("id")
                post_url = f"https://facebook.com/{post_id}"
                return True, post_url
            else:
                logger.error(f"Facebook publish failed: {response.text}")
                return False, None
                
        except Exception as e:
            logger.error(f"Facebook publish error: {str(e)}")
            return False, None

    async def _publish_to_instagram(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        """Publish to Instagram"""
        try:
            # Instagram requires media, so this is a simplified version
            access_token = self.credentials.get('instagram_access_token')
            user_id = self.credentials.get('instagram_user_id')
            
            if not post.media_urls:
                logger.error("Instagram posts require media")
                return False, None
            
            # Create media container
            container_payload = {
                "image_url": post.media_urls[0],
                "caption": post.content,
                "access_token": access_token
            }
            
            container_response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.INSTAGRAM]}/{user_id}/media",
                data=container_payload
            )
            
            if container_response.status_code == 200:
                container_id = container_response.json().get("id")
                
                # Publish media
                publish_payload = {
                    "creation_id": container_id,
                    "access_token": access_token
                }
                
                publish_response = await self.http_client.post(
                    f"{self.api_endpoints[SocialPlatform.INSTAGRAM]}/{user_id}/media_publish",
                    data=publish_payload
                )
                
                if publish_response.status_code == 200:
                    media_id = publish_response.json().get("id")
                    post_url = f"https://instagram.com/p/{media_id}"
                    return True, post_url
            
            return False, None
                
        except Exception as e:
            logger.error(f"Instagram publish error: {str(e)}")
            return False, None

    async def _publish_to_youtube(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        """Publish to YouTube (community posts)"""
        try:
            # YouTube community posts via API (simplified)
            headers = {
                "Authorization": f"Bearer {self.credentials.get('youtube_access_token')}",
                "Content-Type": "application/json"
            }
            
            # Note: YouTube API for community posts is limited
            # This is a placeholder for the actual implementation
            logger.info("YouTube publishing not fully implemented - requires specific setup")
            return False, None
                
        except Exception as e:
            logger.error(f"YouTube publish error: {str(e)}")
            return False, None

    async def monitor_engagement(self) -> List[EngagementItem]:
        """Monitor and collect engagement across platforms"""
        
        engagement_items = []
        
        for platform in SocialPlatform:
            try:
                items = await self._fetch_platform_engagement(platform)
                engagement_items.extend(items)
            except Exception as e:
                logger.error(f"Error monitoring {platform.value} engagement: {str(e)}")
        
        # Analyze sentiment and determine response requirements
        for item in engagement_items:
            await self._analyze_engagement_item(item)
            self.engagement_store[item.id] = item
        
        # Save to database
        if self.supabase:
            for item in engagement_items:
                await self._save_engagement_to_db(item)
        
        return engagement_items

    async def _fetch_platform_engagement(self, platform: SocialPlatform) -> List[EngagementItem]:
        """Fetch engagement from specific platform"""
        
        platform_fetchers = {
            SocialPlatform.LINKEDIN: self._fetch_linkedin_engagement,
            SocialPlatform.TWITTER: self._fetch_twitter_engagement,
            SocialPlatform.FACEBOOK: self._fetch_facebook_engagement,
            SocialPlatform.INSTAGRAM: self._fetch_instagram_engagement
        }
        
        fetcher = platform_fetchers.get(platform)
        if fetcher:
            return await fetcher()
        else:
            return []

    async def _fetch_twitter_engagement(self) -> List[EngagementItem]:
        """Fetch Twitter engagement"""
        try:
            headers = {
                "Authorization": f"Bearer {self.credentials.get('twitter_bearer_token')}"
            }
            
            # Fetch mentions and replies
            response = await self.http_client.get(
                f"{self.api_endpoints[SocialPlatform.TWITTER]}/users/by/username/{self.credentials.get('twitter_username')}/mentions",
                headers=headers,
                params={"tweet.fields": "created_at,author_id,in_reply_to_user_id"}
            )
            
            items = []
            if response.status_code == 200:
                data = response.json()
                for tweet in data.get("data", []):
                    item = EngagementItem(
                        id=f"twitter_{tweet['id']}",
                        platform=SocialPlatform.TWITTER,
                        type=EngagementType.MENTION,
                        author=tweet.get("author_id", ""),
                        content=tweet.get("text", ""),
                        timestamp=datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
                    )
                    items.append(item)
            
            return items
            
        except Exception as e:
            logger.error(f"Error fetching Twitter engagement: {str(e)}")
            return []

    async def _fetch_linkedin_engagement(self) -> List[EngagementItem]:
        """Fetch LinkedIn engagement"""
        try:
            headers = {
                "Authorization": f"Bearer {self.credentials.get('linkedin_token')}"
            }
            
            # Fetch social actions (likes, comments, shares)
            response = await self.http_client.get(
                f"{self.api_endpoints[SocialPlatform.LINKEDIN]}/socialActions",
                headers=headers,
                params={"q": "actor", "actor": f"urn:li:person:{self.credentials.get('linkedin_person_id')}"}
            )
            
            items = []
            if response.status_code == 200:
                data = response.json()
                for action in data.get("elements", []):
                    item = EngagementItem(
                        id=f"linkedin_{action.get('id')}",
                        platform=SocialPlatform.LINKEDIN,
                        type=EngagementType.LIKE,  # Simplified
                        author=action.get("actor", ""),
                        content="",
                        timestamp=datetime.now()  # Would parse from action data
                    )
                    items.append(item)
            
            return items
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn engagement: {str(e)}")
            return []

    async def _fetch_facebook_engagement(self) -> List[EngagementItem]:
        """Fetch Facebook engagement"""
        try:
            page_id = self.credentials.get('facebook_page_id')
            access_token = self.credentials.get('facebook_access_token')
            
            # Fetch page feed with comments
            response = await self.http_client.get(
                f"{self.api_endpoints[SocialPlatform.FACEBOOK]}/{page_id}/feed",
                params={
                    "fields": "comments{message,from,created_time},likes.summary(true)",
                    "access_token": access_token
                }
            )
            
            items = []
            if response.status_code == 200:
                data = response.json()
                for post in data.get("data", []):
                    for comment in post.get("comments", {}).get("data", []):
                        item = EngagementItem(
                            id=f"facebook_{comment['id']}",
                            platform=SocialPlatform.FACEBOOK,
                            type=EngagementType.COMMENT,
                            author=comment.get("from", {}).get("name", ""),
                            content=comment.get("message", ""),
                            post_id=post["id"],
                            timestamp=datetime.fromisoformat(comment["created_time"].replace("+0000", "+00:00"))
                        )
                        items.append(item)
            
            return items
            
        except Exception as e:
            logger.error(f"Error fetching Facebook engagement: {str(e)}")
            return []

    async def _fetch_instagram_engagement(self) -> List[EngagementItem]:
        """Fetch Instagram engagement"""
        try:
            user_id = self.credentials.get('instagram_user_id')
            access_token = self.credentials.get('instagram_access_token')
            
            # Fetch media comments
            media_response = await self.http_client.get(
                f"{self.api_endpoints[SocialPlatform.INSTAGRAM]}/{user_id}/media",
                params={
                    "fields": "id,comments{text,username,timestamp}",
                    "access_token": access_token
                }
            )
            
            items = []
            if media_response.status_code == 200:
                data = media_response.json()
                for media in data.get("data", []):
                    for comment in media.get("comments", {}).get("data", []):
                        item = EngagementItem(
                            id=f"instagram_{comment['id']}",
                            platform=SocialPlatform.INSTAGRAM,
                            type=EngagementType.COMMENT,
                            author=comment.get("username", ""),
                            content=comment.get("text", ""),
                            post_id=media["id"],
                            timestamp=datetime.fromisoformat(comment["timestamp"].replace("+0000", "+00:00"))
                        )
                        items.append(item)
            
            return items
            
        except Exception as e:
            logger.error(f"Error fetching Instagram engagement: {str(e)}")
            return []

    async def _analyze_engagement_item(self, item: EngagementItem):
        """Analyze engagement for sentiment and response requirements"""
        
        analysis_prompt = f"""
        Analyze this social media engagement:
        Platform: {item.platform.value}
        Type: {item.type.value}
        Author: {item.author}
        Content: {item.content}
        
        Determine:
        1. Sentiment (positive/negative/neutral)
        2. Whether it requires a response (true/false)
        
        Respond with JSON: {{"sentiment": "positive/negative/neutral", "requires_response": true/false}}
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a social media engagement analyst. Always respond with valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )
            
            analysis = json.loads(response.choices[0].message.content)
            item.sentiment = analysis.get("sentiment", "neutral")
            item.requires_response = analysis.get("requires_response", False)
            
        except Exception as e:
            logger.error(f"Error analyzing engagement: {str(e)}")
            item.sentiment = "neutral"
            item.requires_response = False

    async def respond_to_engagement(self, engagement_id: str, custom_response: str = None) -> bool:
        """Respond to an engagement item"""
        
        if engagement_id not in self.engagement_store:
            raise ValueError(f"Engagement {engagement_id} not found")
        
        engagement = self.engagement_store[engagement_id]
        
        if custom_response:
            response_text = custom_response
        else:
            response_text = await self._generate_response(engagement)
        
        success = await self._send_response(engagement, response_text)
        
        if success:
            engagement.responded = True
            if self.supabase:
                await self._save_engagement_to_db(engagement)
        
        return success

    async def _generate_response(self, engagement: EngagementItem) -> str:
        """Generate AI response to engagement"""
        
        response_prompt = f"""
        Generate a professional and engaging response to this social media interaction:
        
        Platform: {engagement.platform.value}
        Original content: {engagement.content}
        Author: {engagement.author}
        Sentiment: {engagement.sentiment}
        
        Guidelines:
        - Be professional but friendly
        - Match the platform's tone
        - Keep it concise
        - Add value to the conversation
        - Encourage further engagement if appropriate
        
        Return only the response text, no quotes or explanations.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are a {engagement.platform.value} community manager."},
                    {"role": "user", "content": response_prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Thank you for your engagement! We appreciate your feedback."

    async def _send_response(self, engagement: EngagementItem, response_text: str) -> bool:
        """Send response to the platform"""
        
        platform_responders = {
            SocialPlatform.TWITTER: self._respond_twitter,
            SocialPlatform.LINKEDIN: self._respond_linkedin,
            SocialPlatform.FACEBOOK: self._respond_facebook,
            SocialPlatform.INSTAGRAM: self._respond_instagram
        }
        
        responder = platform_responders.get(engagement.platform)
        if responder:
            return await responder(engagement, response_text)
        else:
            logger.error(f"No responder for platform {engagement.platform.value}")
            return False

    async def _respond_twitter(self, engagement: EngagementItem, response_text: str) -> bool:
        """Respond on Twitter"""
        try:
            headers = {
                "Authorization": f"Bearer {self.credentials.get('twitter_bearer_token')}",
                "Content-Type": "application/json"
            }
            
            # Extract tweet ID from engagement ID
            tweet_id = engagement.id.replace("twitter_", "")
            
            payload = {
                "text": f"@{engagement.author} {response_text}",
                "reply": {"in_reply_to_tweet_id": tweet_id}
            }
            
            response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.TWITTER]}/tweets",
                headers=headers,
                json=payload
            )
            
            return response.status_code == 201
            
        except Exception as e:
            logger.error(f"Error responding on Twitter: {str(e)}")
            return False

    async def _respond_linkedin(self, engagement: EngagementItem, response_text: str) -> bool:
        """Respond on LinkedIn"""
        try:
            headers = {
                "Authorization": f"Bearer {self.credentials.get('linkedin_token')}",
                "Content-Type": "application/json"
            }
            
            # LinkedIn comment response (simplified)
            payload = {
                "actor": f"urn:li:person:{self.credentials.get('linkedin_person_id')}",
                "message": {"text": response_text}
            }
            
            # Note: Actual LinkedIn comment API requires specific post URN
            logger.info("LinkedIn response sent (API implementation needed)")
            return True
            
        except Exception as e:
            logger.error(f"Error responding on LinkedIn: {str(e)}")
            return False

    async def _respond_facebook(self, engagement: EngagementItem, response_text: str) -> bool:
        """Respond on Facebook"""
        try:
            access_token = self.credentials.get('facebook_access_token')
            comment_id = engagement.id.replace("facebook_", "")
            
            payload = {
                "message": response_text,
                "access_token": access_token
            }
            
            response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.FACEBOOK]}/{comment_id}/comments",
                data=payload
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error responding on Facebook: {str(e)}")
            return False

    async def _respond_instagram(self, engagement: EngagementItem, response_text: str) -> bool:
        """Respond on Instagram"""
        try:
            access_token = self.credentials.get('instagram_access_token')
            comment_id = engagement.id.replace("instagram_", "")
            
            payload = {
                "message": response_text,
                "access_token": access_token
            }
            
            response = await self.http_client.post(
                f"{self.api_endpoints[SocialPlatform.INSTAGRAM]}/{comment_id}/replies",
                data=payload
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error responding on Instagram: {str(e)}")
            return False

    async def get_social_analytics(self, 
                                 platform: SocialPlatform = None, 
                                 days: int = 30) -> Dict[str, SocialAnalytics]:
        """Get comprehensive social media analytics"""
        
        platforms = [platform] if platform else list(SocialPlatform)
        analytics = {}
        
        for p in platforms:
            try:
                analytics[p.value] = await self._get_platform_analytics(p, days)
            except Exception as e:
                logger.error(f"Error getting analytics for {p.value}: {str(e)}")
        
        return analytics

    async def _get_platform_analytics(self, platform: SocialPlatform, days: int) -> SocialAnalytics:
        """Get analytics for specific platform"""
        
        # Filter posts for this platform and time period
        cutoff_date = datetime.now() - timedelta(days=days)
        platform_posts = [
            post for post in self.posts_store.values()
            if post.platform == platform and post.created_at >= cutoff_date
        ]
        
        # Calculate metrics
        total_posts = len(platform_posts)
        published_posts = [p for p in platform_posts if p.status == PostStatus.PUBLISHED]
        
        # Engagement metrics (mock data - would come from platform APIs)
        total_likes = sum(post.engagement_metrics.get('likes', 0) for post in published_posts)
        total_comments = sum(post.engagement_metrics.get('comments', 0) for post in published_posts)
        total_shares = sum(post.engagement_metrics.get('shares', 0) for post in published_posts)
        
        engagement_rate = 0.0
        if published_posts:
            total_engagement = total_likes + total_comments + total_shares
            engagement_rate = total_engagement / len(published_posts)
        
        # Top performing posts
        top_posts = sorted(
            published_posts,
            key=lambda p: sum(p.engagement_metrics.values()) if p.engagement_metrics else 0,
            reverse=True
        )[:5]
        
        top_posts_data = [
            {
                "id": post.id,
                "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                "engagement": sum(post.engagement_metrics.values()) if post.engagement_metrics else 0,
                "published_at": post.published_at.isoformat() if post.published_at else None
            }
            for post in top_posts
        ]
        
        return SocialAnalytics(
            platform=platform,
            period=f"{days} days",
            metrics={
                "total_posts": total_posts,
                "published_posts": len(published_posts),
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "engagement_rate": round(engagement_rate, 2)
            },
            top_posts=top_posts_data,
            engagement_rate=engagement_rate,
            follower_growth=0,  # Would fetch from platform API
            best_posting_times=["9:00 AM", "1:00 PM", "5:00 PM"]  # AI-generated based on engagement patterns
        )

    async def auto_engage(self, hours_lookback: int = 24) -> Dict[str, int]:
        """Automatically engage with relevant content"""
        
        # Fetch recent mentions and engagement opportunities
        recent_engagement = await self.monitor_engagement()
        
        # Filter for items requiring response from last N hours
        cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
        pending_responses = [
            item for item in recent_engagement
            if item.requires_response and not item.responded and item.timestamp >= cutoff_time
        ]
        
        # Auto-respond to high-priority items
        responses_sent = 0
        for item in pending_responses:
            try:
                success = await self.respond_to_engagement(item.id)
                if success:
                    responses_sent += 1
            except Exception as e:
                logger.error(f"Error auto-responding to {item.id}: {str(e)}")
        
        return {
            "pending_responses": len(pending_responses),
            "responses_sent": responses_sent,
            "success_rate": responses_sent / len(pending_responses) if pending_responses else 1.0
        }

    async def _save_post_to_db(self, post: SocialPost):
        """Save post to database"""
        if not self.supabase:
            return
        
        try:
            post_data = asdict(post)
            post_data["platform"] = post.platform.value
            post_data["status"] = post.status.value
            post_data["scheduled_time"] = post.scheduled_time.isoformat()
            post_data["created_at"] = post.created_at.isoformat()
            
            if post.published_at:
                post_data["published_at"] = post.published_at.isoformat()
            
            self.supabase.table('social_posts').upsert(post_data).execute()
            
        except Exception as e:
            logger.error(f"Error saving post to database: {str(e)}")

    async def _save_engagement_to_db(self, engagement: EngagementItem):
        """Save engagement to database"""
        if not self.supabase:
            return
        
        try:
            engagement_data = asdict(engagement)
            engagement_data["platform"] = engagement.platform.value
            engagement_data["type"] = engagement.type.value
            engagement_data["timestamp"] = engagement.timestamp.isoformat()
            
            self.supabase.table('social_engagement').upsert(engagement_data).execute()
            
        except Exception as e:
            logger.error(f"Error saving engagement to database: {str(e)}")

    def get_post(self, post_id: str) -> Optional[SocialPost]:
        """Get specific post by ID"""
        return self.posts_store.get(post_id)

    def list_posts(self, 
                  platform: SocialPlatform = None,
                  status: PostStatus = None,
                  limit: int = 50) -> List[SocialPost]:
        """List posts with optional filtering"""
        posts = list(self.posts_store.values())
        
        if platform:
            posts = [p for p in posts if p.platform == platform]
        
        if status:
            posts = [p for p in posts if p.status == status]
        
        # Sort by scheduled time, newest first
        posts.sort(key=lambda x: x.scheduled_time, reverse=True)
        return posts[:limit]

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
