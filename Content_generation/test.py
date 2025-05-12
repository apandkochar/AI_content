#from crewai import Agent, Task, Crew
import re
import os
import requests
from bs4 import BeautifulSoup
import streamlit as st
import openai

# -------------------------------------------------------------------
# Utility Function: Sanitize Text
# -------------------------------------------------------------------
def sanitize_text(text):
    """
    Removes non-ASCII characters from a string.
    """
    if text is None:
        return ""
    return text.encode('ascii', 'ignore').decode('ascii')

# -------------------------------------------------------------------
# Step 1: Extract Content from Links (with UTF-8 sanitization)
# -------------------------------------------------------------------
def extract_content_from_links(links):
    """
    Extracts text content from the provided links using web scraping.
    Sanitizes non-ASCII characters to prevent encoding errors.
    """
    st.write("Extracting content from links...")
    research_data = []
    for link in links:
        if not link.strip():
            st.warning("Skipping empty link.")
            continue

        if not link.startswith(("http://", "https://")):
            link = f"https://{link}"
            st.warning(f"Added 'https://' to link: {link}")

        try:
            response = requests.get(link)
            response.encoding = 'utf-8'  # Force UTF-8 encoding
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string if soup.title else "No Title"
            title = sanitize_text(title)  # Sanitize title
            paragraphs = soup.find_all("p")
            content = " ".join([p.get_text() for p in paragraphs])
            content = sanitize_text(content)  # Sanitize content
            research_data.append({
                "title": title,
                "link": link,
                "content": content
            })
            st.write(f"Extracted content from: {link}")
        except Exception as e:
            st.error(f"Failed to extract content from {link}: {e}")
    return research_data

# -------------------------------------------------------------------
# Step 2: Generate Dynamic Section Titles
# -------------------------------------------------------------------
def generate_section_titles(topic, keywords):
    """
    Generates 5 dynamic, benefit-driven section titles.
    """
    topic = sanitize_text(topic)
    keywords = [sanitize_text(kw) for kw in keywords]
    prompt = f"""
    Generate 5 section titles for a technical article about "{topic}".
    Each title should:
    - Be benefit-driven (e.g., "Enhancing [Topic] with [Technology]").
    - Include one of these keywords: {keywords}.
    - Be concise and engaging.
    Output only the titles, one per line and try to keep the article in 800-1200 words max.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    titles = response.choices[0].message.content.strip().splitlines()
    return titles[:5]  # Ensure exactly 5 titles

# -------------------------------------------------------------------
# Step 3: Generate Content in Layout (with ASCII sanitization)
# -------------------------------------------------------------------
def generate_content_in_layout(topic, research_data, keywords, main_heading):
    """
    Generates the final article with sanitized input/output.
    """
    st.write("Generating final content layout...")
    
    # Sanitize main heading
    main_heading = sanitize_text(main_heading)
    heading_md = f"# {main_heading}"
    
    # Sanitize topic and keywords
    topic = sanitize_text(topic)
    keywords = [sanitize_text(kw) for kw in keywords]
    
    # Sanitize research data
    sanitized_research_data = []
    for data in research_data:
        sanitized_data = {
            "title": sanitize_text(data["title"]),
            "link": data["link"],
            "content": sanitize_text(data["content"])
        }
        sanitized_research_data.append(sanitized_data)
    
    # Introduction prompt
    intro_prompt = f"""
    Write an introduction for a technical article about "{topic}".
    The introduction should:
    - Be 150-200 words.
    - Provide an overview of the topic in the present tense.
    - Explicitly include these SEO keywords: {keywords}.
    - Use clear, formal English suitable for a company website.
    """
    intro_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": intro_prompt}]
    )
    introduction = intro_response.choices[0].message.content

    # Generate 5 dynamic section titles
    section_titles = generate_section_titles(topic, keywords)
    
    # For each section, generate "The Challenge" and "AR-Driven Solutions"
    sections = []
    for title in section_titles:
        # Sanitize title
        title = sanitize_text(title)
        
        # Generate "The Challenge" subsection
        challenge_prompt = f"""
        Write a "Challenge" subsection for the section titled "{title}".
        - Describe the problem in 100 words.
        - Include a statistic or fact from the research data.
        - Use formal, clear English.
        Research Data: {sanitized_research_data}
        """
        challenge_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": challenge_prompt}]
        )
        challenge = challenge_response.choices[0].message.content

        # Generate "AR-Driven Solutions" subsection (2 bullet points)
        solutions_prompt = f"""
        Write 2 AR-driven solutions for the section "{title}".
        Each solution must:
        - Start with a bolded subheader (e.g., **Live Remote Inspection:**).
        - Include a statistic or fact from the research data.
        - Cite a source from the research data (e.g., "uk.rs-online.com").
        - Use formal, clear English and should be in 100-110 words only.
        Research Data: {sanitized_research_data}
        """
        solutions_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": solutions_prompt}] 
        )
        solutions = solutions_response.choices[0].message.content

        # Build section
        section = f"""
        ## {title}

        ### The Challenge
        {challenge}

        ### AR-Driven Solutions
        {solutions}
        """
        sections.append(section)
    
    # Conclusion prompt
    conclusion_prompt = f"""
    Write a conclusion for a technical article about "{topic}".
    The conclusion should:
    - Be 100-150 words.
    - Summarize the key points.
    - Include a call to action that incorporates these SEO keywords: {keywords}.
    - Use formal and engaging language.
    """
    conclusion_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": conclusion_prompt}]
    )
    conclusion = conclusion_response.choices[0].message.content
    
    # Compile references
    references = "\n".join([f"{i+1}. {data['title']} - Retrieved from {data['link']}" for i, data in enumerate(sanitized_research_data)])
    
    # Combine all sections
    sections_joined = "\n\n".join(sections)
    
    # Final content in Markdown
    final_content = f"""
    {heading_md}

    ## Introduction:
    {introduction}

    ## Sections:
    {sections_joined}

    ## Conclusion:
    {conclusion}

    ## References:
    {references}
    """
    return final_content

# -------------------------------------------------------------------
# Streamlit App
# -------------------------------------------------------------------
def main():
    st.title("AI-Powered Technical Content Generator")
    st.markdown("This app generates SEO-optimized technical content with a structured layout using AI agents.")
    
    # User Inputs
    openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")
    topic = st.text_input("Enter the topic for the technical content:")
    keywords = st.text_input("Enter SEO keywords (comma-separated):")
    main_heading = st.text_input("Enter the main heading for the content:")
    links = st.text_area("Enter links to articles, blogs, or news (one per line):")
    
    if st.button("Generate Content"):
        if not openai_api_key or not topic or not keywords or not main_heading or not links:
            st.error("Please fill in all fields.")
        else:
            openai.api_key = sanitize_text(openai_api_key)  # Sanitize API key
            links = links.split("\n")
            research_data = extract_content_from_links(links)
            keywords_list = [kw.strip() for kw in keywords.split(",")]
            
            final_content = generate_content_in_layout(topic, research_data, keywords_list, main_heading)
            
            st.subheader("Final Content:")
            st.markdown(final_content)
            
if __name__ == "__main__":
    main()