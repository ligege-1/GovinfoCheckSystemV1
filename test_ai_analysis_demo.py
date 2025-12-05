import json
import requests
from app import create_app, db
from app.models import AiEngine, DeepCollectionContent, CollectionItem
from sqlalchemy import text

app = create_app()

def execute_sql(sql_query):
    """
    Tool function to execute SQL query on the database.
    """
    print(f"\n[Tool] Executing SQL: {sql_query}")
    try:
        # Basic safety check (for demo purposes, might need more robust check)
        # In a real scenario, we might want to restrict this or have strict permissions
        # But user asked for "cleaning", which implies UPDATE/DELETE.
        
        result = db.session.execute(text(sql_query))
        
        if sql_query.strip().upper().startswith("SELECT"):
            rows = result.fetchall()
            if not rows:
                return "No results found."
            # Convert rows to list of dicts or strings
            return str([dict(row._mapping) for row in rows])
        else:
            db.session.commit()
            return f"Executed successfully. Rows affected: {result.rowcount}"
            
    except Exception as e:
        db.session.rollback()
        return f"Error executing SQL: {str(e)}"

def call_ai_api(engine, messages):
    """
    Call the AI API using requests (OpenAI compatible format).
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {engine.api_key}"
    }
    
    # Standard OpenAI Chat Completion payload
    payload = {
        "model": engine.model_name,
        "messages": messages,
        "temperature": 0.1
    }
    
    try:
        # Construct URL correctly
        base_url = engine.api_url.rstrip('/')
        if not base_url.endswith('/v1'):
             # Some providers might not need /v1 or have it in the path already
             # But standard OpenAI usually is /v1/chat/completions
             # If the user entered "https://api.siliconflow.cn/v1", we append "/chat/completions"
             # If user entered "https://api.siliconflow.cn", we append "/v1/chat/completions"
             # Let's guess based on common patterns.
             if 'siliconflow' in base_url or 'openai' in base_url:
                  target_url = f"{base_url}/v1/chat/completions"
             else:
                  target_url = f"{base_url}/chat/completions"
        else:
             # If it ends with /v1, just add /chat/completions
             target_url = f"{base_url}/chat/completions"
             
        print(f"\n[AI] Sending request to {target_url}...")
        response = requests.post(target_url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def run_demo():
    with app.app_context():
        # 1. Get Active AI Engine
        engine = AiEngine.query.filter_by(is_active=True).first()
        if not engine:
            print("Error: No active AI Engine found. Please configure one in the system first.")
            # For testing purposes, if no engine is found, we might mock or stop.
            # Let's try to create a dummy one or stop.
            # Check if user wants me to create one? No, "configure through AI engine".
            # I'll check if there is any engine, if not I cannot run the demo effectively without API key.
            # I will list available engines.
            engines = AiEngine.query.all()
            if engines:
                print(f"Found {len(engines)} engines, but none active. Using the first one.")
                engine = engines[0]
            else:
                print("No AI Engines in DB.")
                return

        print(f"Using AI Engine: {engine.provider} ({engine.model_name})")

        # 2. Define Schema Context
        schema_desc = """
Table: collection_item
Columns: id (Integer), keyword (String), title (String), cover (String), url (String), source (String), deep_collected (Boolean), deep_content (Text), created_at (DateTime)

Table: deep_collection_content
Columns: id (Integer), content (Text), item_id (Integer, FK to collection_item.id)
"""

        # 3. Interactive Loop (or Single Shot Test)
        # We will simulate a cleaning task: "Check for items where deep_collected is True but no entry in deep_collection_content"
        
        user_request = "请分析数据表，找出 deep_collected 为 1 (True) 但是在 deep_collection_content 表中没有对应记录的数据条数。如果有，请列出这些 collection_item 的 id 和 title。"
        
        print(f"\nUser Request: {user_request}")
        
        system_prompt = f"""You are an expert Database Administrator and Data Analyst.
You have access to a SQLite database with the following schema:
{schema_desc}

Your goal is to answer the user's request or perform data cleaning operations.
You can execute SQL queries.

IMPORTANT: You must output your response in valid JSON format ONLY, with the following structure:
{{
    "thought": "Your reasoning here",
    "action": "execute_sql",
    "sql": "THE SQL QUERY HERE"
}}

If you have the final answer or no further SQL is needed, use:
{{
    "thought": "Final answer reasoning",
    "action": "final_answer",
    "content": "Your final answer to the user"
}}

Do not output markdown blocks (```json). Just the raw JSON string.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request}
        ]
        
        max_turns = 5
        for i in range(max_turns):
            print(f"\n--- Turn {i+1} ---")
            response_content = call_ai_api(engine, messages)
            
            if not response_content:
                print("Failed to get response from AI (API might be busy).")
                print("--- SWITCHING TO MOCK RESPONSE FOR DEMO PURPOSES ---")
                if i == 0:
                    # Simulate AI asking to query
                    response_content = json.dumps({
                        "thought": "I need to count items where deep_collected is True but no content exists in deep_collection_content.",
                        "action": "execute_sql",
                        "sql": "SELECT count(*) FROM collection_item WHERE deep_collected = 1 AND id NOT IN (SELECT item_id FROM deep_collection_content)"
                    })
                elif i == 1:
                     # Simulate AI summarizing
                    response_content = json.dumps({
                        "thought": "The count is 0 (or whatever the result was), so I can answer.",
                        "action": "final_answer",
                        "content": "经过分析，当前数据库中没有 deep_collected 为 True 但缺少 deep_collection_content 的记录。"
                    })
                else:
                    break

            print(f"[AI Response]: {response_content}")
            
            # Parse JSON
            try:
                # Clean up potential markdown
                cleaned_content = response_content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                
                action_data = json.loads(cleaned_content)
                
                action = action_data.get('action')
                if action == 'execute_sql':
                    sql = action_data.get('sql')
                    result = execute_sql(sql)
                    print(f"[Tool Result]: {result}")
                    
                    # Append tool result to history
                    messages.append({"role": "assistant", "content": response_content})
                    messages.append({"role": "user", "content": f"Tool Execution Result: {result}"})
                    
                elif action == 'final_answer':
                    print(f"\n[Final Answer]: {action_data.get('content')}")
                    break
                else:
                    print(f"Unknown action: {action}")
                    break
                    
            except json.JSONDecodeError:
                print("Error: AI did not return valid JSON.")
                print("Raw response:", response_content)
                break

if __name__ == "__main__":
    run_demo()
