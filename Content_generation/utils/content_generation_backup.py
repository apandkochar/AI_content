import os
import re
import openai
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils.search_engine import get_final_result  
from utils.input_layout import LayoutExtractor

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Instantiate layout extractor
le = LayoutExtractor()

class ContentGenerator:
    def __init__(self):
        self.min_section_words = 300  # Minimum words per section
        self.max_section_words = 500  # Maximum words per section
        self.section_depth_requirements = {
            "implementation": {
                "description": "Step-by-step implementation details",
                "elements": [
                    "Numbered steps (1., 2., 3.)",
                    "Detailed explanation of each step",
                    "Required resources/tools",
                    "Timeline estimates",
                    "Potential challenges and solutions"
                ]
            },
            "technical": {
                "description": "In-depth technical explanations",
                "elements": [
                    "Clear definitions of terms",
                    "Technical specifications",
                    "Diagrams/visual descriptions",
                    "Real-world examples",
                    "Comparisons to similar technologies"
                ]
            }
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_content(self, topic: str, title: str, research: List[Dict], 
                        layout: List[Dict], content_type: str, tone: str) -> str:
        """
        Generates comprehensive technical content with:
        - Proper section depth
        - No word count markers
        - Step-by-step implementation details
        - Clear explanations for non-technical readers
        """
        # Validate inputs
        self._validate_inputs(content_type, tone, research)

        # Generate the content
        full_content = self._generate_full_content(topic, title, research, layout, content_type, tone)

        # Post-process and validate
        processed_content = self._post_process_content(full_content, layout)

        return processed_content

    def _validate_inputs(self, content_type: str, tone: str, research: List[Dict]):
        valid_content_types = ["blog", "use_case", "case_study"]
        valid_tones = ["technical", "professional", "conversational"]
        
        if content_type not in valid_content_types:
            raise ValueError(f"Invalid content type. Must be one of: {', '.join(valid_content_types)}")
        if tone not in valid_tones:
            raise ValueError(f"Invalid tone. Must be one of: {', '.join(valid_tones)}")
        if not research or len(research) < 3:
            raise ValueError("At least 3 research sources are required")

    def _generate_full_content(self, topic: str, title: str, research: List[Dict], 
                             layout: List[Dict], content_type: str, tone: str) -> str:
        system_prompt = self._create_system_prompt(topic, title, content_type, tone)
        user_prompt = self._create_user_prompt(research, layout)
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        return response.choices[0].message.content

    def _create_system_prompt(self, topic: str, title: str, content_type: str, tone: str) -> str:
        return f"""You are a senior technical writer creating a comprehensive {content_type} about "{topic}" titled "{title}".

MUST FOLLOW THESE RULES:
1. Depth & Detail:
   - Each main section: 300-500 words
   - Subsections: 150-300 words
   - Implementation sections: Detailed step-by-step breakdowns
   - Technical sections: Clear explanations with examples

2. Clarity:
   - Explain concepts for both technical and non-technical readers
   - Use analogies for complex ideas
   - Define acronyms on first use

3. Structure:
   - Follow the exact provided outline
   - Use Markdown formatting (##, ### headers)
   - Never show word counts
   - Use bullet points and numbered lists appropriately

4. Research Integration:
   - Naturally incorporate all provided research
   - Cite specific data points where applicable
   - Reference sources organically

5. Tone: Maintain a {tone} tone throughout:
   - Technical: Precise terminology, formal structure
   - Professional: Balanced expertise and clarity
   - Conversational: Engaging but informative"""

    def _create_user_prompt(self, research: List[Dict], layout: List[Dict]) -> str:
        research_context = "RESEARCH SOURCES:\n" + "\n\n".join(
            f"Source {i+1}: {src['title']}\n"
            f"URL: {src['href']}\n"
            f"Key Points: {src['snippet']}"
            for i, src in enumerate(research[:5])  # Use top 5 sources
        )

        layout_description = "CONTENT STRUCTURE:\n" + "\n".join(
            f"{section['type'].upper()}:\n"
            f"- Purpose: {section.get('purpose', 'General content')}\n"
            f"- Key Elements: {section.get('elements', 'All relevant aspects')}\n"
            f"- Depth: {self._get_depth_guidance(section['type'])}"
            for section in layout
        )

        return f"""Generate comprehensive content using these research sources and structure:

{research_context}

{layout_description}

SPECIAL INSTRUCTIONS:
1. For implementation/process sections:
   - Break into clear numbered steps (1., 2., 3.)
   - Explain each step thoroughly
   - Include required tools/resources
   - Add timing estimates
   - Describe potential challenges and solutions

2. For technical sections:
   - Start with simple explanations
   - Progress to deeper technical details
   - Use analogies for complex concepts
   - Include real-world examples
   - Reference research data where applicable

3. For all sections:
   - Write for both technical and non-technical audiences
   - Maintain consistent depth
   - Never show word counts
   - Use Markdown formatting properly"""

    def _get_depth_guidance(self, section_type: str) -> str:
        """Returns specific depth requirements for different section types"""
        section_type_lower = section_type.lower()
        for key in self.section_depth_requirements:
            if key in section_type_lower:
                return self.section_depth_requirements[key]["description"]
        return "Comprehensive coverage with examples and explanations"

    def _post_process_content(self, content: str, layout: List[Dict]) -> str:
        """Ensures content meets all quality standards"""
        # Remove word count markers
        content = re.sub(r"\(Word count: \d+\)", "", content)
        
        # Expand short sections
        sections = self._split_by_headings(content)
        processed_sections = []
        
        for i, section in enumerate(sections):
            header, body = section
            if self._section_needs_expansion(body, layout[i]['type'] if i < len(layout) else ""):
                expanded_body = self._expand_section(header, body, layout[i]['type'] if i < len(layout) else "")
                processed_sections.append((header, expanded_body))
            else:
                processed_sections.append((header, body))
        
        return "\n\n".join(f"{header}\n\n{body}" for header, body in processed_sections)

    def _split_by_headings(self, content: str) -> List[tuple]:
        """Splits content into (header, body) tuples"""
        sections = []
        current_header = ""
        current_body = []
        
        for line in content.split('\n'):
            if line.startswith('#'):
                if current_header:
                    sections.append((current_header, '\n'.join(current_body)))
                current_header = line
                current_body = []
            else:
                current_body.append(line)
        
        if current_header:
            sections.append((current_header, '\n'.join(current_body)))
        
        return sections

    def _section_needs_expansion(self, body: str, section_type: str) -> bool:
        """Determines if a section needs more detail"""
        word_count = len(body.split())
        min_words = self.min_section_words
        
        # Increase minimum for implementation/technical sections
        if "implementation" in section_type.lower():
            min_words = max(min_words, 400)
        elif "technical" in section_type.lower():
            min_words = max(min_words, 350)
            
        return word_count < min_words

    def _expand_section(self, header: str, body: str, section_type: str) -> str:
        """Adds depth to underdeveloped sections"""
        expansion_focus = ""
        if "implementation" in section_type.lower():
            expansion_focus = (
                "Provide more detailed step-by-step instructions. Break down each major step into sub-steps. "
                "Include required tools, estimated time for each step, potential challenges and solutions."
            )
        elif "technical" in section_type.lower():
            expansion_focus = (
                "Add deeper technical explanations. Include more examples, analogies, and comparisons. "
                "Describe underlying principles and reference any relevant standards or technologies."
            )
        else:
            expansion_focus = (
                "Expand with more detailed explanations. Add relevant examples, case studies, "
                "and practical applications. Ensure both technical and non-technical readers can understand."
            )
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Expand this section with {expansion_focus}:\n\n{header}\n{body}"
            }],
            temperature=0.2,
            max_tokens=1500
        )
        
        return response.choices[0].message.content.strip()
    
def generate_content(topic, title, research_info, layout, content_type, tone, additional_info=""):
    # Ensure title is properly formatted and distinct from topic
    if title == topic:
        # If title is the same as topic, format it as a proper title
        title = title.title()
    
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

    system_prompt = """You are an expert content writer specializing in creating detailed, comprehensive content. Your task is to generate high-quality, well-structured content that strictly follows the provided instructions and tone requirements.

CRITICAL REQUIREMENTS:
1. Word Count: Generate EXACTLY 2000-2400 words total
2. Section Length: Each section must be AT LEAST 250-400 words
3. Structure: Follow the provided layout exactly
4. Format: Use proper headings, subheadings, and lists
5. Tone: Follow the specified tone characteristics precisely
6. Quality: Include specific data, examples, and statistics
7. Research: Integrate provided research naturally
8. Accuracy: Ensure all information is factual and current
9. Detail: Provide comprehensive explanations for all concepts, especially technical processes
10. Accessibility: Make complex topics understandable to non-technical readers
11. DO NOT include word count annotations within sections
12. BULLET POINTS: Use bullet points extensively to break down complex information
13. NUMBERED LISTS: Use numbered lists for step-by-step processes
14. EXAMPLES: Include concrete examples for every major concept
15. DEPTH: Each section must provide in-depth coverage of its topic, not just 1-3 lines
16. EXPLANATIONS: Explain all technical terms and concepts in detail
17. VISUAL DESCRIPTIONS: Include visual descriptions to help readers understand complex processes"""

    user_prompt = f"""Generate a {content_type.replace("_", " ")} about "{topic}" titled "{title}".

{tone_guide}

CONTENT STRUCTURE:
1. Introduction (300 words):
   - Hook the reader
   - Explain topic significance
   - Preview key points

2. Main Content:
   Follow this exact layout:
{layout_description}

3. Research Integration:
{combined_info}

4. Formatting Requirements:
   - Use clear headings and subheadings
   - Include bullet points for lists
   - Use numbered lists for steps/processes
   - Break up text with white space
   - DO NOT include word count annotations within sections
   - Each section MUST use bullet points to break down information
   - Process sections MUST use numbered lists for step-by-step explanations

Remember:
- Total length: 2000-2400 words
- Each section: atleast 250-400 words
- Include word count ONLY at the end of the entire document
- Follow layout exactly
- Maintain {tone} tone throughout
- Follow all tone-specific characteristics above
- Provide detailed, comprehensive explanations for all concepts
- Make technical processes understandable to non-technical readers
- For process sections, include step-by-step explanations with clear details
- Use examples, analogies, and visual descriptions to enhance understanding
- NEVER provide just 1-3 lines for any section - each section must be detailed and comprehensive
- Use bullet points extensively to break down complex information
- Use numbered lists for all step-by-step processes
- Include concrete examples for every major concept
- Explain all technical terms and concepts in detail"""

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
