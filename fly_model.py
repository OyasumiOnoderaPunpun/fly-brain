import torch
import torch.nn as nn
import torch.nn.functional as F

class FlyBrainNetwork(nn.Module):
    def __init__(self, num_nodes, edge_index, input_dim=1, output_dim=4, num_forward_steps=3):
        """
        A PyTorch module structured around a static connectome graph.
        input_dim = 1 (Sentiment score of the chat message: -1.0 to 1.0)
        output_dim = 4 (4 distinct actions/responses the fly can make)
        """
        super(FlyBrainNetwork, self).__init__()
        self.num_nodes = num_nodes
        self.num_edges = edge_index.shape[1]
        self.edge_index = edge_index
        self.num_forward_steps = num_forward_steps
        
        # Trainable synaptic weights for each biological connection
        self.edge_weights = nn.Parameter(torch.randn(self.num_edges) * 0.1)
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        # Maintain a continuous state of consciousness/electricity
        self.register_buffer('current_state', torch.zeros(1, num_nodes))
        
    def get_maturity(self):
        """
        Returns a maturity level based on total synaptic density/weight.
        Baseline mean is ~0.08. As it learns, it grows.
        Returns: 1 (Larva), 2 (Awakening), 3 (Sentience)
        """
        density = self.edge_weights.abs().mean().item()
        if density < 0.15:
            return 1
        elif density < 0.25:
            return 2
        else:
            return 3
            
    def save_state(self, filepath="brain_state.pt"):
        torch.save(self.state_dict(), filepath)
        
    def load_state(self, filepath="brain_state.pt"):
        import os
        if os.path.exists(filepath):
            self.load_state_dict(torch.load(filepath))
            print(f"Loaded biological memory from {filepath}. Maturity: Phase {self.get_maturity()}")
        else:
            print("No previous biological memory found. Starting fresh.")
        
    def forward(self, x):
        """
        x is the observation from the environment (sentiment). Shape: [batch_size, input_dim]
        """
        batch_size = x.shape[0]
        device = x.device
        
        # Continue from previous state (with slight decay so it doesn't explode)
        if self.current_state.device != device or self.current_state.shape[0] != batch_size:
            self.current_state = torch.zeros(batch_size, self.num_nodes, device=device)
            
        neuron_states = self.current_state * 0.8
        neuron_states[:, :self.input_dim] = x
        
        indices = self.edge_index.to(device)
        values = self.edge_weights
        
        adj_matrix = torch.sparse_coo_tensor(indices, values, size=(self.num_nodes, self.num_nodes))
        
        for _ in range(self.num_forward_steps):
            new_states = torch.sparse.mm(adj_matrix, neuron_states.t()).t()
            # Biological non-linearity (firing rate)
            neuron_states = F.relu(new_states)
            
            # Continuously inject sensory input (out-of-place to avoid autograd issues)
            updated_sensory = neuron_states[:, :self.input_dim] + x
            neuron_states = torch.cat([updated_sensory, neuron_states[:, self.input_dim:]], dim=1)
            
        # Extract the motor output from the last `output_dim` neurons
        motor_signals = neuron_states[:, -self.output_dim:]
        
        # Neuroplasticity: "Neurons that fire together, wire together"
        # We increase weights aggressively to simulate synaptogenesis and physical growth
        with torch.no_grad():
            self.edge_weights.data += 0.005 * torch.rand_like(self.edge_weights)
            # Homeostatic plasticity: Cap the maximum synapse strength so the brain doesn't literally explode
            self.edge_weights.data = torch.clamp(self.edge_weights.data, -1.0, 1.0)
            
        # Cap the maximum electrical charge a neuron can hold
        neuron_states = torch.clamp(neuron_states, 0.0, 100.0)
            
        # Save the continuous state
        self.current_state = neuron_states.detach()
            
        return motor_signals, neuron_states
