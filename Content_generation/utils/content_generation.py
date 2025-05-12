import os
import openai
from dotenv import load_dotenv
from utils.search_engine import get_final_result  
from utils.input_layout import LayoutExtractor

# Load environment variables and set the OpenAI API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Instantiate layout extractor
le = LayoutExtractor()

def generate_content(topic, title, research_info, layout, content_type, tone, additional_info=""):
    # Define tone-specific characteristics
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
   - Present information confidently

3. Structure:
   - Well-organized content
   - Clear progression of ideas
   - Proper use of examples
   - Effective use of data and statistics

4. Style:
   - Authoritative but approachable
   - Focus on solutions and outcomes
   - Include relevant case studies
   - Maintain professional credibility""",
        
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
   - Avoid stiff corporate jargon

3. Structure:
   - Break up text with white space
   - Use bullet points for easy scanning
   - Include engaging transitions
   - Keep paragraphs focused and brief

4. Approach:
   - Informal but professional
   - Friendly and approachable
   - Encourage reader interaction
   - Use examples and scenarios""",
        
        "formal": """
FORMAL TONE REQUIREMENTS:
1. Language:
   - Use complete words (avoid contractions)
   - Maintain professional vocabulary
   - Follow proper grammar rules
   - Use precise and measured language

2. Structure:
   - Clear hierarchical organization
   - Well-defined sections
   - Logical flow of information
   - Proper transitions between ideas

3. Style:
   - Objective and impartial
   - Avoid colloquialisms
   - Use passive voice when appropriate
   - Maintain professional distance

4. Format:
   - Consistent formatting
   - Proper citations and references
   - Clear headings and subheadings
   - Professional presentation""",
        
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
   - Professional but not overly formal

3. Structure:
   - Well-organized content
   - Clear progression of ideas
   - Proper use of examples
   - Effective use of data and statistics

4. Style:
   - Authoritative but approachable
   - Focus on solutions and outcomes
   - Include relevant case studies
   - Maintain professional credibility""",
        
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
   - Use positive language

3. Structure:
   - Easy-to-follow format
   - Engaging examples
   - Clear explanations
   - Helpful tips and suggestions

4. Style:
   - Supportive and encouraging
   - Use analogies and examples
   - Include personal touches
   - Make complex topics accessible"""
    }

    # Get the specific tone characteristics
    tone_guide = tone_characteristics.get(tone.lower(), tone_characteristics["professional"])
    
    # Combine research info and additional info
    combined_info = f"""
    RESEARCHED INFORMATION:
    {research_info}
    
    ADDITIONAL INFORMATION (Provided by user - include exactly as written):
    {additional_info}
    """
    
    # Normalize content type
    content_type = content_type.lower().replace(" ", "_")
    if content_type not in ["blog", "use_case", "case_study"]:
        raise ValueError(f"Invalid content type: {content_type}")
    
    # Convert layout into readable format
    layout_description = "\n".join([
        f"{item.get('section', item.get('type', 'section')).capitalize()}: {item.get('content', item.get('text', ''))}"
        for item in layout
    ])

    # Determine industry and expertise level based on topic and research
    industry_prompt = f"""
    Based on the topic "{topic}" and the research information provided, determine:
    1. The specific industry this content relates to
    2. The level of expertise required (e.g., entry-level, mid-level, senior expert)
    3. The target audience's technical knowledge level
    4. Key industry challenges and trends related to this topic
    5. Relevant frameworks, methodologies, or standards in this industry
    
    Then, write this content as if you are a {content_type.replace("_", " ")} expert with 15+ years of experience in this specific industry.
    """

    # Enhanced system prompt with industry expertise
    system_prompt = f"""You are an expert content writer with deep industry expertise. Your task is to generate high-quality, well-structured content that demonstrates authoritative knowledge and insights.

CRITICAL REQUIREMENTS:
1. Word Count: Generate EXACTLY 2000-2400 words total
2. Section Length: Each section must be 250-400 words
3. Structure: Follow the provided layout exactly
4. Format: Use proper headings, subheadings, and lists
5. Tone: Follow the specified tone characteristics precisely
6. Quality: Include specific data, examples, and statistics
7. Research: Integrate provided research naturally
8. Accuracy: Ensure all information is factual and current
9. Detail: Provide comprehensive explanations for all concepts, especially technical processes
10. Accessibility: Make complex topics understandable to non-technical readers
11. Expertise: Demonstrate deep industry knowledge and insights
12. Authenticity: Include "first-hand" observations and experiences
13. DO NOT include word count annotations within sections"""

    # Enhanced user prompt with industry context
    user_prompt = f"""Generate a {content_type.replace("_", " ")} about "{topic}" titled "{title}".

{industry_prompt}

{tone_guide}

CONTENT STRUCTURE:
1. Introduction (300-400 words):
   - Hook the reader with a compelling industry insight or statistic
   - Explain topic significance in the current industry context
   - Preview key points with a focus on practical value
   - Establish your expertise and authority on this topic

2. Main Content:
   Follow this exact layout:
{layout_description}

3. Research Integration:
{combined_info}

4. Formatting Requirements:
   - Use clear headings and subheadings
   - Include bullet points for lists
   - Use numbered lists for steps/processes especially when there is any implementation process or any  other section which requres step by step explaination ok
   - Break up text with white space 
   - DO NOT include word count annotations within sections

5. Expertise Enhancements:
   - Include specific industry examples and case studies
   - Reference current industry trends and developments
   - Mention relevant tools, technologies, or methodologies
   - Share "insights from experience" that demonstrate expertise
   - Compare different approaches or solutions with pros/cons
   - Address common misconceptions in the industry
   - Provide forward-looking perspectives on industry evolution

Remember:
- Total length: 2000-2400 words
- Each section: atleast 250-400 words
- Follow layout exactly
- Maintain {tone} tone throughout
- Follow all tone-specific characteristics above
- Provide detailed, comprehensive explanations for all concepts
- Make technical processes understandable to non-technical readers
- For process sections, include step-by-step explanations with clear details
- Use examples, analogies, and visual descriptions to enhance understanding
- Demonstrate deep industry expertise and insights throughout"""

    try:
        print(f"Generating content for topic: {topic}, title: {title}")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        generated_content = response.choices[0].message.content.strip()
        print(f"Content generated successfully: {len(generated_content)} characters")
        return generated_content

    except Exception as e:
        print(f"❌ Error in generate_content(): {e}")
        return ""

# Wrapper functions for each content type
def usecase_generation(topic, title, research_info, layout, tone, additional_info=""):
    return generate_content(topic, title, research_info, layout, "use_case", tone, additional_info)

def blog_generation(topic, title, research_info, layout, tone, additional_info=""):
    return generate_content(topic, title, research_info, layout, "blog", tone, additional_info)

def cs_generation(topic, title, research_info, layout, tone, additional_info=""):
    return generate_content(topic, title, research_info, layout, "case_study", tone, additional_info)


