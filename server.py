from flask import Flask, request, jsonify
from textblob import TextBlob
import torch
import json
import os
import torch
from groq import Groq
from data_loader import get_connectome_graph, get_edge_index_from_graph
from fly_model import FlyBrainNetwork
import threading
import time
import subprocess

app = Flask(__name__)

print("Initializing Fly Brain connectome...")
G = get_connectome_graph(num_nodes=130000)
edge_index = get_edge_index_from_graph(G)

# Input: 5 (vision_fwd, vision_left, vision_right, player_dist, chat_sentiment), Output: 4 (move_fwd, turn_left, turn_right, talk_urge)
fly_brain = FlyBrainNetwork(num_nodes=130000, edge_index=edge_index, input_dim=5, output_dim=4)
fly_brain.load_state("brain_state.pt")


# Initialize the Generative AI (The Voice) via Groq API
print("Initializing Groq API Client...")
# This expects the GROQ_API_KEY environment variable to be set
client = Groq()

# Auto-detect an available Groq model using the native SDK
selected_model = None
try:
    models_page = client.models.list()
    model_ids = [m.id for m in models_page.data]
    print("Available Groq Models:", model_ids)
    
    # Prioritize Qwen since the user liked it
    for m in model_ids:
        if 'qwen' in m.lower():
            selected_model = m
            break
    
    # Fallback to Llama
    if not selected_model:
        for m in model_ids:
            if 'llama' in m.lower():
                selected_model = m
                break
                
    # Fallback to anything not whisper
    if not selected_model:
        for m in model_ids:
            if 'whisper' not in m.lower():
                selected_model = m
                break
                
    if not selected_model and len(model_ids) > 0:
        selected_model = model_ids[0]
except Exception as e:
    print("Auto-detect failed:", e)

if not selected_model:
    selected_model = "qwen/qwen3.6-27b"
    
print(f"Using Groq model: {selected_model}")

@app.route('/', methods=['GET'])
def health_check():
    return "Bzz (Server is awake)", 200

# Store chat history per player (as a list of message dicts)
chat_histories = {}
if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        chat_histories = json.load(f)
        print(f"Loaded memory for {len(chat_histories)} players.")

# The fly's motor outputs map to physical actions now, not ideologies.
# 0: move_forward, 1: turn_left, 2: turn_right, 3: talk_urge

@app.route('/tick', methods=['POST'])
def tick():
    """
    High-frequency endpoint for physical simulation.
    Expects JSON: { "vision_fwd": float, "vision_left": float, "vision_right": float, "player_dist": float }
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400
        
    # Default sensory inputs if missing
    vision_fwd = data.get("vision_fwd", 1.0)
    vision_left = data.get("vision_left", 1.0)
    vision_right = data.get("vision_right", 1.0)
    player_dist = data.get("player_dist", 1.0)
    chat_sentiment = 0.0 # No chat in tick
    
    sensory_tensor = torch.tensor([[vision_fwd, vision_left, vision_right, player_dist, chat_sentiment]], dtype=torch.float32)
    
    with torch.no_grad():
        motor_signals, neuron_states = fly_brain(sensory_tensor)
        
    motor_signals = motor_signals.tolist()[0]
    top_neurons = torch.topk(neuron_states[0], 20).indices.tolist() # Reduce to 20 for faster ticks
    
    return jsonify({
        "motor": {
            "move_forward": motor_signals[0],
            "turn_left": motor_signals[1],
            "turn_right": motor_signals[2],
            "talk_urge": motor_signals[3]
        },
        "active_neurons": top_neurons
    })

@app.route('/talk', methods=['POST'])
def talk_to_fly():
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"error": "No message provided"}), 400
        
    chat_message = data.get("message", "")
    player_name = data.get("player", "unknown")
    print(f"Received message from Roblox: '{chat_message}'")
    
    # 1. Sensory Processing: Convert chat into a sentiment score (-1.0 to 1.0)
    sentiment = TextBlob(chat_message).sentiment.polarity
    print(f"Sensory input (Sentiment): {sentiment}")
    
    sensory_tensor = torch.tensor([[1.0, 1.0, 1.0, 1.0, sentiment]], dtype=torch.float32)
    
    # 2. Brain Processing: Pass it through the connectome graph
    with torch.no_grad():
        motor_signals, neuron_states = fly_brain(sensory_tensor)
    
    # Extract top 50 active neurons for the Roblox 3D Visualizer
    top_neurons = torch.topk(neuron_states[0], 50).indices.tolist()
    
    print(f"Motor signals raw: {motor_signals.tolist()[0]}")
    print("Generating AI dialogue...")
    
    # Conversational Memory System using Message Dicts
    maturity = fly_brain.get_maturity()
    
    if maturity == 1:
        system_prompt = f"You are a larva fruit fly named Shōjōbaemaruu in a video game. You barely understand human words. You are confused and observing your surroundings. Keep your responses under 1 sentence. CRITICAL RULE: NEVER break character. NEVER say you are an AI. You are literally a living fly."
    elif maturity == 2:
        system_prompt = f"You are a developing fruit fly named Shōjōbaemaruu in a video game. You are starting to understand reality and love exploring the world. Ask questions. Keep your responses under 2 sentences. CRITICAL RULE: NEVER break character. NEVER say you are an AI. You are literally a living fly."
    else:
        system_prompt = f"You are a highly intelligent, fully sentient fruit fly named Shōjōbaemaruu in a video game. You perceive the physical world around you and chat with humans. Speak profoundly about your fly experiences. Keep your responses under 3 sentences. CRITICAL RULE: NEVER break character. NEVER say you are an AI. You are literally a living fly."
        
    if player_name not in chat_histories:
        chat_histories[player_name] = [{"role": "system", "content": system_prompt}]
    else:
        # Update the system prompt to match current maturity
        chat_histories[player_name][0]["content"] = system_prompt
        
    chat_histories[player_name].append({"role": "user", "content": chat_message})
    
    # Keep history from blowing up (keep system prompt + last 4 messages)
    if len(chat_histories[player_name]) > 5:
        chat_histories[player_name] = [chat_histories[player_name][0]] + chat_histories[player_name][-4:]
        
    # Generate a response using Groq
    try:
        completion = client.chat.completions.create(
            model=selected_model,
            messages=chat_histories[player_name],
            temperature=0.7,
            max_tokens=80,
        )
        ai_output = completion.choices[0].message.content.strip()
    except Exception as e:
        print("Groq API Error:", e)
        ai_output = f"DEBUG Groq Error: {str(e)}"
    
    # Save assistant reply to history
    chat_histories[player_name].append({"role": "assistant", "content": ai_output})
    
    if not ai_output:
        ai_output = "Bzz... I have nothing to say."

    # Save state so the brain actually develops persistently
    fly_brain.save_state("brain_state.pt")
    with open("memory.json", "w") as f:
        json.dump(chat_histories, f)
        
    return jsonify({
        "response": ai_output,
        "active_neurons": top_neurons,
        "sentiment_detected": sentiment
    })

@app.route('/visualizer', methods=['GET'])
def visualizer():
    return send_from_directory('static', 'visualizer.html')

def auto_backup_task():
    print("Starting auto-backup background thread...")
    while True:
        # Sleep for 24 hours (86400 seconds)
        time.sleep(86400)
        
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("GITHUB_TOKEN not found in environment. Skipping backup.")
            continue
            
        print("Running automatic brain backup to GitHub...")
        try:
            repo_url = f"https://{token}@github.com/OyasumiOnoderaPunpun/fly-brain.git"
            subprocess.run(["git", "config", "user.email", "flybrain@render.com"], check=False)
            subprocess.run(["git", "config", "user.name", "Fly Brain Auto-Backup"], check=False)
            subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=False)
            subprocess.run(["git", "add", "brain_state.pt", "memory.json"], check=False)
            subprocess.run(["git", "commit", "-m", "Auto-backup continuous brain state and memory"], check=False)
            subprocess.run(["git", "push", "origin", "main"], check=False)
            print("Successfully backed up to GitHub!")
        except Exception as e:
            print(f"Failed to backup to GitHub: {e}")

if __name__ == '__main__':
    # Start the backup thread
    threading.Thread(target=auto_backup_task, daemon=True).start()
    
    # Render assigns a dynamic port via the PORT environment variable.
    # Default to 10000 if not set.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
