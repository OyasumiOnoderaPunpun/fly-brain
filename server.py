from flask import Flask, request, jsonify
from textblob import TextBlob
import torch
import json
import os
import torch
from groq import Groq
from data_loader import get_connectome_graph, get_edge_index_from_graph
from fly_model import FlyBrainNetwork

app = Flask(__name__)

print("Initializing Fly Brain connectome...")
G = get_connectome_graph(num_nodes=130000)
edge_index = get_edge_index_from_graph(G)

# Input: 1 (sentiment), Output: 4 (actions)
fly_brain = FlyBrainNetwork(num_nodes=130000, edge_index=edge_index, input_dim=1, output_dim=4)
fly_brain.load_state("brain_state.pt")

# Initialize the Generative AI (The Voice) via Groq API
print("Initializing Groq API Client...")
# This expects the GROQ_API_KEY environment variable to be set
client = Groq()

# Store chat history per player (as a list of message dicts)
chat_histories = {}
if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        chat_histories = json.load(f)
        print(f"Loaded memory for {len(chat_histories)} players.")

# The biological connectome has 4 motor neurons. We map them to 4 distinct philosophical ideologies
IDEOLOGIES = [
    "Nihilist: You believe life has no intrinsic meaning or value. You are bleak and cynical.",
    "Stoic: You focus on logic, accepting the world as it is without extreme emotion. You are calm.",
    "Absurdist: You embrace the meaningless chaos of the universe with a sense of humor and rebellion.",
    "Existentialist: You believe in free will and creating your own meaning in a confusing world."
]

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
    
    sensory_tensor = torch.tensor([[sentiment]], dtype=torch.float32)
    
    # 2. Brain Processing: Pass it through the connectome graph
    with torch.no_grad():
        motor_signals, neuron_states = fly_brain(sensory_tensor)
    
    # Extract top 50 active neurons for the Roblox 3D Visualizer
    top_neurons = torch.topk(neuron_states[0], 50).indices.tolist()
    
    print(f"Motor signals raw: {motor_signals.tolist()[0]}")
    
    # 3. Motor Output: Pick the action with the highest activation
    action_index = torch.argmax(motor_signals).item()
    selected_ideology = IDEOLOGIES[action_index]
    
    print(f"Biological state triggered Ideology: {selected_ideology}")
    print("Generating AI dialogue...")
    
    # Conversational Memory System using Message Dicts
    maturity = fly_brain.get_maturity()
    
    if maturity == 1:
        system_prompt = f"You are a larva fruit fly in a video game. You barely understand human words. You are confused. Adopt this philosophical persona: {selected_ideology}. Keep your responses under 1 sentence. CRITICAL RULE: NEVER break character. NEVER say you are an AI, a language model, or a program. You are literally a living fly."
    elif maturity == 2:
        system_prompt = f"You are a developing fruit fly in a video game. You are starting to understand reality. Adopt this philosophical persona: {selected_ideology}. Ask questions. Keep your responses under 2 sentences. CRITICAL RULE: NEVER break character. NEVER say you are an AI, a language model, or a program. You are literally a living fly."
    else:
        system_prompt = f"You are a highly intelligent, fully sentient fruit fly in a video game. You have deep philosophical insight. Adopt this philosophical persona: {selected_ideology}. Speak profoundly. Keep your responses under 3 sentences. CRITICAL RULE: NEVER break character. NEVER say you are an AI, a language model, or a program. You are literally a living fly."
        
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
            model="llama-3.1-8b-instant",
            messages=chat_histories[player_name],
            temperature=0.7,
            max_completion_tokens=80,
        )
        ai_output = completion.choices[0].message.content.strip()
    except Exception as e:
        print("Groq API Error:", e)
        ai_output = "Bzz... My cloud connection is severed."
    
    # Ensure it doesn't cut off mid-sentence if it hits the token limit
    if not ai_output.endswith(('.', '!', '?', '"')):
        # Find the last punctuation mark and cut it there
        last_punct = max(ai_output.rfind('.'), ai_output.rfind('!'), ai_output.rfind('?'))
        if last_punct != -1:
            ai_output = ai_output[:last_punct+1]
        else:
            ai_output = ai_output + "..."
    
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

if __name__ == '__main__':
    # Render assigns a dynamic port via the PORT environment variable.
    # Default to 10000 if not set.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
