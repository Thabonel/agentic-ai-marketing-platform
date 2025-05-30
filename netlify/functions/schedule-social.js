// netlify/functions/schedule-social.js

const { Configuration, OpenAIApi } = require('openai');

const configuration = new Configuration({
  apiKey: process.env.OPENAI_API_KEY,
});
const openai = new OpenAIApi(configuration);

exports.handler = async (event, context) => {
  // Handle CORS
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
  };

  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: '',
    };
  }

  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method not allowed' }),
    };
  }

  try {
    const body = JSON.parse(event.body);
    const { 
      platform, 
      content, 
      scheduled_time, 
      media_urls = [], 
      hashtags = [] 
    } = body;

    // Validate required fields
    if (!platform || !content || !scheduled_time) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Missing required fields: platform, content, scheduled_time' }),
      };
    }

    // Optimize content for specific platform using AI
    const optimizationPrompt = `Optimize this content for ${platform}:
"${content}"

Platform requirements:
- LinkedIn: Professional tone, up to 3000 chars, business-focused
- Twitter: Concise, up to 280 chars, engaging
- Facebook: Conversational, up to 2000 chars, community-focused
- Instagram: Visual-first, up to 2200 chars, lifestyle-oriented

Return only the optimized content, no explanations.`;

    const completion = await openai.createChatCompletion({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: `You are a ${platform} content optimization expert.`,
        },
        {
          role: 'user',
          content: optimizationPrompt,
        },
      ],
      temperature: 0.7,
      max_tokens: 500,
    });

    const optimizedContent = completion.data.choices[0].message.content.trim();

    // Apply platform-specific length limits
    const platformLimits = {
      twitter: 280,
      linkedin: 3000,
      facebook: 2000,
      instagram: 2200
    };

    const maxLength = platformLimits[platform.toLowerCase()] || 2000;
    const finalContent = optimizedContent.length > maxLength 
      ? optimizedContent.substring(0, maxLength - 3) + '...'
      : optimizedContent;

    // Create post response
    const postId = `post_${platform}_${Date.now()}`;
    const scheduledDate = new Date(scheduled_time);

    const response = {
      post_id: postId,
      platform: platform,
      content: finalContent,
      media_urls: media_urls,
      hashtags: hashtags,
      scheduled_time: scheduledDate.toISOString(),
      status: 'scheduled',
      created_at: new Date().toISOString(),
      engagement_metrics: {}
    };

    // In a real implementation, you would:
    // 1. Store the post in your database
    // 2. Set up actual scheduling with platform APIs
    // 3. Handle authentication with social media platforms

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(response),
    };

  } catch (error) {
    console.error('Error scheduling social post:', error);
    
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ 
        error: 'Failed to schedule social post',
        details: error.message 
      }),
    };
  }
};
