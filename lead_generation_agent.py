import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from openai import AsyncOpenAI
import logging
from bs4 import BeautifulSoup
import csv
import io
from urllib.parse import urljoin, urlparse
import time

class LeadStatus(Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"

class DataSource(Enum):
    WEBSITE_SCRAPING = "website_scraping"
    LINKEDIN = "linkedin"
    GOOGLE_SEARCH = "google_search"
    SOCIAL_MEDIA = "social_media"
    DATABASE = "database"
    API = "api"

class LeadQuality(Enum):
    HOT = "hot"          # 80-100 score
    WARM = "warm"        # 60-79 score
    COLD = "cold"        # 40-59 score
    UNQUALIFIED = "unqualified"  # 0-39 score

@dataclass
class LeadCriteria:
    industry: Optional[str] = None
    company_size: Optional[str] = None  # "1-10", "11-50", "51-200", "201-1000", "1000+"
    location: Optional[str] = None
    job_titles: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    revenue_range: Optional[str] = None
    exclude_competitors: bool = True

@dataclass
class Lead:
    id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    job_title: Optional[str]
    company: str
    company_website: Optional[str]
    company_size: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    linkedin_url: Optional[str]
    source: DataSource
    quality_score: float
    quality_level: LeadQuality
    status: LeadStatus
    notes: Optional[str]
    tags: List[str]
    contact_attempts: int
    last_contacted: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    custom_fields: Dict[str, Any]

@dataclass
class SearchTask:
    id: str
    name: str
    criteria: LeadCriteria
    sources: List[DataSource]
    max_leads: int
    status: str  # "pending", "running", "completed", "failed"
    progress: float
    leads_found: int
    created_at: datetime
    completed_at: Optional[datetime]
    results_summary: Dict[str, Any]

class LeadGenerationAgent:
    def __init__(self, openai_api_key: str, integrations: Dict[str, str]):
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.integrations = integrations
        self.leads: Dict[str, Lead] = {}
        self.search_tasks: Dict[str, SearchTask] = {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize scrapers and data sources
        self.web_scraper = WebScraper()
        self.linkedin_scraper = LinkedInScraper(integrations.get('linkedin_api_key'))
        self.google_search = GoogleSearchClient(integrations.get('google_search_api_key'))
        self.apollo_client = ApolloClient(integrations.get('apollo_api_key'))
        self.zoominfo_client = ZoomInfoClient(integrations.get('zoominfo_api_key'))

    async def create_search_task(self, 
                               name: str,
                               criteria: LeadCriteria,
                               sources: List[DataSource],
                               max_leads: int = 100) -> SearchTask:
        """Create a new lead generation search task"""
        
        task_id = f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        task = SearchTask(
            id=task_id,
            name=name,
            criteria=criteria,
            sources=sources,
            max_leads=max_leads,
            status="pending",
            progress=0.0,
            leads_found=0,
            created_at=datetime.now(),
            completed_at=None,
            results_summary={}
        )
        
        self.search_tasks[task_id] = task
        
        # Start the search process
        asyncio.create_task(self._execute_search_task(task_id))
        
        self.logger.info(f"Created search task {task_id}: {name}")
        return task

    async def _execute_search_task(self, task_id: str):
        """Execute lead generation search task"""
        
        task = self.search_tasks[task_id]
        task.status = "running"
        
        try:
            all_leads = []
            total_sources = len(task.sources)
            
            for i, source in enumerate(task.sources):
                self.logger.info(f"Searching {source.value} for leads...")
                
                # Update progress
                task.progress = (i / total_sources) * 100
                
                try:
                    source_leads = await self._search_source(source, task.criteria, task.max_leads // total_sources)
                    all_leads.extend(source_leads)
                    
                    self.logger.info(f"Found {len(source_leads)} leads from {source.value}")
                    
                except Exception as e:
                    self.logger.error(f"Error searching {source.value}: {str(e)}")
                    continue
            
            # Deduplicate leads
            unique_leads = await self._deduplicate_leads(all_leads)
            
            # Score and qualify leads
            qualified_leads = []
            for lead in unique_leads:
                if len(qualified_leads) >= task.max_leads:
                    break
                    
                # AI-powered lead scoring
                score = await self._score_lead(lead, task.criteria)
                lead.quality_score = score
                lead.quality_level = self._get_quality_level(score)
                
                # Store lead
                self.leads[lead.id] = lead
                qualified_leads.append(lead)
            
            # Update task completion
            task.status = "completed"
            task.progress = 100.0
            task.leads_found = len(qualified_leads)
            task.completed_at = datetime.now()
            task.results_summary = await self._generate_results_summary(qualified_leads, task.criteria)
            
            self.logger.info(f"Completed search task {task_id}: {len(qualified_leads)} qualified leads")
            
        except Exception as e:
            task.status = "failed"
            task.results_summary = {"error": str(e)}
            self.logger.error(f"Search task {task_id} failed: {str(e)}")

    async def _search_source(self, source: DataSource, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Search a specific data source for leads"""
        
        if source == DataSource.WEBSITE_SCRAPING:
            return await self._search_websites(criteria, max_results)
        elif source == DataSource.LINKEDIN:
            return await self._search_linkedin(criteria, max_results)
        elif source == DataSource.GOOGLE_SEARCH:
            return await self._search_google(criteria, max_results)
        elif source == DataSource.DATABASE:
            return await self._search_databases(criteria, max_results)
        else:
            return []

    async def _search_websites(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Scrape websites for lead information"""
        
        leads = []
        
        # Generate target websites based on criteria
        target_websites = await self._find_target_websites(criteria)
        
        for website in target_websites[:10]:  # Limit to 10 websites
            try:
                website_leads = await self.web_scraper.scrape_website(website, criteria)
                leads.extend(website_leads)
                
                if len(leads) >= max_results:
                    break
                    
                # Rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error scraping {website}: {str(e)}")
                continue
        
        return leads[:max_results]

    async def _search_linkedin(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Search LinkedIn for leads"""
        
        try:
            return await self.linkedin_scraper.search_professionals(criteria, max_results)
        except Exception as e:
            self.logger.error(f"LinkedIn search error: {str(e)}")
            return []

    async def _search_google(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Use Google Search to find leads"""
        
        # Generate search queries based on criteria
        search_queries = await self._generate_search_queries(criteria)
        
        leads = []
        for query in search_queries:
            try:
                results = await self.google_search.search(query, max_results=20)
                query_leads = await self._extract_leads_from_search_results(results, criteria)
                leads.extend(query_leads)
                
                if len(leads) >= max_results:
                    break
                    
            except Exception as e:
                self.logger.error(f"Google search error: {str(e)}")
                continue
        
        return leads[:max_results]

    async def _search_databases(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Search commercial lead databases"""
        
        leads = []
        
        # Apollo.io search
        if self.apollo_client.api_key:
            try:
                apollo_leads = await self.apollo_client.search_people(criteria, max_results // 2)
                leads.extend(apollo_leads)
            except Exception as e:
                self.logger.error(f"Apollo search error: {str(e)}")
        
        # ZoomInfo search
        if self.zoominfo_client.api_key:
            try:
                zoominfo_leads = await self.zoominfo_client.search_contacts(criteria, max_results // 2)
                leads.extend(zoominfo_leads)
            except Exception as e:
                self.logger.error(f"ZoomInfo search error: {str(e)}")
        
        return leads[:max_results]

    async def _find_target_websites(self, criteria: LeadCriteria) -> List[str]:
        """Find websites to scrape based on criteria"""
        
        # Generate search query for finding company websites
        query_parts = []
        
        if criteria.industry:
            query_parts.append(f'"{criteria.industry}" companies')
        if criteria.location:
            query_parts.append(f'in {criteria.location}')
        if criteria.keywords:
            query_parts.extend(criteria.keywords)
        
        query = " ".join(query_parts) + " contact us"
        
        try:
            search_results = await self.google_search.search(query, max_results=50)
            
            websites = []
            for result in search_results:
                url = result.get('url', '')
                domain = urlparse(url).netloc
                if domain and domain not in websites:
                    websites.append(domain)
            
            return websites
            
        except Exception as e:
            self.logger.error(f"Error finding target websites: {str(e)}")
            return []

    async def _generate_search_queries(self, criteria: LeadCriteria) -> List[str]:
        """Generate Google search queries based on criteria"""
        
        queries = []
        
        # Job title + industry queries
        if criteria.job_titles and criteria.industry:
            for title in criteria.job_titles:
                queries.append(f'"{title}" {criteria.industry} contact email')
                queries.append(f'"{title}" {criteria.industry} LinkedIn')
        
        # Company size + location queries
        if criteria.company_size and criteria.location:
            queries.append(f'{criteria.company_size} employees {criteria.location} companies')
        
        # Technology + industry queries
        if criteria.technologies and criteria.industry:
            for tech in criteria.technologies:
                queries.append(f'{tech} {criteria.industry} companies contact')
        
        # Keyword-based queries
        if criteria.keywords:
            for keyword in criteria.keywords:
                queries.append(f'"{keyword}" decision maker contact')
        
        return queries[:10]  # Limit to 10 queries

    async def _extract_leads_from_search_results(self, results: List[Dict], criteria: LeadCriteria) -> List[Lead]:
        """Extract lead information from Google search results"""
        
        leads = []
        
        for result in results:
            try:
                # Scrape the page for contact information
                page_leads = await self.web_scraper.extract_contacts_from_url(result['url'], criteria)
                leads.extend(page_leads)
                
            except Exception as e:
                self.logger.error(f"Error extracting from {result['url']}: {str(e)}")
                continue
        
        return leads

    async def _deduplicate_leads(self, leads: List[Lead]) -> List[Lead]:
        """Remove duplicate leads based on email and company"""
        
        seen = set()
        unique_leads = []
        
        for lead in leads:
            # Create a unique identifier
            identifier = f"{lead.email}:{lead.company}".lower()
            
            if identifier not in seen:
                seen.add(identifier)
                unique_leads.append(lead)
        
        return unique_leads

    async def _score_lead(self, lead: Lead, criteria: LeadCriteria) -> float:
        """AI-powered lead scoring based on criteria match"""
        
        prompt = f"""
        Score this lead from 0-100 based on how well they match the ideal customer criteria:
        
        Lead Information:
        - Name: {lead.first_name} {lead.last_name}
        - Job Title: {lead.job_title}
        - Company: {lead.company}
        - Industry: {lead.industry}
        - Company Size: {lead.company_size}
        - Location: {lead.location}
        
        Target Criteria:
        - Industry: {criteria.industry}
        - Company Size: {criteria.company_size}
        - Location: {criteria.location}
        - Job Titles: {criteria.job_titles}
        - Keywords: {criteria.keywords}
        - Technologies: {criteria.technologies}
        
        Consider:
        1. Job title match (40 points)
        2. Industry match (25 points)
        3. Company size match (15 points)
        4. Location match (10 points)
        5. Technology/keyword relevance (10 points)
        
        Return only the numeric score (0-100).
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            score_text = response.choices[0].message.content.strip()
            score = float(re.search(r'\d+', score_text).group())
            return min(max(score, 0), 100)  # Clamp between 0-100
            
        except Exception as e:
            self.logger.error(f"Error scoring lead: {str(e)}")
            return 50.0  # Default neutral score

    def _get_quality_level(self, score: float) -> LeadQuality:
        """Convert numeric score to quality level"""
        
        if score >= 80:
            return LeadQuality.HOT
        elif score >= 60:
            return LeadQuality.WARM
        elif score >= 40:
            return LeadQuality.COLD
        else:
            return LeadQuality.UNQUALIFIED

    async def _generate_results_summary(self, leads: List[Lead], criteria: LeadCriteria) -> Dict[str, Any]:
        """Generate AI summary of search results"""
        
        prompt = f"""
        Analyze these lead generation results and provide insights:
        
        Search Criteria:
        {json.dumps(asdict(criteria), indent=2)}
        
        Results:
        - Total leads found: {len(leads)}
        - Hot leads: {len([l for l in leads if l.quality_level == LeadQuality.HOT])}
        - Warm leads: {len([l for l in leads if l.quality_level == LeadQuality.WARM])}
        - Cold leads: {len([l for l in leads if l.quality_level == LeadQuality.COLD])}
        - Average score: {sum(l.quality_score for l in leads) / len(leads) if leads else 0:.1f}
        
        Top companies: {list(set([l.company for l in leads[:10]]))}
        
        Provide:
        1. Quality assessment
        2. Industry distribution
        3. Geographic insights
        4. Recommended next actions
        5. Improvement suggestions
        
        Return as structured JSON.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {str(e)}")
            return {"summary": "Analysis unavailable"}

    async def get_leads(self, 
                       quality_filter: Optional[LeadQuality] = None,
                       status_filter: Optional[LeadStatus] = None,
                       source_filter: Optional[DataSource] = None,
                       limit: int = 100) -> List[Lead]:
        """Get leads with filtering options"""
        
        filtered_leads = list(self.leads.values())
        
        if quality_filter:
            filtered_leads = [l for l in filtered_leads if l.quality_level == quality_filter]
        
        if status_filter:
            filtered_leads = [l for l in filtered_leads if l.status == status_filter]
        
        if source_filter:
            filtered_leads = [l for l in filtered_leads if l.source == source_filter]
        
        # Sort by quality score (highest first)
        filtered_leads.sort(key=lambda x: x.quality_score, reverse=True)
        
        return filtered_leads[:limit]

    async def update_lead_status(self, lead_id: str, status: LeadStatus, notes: Optional[str] = None):
        """Update lead status and add notes"""
        
        if lead_id not in self.leads:
            raise ValueError(f"Lead {lead_id} not found")
        
        lead = self.leads[lead_id]
        lead.status = status
        lead.updated_at = datetime.now()
        
        if status == LeadStatus.CONTACTED:
            lead.contact_attempts += 1
            lead.last_contacted = datetime.now()
        
        if notes:
            lead.notes = notes
        
        self.logger.info(f"Updated lead {lead_id} status to {status.value}")

    async def export_leads(self, 
                          leads: List[Lead], 
                          format: str = "csv",
                          include_fields: Optional[List[str]] = None) -> str:
        """Export leads to various formats"""
        
        if format.lower() == "csv":
            return await self._export_to_csv(leads, include_fields)
        elif format.lower() == "json":
            return await self._export_to_json(leads, include_fields)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def _export_to_csv(self, leads: List[Lead], include_fields: Optional[List[str]] = None) -> str:
        """Export leads to CSV format"""
        
        if not leads:
            return ""
        
        # Default fields to include
        if not include_fields:
            include_fields = [
                'first_name', 'last_name', 'email', 'phone', 'job_title',
                'company', 'company_website', 'industry', 'location',
                'quality_score', 'quality_level', 'status', 'source'
            ]
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(include_fields)
        
        # Write data
        for lead in leads:
            lead_dict = asdict(lead)
            row = []
            for field in include_fields:
                value = lead_dict.get(field, '')
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                elif isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, 'value'):  # Enum
                    value = value.value
                row.append(str(value))
            writer.writerow(row)
        
        return output.getvalue()

    async def _export_to_json(self, leads: List[Lead], include_fields: Optional[List[str]] = None) -> str:
        """Export leads to JSON format"""
        
        export_data = []
        
        for lead in leads:
            lead_dict = asdict(lead)
            
            # Convert enums and datetime objects
            for key, value in lead_dict.items():
                if hasattr(value, 'value'):  # Enum
                    lead_dict[key] = value.value
                elif isinstance(value, datetime):
                    lead_dict[key] = value.isoformat()
            
            # Filter fields if specified
            if include_fields:
                lead_dict = {k: v for k, v in lead_dict.items() if k in include_fields}
            
            export_data.append(lead_dict)
        
        return json.dumps(export_data, indent=2)

# Data Source Client Classes

class WebScraper:
    def __init__(self):
        self.session = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )

    async def scrape_website(self, domain: str, criteria: LeadCriteria) -> List[Lead]:
        """Scrape a website for contact information"""
        
        leads = []
        
        # Common contact pages
        contact_pages = [
            f"https://{domain}/contact",
            f"https://{domain}/contact-us",
            f"https://{domain}/about",
            f"https://{domain}/team",
            f"https://{domain}/leadership"
        ]
        
        for url in contact_pages:
            try:
                page_leads = await self.extract_contacts_from_url(url, criteria)
                leads.extend(page_leads)
            except Exception as e:
                continue
        
        return leads

    async def extract_contacts_from_url(self, url: str, criteria: LeadCriteria) -> List[Lead]:
        """Extract contact information from a specific URL"""
        
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract emails
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', soup.text)
            
            # Extract names and titles from common patterns
            contacts = self._extract_contact_info(soup, emails)
            
            # Convert to Lead objects
            leads = []
            for contact in contacts:
                lead = self._create_lead_from_contact(contact, url, criteria)
                if lead:
                    leads.append(lead)
            
            return leads
            
        except Exception as e:
            raise Exception(f"Error scraping {url}: {str(e)}")

    def _extract_contact_info(self, soup: BeautifulSoup, emails: List[str]) -> List[Dict]:
        """Extract structured contact information from HTML"""
        
        contacts = []
        
        # Look for structured contact information
        for email in emails:
            contact = {'email': email}
            
            # Try to find name and title near email
            email_element = soup.find(string=re.compile(email))
            if email_element:
                parent = email_element.parent
                siblings = parent.find_all_next(string=True, limit=10)
                
                # Extract potential names and titles
                for text in siblings:
                    text = text.strip()
                    if len(text) > 2 and text not in email:
                        # Simple heuristics for names and titles
                        if any(title in text.lower() for title in ['ceo', 'president', 'director', 'manager', 'head']):
                            contact['job_title'] = text
                        elif len(text.split()) == 2 and text[0].isupper():
                            contact['name'] = text
            
            contacts.append(contact)
        
        return contacts

    def _create_lead_from_contact(self, contact: Dict, source_url: str, criteria: LeadCriteria) -> Optional[Lead]:
        """Create Lead object from extracted contact info"""
        
        try:
            # Parse name
            name_parts = contact.get('name', '').split() if contact.get('name') else ['', '']
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Extract company from domain
            domain = urlparse(source_url).netloc
            company = domain.replace('www.', '').split('.')[0].title()
            
            lead_id = f"lead_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(contact.get('email', ''))}"
            
            return Lead(
                id=lead_id,
                first_name=first_name,
                last_name=last_name,
                email=contact.get('email'),
                phone=contact.get('phone'),
                job_title=contact.get('job_title'),
                company=company,
                company_website=f"https://{domain}",
                company_size=None,
                industry=criteria.industry,
                location=criteria.location,
                linkedin_url=None,
                source=DataSource.WEBSITE_SCRAPING,
                quality_score=0.0,
                quality_level=LeadQuality.COLD,
                status=LeadStatus.NEW,
                notes=f"Found on {source_url}",
                tags=[],
                contact_attempts=0,
                last_contacted=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                custom_fields={}
            )
            
        except Exception as e:
            return None

class LinkedInScraper:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    async def search_professionals(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Search LinkedIn for professionals matching criteria"""
        
        if not self.api_key:
            return []
        
        # This would integrate with LinkedIn Sales Navigator API
        # For demo purposes, returning mock data
        
        leads = []
        
        # Mock implementation - replace with real LinkedIn API calls
        for i in range(min(max_results, 10)):
            lead = Lead(
                id=f"linkedin_lead_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                first_name=f"John{i}",
                last_name=f"Doe{i}",
                email=f"john.doe{i}@company{i}.com",
                phone=None,
                job_title=criteria.job_titles[0] if criteria.job_titles else "Manager",
                company=f"Company {i}",
                company_website=f"https://company{i}.com",
                company_size=criteria.company_size,
                industry=criteria.industry,
                location=criteria.location,
                linkedin_url=f"https://linkedin.com/in/john-doe{i}",
                source=DataSource.LINKEDIN,
                quality_score=0.0,
                quality_level=LeadQuality.COLD,
                status=LeadStatus.NEW,
                notes="Found via LinkedIn search",
                tags=["linkedin"],
                contact_attempts=0,
                last_contacted=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                custom_fields={}
            )
            leads.append(lead)
        
        return leads

class GoogleSearchClient:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Perform Google search and return results"""
        
        if not self.api_key:
            # Return mock results for demo
            return [
                {
                    'title': f'Result {i}',
                    'url': f'https://example{i}.com',
                    'snippet': f'Sample snippet for result {i}'
                }
                for i in range(max_results)
            ]
        
        # Real implementation would use Google Search API
        return []

class ApolloClient:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    async def search_people(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Search Apollo.io database for people"""
        
        if not self.api_key:
            return []
        
        # This would integrate with Apollo.io API
        # Implementation would go here
        return []

class ZoomInfoClient:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    async def search_contacts(self, criteria: LeadCriteria, max_results: int) -> List[Lead]:
        """Search ZoomInfo database for contacts"""
        
        if not self.api_key:
            return []
        
        # This would integrate with ZoomInfo API
        # Implementation would go here
        return []
