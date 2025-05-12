import os
import json
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def title_generate(topic: str) -> str:
    prompt = f"""
Generate 5 creative, SEO-optimized titles for a technical blog or article.
Each title should be concise, attention-grabbing, and clearly convey the essence of the topic.

Topic: {topic}
"""
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.4
    )
    titles = response.choices[0].message.content.strip().split('\n')
    titles = [title.strip("•- ") for title in titles if title.strip()]
    return titles

def generate_new_titles(topic: str, previous_result: str) -> str:
    prompt = f"""
Previously, you generated these 5 titles on the topic "{topic}":
{previous_result}

Now, please generate 5 new, creative, SEO-optimized titles for a technical blog or article on the same topic.
Each title should be concise, attention-grabbing, and clearly convey the essence of the topic.
"""
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.4
    )
    return response.choices[0].message.content

def save_results(data: dict, filename: str = "generated_titles.json"):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []
    existing_data.append(data)
    with open(filename, 'w') as f:
        json.dump(existing_data, f, indent=4)

def load_all_titles(filename: str = "generated_titles.json"):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []
