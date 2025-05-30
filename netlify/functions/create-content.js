// netlify/functions/create-content.js

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
      title, 
      content_type, 
      target_audience, 
      key_messages, 
      platform, 
      tone = 'professional',
      length = 'medium',
      keywords = [],
      cta 
    } = body;

    // Validate required fields
    if (!title || !content_type || !target_audience || !key_messages || !platform) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Missing required fields' }),
      };
    }

    // Create prompt for content generation
    let prompt = `Create ${content_type} content for ${platform} platform.
Target Audience: ${target_audience}
Tone: ${tone}
Length: ${length}
Key Messages: ${key_messages.join(', ')}`;

    if (keywords.length > 0) {
      prompt += `\nKeywords to include: ${keywords.join(', ')}`;
    }

    if (cta) {
      prompt += `\nCall to Action: ${cta}`;
    }

    prompt += `\n\nCreate engaging content with:
1. Compelling headline/title
2. Main content body
3. Call-to-action
4. Relevant hashtags or tags

Format as JSON with keys: title, content, cta, tags`;

    // Generate content using OpenAI
    const completion = await openai.createChatCompletion({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: 'You are an expert content creator. Always respond with valid JSON.',
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      temperature: 0.7,
      max_tokens: 2000,
    });

    const generatedContent = completion.data.choices[0].message.content;
    
    let contentData;
    try {
      contentData = JSON.parse(generatedContent);
    } catch (parseError) {
      // Fallback if JSON parsing fails
      contentData = {
        title: title,
        content: generatedContent,
        cta: cta || 'Learn more',
        tags: keywords
      };
    }

    // Calculate simple quality scores
    const contentText = JSON.stringify(contentData);
    const keywordMentions = keywords.reduce((count, keyword) => {
      return count + (contentText.toLowerCase().match(new RegExp(keyword.toLowerCase(), 'g')) || []).length;
    }, 0);

    const seoScore = Math.min(100, Math.max(50, 70 + keywordMentions * 5));
    const wordCount = contentText.split(' ').length;
    const readabilityScore = (wordCount >= 300 && wordCount <= 800) ? 85 : 70;

    const response = {
      content_id: `content_${Date.now()}_${content_type}`,
      content: contentData,
      seo_score: seoScore,
      readability_score: readabilityScore,
      engagement_prediction: 0.7,
      status: 'draft',
      created_at: new Date().toISOString()
    };

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(response),
    };

  } catch (error) {
    console.error('Error creating content:', error);
    
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ 
        error: 'Failed to create content',
        details: error.message 
      }),
    };
  }
};
