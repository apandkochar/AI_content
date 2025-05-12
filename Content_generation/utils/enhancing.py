import openai
import os
import time
import logging
from dotenv import load_dotenv
from openai.error import APIError, RateLimitError, APIConnectionError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def refine_content(
    generated_content: str,
    use_layout_instructions: bool,
    use_research_context: bool,
    layout: str,
    research_context: str,
    additional_instructions: str,
    tone: str,
) -> str:
    # Maximum number of retries for transient errors
    max_retries = 3
    retry_delay = 2  # seconds
    
    # Prepare context parts based on user's choices
    layout_part = f"Layout Instructions: {layout}" if use_layout_instructions else ""
    research_part = f"Research Context: {research_context}" if use_research_context else ""
    
    # Determine the tone characteristics based on the specified tone
    tone_characteristics = {
        "technical": """
TECHNICAL TONE REQUIREMENTS:
1. Precision & Accuracy:
   - Use exact technical terminology
   - Avoid colloquialisms and informal language
   - Include specific metrics and data points
   - Reference industry standards and protocols

2. Writing Style:
   - Use third-person perspective
   - Avoid "you" and "we"
   - Prefer passive constructions for objectivity
   - Include discipline-specific conventions
   - Maintain authority while being clear
   - Use industry-standard terminology
   - Present information confidently""",
        
        "conversational": """
CONVERSATIONAL TONE REQUIREMENTS:
1. Engagement:
   - Use direct address ("you," "we," "us")
   - Include rhetorical questions
   - Write as if having a discussion
   - Make it feel personal and relatable

2. Language Style:
   - Use contractions naturally
   - Keep sentences and paragraphs short
   - Use active voice
   - Avoid stiff corporate jargon""",
        
        "formal": """
FORMAL TONE REQUIREMENTS:
1. Language:
   - Use complete words (avoid contractions)
   - Maintain professional vocabulary
   - Follow proper grammar rules
   - Use precise and measured language

2. Style:
   - Objective and impartial
   - Avoid colloquialisms
   - Use passive voice when appropriate
   - Maintain professional distance""",
        
        "professional": """
PROFESSIONAL TONE REQUIREMENTS:
1. Approach:
   - Balance expertise with accessibility
   - Maintain authority while being clear
   - Use industry-standard terminology
   - Present information confidently

2. Language:
   - Clear and precise
   - Industry-appropriate terminology
   - Balanced use of active/passive voice
   - Professional but not overly formal""",
        
        "friendly": """
FRIENDLY TONE REQUIREMENTS:
1. Approach:
   - Warm and welcoming
   - Encouraging and supportive
   - Easy to understand
   - Relatable and down-to-earth

2. Language:
   - Use friendly, approachable terms
   - Include encouraging phrases
   - Keep it simple and clear
   - Use positive language"""
    }
    
    # Get the specific tone characteristics
    tone_guide = tone_characteristics.get(tone.lower(), tone_characteristics["professional"])
    
    # Compose refinement prompt
    prompt = f"""
You are an expert content refinement specialist. Your task is to carefully refine the content provided below while maintaining its core message and structure. Your goal is to enhance the content without fundamentally changing its meaning or purpose.

**CRITICAL REFINEMENT RULES:**
1. PRESERVE THE ORIGINAL TONE: Maintain the {tone} tone consistently throughout the content. Follow these tone characteristics:
{tone_guide}

2. RESPECT USER PREFERENCES: 
   - DO NOT change any content that the user has specifically indicated should remain unchanged
   - If additional_instructions mention specific sections to keep unchanged, preserve those sections exactly
   - Only enhance and polish the content, don't rewrite it completely

3. FOLLOW LAYOUT INSTRUCTIONS:
   - If layout instructions are provided, ensure the content follows the specified structure
   - Maintain the same headings and subheadings as in the original content
   - Preserve the original section order unless explicitly instructed otherwise

4. ENHANCEMENT GUIDELINES:
   - Improve clarity and readability without changing the core message
   - Fix grammar, punctuation, and spelling errors
   - Enhance transitions between sections for better flow
   - Ensure consistency in terminology and style
   - Integrate research information naturally where appropriate
   - Add bullet points and numbered lists to break down complex information
   - Make technical concepts more accessible to non-technical readers

**Generated Content to Refine:**
{generated_content}

**Layout Guidelines:**
{layout_part}

**Research Details:**
{research_part}

**Additional Instructions:**
{additional_instructions}

Your final version should:
- Maintain the exact same {tone} tone throughout the entire document
- Follow the layout instructions precisely (if provided)
- Integrate research information naturally (if provided)
- Preserve any sections that should remain unchanged
- Enhance readability and flow without changing the core message
- Use bullet points and numbered lists to break down complex information
- Make technical concepts more accessible to non-technical readers

Generate the final refined version of the content.
"""

    # Implement retry logic for transient errors
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to refine content (attempt {attempt+1}/{max_retries})")
            
            # Check if API key is available
            if not openai.api_key:
                raise ValueError("OpenAI API key is not set. Please check your environment variables.")
            
            # Make the API call
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": 
                    "You are an expert content refinement specialist. Your task is to carefully refine content while preserving its core message, tone, and structure. Follow the user's instructions precisely."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,  # Slightly higher temperature for more creative refinements
                max_tokens=4000
            )
            
            # Extract and validate the response
            refined_content = response.choices[0].message.content.strip()
            if not refined_content:
                raise ValueError("No content was generated")
                
            logger.info("Content refinement successful")
            return refined_content
            
        except RateLimitError as e:
            # Handle rate limiting - wait and retry
            wait_time = retry_delay * (attempt + 1)  # Exponential backoff
            logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds before retry. Error: {str(e)}")
            time.sleep(wait_time)
            
        except APIConnectionError as e:
            # Handle connection issues - wait and retry
            wait_time = retry_delay * (attempt + 1)
            logger.warning(f"API connection error. Waiting {wait_time} seconds before retry. Error: {str(e)}")
            time.sleep(wait_time)
            
        except APIError as e:
            # Handle other API errors
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                logger.warning(f"API error. Waiting {wait_time} seconds before retry. Error: {str(e)}")
                time.sleep(wait_time)
            else:
                logger.error(f"API error after {max_retries} attempts: {str(e)}")
                raise Exception(f"OpenAI API error: {str(e)}")
                
        except Exception as e:
            # Handle all other exceptions
            logger.error(f"Error in refine_content: {str(e)}")
            raise Exception(f"Error refining content: {str(e)}")
    
    # If we've exhausted all retries
    raise Exception(f"Failed to refine content after {max_retries} attempts due to persistent errors")