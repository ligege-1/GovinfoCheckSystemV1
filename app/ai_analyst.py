import json
import requests
import re
import time
import random
import threading
import queue
from sqlalchemy import text
from app import db
from app.models import AiEngine

class AiDataAnalyst:
    def __init__(self, engine_id=None):
        if engine_id:
            self.engine_config = db.session.get(AiEngine, engine_id)
        else:
            self.engine_config = AiEngine.query.filter_by(is_active=True).first()
        
    def get_schema_context(self):
        return """
Table: collection_item
Columns: 
- id (Integer, Primary Key)
- keyword (String): Search keyword used
- title (String): Title of the content
- cover (String): URL of the cover image
- url (String): Source URL
- source (String): Source name (e.g., 'baidu', 'xinhua')
- deep_collected (Boolean): Whether deep content has been collected
- deep_content (Text): (Legacy) Deep content text
- created_at (DateTime)

Table: deep_collection_content
Columns: 
- id (Integer, Primary Key)
- content (Text): The full content text
- item_id (Integer, Foreign Key to collection_item.id)
- created_at (DateTime)

Table: crawl_rule
Columns:
- id (Integer)
- name (String)
- site (String)
"""

    def execute_sql(self, sql_query):
        """
        Tool function to execute SQL query on the database.
        """
        try:
            # Basic safety: Prevent DROP TABLE or massive destructive commands if needed
            # For now, we trust the AI as per requirements for "cleaning"
            
            result = db.session.execute(text(sql_query))
            
            if sql_query.strip().upper().startswith("SELECT"):
                rows = result.fetchall()
                if not rows:
                    return "No results found."
                # Convert rows to list of dicts
                return str([dict(row._mapping) for row in rows])
            else:
                db.session.commit()
                return f"Executed successfully. Rows affected: {result.rowcount}"
                
        except Exception as e:
            db.session.rollback()
            return f"Error executing SQL: {str(e)}"

    def call_ai_api(self, messages):
        if not self.engine_config:
            raise ValueError("No active AI Engine configured.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.engine_config.api_key}"
        }
        
        payload = {
            "model": self.engine_config.model_name,
            "messages": messages,
            "temperature": 0.1
        }
        
        # Handle URL construction logic
        base_url = self.engine_config.api_url.rstrip('/')
        if not base_url.endswith('/v1'):
            if 'siliconflow' in base_url or 'openai' in base_url:
                target_url = f"{base_url}/v1/chat/completions"
            else:
                target_url = f"{base_url}/chat/completions"
        else:
            target_url = f"{base_url}/chat/completions"

        try:
            max_retries = 3
            base_delay = 1
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(target_url, json=payload, headers=headers, timeout=60)
                    
                    if response.status_code == 200:
                        data = response.json()
                        return data['choices'][0]['message']['content']
                    elif response.status_code == 503:
                        # 503 Service Unavailable - often means system is busy, so we retry
                        if attempt < max_retries - 1:
                            delay = (base_delay * (2 ** attempt)) + (random.randint(0, 1000) / 1000)
                            print(f"DEBUG: API 503 Busy. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})", flush=True)
                            time.sleep(delay)
                            continue
                        else:
                            error_msg = f"API Error: {response.status_code} - {response.text}"
                            raise Exception(error_msg)
                    else:
                        # Other errors - raise immediately
                        error_msg = f"API Error: {response.status_code} - {response.text}"
                        raise Exception(error_msg)
                        
                except requests.exceptions.RequestException as e:
                    # Network-level errors (timeout, connection refused, etc.)
                    if attempt < max_retries - 1:
                        delay = (base_delay * (2 ** attempt)) + (random.randint(0, 1000) / 1000)
                        print(f"DEBUG: Network Error: {e}. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})", flush=True)
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"Request failed: {str(e)}")
                        
        except Exception as e:
            # Re-raise exception
            raise Exception(f"Request failed: {str(e)}")

    def analyze_heatmap(self, data_samples):
        """
        Analyze a list of content samples to generate regional heatmap data.
        data_samples: List of strings (content snippets)
        """
        if not self.engine_config:
            raise ValueError("No active AI Engine configured.")
            
        if not data_samples:
            return []

        # Limit tokens by truncating samples and limiting count
        combined_text = ""
        for i, text in enumerate(data_samples):
            combined_text += f"[{i+1}] {text[:200]}...\n"
            
        system_prompt = """You are a data analyst. Analyze the provided news snippets.
Task: Identify Chinese provinces (e.g., 广东, 四川, 北京) and major cities (e.g., 成都, 深圳, 杭州) mentioned in the text.
IMPORTANT:
1. If a city is identified, you MUST also identify its corresponding Province Name for mapping purposes (unless it's a direct municipality like 北京, 上海, 天津, 重庆).
2. Return the result strictly as a JSON list of objects.
3. Each object should have:
   - "name": The standardized Province Name (for ECharts map matching) or Municipality Name.
   - "value": Frequency count.
   - "keywords": 1-2 hot keywords associated with that region.
   - "city": If a specific city was the main focus, include the city name, otherwise null.

Format: [{"name": "广东", "value": 5, "keywords": "暴雨, 洪涝", "city": "深圳"}, ...]
Do not output any markdown or explanations, just the JSON string.
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combined_text}
        ]
        
        try:
            response_content = self.call_ai_api(messages)
            # Clean response
            cleaned = response_content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            return json.loads(cleaned)
        except Exception as e:
            print(f"Heatmap analysis error: {e}")
            return []

    def run_analysis(self, user_query):
        """
        Generator that runs the analysis loop and yields SSE events.
        """
        print(f"DEBUG: Starting run_analysis with query: {user_query}, Engine: {self.engine_config}", flush=True)
        
        if not self.engine_config:
            print("DEBUG: No engine config found", flush=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'No active AI Engine found. Please configure one first.'}, ensure_ascii=False)}\n\n"
            return

        system_prompt = f"""You are an expert Database Administrator and Data Analyst.
You have access to a SQLite database with the following schema:
{self.get_schema_context()}

Your goal is to answer the user's request or perform data cleaning operations.
You can execute SQL queries.

IMPORTANT: You must output your response in valid JSON format ONLY, with the following structure:
{{
    "thought": "Your reasoning here (explain what you are going to do)",
    "action": "execute_sql",
    "sql": "THE SQL QUERY HERE"
}}

If you have the final answer or no further SQL is needed, use:
{{
    "thought": "Final answer reasoning",
    "action": "final_answer",
    "content": "Your final answer to the user (can be in markdown). IMPORTANT: When presenting data rows, ALWAYS use Markdown tables."
}}

Do not output markdown blocks (```json) around the JSON. Just the raw JSON string. Do not include any text outside the JSON.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]

        max_turns = 10
        yield f"data: {json.dumps({'type': 'start', 'content': 'Starting analysis...'}, ensure_ascii=False)}\n\n"

        for i in range(max_turns):
            print(f"DEBUG: Turn {i}", flush=True)
            
            # Notify frontend about progress
            yield f"data: {json.dumps({'type': 'thought', 'content': f'正在思考 (第 {i+1} 轮)...'}, ensure_ascii=False)}\n\n"

            def threaded_api_call(url, payload, headers, result_q):
                try:
                    # Increase timeout to 300s (5 mins) for slow reasoning models
                    response = requests.post(url, json=payload, headers=headers, timeout=300)
                    if response.status_code == 200:
                        data = response.json()
                        content = data['choices'][0]['message']['content']
                        result_q.put({"status": "success", "content": content})
                    else:
                        result_q.put({"status": "error", "error": f"API Error: {response.status_code} - {response.text}"})
                except Exception as e:
                    result_q.put({"status": "error", "error": str(e)})

            # Extract config values to avoid thread-safety issues with SQLAlchemy objects
            api_key = self.engine_config.api_key
            api_url = self.engine_config.api_url
            model_name = self.engine_config.model_name
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.1
            }
            
            # Handle URL construction logic
            base_url = api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                if 'siliconflow' in base_url or 'openai' in base_url:
                    target_url = f"{base_url}/v1/chat/completions"
                else:
                    target_url = f"{base_url}/chat/completions"
            else:
                target_url = f"{base_url}/chat/completions"

            # Use threading to allow heartbeat pings
            q = queue.Queue()
            t = threading.Thread(target=threaded_api_call, args=(target_url, payload, headers, q))
            t.start()
            
            # Wait for result while sending heartbeats
            while t.is_alive():
                t.join(timeout=2.0) # Wait 2 seconds
                # Send a ping/keep-alive event (ignored by frontend logic but keeps connection open)
                # Using 'thought' with hidden content or just a special type if supported
                # Since frontend ignores unknown types, we can send 'ping'
                yield f"data: {json.dumps({'type': 'ping'}, ensure_ascii=False)}\n\n"
                
            # Retrieve result
            try:
                result = q.get_nowait()
            except queue.Empty:
                raise Exception("Thread finished but no result in queue")
                
            if result['status'] == 'error':
                raise Exception(result['error'])
                
            ai_response = result['content']


            # Parse Response
            try:
                # Try to extract JSON from the response
                cleaned_content = ai_response.strip()
                
                # 1. Try to find JSON block with regex
                match = re.search(r'\{[\s\S]*\}', cleaned_content)
                if match:
                    json_str = match.group(0)
                    action_data = json.loads(json_str)
                    # Update cleaned_content to be the valid JSON string for history consistency
                    cleaned_content = json_str
                else:
                    # 2. Fallback to direct parse
                    action_data = json.loads(cleaned_content)
                
                if not isinstance(action_data, dict):
                    raise ValueError(f"AI returned {type(action_data)}, expected dict")
                    
            except (json.JSONDecodeError, ValueError) as e:
                # If JSON parse fails or not a dict
                yield f"data: {json.dumps({'type': 'thought', 'content': f'Raw AI Response: {ai_response}'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'error', 'content': f'Failed to parse AI response: {str(e)}'}, ensure_ascii=False)}\n\n"
                return

            try:
                # Emit thought
                thought = action_data.get('thought', '')
                if thought:
                    yield f"data: {json.dumps({'type': 'thought', 'content': thought}, ensure_ascii=False)}\n\n"

                action = action_data.get('action')
                
                if action == 'execute_sql':
                    sql = action_data.get('sql')
                    yield f"data: {json.dumps({'type': 'sql', 'content': sql}, ensure_ascii=False)}\n\n"
                    
                    # Execute SQL
                    tool_result = self.execute_sql(sql)
                    yield f"data: {json.dumps({'type': 'result', 'content': tool_result}, ensure_ascii=False)}\n\n"
                    
                    # Update history
                    messages.append({"role": "assistant", "content": cleaned_content})
                    messages.append({"role": "user", "content": f"Tool Execution Result: {tool_result}"})
                    
                elif action == 'final_answer':
                    content = action_data.get('content')
                    yield f"data: {json.dumps({'type': 'answer', 'content': content}, ensure_ascii=False)}\n\n"
                    return # End successfully
                else:
                    yield f"data: {json.dumps({'type': 'error', 'content': f'Unknown action: {action}'}, ensure_ascii=False)}\n\n"
                    break
            except Exception as e:
                 print(f"DEBUG: Processing Error: {e}", flush=True)
                 yield f"data: {json.dumps({'type': 'error', 'content': f'Processing Error: {str(e)}'}, ensure_ascii=False)}\n\n"
                 return
        
        # If loop finishes without final answer
        yield f"data: {json.dumps({'type': 'answer', 'content': '**分析结束：** 达到最大对话轮数，未能得出最终结论。'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
