// netlify/functions/send-email.js

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
      action,
      name,
      email_type,
      content_brief,
      target_audience = 'general',
      email,
      first_name,
      last_name,
      company
    } = body;

    if (action === 'create_template') {
      // Create email template
      if (!name || !email_type || !content_brief) {
        return {
          statusCode: 400,
          headers,
          body: JSON.stringify({ error: 'Missing required fields for template creation' }),
        };
      }

      // Email type specifications
      const typeSpecs = {
        welcome: {
          purpose: 'Welcome new subscribers and set expectations',
          tone: 'friendly and welcoming',
          structure: 'greeting, value proposition, next steps, contact info'
        },
        nurture: {
          purpose: 'Educate and build relationship with prospects',
          tone: 'helpful and educational',
          structure: 'valuable content, insights, soft CTA'
        },
        promotional: {
          purpose: 'Drive sales and conversions',
          tone: 'persuasive and urgent',
          structure: 'attention-grabbing headline, offer details, strong CTA'
        }
      };

      const specs = typeSpecs[email_type] || typeSpecs.nurture;

      const templatePrompt = `Create an email template for ${email_type} email:

Content Brief: ${content_brief}
Target Audience: ${target_audience}
Purpose: ${specs.purpose}
Tone: ${specs.tone}
Structure: ${specs.structure}

Generate:
1. Subject line (compelling, under 50 characters)
2. HTML email content (responsive design)
3. Plain text version
4. List of personalization variables ({{variable_name}} format)

Format as JSON:
{
  "subject": "subject line",
  "html": "complete HTML email",
  "text": "plain text version",
  "variables": ["first_name", "company", etc.]
}`;

      const completion = await openai.createChatCompletion({
        model: 'gpt-4',
        messages: [
          {
            role: 'system',
            content: 'You are an expert email marketing copywriter. Always respond with valid JSON.',
          },
          {
            role: 'user',
            content: templatePrompt,
          },
        ],
        temperature: 0.7,
        max_tokens: 2500,
      });

      let templateContent;
      try {
        templateContent = JSON.parse(completion.data.choices[0].message.content);
      } catch (parseError) {
        templateContent = {
          subject: `${email_type.charAt(0).toUpperCase() + email_type.slice(1)} Email`,
          html: `<h1>${email_type.charAt(0).toUpperCase() + email_type.slice(1)}</h1><p>${content_brief}</p>`,
          text: `${email_type.charAt(0).toUpperCase() + email_type.slice(1)}\n\n${content_brief}`,
          variables: ['first_name', 'company']
        };
      }

      const response = {
        template_id: `template_${email_type}_${Date.now()}`,
        name: name,
        email_type: email_type,
        subject_line: templateContent.subject,
        html_content: templateContent.html,
        text_content: templateContent.text,
        variables: templateContent.variables,
        created_at: new Date().toISOString()
      };

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(response),
      };

    } else if (action === 'add_contact') {
      // Add email contact
      if (!email) {
        return {
          statusCode: 400,
          headers,
          body: JSON.stringify({ error: 'Email is required' }),
        };
      }

      const contactId = `contact_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      const response = {
        contact_id: contactId,
        email: email,
        first_name: first_name || '',
        last_name: last_name || '',
        company: company || '',
        tags: [],
        subscribed: true,
        created_at: new Date().toISOString()
      };

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(response),
      };

    } else {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Invalid action. Use "create_template" or "add_contact"' }),
      };
    }

  } catch (error) {
    console.error('Error in email function:', error);
    
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ 
        error: 'Email function failed',
        details: error.message 
      }),
    };
  }
};
