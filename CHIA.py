#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 12 16:50:42 2024

@author: barbaratao
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os 


# Get API KEY from .env file
load_dotenv()
api_key = os.getenv('API_KEY')


def search_provider(zip_code):
    # Set the path to the WebDriver
    # Initialize Chrome options
    chrome_options = Options()
    # Use ChromeDriverManager to get the ChromeDriver path
    driver_path = ChromeDriverManager().install()
    
    service = Service(driver_path)

    driver = webdriver.Chrome(service=service, options=chrome_options.add_argument('--headless'))

    # Open the website
    driver.get("https://preplocator.org/")

    # Wait for the page to load
    time.sleep(2)

    # Find the search box and enter the ZIP code
    search_box = driver.find_element(By.CSS_SELECTOR, "input[type='search']")
    search_box.clear()
    search_box.send_keys(zip_code)

    # Find the submit button and click it
    submit_button = driver.find_element(By.CSS_SELECTOR, "button.btn[type='submit']")
    submit_button.click()

    # Wait for results to load (adjust the sleep time as needed)
    time.sleep(180)

    # Now scrape the locator-results-item elements
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    results = soup.find_all('div', class_='locator-results-item')
    
    extracted_data = []
    for result in results:
        # Extract the relevant information from each result item
        name = result.find('h3').text.strip() if result.find('h3') else 'N/A'
        details = result.find_all('span')
        address = details[0].text.strip() if len(details) > 0 else 'N/A'
        phone = details[1].text.strip() if len(details) > 1 else 'N/A'
        distance_with_label = details[2].text.strip() if len(details) > 2 else 'N/A'
        distance = distance_with_label.replace('Distance from your location:', '').strip() if distance_with_label != 'N/A' else 'N/A'
        extracted_data.append({
            'Name': name,
            'Address': address,
            'Phone': phone,
            'Distance': distance
        })
    driver.quit()
        
    df = pd.DataFrame(extracted_data)
    df['Distance'] = df['Distance'].str.replace(r'[^\d.]+', '', regex=True)
    df['Distance'] = pd.to_numeric(df['Distance'], errors='coerce')
    # Filter for locations within 30 miles
    return df[df['Distance'] <=30]
    # Print or process the extracted data
    

# Testing if search_provider works
search_provider("02806") 

def assess_hiv_risk():
    questions = {
        'sex_with_men': "Have you had unprotected sexual intercourse with men in the past 3 months? (Yes/No): ",
        'multiple_partners': "Have you had multiple sexual partners in the past 12 months? (Yes/No): ",
        'iv_drug_use': "Have you used intravenous drugs or shared needles? (Yes/No): ",
        'partner_hiv_positive/unknown': "Do you have a sexual partner who is HIV positive/ has unknown HIV status? (Yes/No): ",
        'std_history': "Have you been diagnosed with a sexually transmitted disease (STD) in the past 12 months? (Yes/No): ",
        # Add more questions as necessary
    }
    
    high_risk = False
    responses = {}
    
    print("HIV Risk Assessment Questionnaire\n")
    
    for key, question in questions.items():
        response = input(question).strip().lower()
        responses[key] = response
        if response == 'yes':
            high_risk = True
    
    if high_risk:
        print("\nBased on your responses, you may be at a higher risk for HIV. It is recommended to consider taking PrEP to protect from HIV infection.")
    else:
        print("\nBased on your responses, your risk for HIV appears to be lower. However, continue to practice safe behaviors and consult a healthcare professional for personalized advice.")
    
    return responses


import gradio as gr
import os
from pathlib import Path
import shutil
import openai
import autogen
import chromadb
import multiprocessing as mp
#from hiv_risk import assess_hiv_risk
#import search_provider
from autogen.retrieve_utils import TEXT_FORMATS, get_file_from_url, is_url
# from .autonotebook import tqdm as notebook_tqdm
import tqdm as notebook_tqdm


config_list = [
    {
        'model': 'gpt-4-0125-preview',
        'OPENAI_API_KEY': 'API_KEY',  # Ensure to replace with your actual API key
    }
]

llm_config = [
    {
    #"request_timeout": 600,
    "seed": 42,
    "config_list": config_list,
    "temperature": 0,
    "top_p": 1,
    }
]


#TIMEOUT = 60

llm_config_counselor = {
"functions": [
    {
        "name": "assess_hiv_risk",
        "description": "ask patients a couple of questions to assess their HIV risk",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "a series of questions",
                },
            },
            "required": ["questions"],
        },
    },
    {
        "name": "search_provider",
        "description": "Visit the website (https://preplocator.org/),input patients' Zipcode to search PrEP providers within a radius of 30 miles, and, scraping website relevant content",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "visit the specified website and input Zip Code",
                },
            },
            "required": ["Zip Code"],
        },
    },
],
"config_list": llm_config}


def initialize_agents(llm_config):
    llm_config_counselor = {
    "functions": [
        {
            "name": "assess_hiv_risk",
            "description": "ask patients a couple of questions to assess their HIV risk",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "a series of questions",
                    },
                },
                "required": ["questions"],
            },
        },
        {
            "name": "search_provider",
            "description": "Visit the website (https://preplocator.org/),input patients' Zipcode to search PrEP providers within a radius of 30 miles, and, scraping website relevant content",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "visit the specified website and input Zip Code",
                    },
                },
                "required": ["Zip Code"],
            },
        },
    ],
    "config_list": llm_config}

    #autogen.ChatCompletion.start_logging()

    patients = autogen.UserProxyAgent(
        name="patients",
        code_execution_config={"last_n_messages": 2, "work_dir": "coding","use_docker":False},
        max_consecutive_auto_reply=0,
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="TERMINATE",
        llm_config=llm_config,
    )
    
    counselor = autogen.AssistantAgent(
        name="counselor",
        llm_config=llm_config_counselor,
        code_execution_config=False,
        system_message="You are an HIV PrEP counselor. You will be guided by the HIV provider to assess patients' risk and conduct motivational interviewing for PrEP if indicated",
    )

    return patients, counselor

def initialize_agents(llm_config):
    llm_config_counselor = {
    "functions": [
        {
            "name": "assess_hiv_risk",
            "description": "ask patients a couple of questions to assess their HIV risk",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "a series of questions",
                    },
                },
                "required": ["questions"],
            },
        },
        {
            "name": "search_provider",
            "description": "Visit the website (https://preplocator.org/),input patients' Zipcode to search PrEP providers within a radius of 30 miles, and, scraping website relevant content",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "visit the specified website and input Zip Code",
                    },
                },
                "required": ["Zip Code"],
            },
        },
    ],
    "config_list": llm_config}

    #autogen.ChatCompletion.start_logging()

    patients = autogen.UserProxyAgent(
        name="patients",
        code_execution_config={"last_n_messages": 2, "work_dir": "coding"},
        max_consecutive_auto_reply=0,
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="TERMINATE",
        llm_config=llm_config,
    )
    
    counselor = autogen.AssistantAgent(
        name="counselor",
        llm_config=llm_config_counselor,
        system_message="You are an HIV PrEP counselor. You will be guided by the HIV provider to assess patients' risk and conduct motivational interviewing for PrEP if indicated",
    )

    return patients, counselor

patients,counselor=initialize_agents(llm_config)
problem="I would like to assess my HIV risk"
counselor.initiate_chat(patients, message=problem, silent=False,)





def get_description_text():
    return """
    # Chatbot for HIV Prevention and Action (CHIA)
    
    This demo shows how to use AI agent to conduct motivational interviewing to promote PrEP use.

    """


def initiate_chat_with_agent(problem, queue, n_results=3):
    try:
        counselor.initiate_chat(
            patients, problem=problem, silent=False, n_results=n_results
        )
        messages = counselor.chat_messages
        messages = [messages[k] for k in messages.keys()][0]
        messages = [m["content"] for m in messages if m["role"] == "user"]
        print("messages: ", messages)
    except Exception as e:
        messages = [str(e)]
    queue.put(messages)


TIMEOUT = 60
def chatbot_reply(input_text):
    """Chat with the agent through terminal."""
    queue = mp.Queue()
    process = mp.Process(
        target=initiate_chat_with_agent,
        args=(input_text, queue),
    )
    process.start()
    try:
        # process.join(TIMEOUT+2)
        messages = queue.get(timeout=TIMEOUT)
    except Exception as e:
        messages = [
            str(e)
            if len(str(e)) > 0
            else "Invalid Request to OpenAI, please check your API keys."
        ]
    finally:
        try:
            process.terminate()
        except:
            pass
    return messages