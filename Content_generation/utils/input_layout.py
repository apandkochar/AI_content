import requests
from bs4 import BeautifulSoup
import json
import openai

from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup

load_dotenv()

class LayoutExtractor:
    def __init__(self):
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/91.0.4472.124 Safari/537.36')
        }
    def extract_layout(self, url, research_context: str = ""):
        """Extract document structure and generate layout instructions to be used for content generation."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code} for URL: {url}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted tags
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            
            # Try multiple selectors to find the main content
            main_content = (soup.find('article') or 
                          soup.find('div', class_='main-content') or 
                          soup.find('div', id='main') or 
                          soup.body)
            
            if not main_content:
                print("Error: No main content container found.")
                return None
            
            # Extract the structure and writing style
            structure = []
            writing_style = {
                'tone': '',
                'sentence_length': [],
                'paragraph_length': [],
                'transition_words': set(),
                'technical_terms': set(),
                'formatting': set()
            }
            
            # Common transition words to track
            transition_words = {'however', 'therefore', 'furthermore', 'moreover', 'consequently', 
                              'additionally', 'in addition', 'first', 'second', 'finally', 'in conclusion'}
            
            for element in main_content.find_all(recursive=True):
                element_data = None
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    text = element.get_text().strip()
                    if text:
                        element_data = {
                            'type': 'heading',
                            'level': element.name.upper(),
                            'text': text,
                            'position': len(structure) + 1
                        }
                elif element.name in ['ul', 'ol']:
                    items = [li.get_text().strip() for li in element.find_all('li')]
                    if items:
                        element_data = {
                            'type': 'list',
                            'list_type': 'unordered' if element.name == 'ul' else 'ordered',
                            'items': items,
                            'position': len(structure) + 1
                        }
                        writing_style['formatting'].add('lists')
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        # Analyze writing style
                        sentences = text.split('. ')
                        writing_style['sentence_length'].append(len(sentences))
                        writing_style['paragraph_length'].append(len(text.split()))
                        
                        # Track transition words
                        for word in transition_words:
                            if word.lower() in text.lower():
                                writing_style['transition_words'].add(word)
                        
                        # Track technical terms (words with numbers or special characters)
                        words = text.split()
                        technical_terms = [w for w in words if any(c.isdigit() or not c.isalnum() for c in w)]
                        writing_style['technical_terms'].update(technical_terms)
                        
                        element_data = {
                            'type': 'paragraph',
                            'text': text,
                            'position': len(structure) + 1
                        }
                
                if element_data:
                    structure.append(element_data)

            if not structure:
                print("Warning: No structured layout elements found.")
                return None

            # Calculate average sentence and paragraph lengths
            avg_sentence_length = sum(writing_style['sentence_length']) / len(writing_style['sentence_length']) if writing_style['sentence_length'] else 0
            avg_paragraph_length = sum(writing_style['paragraph_length']) / len(writing_style['paragraph_length']) if writing_style['paragraph_length'] else 0

            # Generate layout instructions using OpenAI
            layout_prompt = f"""
            Analyze this content structure and create a detailed layout template that preserves the exact writing style and structure:

            Content Structure:
            {json.dumps(structure, indent=2)}

            Writing Style Analysis:
            - Average sentence length: {avg_sentence_length:.1f} sentences per paragraph
            - Average paragraph length: {avg_paragraph_length:.1f} words per paragraph
            - Common transition words: {', '.join(writing_style['transition_words'])}
            - Technical terms usage: {len(writing_style['technical_terms'])} unique technical terms
            - Formatting elements: {', '.join(writing_style['formatting'])}

            Research Context:
            {research_context if research_context else "No research context provided."}

            Create a detailed layout template that:
            1. Follows the EXACT same structure as the original content
            2. Maintains the same writing style, including:
               - Sentence and paragraph lengths
               - Use of transition words
               - Technical terminology level
               - Formatting elements (lists, headings, etc.)
            3. Preserves the flow and progression of ideas
            4. Includes specific instructions for each section
            5. Incorporates relevant information from the research context where appropriate

            Return ONLY a JSON array where each element is a dictionary with these keys:
            - "section": The section name or heading
            - "content": Detailed instructions for that section, including:
              * Writing style requirements
              * Structure requirements
              * Content organization
              * Key points to cover
              * Formatting guidelines
              * Relevant research context to incorporate

            The layout should be so detailed that when given to another LLM with a topic and context, it will generate content that matches the original article's structure and style exactly, just with different content.

            Return only the JSON array.
            """

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing content structure and creating detailed layout templates that preserve writing style."},
                    {"role": "user", "content": layout_prompt}
                ],
                temperature=0.3
            )

            try:
                # Parse the GPT response into JSON
                layout_json = json.loads(response.choices[0].message.content.strip())
                
                # Ensure it's a list of dictionaries with 'section' and 'content' keys
                if not isinstance(layout_json, list):
                    raise ValueError("Layout must be a list")
                
                for item in layout_json:
                    if not isinstance(item, dict) or 'section' not in item or 'content' not in item:
                        raise ValueError("Each layout item must be a dictionary with 'section' and 'content' keys")
                
                return layout_json

            except json.JSONDecodeError:
                print("Error: Could not parse layout instructions")
                return []
            except ValueError as e:
                print(f"Error: {str(e)}")
                return []

        except Exception as e:
            print(f"Error extracting layout: {e}")
            return []

        
    @staticmethod
    def custom_layout(user_input: str, search_context: str, additional_info: str = "") -> list:
        """
        Create a custom layout based on user instructions and research context.
        
        This function handles two scenarios:
        1. When users provide specific layout instructions
        2. When users provide a complete blog/article text, and we want to extract its layout structure
        
        Args:
            user_input: User's custom layout instructions or a complete blog/article text
            search_context: Research information from search results
            additional_info: Optional additional information provided by user (defaults to empty string)
        """
        # Determine if the user_input is a complete article or just instructions
        # If it's longer than 500 characters and contains multiple paragraphs, it's likely a complete article
        is_complete_article = len(user_input) > 500 and user_input.count('\n\n') > 1
        
        if is_complete_article:
            # Extract layout from the complete article
            prompt = f"""
            You are an expert at analyzing content structure and creating detailed layout templates.
            
            I've provided you with a complete article on a similar topic. Your task is to:
            1. Analyze the structure and organization of this article
            2. Extract the layout pattern (headings, sections, flow)
            3. Create a new layout template based on this structure
            4. DO NOT copy any specific content, facts, or examples from the article
            
            Here's the article to analyze:
            ```
            {user_input}
            ```
            
            Research Context (use this to inform your layout decisions):
            ```
            {search_context}
            ```
            
            Additional Information:
            ```
            {additional_info}
            ```
            
            Create a detailed layout template that:
            1. Follows the EXACT same structure as the provided article
            2. Maintains the same writing style and flow
            3. Preserves the progression of ideas
            4. Incorporates relevant information from the research context
            5. Includes specific instructions for each section
            
            Return ONLY a JSON array where each element is a dictionary with these keys:
            - "section": The section name or heading
            - "content": Detailed instructions for that section, including:
              * Writing style requirements
              * Structure requirements
              * Content organization
              * Key points to cover
              * Formatting guidelines
              * Relevant research context to incorporate
            
            The layout should be so detailed that when given to another LLM with a topic and context, 
            it will generate content that matches the original article's structure and style exactly, 
            just with different content.
            
            Return only the JSON array.
            """
        else:
            # Process as user instructions
            prompt = f"""
            You are a professional technical content writer. You will be provided with:

            1. **Content Layout Instructions:**  
            {user_input}

            2. **Research Context:**  
            {search_context}

            3. **Additional Information:**
            {additional_info}

            Your task is to create a structured layout that:
            - Incorporates the user's layout instructions
            - Effectively organizes the research information
            - Properly integrates any additional information provided
            - Creates a logical flow of information
            - Provides detailed instructions for each section
            
            Return ONLY a JSON array where each element is a dictionary with these keys:
            - "section": The section name or heading
            - "content": Detailed instructions for that section, including:
              * Writing style requirements
              * Structure requirements
              * Content organization
              * Key points to cover
              * Formatting guidelines
              * Relevant research context to incorporate
            
            The layout should be so detailed that when given to another LLM with a topic and context, 
            it will generate content that follows the user's instructions exactly.
            
            Return only the JSON array.
            """
        
        try:
            response = openai.ChatCompletion.create(
                model='gpt-4',
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing content structure and creating detailed layout templates."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            layout_text = response.choices[0].message.content.strip()
            try:
                layout_json = json.loads(layout_text)
                
                # Validate the layout structure
                if not isinstance(layout_json, list):
                    raise ValueError("Layout must be a list")
                
                for item in layout_json:
                    if not isinstance(item, dict) or 'section' not in item or 'content' not in item:
                        raise ValueError("Each layout item must be a dictionary with 'section' and 'content' keys")
                
                return layout_json
            except json.JSONDecodeError:
                print("⚠️ Failed to parse custom layout into JSON.")
                return []
            except ValueError as e:
                print(f"⚠️ Layout validation error: {str(e)}")
                return []
        except Exception as e:
            print(f"Error generating custom layout: {e}")
            return []

    def default_layout(self, topic: str, title: str, content_type: str, search_context) -> str:
        """
        Generates a default layout based on the content type (e.g., Blog, Use Case, Case Study).
        Returns a structured layout in Markdown format.
        """
        # Normalize the content type: convert to lowercase and handle both space and underscore formats
        ct = content_type.lower().strip().replace('_', ' ')
        
        # Define the default layout prompts based on the content type
        if ct == "blog":
            prompt = f'''
            You are an expert technical content strategist with 15+ years of experience in content creation. Your task is to create a structured layout for a technical blog on the topic: {topic} with the title: {title}. You can use {search_context} for additional information.
            
            Follow these guidelines precisely:

            1. **Introduction:**  
            - Provide a compelling introduction that hooks the reader with a surprising statistic or industry insight
            - Explain why this topic is critically important in the current industry landscape
            - Establish your expertise and authority on this subject
            - Preview the key insights readers will gain in 250-300 words

            2. **Five Subsections:**  
            For each subsection, include:
            - **Title:** A creative, attention-grabbing, and SEO-optimized title that demonstrates industry expertise. The title must be highly relevant to the topic "{topic}" and the reference title "{title}".  
            - **Description:** A detailed explanation of the subsection's focus that delves deeply into the subject. Incorporate:
                * Real-world examples from your "industry experience"
                * Specific data points, statistics, and research findings
                * Analysis of industry trends and developments
                * Comparison of different approaches or solutions
                * Insights on common misconceptions or challenges
                * Forward-looking perspectives on industry evolution
            - **Length:** Each section should be 100-150 words in the outline

            3. **Conclusion:**  
            - Synthesize the key insights and their practical implications
            - Connect the insights to broader industry trends and developments
            - Provide actionable recommendations or next steps
            - End with a forward-looking perspective on the topic's future
            - Length: around 120-150 words

            Output the final layout in a clear, structured format with SEO optimization. Include proper formatting for headings, subsections, and bullet points where needed.
            
            Please output the final layout as a valid JSON array. Each element in the array must be a JSON object with two keys:
            "section": (the section name) and "content": (the detailed description for that section).
            Return only the JSON array.
            '''
        
        elif ct == "use case":
            prompt = f'''
            You are an expert technical content strategist with 15+ years of experience in creating detailed use cases. Your task is to create a structured layout for a technical use case on the topic: {topic} with the title: {title}. 
            
            Make the use case highly descriptive and based on a real-world example such as a technical failure or problem in a specific industry component. Focus particularly on the industry context from {search_context}.
            
            Follow these guidelines precisely:

            1. **Introduction:**  
            - Provide a compelling introduction that sets the context for this specific industry challenge
            - Explain why this problem is significant and what readers will learn from this use case
            - Establish your expertise in this industry and with this type of technical challenge
            - Preview the key insights and solutions readers will discover in 150-200 words

            2. **Five Subsections:**  
            For each subsection, include:
            - **Title:** A creative, attention-grabbing, and SEO-optimized title that demonstrates industry expertise. The title must be highly relevant to the topic "{topic}" and the reference title "{title}".  
            - **Description:** A detailed explanation of the subsection's focus that delves deeply into the subject. Incorporate:
                * Specific details about the technical challenge or failure
                * Real-world examples from your "industry experience"
                * Specific data points, statistics, and research findings
                * Analysis of why this problem occurs and its impact
                * Comparison of different potential solutions
                * Step-by-step explanation of the recommended approach
                * Results and outcomes with quantifiable metrics
            - **Length:** Each section should be 100-150 words in the outline

            3. **Conclusion:**  
            - Synthesize the key insights and lessons learned
            - Provide actionable recommendations for preventing similar issues
            - Connect the insights to broader industry best practices
            - End with a forward-looking perspective on industry evolution
            - Length: around 120 words

            Output the final layout in a clear, structured format with SEO optimization. Include proper formatting for headings, subsections, and bullet points where needed.
            
            Please output the final layout as a valid JSON array. Each element in the array must be a JSON object with two keys:
            "section": (the section name) and "content": (the detailed description for that section).
            Return only the JSON array.
            '''

        elif ct == "case study":
            prompt = f'''
            You are an expert technical content strategist with 15+ years of experience in creating detailed case studies. Create a practical, results-driven case study layout about '{topic}' titled "{title}",
            using the context: {search_context} 
            
            Follow this comprehensive structure:
            
            1. **Executive Summary** 
            - Quick snapshot of the case, industry, and the core problem solved
            - One-line impact statement with quantifiable results
            - Key stakeholders and their roles
            
            2. **Client Background (Industry Context)** 
            - Detailed introduction of the industry sector and its current challenges
            - Specific environmental factors affecting this client
            - Relevant operational setup with specific details (e.g., number of sites, technical workforce size)
            - Client's position in the market and competitive landscape
            
            3. **The Challenge** 
            - Detailed description of the specific business or technical issues they were facing
            - Quantification of the problem's impact (cost, time, resources)
            - Previous attempts to solve the problem and why they failed
            - Stakeholders affected and their specific pain points
            
            4. **The Solution** 
            - Introduction of the company and their specific solution implemented
            - Detailed description of the deployment:
                * Specific devices used with technical specifications
                * Technologies included with detailed explanation of integration
                * AR features leveraged with specific use cases
            - Include a conceptual architecture diagram description
            - Explain the decision-making process and why this solution was chosen
            
            5. **Implementation Process** 
            - Detailed timeline with specific dates and milestones
            - Teams involved with their specific roles and responsibilities
            - Key milestones with quantifiable deliverables
            - Challenges encountered during implementation and how they were overcome
            
            6. **Results & Impact** 
            - Quantifiable outcomes with specific metrics:
                * ROI calculations
                * Time savings
                * Cost reductions
                * Quality improvements
            - Before vs After snapshot with specific data points
            - Long-term benefits and strategic advantages gained
            
            7. **Insights & Takeaways** 
            - Success factors with specific examples
            - Challenges overcome with detailed explanations
            - Lessons learned that could benefit similar organizations
            - Best practices identified during the implementation
            
            8. **Looking Ahead** 
            - Plans for broader integration with specific next steps
            - Potential for scaling the solution
            - Future innovations and enhancements planned
            - Industry trends that align with this solution
            
            9. **Detailed Conclusion** 
            - Synthesis of key findings and their implications
            - Broader industry context and relevance
            - Final assessment of the solution's effectiveness
            
            10. **Call to Action**
            - Specific next steps for readers interested in this solution
            - Contact information or resources for further information
            - Invitation to discuss similar challenges
            
            Please output the final layout as a valid JSON array. Each element in the array must be a JSON object with two keys:
            "section": (the section name) and "content": (the detailed description for that section).
            Return only the JSON array.            
            '''

        else:
            # Add additional logging to help diagnose issues
            print(f"Received content_type: '{content_type}', normalized to: '{ct}'")
            raise ValueError(f"Unsupported content type: {content_type}")

        # Send the prompt to OpenAI GPT-4
        chat = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role":"user","content":prompt}],
            temperature=0.4
        )
        layout_text = chat.choices[0].message.content.strip()
        try:
            layout_json = json.loads(layout_text)
            return layout_json
        except json.JSONDecodeError:
            print("⚠️ Failed to parse default layout into JSON.")
            return []

def safely_parse_layout(layout_raw: str):
    """Safely parse a layout string into a list of dictionaries."""
    if not layout_raw or not isinstance(layout_raw, str):
        raise ValueError("Layout must be a non-empty string")
    
    try:
        parsed = json.loads(layout_raw)
        # Handle double-encoded JSON
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
            
        if not isinstance(parsed, list):
            raise ValueError("Layout must be a list")
            
        # Validate and normalize each item in the layout
        normalized_layout = []
        for item in parsed:
            if not isinstance(item, dict):
                raise ValueError("Each layout item must be a dictionary")
                
            # Convert old format to new format if needed
            if 'section' in item and 'content' in item:
                normalized_layout.append({
                    'type': 'section',
                    'text': f"{item['section']}: {item['content']}",
                    'level': 'H2'
                })
            elif 'type' in item:
                if 'text' not in item:
                    item['text'] = ''
                if 'level' not in item:
                    item['level'] = 'H2'
                normalized_layout.append(item)
            else:
                raise ValueError("Layout items must have either 'section' and 'content' or 'type' and 'text' fields")
                
        return normalized_layout
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid layout JSON: {str(e)}")