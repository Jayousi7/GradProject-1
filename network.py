import torch
import torch.nn.functional as F
from torch import nn
from models import CNNEmbedding

class TimeSeriesClassifier(nn.Module):
    def __init__(self, input_dim=6, cnn_output_dim=120, hidden_dim=32, num_layers=2):
        super().__init__()
        
        self.cnn = CNNEmbedding(input_dim=input_dim, output_dim=cnn_output_dim)
        self.lstm = nn.LSTM(input_size=cnn_output_dim, hidden_size=hidden_dim, batch_first=True, bidirectional=True, num_layers=num_layers, dropout=0.5)
        
        self.projection = nn.Linear(hidden_dim * 2, 16)
        self.projection1 = nn.Linear(16, 16)
        self.projection2 = nn.Linear(16, 1)

        self.dropout = nn.Dropout(0.5)
        
    def forward(self, x):
        x = self.dropout(self.cnn(x))
        x = x.permute(0, 2, 1)
        
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        last_forward = h_n[-2, :, :]
        last_backward = h_n[-1, :, :]
        last_hidden_state = torch.cat((last_forward, last_backward), dim=1)
        
        x = F.relu(self.projection(self.dropout(last_hidden_state)))
        x = F.relu(self.projection1(self.dropout(x)))
        logits = self.projection2(x)
        
        return logits
